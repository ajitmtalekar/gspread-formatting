# -*- coding: utf-8 -*-

import os
import re
import random
import unittest
import itertools
import uuid
from datetime import datetime, date
import pandas as pd
from gspread_dataframe import set_with_dataframe

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

from oauth2client.service_account import ServiceAccountCredentials

import gspread
from gspread import utils
from gspread_formatting import *
from gspread_formatting.dataframe import *

try:
    unicode
except NameError:
    basestring = unicode = str


CONFIG_FILENAME = os.path.join(os.path.dirname(__file__), 'tests.config')
CREDS_FILENAME = os.path.join(os.path.dirname(__file__), 'creds.json')
SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive.file'
]

I18N_STR = u'Iñtërnâtiônàlizætiøn'  # .encode('utf8')


def read_config(filename):
    config = ConfigParser.ConfigParser()
    config.readfp(open(filename))
    return config


def read_credentials(filename):
    return ServiceAccountCredentials.from_json_keyfile_name(filename, SCOPE)


def gen_value(prefix=None):
    if prefix:
        return u'%s %s' % (prefix, gen_value())
    else:
        return unicode(uuid.uuid4())


class GspreadTest(unittest.TestCase):
    config = None
    gc = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.config = read_config(CONFIG_FILENAME)
            credentials = read_credentials(CREDS_FILENAME)
            cls.gc = gspread.authorize(credentials)
        except IOError as e:
            msg = "Can't find %s for reading test configuration. "
            raise Exception(msg % e.filename)

    def setUp(self):
        if self.__class__.gc is None:
            self.__class__.setUpClass()
        self.assertTrue(isinstance(self.gc, gspread.client.Client))

class WorksheetTest(GspreadTest):
    """Test for gspread.Worksheet."""
    spreadsheet = None

    @classmethod
    def setUpClass(cls):
        super(WorksheetTest, cls).setUpClass()
        ss_id = cls.config.get('Spreadsheet', 'id')
        cls.spreadsheet = cls.gc.open_by_key(ss_id)
        try:
            test_sheet = cls.spreadsheet.worksheet('wksht_test')
            if test_sheet:
                # somehow left over from interrupted test, remove.
                cls.spreadsheet.del_worksheet(test_sheet)
        except gspread.exceptions.WorksheetNotFound:
            pass # expected

    def setUp(self):
        super(WorksheetTest, self).setUp()
        if self.__class__.spreadsheet is None:
            self.__class__.setUpClass()
        try:
            test_sheet = self.spreadsheet.worksheet('wksht_test')
            if test_sheet:
                # somehow left over from interrupted test, remove.
                self.spreadsheet.del_worksheet(test_sheet)
        except gspread.exceptions.WorksheetNotFound:
            pass # expected
        self.sheet = self.spreadsheet.add_worksheet('wksht_test', 20, 20)

    def tearDown(self):
        self.spreadsheet.del_worksheet(self.sheet)

    def test_some_format_constructors(self):
        f = numberFormat('TEXT', '###0')
        f = border('DOTTED', color(0.2, 0.2, 0.2))

    def test_bottom_attribute(self):
        f = padding(bottom=1.1)
        f = borders(bottom=border('SOLID'))

    def test_format_range(self):
        rows = [["", "", "", ""],
                ["", "", "", ""],
                ["A1", "B1", "", "D1"],
                [1, "b2", 1.45, ""],
                ["", "", "", ""],
                ["A4", 0.4, "", 4]]

        def_fmt = get_default_format(self.spreadsheet)
        cell_list = self.sheet.range('A1:D6')
        for cell, value in zip(cell_list, itertools.chain(*rows)):
            cell.value = value
        self.sheet.update_cells(cell_list)

        fmt = cellFormat(textFormat=textFormat(bold=True), backgroundColorStyle=ColorStyle(rgbColor=Color(1,0,0)))
        format_cell_ranges(self.sheet, [('A1:B6', fmt), ('C1:D6', fmt)])
        ue_fmt = get_user_entered_format(self.sheet, 'A1')
        self.assertEqual(ue_fmt.textFormat.bold, True)
        # userEnteredFormat will not have backgroundColorStyle...
        eff_fmt = get_effective_format(self.sheet, 'A1')
        self.assertEqual(eff_fmt.textFormat.bold, True)
        # effectiveFormat will have backgroundColorStyle...
        self.assertEqual(eff_fmt.backgroundColorStyle.rgbColor.red, 1)
        self.assertEqual(eff_fmt.textFormat.bold, True)
        fmt2 = cellFormat(textFormat=textFormat(italic=True))
        format_cell_range(self.sheet, 'A1:D6', fmt2)
        ue_fmt = get_user_entered_format(self.sheet, 'A1')
        self.assertEqual(ue_fmt.textFormat.italic, True)
        eff_fmt = get_effective_format(self.sheet, 'A1')
        self.assertEqual(eff_fmt.textFormat.italic, True)

    def test_bottom_formatting(self):
        rows = [["", "", "", ""],
                ["", "", "", ""],
                ["A1", "B1", "", "D1"],
                [1, "b2", 1.45, ""],
                ["", "", "", ""],
                ["A4", 0.4, "", 4]]

        def_fmt = get_default_format(self.spreadsheet)
        cell_list = self.sheet.range('A1:D6')
        for cell, value in zip(cell_list, itertools.chain(*rows)):
            cell.value = value
        self.sheet.update_cells(cell_list)
        fmt = cellFormat(textFormat=textFormat(bold=True))
        format_cell_ranges(self.sheet, [('A1:B6', fmt), ('C1:D6', fmt)])

        orig_fmt = get_user_entered_format(self.sheet, 'A1')
        new_fmt = cellFormat(borders=borders(bottom=border('SOLID')), padding=padding(bottom=3))
        format_cell_range(self.sheet, 'A1:A1', new_fmt)
        ue_fmt = get_user_entered_format(self.sheet, 'A1')
        self.assertEqual(ue_fmt, fmt + new_fmt)
        self.assertEqual(new_fmt.borders.bottom.style, ue_fmt.borders.bottom.style)
        self.assertEqual(new_fmt.padding.bottom, ue_fmt.padding.bottom)
        eff_fmt = get_effective_format(self.sheet, 'A1')
        self.assertEqual(new_fmt.borders.bottom.style, eff_fmt.borders.bottom.style)
        self.assertEqual(new_fmt.padding.bottom, eff_fmt.padding.bottom)

    def test_frozen_rows_cols(self):
        set_frozen(self.sheet, rows=1, cols=1)
        fresh = self.sheet.spreadsheet.fetch_sheet_metadata({'includeGridData': True})
        item = utils.finditem(lambda x: x['properties']['title'] == self.sheet.title, fresh['sheets'])
        pr = item['properties']['gridProperties']
        self.assertEqual(pr.get('frozenRowCount'), 1)
        self.assertEqual(pr.get('frozenColumnCount'), 1)
        self.assertEqual(get_frozen_row_count(self.sheet), 1)
        self.assertEqual(get_frozen_column_count(self.sheet), 1)

    def test_format_props_roundtrip(self):
        fmt = cellFormat(backgroundColor=Color(1,0,1),textFormat=textFormat(italic=False))
        fmt_roundtrip = CellFormat.from_props(fmt.to_props())
        self.assertEqual(fmt, fmt_roundtrip)

    def test_formats_equality_and_arithmetic(self):
        def_fmt = cellFormat(backgroundColor=Color(1,0,1),textFormat=textFormat(italic=False))
        fmt = cellFormat(textFormat=textFormat(bold=True))
        effective_format = def_fmt + fmt
        self.assertEqual(effective_format.textFormat.bold, True)
        effective_format2 = def_fmt + fmt
        self.assertEqual(effective_format, effective_format2)
        self.assertEqual(effective_format - fmt, def_fmt)
        self.assertEqual(effective_format.difference(fmt), def_fmt)
        self.assertEqual(effective_format.intersection(effective_format), effective_format)
        self.assertEqual(effective_format & effective_format, effective_format)
        self.assertEqual(effective_format - effective_format, None)

    def test_date_formatting_roundtrip(self):
        rows = [
            ["9/1/2018", "1/2/2017", "4/4/2014", "4/4/2019"],
            ["10/2/2019", "2/4/2000", "5/5/1994", "7/7/1979"]
        ]
        def_fmt = get_default_format(self.spreadsheet)
        cell_list = self.sheet.range('A1:D2')
        for cell, value in zip(cell_list, itertools.chain(*rows)):
            cell.value = value
        self.sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
        fmt = cellFormat(
                numberFormat=numberFormat('DATE', ' DD MM YYYY'),
                backgroundColor=color(0.8, 0.9, 1),
                horizontalAlignment='RIGHT',
                textFormat=textFormat(bold=False))
        format_cell_range(self.sheet, 'A1:D2', fmt)
        ue_fmt = get_user_entered_format(self.sheet, 'A1')
        self.assertEqual(ue_fmt.numberFormat.type, 'DATE')
        self.assertEqual(ue_fmt.numberFormat.pattern, ' DD MM YYYY')
        eff_fmt = get_effective_format(self.sheet, 'A1')
        self.assertEqual(eff_fmt.numberFormat.type, 'DATE')
        self.assertEqual(eff_fmt.numberFormat.pattern, ' DD MM YYYY')
        dt = self.sheet.acell('A1').value
        self.assertEqual(dt, ' 01 09 2018')

    def test_data_validation_rule(self):
        rows = [
            ["A", "B", "C", "D"],
            ["1", "2", "3", "4"]
        ]
        cell_list = self.sheet.range('A1:D2')
        for cell, value in zip(cell_list, itertools.chain(*rows)):
            cell.value = value
        self.sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
        validation_rule = DataValidationRule(
            BooleanCondition('ONE_OF_LIST', ['1', '2', '3', '4']), 
            showCustomUi=True
        )
        set_data_validation_for_cell_range(self.sheet, 'A2:D2', validation_rule)
        # No data validation for A1
        eff_rule = get_data_validation_rule(self.sheet, 'A1')
        self.assertEqual(eff_rule, None)
        # data validation for A2 should be equal to validation_rule
        eff_rule = get_data_validation_rule(self.sheet, 'A2')
        self.assertEqual(eff_rule.condition.type, 'ONE_OF_LIST')
        self.assertEqual([ x.userEnteredValue for x in eff_rule.condition.values ], ['1', '2', '3', '4'])
        self.assertEqual(eff_rule.showCustomUi, True)
        self.assertEqual(eff_rule.strict, None)
        self.assertEqual(eff_rule, validation_rule)

    def test_dataframe_formatter(self):
        rows = [  
            {
                'A': 'Label ' + str(i), 
                'B': i * 100 + 2.34, 
                'C': date(2019, 3, i % 31 + 1), 
                'D': datetime(2019, 3, i % 31 + 1, i % 24, i % 60, i % 60),
                'E': i * 1000 + 7.8001, 
            } 
            for i in range(200) 
        ]
        df = pd.DataFrame.from_records(rows)
        set_with_dataframe(self.sheet, df, include_index=True)
        format_with_dataframe(
            self.sheet, 
            df, 
            formatter=BasicFormatter.with_defaults(
                freeze_headers=True, 
                column_formats={
                    'C': cellFormat(
                            numberFormat=numberFormat(type='DATE', pattern='yyyy mmmmmm dd'), 
                            horizontalAlignment='CENTER'
                        ),
                    'E': cellFormat(
                            numberFormat=numberFormat(type='NUMBER', pattern='[Color23][>40000]"HIGH";[Color43][<=10000]"LOW";0000'), 
                            horizontalAlignment='CENTER'
                        )
                }
            ), 
            include_index=True,
        )
        for cell_range, expected_uef in [
            ('A1:A201', cellFormat(numberFormat=numberFormat(type='NUMBER'), horizontalAlignment='RIGHT')), 
            ('B1:B201', cellFormat(horizontalAlignment='CENTER')), 
            ('C1:C201', cellFormat(numberFormat=numberFormat(type='NUMBER'), horizontalAlignment='RIGHT')), 
            ('D1:D201', 
                cellFormat(
                    numberFormat=numberFormat(type='DATE', pattern='yyyy mmmmmm dd'), 
                    horizontalAlignment='CENTER'
                )
            ), 
            ('E1:E201', cellFormat(numberFormat=numberFormat(type='DATE'), horizontalAlignment='CENTER')), 
            ('F1:F201', 
                cellFormat(
                    numberFormat=numberFormat(
                        type='NUMBER', 
                        pattern='[Color23][>40000]"HIGH";[Color43][<=10000]"LOW";0000'
                    ), 
                    horizontalAlignment='CENTER'
                )
            ), 
            ('A1:A201', 
                cellFormat(
                    backgroundColor=DEFAULT_HEADER_BACKGROUND_COLOR,
                    textFormat=textFormat(bold=True)
                )
            ), 
            ('A1:F1', 
                cellFormat(
                    backgroundColor=DEFAULT_HEADER_BACKGROUND_COLOR,
                    textFormat=textFormat(bold=True)
                )
            )
            ]:
            start_cell, end_cell = cell_range.split(':')
            for cell in (start_cell, end_cell):
                actual_uef = get_user_entered_format(self.sheet, cell)
                # actual_uef must be a superset of expected_uef
                self.assertTrue(actual_uef & expected_uef == expected_uef)
        self.assertEqual(1, get_frozen_row_count(self.sheet))
        self.assertEqual(1, get_frozen_column_count(self.sheet))



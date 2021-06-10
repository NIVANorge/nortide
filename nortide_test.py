#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Unit tests for the nortide package.
nortide.py is a Python wrapper for Kartverkets sehavniva.no REST API
More information about the API is found here: 
http://api.sehavniva.no/tideapi_no.html

NOTE: If tests fail make sure the sehavniva API is online and
working as it should.

2017-04-24
Grunde Løvoll, grunde.loevoll@niva.no
'''
from __future__ import division, unicode_literals
import nortide
import unittest
from tempfile import TemporaryFile

# Unit tests
class TestNortide(unittest.TestCase):
    """TestNortide is a set of UnitTests for the nortide wrapper"""
    def setUp(self):
        self.tidal = nortide.Tidal()
        self.test_station = self.tidal.get_station("honningsvåg")


    def tearDown(self):
        pass


    def test_station_list(self):
        station_list = self.tidal.stations
        self.assertTrue("anx" in [s.code.lower() for s in station_list]) # Station Andenes
        self.assertTrue(len(station_list) >= 25) # Assume that stations wont be removed


    def test_get_station(self):
        # Check by querying for station Tromsø
        station = self.tidal.get_station("tromsø")
        self.assertAlmostEqual(station.latitude, 69.64611, 4) # 69.64611, 18.95479
        self.assertAlmostEqual(station.longitude, 18.95479, 4)


    def test_station_levels(self):
        levels = self.test_station.levels()
        self.assertTrue('reflevel' in levels)
        codes = [r['@code'].lower() for r in levels['reflevel']]
        self.assertTrue('howl' in codes)


    def test_water_levels(self):
        # Implicit this also tests both waterlevels() and waterlevels_df()
        test_data = self.tidal.waterlevel_df(start_time='2017-01-01', end_time='2017-01-04',
                                        lat=59.535033, lon=10.554628, datatype='PRE')
        self.assertTrue(test_data.shape[1] == 4)
        self.assertTrue(test_data.shape[0] == 73)
        print(test_data.iloc[3,test_data.columns.get_loc('value')])
        self.assertAlmostEqual(test_data.iloc[3,test_data.columns.get_loc('value')], 59.7, 1)


    def test_get_waterlevel(self):
        test_data = self.tidal.get_waterlevel("2016-02-08T10:14:04.432",
                                              lat=59.535033, lon=10.554628)
        self.assertAlmostEqual(test_data.data, 67, 3)


    def test_get_languages(self):
        languages = self.tidal.languages
        lang_codes = [l.code for l in languages]
        self.assertTrue('en' in lang_codes)


    def test_get_ref_water_levels(self):
        wlevel_refs = self.tidal.get_ref_levels(lat=59.535, lon=10.5546)
        wlevel_codes = [wl.code for wl in wlevel_refs]
        self.assertTrue('CD' in wlevel_codes)


    def test_water_level_on_land(self):
        '''The API will give an Error message if the passed in coordinates are
        out of range or on land'''
        # Trying to fetch data from Lesja which should result in an error
        self.assertRaises(nortide.TidalExcept, self.tidal.get_waterlevel, 
                          '2015-10-10T09:13:14.32', lat=62.2984, lon=9.2422)
    
    def test_dump_excel(self):

        test_data = self.tidal.waterlevel_df(start_time='2017-01-01', end_time='2017-01-04',
                                        lat=59.535033, lon=10.554628, datatype='PRE')
        
        with TemporaryFile("wb") as f:
            test_data.to_excel(f)

 
def run_test():
    unittest.main()

if __name__ == '__main__':
    unittest.main()
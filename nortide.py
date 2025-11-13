# coding=utf-8
# -*- coding: utf-8 -*-
'''
Python API to download tidal data for the Norwegian coast using
the sehavniva.no API from Kartverkets.

More information about the API is found here: 
http://api.sehavniva.no/tideapi_no.html

Note that the API assumes that all incomming time-stamps are UTC+1

Functionality for XML parsing is taken from Hay Kranen's xml2json tool.
See https://github.com/hay/xml2json

2017-04-25
Grunde Løvoll, grunde.loevoll@niva.no
'''

from __future__ import division, unicode_literals

# import logging
import requests as rq
import pandas as pd
import xml.etree.ElementTree as ET
from collections import OrderedDict, namedtuple
import json
import re
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import time
import math
from dateutil.parser import parse as dt_parse


API_URL = "https://vannstand.kartverket.no/tideapi.php"

WaterLevelData = namedtuple('WaterLevelData', 'data, data_type, refcode')
RefLevel = namedtuple('RefLevel', 'code, name, descr')

# The sehavniva.no API assumes timestamps are in this timezone
tz_norway = timezone("Europe/Oslo")


def _strip_tag(tag):
    '''Helper function for parsing XML data

    The code is taken from Hay Kranen's xml2json tool.
    https://github.com/hay/xml2json
    '''
    strip_ns_tag = tag
    split_array = tag.split('}')
    if len(split_array) > 1:
        strip_ns_tag = split_array[1]
        tag = strip_ns_tag
    return tag


def _elem_to_internal(elem, strip_ns=1, strip=1):
    '''Helper function which convert an element in an XML-ElementTree to an
    OrderedDict instance.

    The code is taken from Hay Kranen's xml2json tool.
    https://github.com/hay/xml2json
    '''

    d = OrderedDict()
    elem_tag = elem.tag

    if strip_ns:
        elem_tag = _strip_tag(elem.tag)
    for key, value in list(elem.attrib.items()):
        d['@' + key] = value

    # loop over subelements to merge them
    for subelem in elem:
        v = _elem_to_internal(subelem, strip_ns=strip_ns, strip=strip)

        tag = subelem.tag
        if strip_ns:
            tag = _strip_tag(subelem.tag)

        value = v[tag]

        try:
            # add to existing list for this tag
            d[tag].append(value)
        except AttributeError:
            # turn existing entry into a list
            d[tag] = [d[tag], value]
        except KeyError:
            # add a new non-list entry
            d[tag] = value
    text = elem.text
    tail = elem.tail
    if strip:
        # ignore leading and trailing whitespace
        if text:
            text = text.strip()
        if tail:
            tail = tail.strip()

    if tail:
        d['#tail'] = tail

    if d:
        # use #text element if other attributes exist
        if text:
            d["#text"] = text
    else:
        # text is the value if no attributes
        d = text or None
    return {elem_tag: d}

def _ts_localize(ts, tz=tz_norway):

    assert(isinstance(ts, datetime))
    if ts.tzinfo is None:
        return tz.localize(ts)
    else:
        return ts.astimezone(tz)

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def find_closest_station(lat, lon, stations):
  
    closest_station = None
    closest_distance = float('inf')
    for s in stations:
        d = _haversine(lat, lon, s.latitude, s.longitude)
        if d < closest_distance:
            closest_distance = d
            closest_station = s
    return closest_station, closest_distance


class TidalExcept(Exception):
    '''For exeptions raised by this module'''
    pass


class Station(object):
    '''Class for wrapping station data from the tidal API'''
    def __init__(self, **kwargs):
        self.name = kwargs.get('@name') or kwargs.get('name')
        self.code = kwargs.get('@code') or kwargs.get('code')
        self.latitude = float(kwargs.get('latitude') or kwargs.get('@latitude'))
        self.longitude = float(kwargs.get('longitude') or kwargs.get('@longitude'))
        self.type = kwargs.get('@type') or kwargs.get('type')
        self.url = kwargs.get('url')
        self._levels = None


    def __repr__(self):
        return("<Station %s:%s (%f, %f)>" % (self.code, self.name,
            self.latitude, self.longitude))


    def to_dict(self):
        return(OrderedDict([
            ('name', self.name),
            ('code', self.code),
            ('latitude', self.latitude),
            ('longitude', self.longitude),
            ('type', self.type),
            ('url', self.url)]))



    def levels(self, lang='nb', refcode='MSL', force_query=False):
        '''Query statistical tidal data for this station instance

        Returns: an OrderedDict wiht the relevant information
        '''
        # Return cache if query already done
        if self._levels and not force_query:
            return(self._levels)
        
        params = {'tide_request': 'stationlevels',
                  'stationcode': self.code,
                  'lang': lang,
                  'refcode': refcode}

        r = rq.get(self.url, params=params)
        levels = ET.fromstring(r.text.encode('utf8'))
        levels = _elem_to_internal(levels)
        try:
            levels = levels['tide']['locationlevel']
        except LookupError:
            raise TidalExcept('Location level data not found in response', r.text)
        
        self._levels = levels
        return(self._levels)



class Tidal(object):
    '''Class wrapping data from the tidal API'''

    # List of avaliable data types when querying tidal data
    DATATYPES = ['TAB', #  = tide table (high tide and low tide)
                 'PRE', #  = predictions = astronomic tide
                 'OBS', #  = observations = measured water level
                 'ALL'  # = predictions, observations, weathereffect and forecast will be returned]
                 ]
    

    def __init__(self, url=API_URL):
        self.url = url
        self._stations = None
        self._languages = None


    def __repr__(self):
        return('<Tidal: ' + self.url + '>')

    # Add method for serialization?


    @property
    def stations(self):
        '''List of stations avaliable from the API
        Run query if no cached data
        '''
        params = {'tide_request': 'stationlist',
                  'type': 'public'}

        # if cached data return it without query
        if self._stations:
            return self._stations

        # do request, parse xml, and create Station instances
        r = rq.get(self.url, params=params)
        elem = ET.fromstring(r.text.encode('utf8'))
        stations = _elem_to_internal(elem)
        stations = stations['tide']['stationinfo']['location']
        self._stations = [Station(url=self.url, **sd) for sd in stations]

        return(self._stations)

    
    def find_stations(self, q_name):
        '''Method searching for a station name matching string,
        returns a list of matches.
        '''
        match = [s for s in self.stations if q_name.lower() in s.name.lower()]
        return(match)


    def get_station(self, q_name):
        '''Find a station with name match

        Raises an error if more than one station matches, None if there is no match
        '''
        m_list = self.find_stations(q_name)
        if len(m_list) == 1:
            return m_list[0]
        elif len(m_list) > 1:
            raise TidalExcept("More than one station matches '%s'" % (q_name))
        else:
            return None



    def waterlevel(self, start_time=None, end_time=None, lon=None, lat=None,
                   station=None, datatype='OBS', refcode='CD', interval=60, lang='nb'):
        '''Get time-series of tidal data for a time period, data returned as Pands DataFrame

        Params:
        start_time -- query start, datetime object or parsable time string (default None)
        end_time   -- query end, datetime object or parsable time string (default None)
                      If both start_time and end_time is omitted the last 24 hours are
                      queried
        lon        -- longitude of query location (default None)
        lat        -- latitude of query location (default None)
        station    -- Station object instance, if present lon and lat is ignored (default None)
        datatype   -- Type of data to return (default 'ALL')
                      'TAB' = tide table (high tide and low tide)
                      'PRE' = predictions = astronomic tide
                      'OBS' = observations = measured water level
                      'ALL' = predictions, observations, weathereffect and forecast
                              will be returned
        refcode    -- code of reference level, the zero level in the response.
                      Any existing level of the area may be used returned.
                      (default 'CD' = sea map zero (sjoekartnull))
                      For a list of av available refcodes at a location use
                      the get_ref_levels() method
        interval   -- time interval of returned values in minutes [10, 60] (default 60)
        lang       -- language of returned data (default 'nb')
        
        Returns: an OrderedDict with the query results
        '''
        if station:
            assert(isinstance(station, Station))
            lon = station.longitude
            lat = station.latitude
        assert(isinstance(lon, (float, int)))
        assert(isinstance(lat, (float, int)))

        # Check for time span and parse if string
        if not all((start_time, end_time)):
            end_time = datetime.utcnow().astimezone(tz_norway)
            start_time = end_time - timedelta(1)
        
        # Note that the API assumes all queried times are in utc+1 time
        if isinstance(start_time, str):
            start_time = dt_parse(start_time)        
        # assert(isinstance(start_time, datetime))
        start_time = _ts_localize(start_time, tz_norway)
        # start_time.astimezone(tz_norway)
        start_time_str = start_time.isoformat()
        
        if isinstance(end_time, str):
            end_time = dt_parse(end_time)
        end_time = _ts_localize(end_time, tz_norway)
        # assert(isinstance(end_time, datetime))
        # end_time_str = end_time.astimezone(tz_norway)
        end_time_str = end_time.isoformat()
        
        params = {'tide_request': 'locationdata',
                  'lat': lat,
                  'lon': lon,
                  'fromtime': start_time_str, # start_time.isoformat(), #  + '+00:00',
                  'totime': end_time_str, # end_time.isoformat(), #  + '+00:00',
                  'refcode': refcode,
                  'datatype': datatype,
                  'interval': interval,
                  'lang': lang,
                  'dst': 1
                  # 'tzone': 0
                  }
        r = rq.get(self.url, params=params)
        data = ET.fromstring(r.text.encode('utf8'))
        data = _elem_to_internal(data)
        try:
            data = data['tide']['locationdata']
        except LookupError:
            raise TidalExcept('No locationdata in the recieved data')
        return(data)



    def waterlevel_df(self, datatype='OBS', **kwargs):
        '''Get time-series of tidal data for a time period, data returned as Pands DataFrame

        Params:
        **kwargs   -- all parameters are passed on to the waterlevel() method,
                      see waterlevel() method for details

        Returns: a Pandas DataFrame with the time series, raises exception on failure
        '''
        
        data = self.waterlevel(datatype=datatype, **kwargs)
        # Check if the recieved data is OK, if not a TidalExcept is raised
        if 'data' not in data:
            if 'nodata' in data:
                raise TidalExcept(data['nodata']['@info'])
            else:
                raise TidalExcept('No tabular data returned from sehavniva.no', data)

        out_data = []
        if isinstance(data['data'], (dict, OrderedDict)):
            if isinstance(data['data']['waterlevel'], dict):
                c_data = data['data']['waterlevel']
                c_data['type'] = data['data']['@type']
                out_data.append(c_data)
            elif isinstance(data['data']['waterlevel'], list):
                for dsi in data['data']['waterlevel']:
                    dsi['type'] = data['data']['@type']
                    out_data.append(dsi)
                

        elif isinstance(data['data'], list):
            for ds in data['data']:
                if isinstance(ds['waterlevel'], list):
                    for dsi in ds['waterlevel']:
                        dsi['type'] = ds['@type']
                        out_data.append(dsi)
                elif isinstance(ds['waterlevel'], (dict, OrderedDict)):
                    ds['waterlevel']['type'] = ds['@type']
                    out_data.append(ds['waterlevel'])

        out_data = pd.DataFrame(out_data)
        # Rename columns/remove leading @ and # symbols
        out_data.columns = [re.sub(r'^[@|#]', '', str(c)).lower() for c in out_data.columns]
        out_data.value = pd.to_numeric(out_data.value)
        if datatype != 'ALL':
            out_data.index = pd.DatetimeIndex(out_data.loc[:, 'time']).tz_localize(None)
            out_data.rename(columns={'time': 'time_orig'}, inplace=True)
        else:
            out_data.time = pd.DatetimeIndex(out_data.loc[:, 'time']).tz_localize(None)
        return out_data



    def get_waterlevel(self, time_stamp, lon, lat, refcode="CD", datatype="OBS", fallback_station_distance=0, **kwargs):
        '''Method which gives a single water level data point for a given
        time-stamp.

        fallback_station_distance will try to use the closest station within the given
        distance(km) if no data is found for the given lon, lat position.

        Note that Kartverket returns data in 10 min intervals, the returned value is
        thus a linear interpolation in time between the two nearest data-points
        returned. The return value is in cm higher than the reference level, and
        it is rounded off to the nearest cm.

        Warning: if abused Kartverket will block your IP for a while...
        '''
        if isinstance(time_stamp, str):
            # Parse timestamp and convert to datetime object
            time_stamp = dt_parse(time_stamp)
        time_stamp = _ts_localize(time_stamp, tz_norway)
        td = timedelta(0, 3 * 60 * 60) # 3-hour before and after in query
        start_time = time_stamp - td
        end_time = time_stamp + td # timedelta(0, 60 * 60) # 1-hour after

        try:
            adj_data = self.waterlevel_df(start_time=start_time, end_time=end_time,
                                       lon=lon, lat=lat, refcode=refcode,
                                       datatype=datatype, interval=10, **kwargs)
        except TidalExcept as e:
            if fallback_station_distance > 0:
                # Find closest station and try again
                stations = self.stations
                closest_station, distance = find_closest_station(lat, lon, stations)
                if distance > fallback_station_distance:
                    raise TidalExcept(f"No station within {fallback_station_distance} km") from e
                adj_data = self.waterlevel_df(start_time=start_time, end_time=end_time,
                                       station=closest_station, refcode=refcode,
                                       datatype=datatype, interval=10, **kwargs)
                print(f"Using station {closest_station.name} ({lat}, {lon}) {distance:.1f} km away")
            else:
                raise e

        time_stamp = time_stamp.replace(tzinfo=None) # make naive for comparison
        # find nearest points in time compared to time_stamp
        t_dist = abs((adj_data.index - time_stamp).total_seconds())
        adj_data = adj_data.iloc[t_dist.argsort()[:2]]

        # Interpolate and return the data
        y = adj_data.loc[:, 'value']
        t = adj_data.index
        value = y.iloc[0] + (time_stamp - t[0]).total_seconds() * ((y.iloc[1] - y.iloc[0])/
                        (t[1] - t[0]).total_seconds())
        print(f"Interpolating between {t[0]} ({y.iloc[0]}) and {t[1]} ({y.iloc[1]})")
        value = round(value) # Round of to nearest cm
        return(WaterLevelData(value, adj_data.iloc[0, adj_data.columns.get_loc('type')], refcode))


    @property
    def languages(self):
        '''return a list of avaliable languages in the API'''
        LangCode = namedtuple('LangCode', 'code, name')
        if self._languages:
            return(self._languages)
        params = {'tide_request': 'languages'}
        r = rq.get(self.url, params=params)
        lan_list = ET.fromstring(r.text.encode('utf8'))
        lan_list = _elem_to_internal(lan_list)
        lan_list = lan_list['tide']['languages']['lang']
        self._languages = [LangCode(l['@code'], l['@name']) for l in lan_list]
        return(self._languages)


    def get_ref_levels(self, lat, lon, lang='nb'):
        '''Get standard level codes for location'''
        params = {'tide_request': 'standardlevels',
                  'lang': lang,
                  'lat': lat,
                  'lon': lon}

        r = rq.get(self.url, params=params)
        ref_levels = ET.fromstring(r.text.encode('utf8'))
        ref_levels = _elem_to_internal(ref_levels)
        ref_levels = ref_levels['tide']['standardlevels']['reflevel']
        ref_levels = [RefLevel(l['@code'], l['@name'], l['@descr']) for l in ref_levels]
        return(ref_levels)

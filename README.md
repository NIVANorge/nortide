# nortide
Python API/wrapper to download tidal data (water level data) for the Norwegian
coast using the sehavniva.no API from Kartverket.

The wrapper the sehavniva.no API as pure Python objects
with methods for queries of data and meta-data.
The wrapper can also return tabular data as Pandas DataFrames
which are convenient for data analytics and export to
various formats (like csv, Excel and HDF5).

For more information about the API see: [http://api.sehavniva.no/tideapi_no.html]


## beware of!
The sehavniva.no API treats all incoming time-stamps as UTC+1/CET
This will usually be taken care of by the nortide wrapper, but you
never know...

Also note that Kartverket only accepts a limited number of queries
pr. unit time from a given IP. So if you plan to to many queries
you should throttle your queries.


## Install
Written for Python3 and tested with Python2.7

Install with pip from repository:
```
>> pip install https://github.com/NIVANorge/nortide/zipball/master
```

Or download module [nortide_test.py](./nortide_test.py) and put it
in your `PYTHONPATH`.


## Testing
The package comes with a test script [nortide_test.py](./nortide_test.py)
with unit tests for the package.
To run the test do:
```
>> python nortide_test.py
```

The test package can also be tested with the setuptools `setup.py` script:
```
>> python setup.py test
```


### Dependencies
nortide uses the following "non standard" Python packages
* [Pandas](http://pandas.pydata.org)
* [Requests](http://docs.python-requests.org/en/master/)


## Examples
```python
from nortide import Tidal

tidal = Tidal()

# Get list if monitoring stations
print(tidal.stations)

# Find and get Station-Tromsø
st_tromso = tidal.get_station("tromsø")

# Get a table with tidal data in Tromsø
water_levels =  tidal.waterlevel_df(start_time='2017-01-01T10:00:00',
                                    end_time='2017-01-01T12:00:00',
                                    station=st_tromso, datatype='OBS')

# Get a table with waterlevel data at an "arbitrary" location
water_levels =  tidal.waterlevel_df(start_time='2017-01-01T10:00:00+03:00',
                                    end_time='2017-01-01T12:00:00+03:00',
                                    lat=59.535033, lon=10.554628, datatype='PRE')

# Get water level at an "arbitrary" location at a specific time.
water_level = tidal.get_waterlevel("2016-02-08T10:14:04.432",
                                    lat=59.535033, lon=10.554628)
```

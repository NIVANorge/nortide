# nortide
Python API to download tidal data for the Norwegian coast using the sehavniva.no
API from Kartverket.

More information about the API and the package/wrapper

## Insatall
Written and tested in Python 3.6

## Examples

```python
from nortide import Tidal

tidal = Tidal()

# Get list if monitoring stations
print(tidal.stations)

# Find and get Station-Tromsø
st_tromso = tidal.get_station("tromsø")

# Get a table with tidal data in Tromsø


# Get a table with waterlevel data at an "arbitrary" location


# Get water level at an "arbitrary" location
```

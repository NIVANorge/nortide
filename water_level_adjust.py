#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Small script to adjust depth measurement from tidal data
'''
import logging
import pandas as pd
from pandas.api.types import is_string_dtype
from pandas.api.types import is_numeric_dtype

from datetime import datetime, timedelta
from pytz import timezone
import pytz
from collections import namedtuple
from dateutil.parser import parse as dt_parse
import time
import re
from nortide import *

Correction = namedtuple('Correction', 'correction, correction_type, refcode')
tz_norway = timezone("Europe/Oslo")


def _r2ts(row):
    try:
        time_stamp = datetime.combine(getattr(row, date_field).to_pydatetime(),
                                      getattr(row, time_field))
    except:
        try:
            if isinstance(row[1], datetime):
                ts_str = str(row[1].date()) + 'T' + str(row[2])
            elif isinstance(row[1], str):
                date_str = row[1].strip()
                # Try to guess if the date string has day first in the format (usually the case in Norway)
                if re.match(r'^\d{1,2}(\.|\-|\/)', date_str):
                    dayfirst = True
                else:
                    dayfirst = False
                try:
                    c_date = dt_parse(date_str, dayfirst=dayfirst)
                except:
                    c_date = dt_parse(date_str.split()[0], dayfirst=dayfirst)
                c_date = str(c_date.date())
                # ts_str = row[1] + 'T' + str(row[2])
                ts_str = c_date + 'T' + str(row[2])
            else:
                raise TypeError
            time_stamp = dt_parse(ts_str)
        except:
            time_stamp = None
    return(time_stamp)


def _as_float(v):
    try:
        return(float(v))
    except:
        try:
            return(float(v.replace(',', '.')))
        except:
            return(None)



def row2correct(row, tidal, delay=0.1):
    time.sleep(delay) # not to overwhelm the REST API
    try:
        time_stamp = row.timestamp # = datetime.combine(row.Date.to_pydatetime(), row.Time)
        latitude = row[1]  # getattr(row, lat_name) # row.Latitude
        longitude = row[2] # getattr(row, long_name) # row.Longitude
        stuff = tidal.get_waterlevel(time_stamp, longitude, latitude) # , tidal)
        logging.debug("%i %f %f %s %s" % (row.Index, row[1], row[2], row.timestamp, stuff))
        return(stuff)
    except:
        logging.warning("Insuficient data: ", row.Index, row[1], row[2], row.timestamp)
        return(Correction(None, None, None))


def main(args):
    tidal = Tidal()
    if args.infile.lower().endswith(".xlsx"):
        in_data = pd.read_excel(args.infile, args.sheet_n)
    elif args.infile.lower().endswith(".csv"):
        sep = ','
        decimal = '.'
        try:
            in_data = pd.read_csv(args.infile)
        except:
            in_data = pd.DataFrame()
        if in_data.shape[1] < 4:
            # probably Norwegian locale csv file :-(
            sep = ';'
            decimal = ','
            in_data = pd.read_csv(args.infile, sep=sep, decimal=decimal)
    assert(in_data.shape[1] >= 4) # make sure we have enough parameters

    # Read in and fix timestamps
    if args.ts_colname is None:
        in_data['timestamp'] = [_r2ts(r)
            for r in in_data.loc[:, [args.date, args.time]].itertuples()]
    else:
        in_data['timestamp'] = [dt_parse(ts) for ts in in_data[args.ts_colname]]

    # Fix timezones
    # in_data.timestamp = pd.DatetimeIndex(in_data.Date).tz_localize(tz_norway)
    tz = timezone(args.timezone)
    print("Got timezone", tz)
    # print(in_data.timestamp)
    in_data.timestamp = pd.DatetimeIndex(in_data.timestamp).tz_localize(tz)

    # in_data = in_data[0:20]
    if args.end_row is None or args.end_row > in_data.shape[0]:
        end_row = in_data.shape[0]
    else:
        end_row = args.end_row
    start_row = args.start_row
    in_data = in_data[start_row:end_row]

    # Fix Excel fuckup for string formated floats in Norwegian locale
    for cn in [args.lat_col, args.lng_col, args.depth_col]:
        if is_string_dtype(in_data[cn]):
            in_data[cn] = [_as_float(v) for v in in_data[cn]]
    # If depth is given as negative numbers, invert it
    if args.inv_depth:
        in_data[args.depth_col] = -in_data[args.depth_col]

    # Do tidal correction
    corrections = [row2correct(r, tidal)
        for r in in_data.loc[:, [args.lat_col, args.lng_col, 'timestamp']].itertuples()]
    corrections = pd.DataFrame(corrections, index=in_data.index)

    # merge the dataframes
    out_data = pd.concat([in_data, corrections], axis=1) # , ignore_index=True)
    # out_data.to_excel(args.outfile, sheet_name='Tidevann dybdekorreksjon', index=False)
    dyp_float = pd.Series([_as_float(v) for v in in_data[args.depth_col]],
                             index=out_data.index)
 
    # Calculate corrected depth data
    corrections.columns = ['correction', 'correction_type', 'refcode']
    calc_correction = pd.DataFrame(dyp_float - corrections.correction/100,
                                       columns=['corr_Dyp',])

    # Remove timezone before dump to excel
    in_data.timestamp = pd.DatetimeIndex(in_data.timestamp).tz_localize(None)
    # FIXME: rervert to original column names
    # merge the dataframes
    out_data = pd.concat([in_data, calc_correction, corrections], axis=1) # , ignore_index=True)
    if args.outfile.lower().endswith(".xlsx"):
        out_data.to_excel(args.outfile, sheet_name='Tidevann dybdekorreksjon', index=False)
    elif args.outfile.lower().endswith(".csv"):
        out_data.to_csv(args.outfile, index=False, sep=sep, decimal=decimal)



if __name__ == '__main__':
    import sys
    import argparse

    # Set up and parse command line arguments
    parser = argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-t", "--ts_col", required=False, default=None,
            help="Column name of column with time stamp", dest="ts_colname")
    parser.add_argument("--time-zone", required=False, default="Europe/Oslo",
            help="Time zone of time column, default 'Europe/Oslo'", dest="timezone")
    parser.add_argument("--date", required=False,
            help="Column for sample date, only relevant if the input data don't have" +
                 " a timestamp column. Time coloumn is in this case also needed.",
            dest="date", default=None)
    parser.add_argument("--time", required=False,
            help="Column for sample time, only relevant if the input data don't have" +
                 " a timestamp column. Date column is as in this case also needed.",
            dest="time", default=None)
    parser.add_argument("--longitude", required=False, default="Longitude",
            help="Column name of column with longitude data", dest="lng_col")
    parser.add_argument("--latitude", required=False, default="Latitude",
            help="Column name of column with latitude data", dest="lat_col")
    parser.add_argument("-d", "--depth", required=False, default="Dyp",
            help="Column name of column with measured depth data", dest="depth_col")
    parser.add_argument("-n", "--sheet-number", type=int, required=False,
            help="Sheet number in Excel file to read",
            default=0, dest="sheet_n")
    parser.add_argument("-s", "--start-row", type=int, required=False,
            help="Process from row number",
            default=0, dest="start_row")
    parser.add_argument("-e", "--end-row", type=int, required=False,
            help="Process up to row number",
            default=None, dest="end_row")
    parser.add_argument("--invert-depth", required=False,
            action="store_true", 
            help="Invert depth measurements if given as negative values",
            dest="inv_depth")
    parser.add_argument("--debug", required=False,
            help="Set debug flag for more detailed logging",
            action="store_true", dest="debug")
    parser.add_argument("-l", "--log-file", required=False,
            help="Path to log-file (default STDOUT)",
            default=sys.stdout, dest="logfile")

    parser.add_argument("infile", help="In-file with data for depth adjustment (excel or csv format)")
    parser.add_argument("outfile", help="Out-file for adjusted data (excel or csv format)")
    args = parser.parse_args()

    # Set up logger
    LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(filename)s:%(lineno)s:%(funcName)s:%(message)s"
    if args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    if args.logfile == sys.stdout:
        logging.basicConfig(stream=args.logfile, level=log_level, format=LOG_FORMAT)
    else:
        logging.basicConfig(filename=args.logfile, level=log_level, format=LOG_FORMAT)

    logging.info("Script started")
    main(args)
    logging.info("Script finished")

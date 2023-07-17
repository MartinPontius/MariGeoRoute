"""Utility functions."""
import datetime
import logging
import math

import numpy as np

import WeatherRoutingTool.utils.formatting as form

logger = logging.getLogger('WRT.weather')

def mps_to_knots(vals):
    """convert the Meters/second to knots.
    knot is a unit of speed equal to one nautical mile per hour, exactly 1.852 km/h."""
    return vals * 3600.0 / 1852.0

def knots_to_mps(vals):
    """convert the Meters/second to knots.
        knot is a unit of speed equal to one nautical mile per hour, exactly 1.852 km/h."""

    return vals * 1852.0 / 3600.0

def round_time(dt=None, round_to=60):
    """
        Round a datetime object to any time lapse in seconds.
        ref: /questions/3463930/how-to-round-the-minute-of-a-datetime-object
        dt : datetime.datetime object, default now.
        round_to : Closest number of seconds to round to, default 1 minute.

        """

    if dt is None:
        dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to

    # print('dt = ', dt)
    # print('seconds = ', seconds)
    # print('rounging = ', rounding)
    # print('return = ', dt + datetime.timedelta(0, rounding - seconds, - dt.microsecond))

    return dt + datetime.timedelta(0, rounding - seconds, - dt.microsecond)

def degree_to_pmpi(degrees):
    if(degrees>=360): degrees = degrees-360
    if(degrees<=-360): degrees = degrees+360
    if(degrees>180): degrees = degrees-360
    if(degrees<-180): degrees = degrees+360
    degrees = math.radians(degrees)
    return degrees

def convert_nptd64_to_h(time):
    time = time.astype('timedelta64[m]') / np.timedelta64(1, 'm')
    return time

def convert_nptd64_to_ints(time):
    dt64 = np.datetime64(time)
    ts = (dt64 - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
    return ts

def check_dataset_spacetime_consistency(ds1, ds2, coord, ds1_name, ds2_name):
    coord1 = ds1[coord].to_numpy()
    coord2 = ds2[coord].to_numpy()

    res1 = coord1[1] - coord1[0]
    res2 = coord2[1] - coord2[0]

    shift2 = coord2[0] - coord1[0]

    if coord == 'time':
        res1 = convert_nptd64_to_h(res1)
        res2 = convert_nptd64_to_h(res2)
        shift2 = convert_nptd64_to_h(shift2)

    logger.info(form.get_log_step('Checking consistency of datasets ' + ds1_name + ' and ' + ds2_name + ' for variable/dimension ' + coord))
    logger.info(form.get_log_step('Resolutions are: ' + ds1_name + ':' + str(res1) + ', ' +  ds2_name + ':' + str(res2) , 2))
    logger.info(form.get_log_step(
        ds2_name + ' is shifted wrt. ' + ds1_name + ' by ' + str(shift2), 2))

    return res1, res2, shift2


"""Weather functions."""
import datetime as dt
import logging
import sys

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator

import utils.graphics as graphics
import utils.formatting as form
from maridatadownloader import DownloaderFactory
from utils.maps import Map
from utils.unit_conversion import round_time

logger = logging.getLogger('WRT.weather')

class WeatherCond():
    model: str
    time_steps: int
    time_res: dt.timedelta
    time_start: dt.datetime
    time_end: dt.timedelta
    map_size: Map
    ds: xr.Dataset

    def __init__(self, model, time, hours, time_res):
        form.print_line()
        logger.info('Initialising weather')

        self.model = model
        self.time_res = time_res
        self.time_start = time
        self.time_end = time + dt.timedelta(hours=hours)

        time_passed = self.time_end - self.time_start
        self.time_steps = int(time_passed.total_seconds()/self.time_res.total_seconds())

        logger.info(form.get_log_step('forecast from ' + str(self.time_start) + ' to ' + str(self.time_end), 1))
        logger.info(form.get_log_step('nof time steps ' + str(self.time_steps),1))
        form.print_line()

    @property
    def time_res(self):
        return self._time_res

    @time_res.setter
    def time_res(self, value):
        if (value < 3): raise ValueError('Resolution below 3h not possible')
        self._time_res = dt.timedelta(hours=value)
        logger.info(form.get_log_step('time resolution: ' + str(self._time_res) + ' hours',1))

    @property
    def time_start(self):
        return self._time_start

    @time_start.setter
    def time_start(self,value):
        print('type: ', type(value))
        rounded_time = value - self.time_res/2
        rounded_time = round_time(rounded_time, int(self.time_res.total_seconds()))
        self._time_start = rounded_time

    @property
    def time_end(self):
        return self._time_end

    @time_end.setter
    def time_end(self, value):
        rounded_time = value + self.time_res / 2
        rounded_time = round_time(rounded_time, int(self.time_res.total_seconds()))
        self._time_end = rounded_time

    def set_map_size(self, map):
        self.map_size=map

    def get_map_size(self):
        return self.map_size

    def read_dataset(self, filepath = None):
        pass
class WeatherCondODC(WeatherCond):

    def __init__(self,model, time, hours, time_res):
        super().__init__(model, time, hours, time_res)

    def read_dataset(self, filepath = None):
        #time_min = "2023-05-05T12:00:00"
        #time_max = "2023-05-05T18:00:00"

        time_min = self.time_start.strftime("%Y-%m-%dT%H:%M:%S")
        time_max = self.time_end.strftime("%Y-%m-%dT%H:%M:%S")

        #lon_min = -180
        #lon_max = 180
        #lat_min = -90
        #lat_max = 90

        lon_min = self.map_size.lon1
        lon_max = self.map_size.lon2
        lat_min = self.map_size.lat1
        lat_max = self.map_size.lat2

        height_min = 10
        height_max = 20

        # download GFS data
        #par_GFS = ["Temperature_surface"]
        #sel_dict_GFS = {'time': slice(time_min, time_max), 'time1': slice(time_min, time_max),
        #            'height_above_ground2': slice(height_min, height_max)}

        #downloader_gfs = DownloaderFactory.get_downloader('opendap', 'gfs')
        #ds_GFS = downloader_gfs.download(par_GFS, sel_dict_GFS)

        # download CMEMS data
        par_CMEMS = ["VMDR"]
        sel_dict_CMEMS = {'time': slice(time_min, time_max)}

        downloader_cmems = DownloaderFactory.get_downloader(product_type='cmems', product='cmems_mod_glo_wav_anfc_0.083deg_PT3H-i')
        ds_CMEMS = downloader_cmems.download(parameters=par_CMEMS, sel_dict=sel_dict_CMEMS, product='cmems_mod_glo_wav_anfc_0.083deg_PT3H-i')

        print('self.ds: ',ds_CMEMS)

        raise Exception('Stop here')


    def print_sth(self):
        print('sth')

class WeatherCondFromFile(WeatherCond):
    wind_functions: None
    wind_vectors: None

    def __init__(self, model, time, hours, time_res, filepath):
        super().__init__(model, time, hours, time_res)
        self.read_dataset(filepath)

    def calculate_wind_function(self, time):
        time_str=time.strftime('%Y-%m-%d %H:%M:%S')
        #print('Reading time', time_str)

        try:
            u = self.ds['u-component_of_wind_height_above_ground'].sel(time=time_str, height_above_ground2=10)
            v = self.ds['v-component_of_wind_height_above_ground'].sel(time=time_str, height_above_ground2=10)
        except KeyError:
            time = self.ds['time']
            print('time: ', time.to_numpy())
            print('time string: ', time_str)
            raise Exception('Please make sure that time stamps of environmental data match full hours: time = ' + time_str)

        twa, tws = self.get_twatws_from_uv(u,v)

        tws = tws.to_numpy()
        twa = twa.to_numpy()

        return {'twa': twa, 'tws': tws}

    def read_wind_functions(self, iTime):
        time = self.time_start + self.time_res*iTime
        #wind = self.nc_to_wind_function_old_format()
        wind = self.calculate_wind_function(time)

        if not (wind['twa'].shape==wind['tws'].shape): raise ValueError('Shape of twa and tws not matching!')

        lat_shape = wind['twa'].shape[0]
        lon_shape = wind['twa'].shape[1]
        lats_grid = np.linspace(self.map_size.lat1, self.map_size.lat2, lat_shape)
        lons_grid = np.linspace(self.map_size.lon1, self.map_size.lon2, lon_shape)

        f_twa = RegularGridInterpolator(
            (lats_grid, lons_grid), wind['twa'],
        )

        f_tws = RegularGridInterpolator(
            (lats_grid, lons_grid), wind['tws'],
        )

        return {'twa': f_twa, 'tws': f_tws, 'timestamp': time}

    def read_wind_vectors(self, time):
        """Return u-v components for given rect for visualization."""

        lat1 = self.map_size.lat1
        lat2 = self.map_size.lat2
        lon1 = self.map_size.lon1
        lon2 = self.map_size.lon2
        time_str = time.strftime('%Y-%m-%d %H:%M:%S')

        ds_time=self.ds.sel(time = time_str)

        u = ds_time['u-component_of_wind_height_above_ground'].where(
            (ds_time.latitude >= lat1) & (ds_time.latitude <= lat2) & (ds_time.longitude >= lon1) & (
                    ds_time.longitude <= lon2) & (ds_time.height_above_ground2 == 10), drop=True)
        v = ds_time['v-component_of_wind_height_above_ground'].where(
            (ds_time.latitude >= lat1) & (ds_time.latitude <= lat2) & (ds_time.longitude >= lon1) & (
                    ds_time.longitude <= lon2) & (ds_time.height_above_ground2 == 10), drop=True)
        lats_u_1D = ds_time['latitude'].where((ds_time.latitude >= lat1) & (ds_time.latitude <= lat2), drop=True)
        lons_u_1D = ds_time['longitude'].where((ds_time.longitude >= lon1) & (ds_time.longitude <= lon2), drop=True)

        u = u.to_numpy()
        v = v.to_numpy()
        lats_u_1D = lats_u_1D.to_numpy()
        lons_u_1D = lons_u_1D.to_numpy()
        lats_u = np.tile(lats_u_1D[:, np.newaxis], u.shape[1])
        lons_u = np.tile(lons_u_1D, (u.shape[0], 1))

        return {'u': u, 'v': v, 'lats_u': lats_u, 'lons_u': lons_u, 'timestamp': time}

    def plot_weather_map(self, fig, ax, time):
        rebinx = 10
        rebiny = 10

        u = self.ds['u-component_of_wind_height_above_ground'].sel(
            time=time, height_above_ground2=10)  # .where((ds_wind.latitude>=lat1) & (ds_wind.latitude<=lat2) & (ds_wind.longitude>=lon1) & (ds_wind.longitude<=lon2), drop=True)
        v = self.ds['v-component_of_wind_height_above_ground'].sel(
            time=time,  height_above_ground2=10)  # .where((ds_wind.latitude>=lat1) & (ds_wind.latitude<=lat2) & (ds_wind.longitude>=lon1) & (ds_wind.longitude<=lon2), drop=True)

        u = u[::3, ::6]
        v = u[::3, ::6]

        #u = u.coarsen(latitude=100).to_numpy()
        #v = v.coarsen(latitude=100).to_numpy()
        #ds_rebin = self.ds.coarsen(latitude=100)
        unp = u.to_numpy()
        vnp = v.to_numpy()
        unp = graphics.rebin(unp, rebinx, rebiny)
        vnp = graphics.rebin(vnp, rebinx, rebiny)

        windspeed = np.sqrt(u ** 2 + v ** 2)
        windspeed.plot()
        plt.title('ECMWF wind speed and direction, June 1, 1984')
        plt.ylabel('latitude')
        plt.xlabel('longitude')
        x = windspeed.coords['longitude'].values
        y = windspeed.coords['latitude'].values

        print('x = ', x.shape)
        print('y = ', y.shape)

        #plt.barbs(x, y, u.values, v.values)
        plt.quiver(x, y, u.values, v.values)
    def close_env_file(self):
        self.ds.close()
    def adjust_depth_format(self, depth_path):
        debug = True
        ds_depth = xr.open_dataset(depth_path)
        ds_depth = ds_depth.sortby("latitude")
        ds_depth.load()
        ds_depth_pos = ds_depth.where(ds_depth.longitude <= 180, drop=True)
        ds_depth_neg = ds_depth.where(ds_depth.longitude > 180, drop=True)
        ds_depth_neg['longitude'] = ds_depth_neg['longitude'] - 360
        ds_depth = ds_depth_pos.merge(ds_depth_neg)

        if(debug):
            print('ds_depth_pos', ds_depth_pos)
            print('ds_depth_neg', ds_depth_neg)
            print('ds_depth new', ds_depth)

        return ds_depth

    def add_depth_to_EnvData(self, depth_path, bWriteEnvData=False):
        try:
            lat_start = self.map_size.lat1
            lat_end = self.map_size.lat2
            lon_start = self.map_size.lon1
            lon_end = self.map_size.lon2
        except:
            raise Exception('Need to initialise weather data bounding box before adding depth data!')

        ds_depth = xr.open_dataset(depth_path)
        ds_depth = ds_depth.where((ds_depth.lat > lat_start) & (ds_depth.lat < lat_end) & (ds_depth.lon > lon_start) & (
                    ds_depth.lon < lon_end) & (ds_depth.z < 0), drop=True)

        ds_depth = ds_depth.rename(lat="latitude", lon="longitude")
        weather_int = self.ds.interp_like(ds_depth, method="linear")

        depth = ds_depth['z'].to_numpy()
        depth = np.nan_to_num(depth)

        weather_int['depth'] = (['latitude', 'longitude'], depth)
        depth_test = weather_int['depth'].to_numpy()
        if(np.isnan(depth_test).any()):
            print('depth_test:', depth_test)
            raise Exception('element of depth is nan!')
        self.ds = weather_int

        if bWriteEnvData:
            self.ds.to_netcdf('/home/kdemmich/MariData/Code/MariGeoRoute/Isochrone/Data/Depth_u_EnvData/EnvData_Depth.nc')


    def get_time_step_index(self, time):
        rounded_time = round_time(time, int(self.time_res.total_seconds()))
        time_passed = rounded_time - self.time_start
        idx = (time_passed.total_seconds() / self.time_res.total_seconds())
        return {'rounded_time' : rounded_time, 'idx' : idx}

    def manipulate_dataset(self):
        #condition =  4
        #lat = 54.608889
        #lon = 6.179722
        condition = 8
        lat = 55.048333
        lon = 5.130000

        #condition = 4
        #condition = 8

        dim = 0.25
        xmin = lon - dim
        xmax = lon + dim
        ymin = lat - dim
        ymax = lat + dim
        ll = dict(longitude=slice(xmin, xmax), latitude=slice(ymin, ymax))
        print('before: ', self.ds["VHM0"].loc[ll].to_numpy())
        self.ds["VHM0"].loc[ll] = condition
        print('after: ', self.ds["VHM0"].loc[ll].to_numpy())
        self.ds.to_netcdf('/home/kdemmich/MariData/Simulationsstudie_April23/manipulated_data.nc')

        return self.ds

    def get_twatws_from_uv(self, u, v):
        tws = np.sqrt(u ** 2 + v ** 2)
        twa = 180.0 / np.pi * np.arctan2(u, v) + 180.0  # angle from 0° to 360°, 0° = N
        return twa, tws

    def init_wind_vectors(self):
        """Return wind vectors for given number of hours.
            Parameters:
                    model (dict): available forecast wind functions
                    hours_ahead (int): number of hours looking ahead
                    lats, lons: rectange defining forecast area
            Returns:
                    wind_vectors (dict):
                        model: model timestamp
                        hour: function for given forecast hour
            """

        wind_vectors = {}
        wind_vectors['model'] = self.model

        for i in range(self.time_steps):
            time = self.time_start + self.time_res * i
            wind_vectors[i] = self.read_wind_vectors(time)
            #print('reading wind vector time', time)

        self.wind_vectors = wind_vectors

    def get_wind_vector(self, time):
        time_passed = self.get_time_step_index(time)
        rounded_time = time_passed['rounded_time']
        idx = time_passed['idx']

        try:
            wind_timestamp = self.wind_vectors[idx]['timestamp']
        except KeyError:
            print('Requesting weather data for ' + str(time) + ' at index ' + str(idx) + ' but only ' + str(self.time_steps) + ' available')
            raise

        if not (rounded_time == wind_timestamp):
            ex = 'Accessing wrong weather forecast. Accessing element ' + str(
                self.wind_vectors[idx]['timestamp']) + ' but current rounded time is ' + str(rounded_time)
            raise Exception(ex)

        return self.wind_vectors[idx]
    def read_dataset(self, filepath):
        logger.info(form.get_log_step('Reading dataset from' + str(filepath),1))
        self.ds = xr.open_dataset(filepath)
        #self.ds = self.manipulate_dataset()

        print(self.ds)
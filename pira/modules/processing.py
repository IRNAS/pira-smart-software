"""
processing.py

It is a module that processes sensor data from raw to calculated .csv with lookup table /data/config.json

ENV VARS:
    - PROCESS_CSV_FILENAME (default is 'processed')
    - GDD_SENSOR_NAME (default is 'Temperature Middle 1 (F)')
    - GDD_BASE_TEMP (default is 50 F)
    - PROCESSING_RUN (default is cont)
"""
from __future__ import print_function

import os
import time
import json
import struct
import pickle
import csv
import tailer as tl
import io

from os import listdir
from os.path import isfile, join
from datetime import datetime
from datetime import timedelta

# sync folder path on device
sync_folder_path = "/data/"
# Raw data files storage location.
RAW_DATA_STORAGE_PATH = '/data/raw'
# Calculated data file storage location.
CSV_DATA_STORAGE_PATH = '/data/calculated'

# timestamp format - how header looks like
timestamp_text_format = 'Timestamp (mmddyyyy-hhmm)'

class Module(object):
    def __init__(self, boot):
        """ Inits the module"""
        self._boot = boot

        # Read environs
        filename = os.environ.get('PROCESS_CSV_FILENAME', 'processed')
        self._gdd_sensor = os.environ.get('PROCESS_GDD_SENSOR_NAME', 'Temperature middle 1 (F)')
        base_temp = os.environ.get('PROCESS_GDD_BASE_TEMP', 50)
        try:
            self._base_temp = int(base_temp)
        except:
            self._base_temp = 50

        # Ensure storage location for calculated file exists.
        try:
            os.makedirs(CSV_DATA_STORAGE_PATH)
        except OSError:
            pass

        # read config file
        config_full_path = sync_folder_path + "config.json"
        if not os.path.isfile(config_full_path):
            print("WARNING processing: config.json file not found in data directory! Exiting...")
            self._enabled = False
            return

        # check if config file is empty -> delete it, Azure module will download it in next iteration
        if os.path.getsize(config_full_path) > 0:
            with open(config_full_path, "rb") as fp:
                self._config_file = json.load(fp)
        else:
            print("WARNING processing: config.json file is empty, deleting it and exiting...")
            os.remove(config_full_path)
            self._enabled = False
            return
        
        #print(self._config_file)
        try:
            config_file_version = str(self._config_file['version'])
        except:
            config_file_version = "1"
        self._csv_filename = CSV_DATA_STORAGE_PATH  + '/' + filename + "-v" + config_file_version + ".csv"

        # prepare dictionaries of raw and calculated data
        self._raw_data = {}
        self._calculated_data = {}

        # prepare list of all csv columns (all possible sensors)
        self._csv_columns = []
        self._csv_columns.append('Timestamp (mmddyyyy-hhmm)')
        for sensor in self._config_file:
            if sensor != "version":
                name = self._config_file[sensor]['name']
                unit = self._config_file[sensor]['unit']
                self._csv_columns.append(name + " (" + unit + ")")
                if "air_pres" in sensor:
                    self._csv_columns.append(name + " (inhg)")
        self._csv_columns.append('Total accumulation (GDD)')

        # prepare temp lists, dicts and vars for combined calculations
        self._temp_lux = {}
        #self._header_row = []  # not needed
        self._file_timestamps = {}
        self._gdd_dict = {}
        self._old_gdd = 0
        self._file_gdd = 0
        self._data_ready = False
        self._write_header = False

        # everything is ok, enable this module
        self._enabled = True

    def process_data(self):
        """
        Processes self._raw_data into hourly lists per value
        Result is dict self._calculated_data - key: sensor_name, value: dict (hour_timestamp,avg_value)
        """
        try:
            for value_name in self._raw_data:
                timestamps = list(self._raw_data[value_name].keys())
                if not timestamps:
                    # we don't have data to process for current value_name
                    pass
                else:
                    timestamps.sort()   # we sort timestamps, so that the first entry is the oldest
                    min_time = min(timestamps)
                    max_time = max(timestamps)
                    # find out how many hourly intervals we have in current value
                    delta_time = max_time - min_time
                    delta_hours = int(delta_time.total_seconds() / 3600) + 1
                    hour_list = []
                    if delta_hours > 0:
                        #make list of values per hour
                        for hour in range(0, delta_hours+1):
                            hour_list = []
                            max_tstamp = min_time
                            for tstamp in timestamps:
                                test_tstamp = tstamp.replace(minute=0, second=0, microsecond=0)
                                test_delta = (min_time + timedelta(hours=hour)).replace(minute=0, second=0, microsecond=0)
                                if test_tstamp == test_delta:
                                    hour_list.append(self._raw_data[value_name][tstamp])
                                    if max_tstamp < tstamp:
                                        max_tstamp = tstamp
                            if hour_list:
                                hour_timestamp = max_tstamp.replace(minute=0, second=0, microsecond=0)
                                self.process_hourly_data(value_name, hour_list, hour_timestamp)
                    else:
                        #if we have all data in an hour
                        for item in self._raw_data[value_name]:
                            hour_list.append(self._raw_data[value_name][item])
                        hour_timestamp = max_time.replace(minute=0, second=0, microsecond=0)
                        self.process_hourly_data(value_name, hour_list, hour_timestamp)
                
        except Exception as e:
            print("ERROR processing: all new data - {}".format(e))
            #print("Processing module: error when processing raw data!")


    def process_hourly_data(self, value_name, data, timestamp):
        """
        Processes list of values from value_name for an hour.
        Each value_name is processed with variables from config file.
        Result is new entry in dictionary self._calculated_data - pair: calculated_name, value
        """
        after_equ_data = []
        try:
            #DEBUG
            #print("value name: {}".format(value_name))
            #print("Current timestamp: {}".format(timestamp))
            #print("Hourly input data: {}".format(data))

            # Battery state of charge
            if value_name == "4_8_3":
                calculated_name = self._config_file['bat']['name']
                unit = self._config_file['bat']['unit']
                config_vars = self._config_file['bat']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                z = config_vars['convert']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)
            
            # Battery voltage
            if value_name == "4_8_0":
                calculated_name = self._config_file['bat_vol']['name']
                unit = self._config_file['bat_vol']['unit']
                config_vars = self._config_file['bat_vol']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                z = config_vars['convert']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Battery current
            if value_name == "4_8_2":
                calculated_name = self._config_file['bat_cur']['name']
                unit = self._config_file['bat_cur']['unit']
                config_vars = self._config_file['bat_cur']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                z = config_vars['convert']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Rain
            if value_name == "1_5_0":
                calculated_name = self._config_file['rain']['name']
                unit = self._config_file['rain']['unit']
                config_vars = self._config_file['rain']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                result = 0.0
                for value in data:
                    result += (value + x) * y
                after_equ_data.append(result)

            # Wind
            if value_name == "1_4_0":
                calculated_name = self._config_file['wind']['name']
                unit = self._config_file['wind']['unit']
                config_vars = self._config_file['wind']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                z = config_vars['convert']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y * z
                    after_equ_data.append(result)

            # Lux top, 1_2_1 -> fullspectrum, 1_2_2 -> infrared
            if value_name == "1_2_1" or value_name == "1_2_2":
                # if this is the second sensor from the pair - perform calculations
                if value_name not in self._temp_lux and self._temp_lux:
                    keys = [key for key, value in self._temp_lux.items() if "1_2" in key]
                    if not keys:
                        # this is the first sensor from the pair - save it to temporary dict
                        temp_dict = {}
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_index = keys[0]
                    if timestamp not in self._temp_lux[temp_index]:
                        # check if we don't have current hour in temp list - save it to temporary dict
                        temp_dict = self._temp_lux[value_name]
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_list = self._temp_lux[temp_index][timestamp]
                    #print("temp lux index: {}".format(temp_list))
                    calculated_name = self._config_file['lux_top']['name']
                    unit = self._config_file['lux_top']['unit']
                    config_vars = self._config_file['lux_top']['vars']
                    x = config_vars['offset']
                    y = config_vars['multiply']
                    res_min = config_vars['min']
                    res_max = config_vars['max']
                    if len(data) > len(temp_list):
                        length = len(temp_list)
                        data = data[:length]
                    for index, value in enumerate(data):
                        com_value = (value + x) * y
                        com_temp = (temp_list[index] + x) * y
                        if value_name == "1_2_1":
                            result = self.calculate_lux(com_value, com_temp)
                        else:
                            result = self.calculate_lux(com_temp, com_value)
                        after_equ_data.append(result)
                    # remove current value since we processed it
                    del self._temp_lux[temp_index][timestamp]
                else:
                    # if this is the first sensor - save it to temporary dict
                    temp_dict = {}
                    if value_name in self._temp_lux:
                        temp_dict = self._temp_lux[value_name]
                    temp_dict[timestamp] = data
                    self._temp_lux[value_name] = temp_dict

            # Lux middle 1
            if value_name == "2_2_1" or value_name == "2_2_2":
                # if this is the second sensor from the pair - perform calculations
                if value_name not in self._temp_lux and self._temp_lux:
                    keys = [key for key, value in self._temp_lux.items() if "2_2" in key]
                    if not keys:
                        # this is the first sensor from the pair - save it to temporary dict
                        temp_dict = {}
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_index = keys[0]
                    if timestamp not in self._temp_lux[temp_index]:
                        # check if we don't have current hour in temp list - save it to temporary dict
                        temp_dict = self._temp_lux[value_name]
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_list = self._temp_lux[temp_index][timestamp]
                    calculated_name = self._config_file['lux_mid1']['name']
                    unit = self._config_file['lux_mid1']['unit']
                    config_vars = self._config_file['lux_mid1']['vars']
                    x = config_vars['offset']
                    y = config_vars['multiply']
                    res_min = config_vars['min']
                    res_max = config_vars['max']
                    if len(data) > len(temp_list):
                        length = len(temp_list)
                        data = data[:length]
                    for index, value in enumerate(data):
                        com_value = (value + x) * y
                        com_temp = (temp_list[index] + x) * y
                        if value_name == "2_2_1":
                            result = self.calculate_lux(com_value, com_temp)
                        else:
                            result = self.calculate_lux(com_temp, com_value)
                        after_equ_data.append(result)
                    # remove current value since we processed it
                    del self._temp_lux[temp_index][timestamp]
                else:
                    # if this is the first sensor from the pair - save it to temporary dict
                    temp_dict = {}
                    if value_name in self._temp_lux:
                        temp_dict = self._temp_lux[value_name]
                    temp_dict[timestamp] = data
                    self._temp_lux[value_name] = temp_dict

            # Lux middle 2
            if value_name == "3_2_1" or value_name == "3_2_2":
                # if this is the second sensor from the pair - perform calculations
                if value_name not in self._temp_lux and self._temp_lux:
                    keys = [key for key, value in self._temp_lux.items() if "3_2" in key]
                    if not keys:
                        # this is the first sensor from the pair - save it to temporary dict
                        temp_dict = {}
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_index = keys[0]
                    if timestamp not in self._temp_lux[temp_index]:
                        # check if we don't have current hour in temp list - save it to temporary dict
                        temp_dict = self._temp_lux[value_name]
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_list = self._temp_lux[temp_index][timestamp]
                    calculated_name = self._config_file['lux_mid2']['name']
                    unit = self._config_file['lux_mid2']['unit']
                    config_vars = self._config_file['lux_mid2']['vars']
                    x = config_vars['offset']
                    y = config_vars['multiply']
                    res_min = config_vars['min']
                    res_max = config_vars['max']
                    if len(data) > len(temp_list):
                        length = len(temp_list)
                        data = data[:length]
                    for index, value in enumerate(data):
                        com_value = (value + x) * y
                        com_temp = (temp_list[index] + x) * y
                        if value_name == "3_2_1":
                            result = self.calculate_lux(com_value, com_temp)
                        else:
                            result = self.calculate_lux(com_temp, com_value)
                        after_equ_data.append(result)
                    # remove current value since we processed it
                    del self._temp_lux[temp_index][timestamp]
                else:
                    # if this is the first sensor from the pair - save it to temporary list
                    temp_dict = {}
                    if value_name in self._temp_lux:
                        temp_dict = self._temp_lux[value_name]
                    temp_dict[timestamp] = data
                    self._temp_lux[value_name] = temp_dict

            # Lux bottom
            if value_name == "4_2_1" or value_name == "4_2_2":
                # if this is the second sensor from the pair - perform calculations
                if value_name not in self._temp_lux and self._temp_lux:
                    keys = [key for key, value in self._temp_lux.items() if "4_2" in key]
                    if not keys:
                        # this is the first sensor from the pair - save it to temporary dict
                        temp_dict = {}
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_index = keys[0]
                    if timestamp not in self._temp_lux[temp_index]:
                        # check if we don't have current hour in temp list - save it to temporary dict
                        temp_dict = self._temp_lux[value_name]
                        temp_dict[timestamp] = data
                        self._temp_lux[value_name] = temp_dict
                        return
                    temp_list = self._temp_lux[temp_index][timestamp]
                    calculated_name = self._config_file['lux_bot']['name']
                    unit = self._config_file['lux_bot']['unit']
                    config_vars = self._config_file['lux_bot']['vars']
                    x = config_vars['offset']
                    y = config_vars['multiply']
                    res_min = config_vars['min']
                    res_max = config_vars['max']
                    if len(data) > len(temp_list):
                        length = len(temp_list)
                        data = data[:length]
                    for index, value in enumerate(data):
                        com_value = (value + x) * y
                        com_temp = (temp_list[index] + x) * y
                        if value_name == "4_2_1":
                            result = self.calculate_lux(com_value, com_temp)
                        else:
                            result = self.calculate_lux(com_temp, com_value)
                        after_equ_data.append(result)
                    # remove current value since we processed it
                    del self._temp_lux[temp_index][timestamp]
                else:
                    # if this is the first sensor from the pair - save it to temporary list
                    temp_dict = {}
                    if value_name in self._temp_lux:
                        temp_dict = self._temp_lux[value_name]
                    temp_dict[timestamp] = data
                    self._temp_lux[value_name] = temp_dict

            # CO2
            if value_name == "1_6_0":
                calculated_name = self._config_file['co2']['name']
                unit = self._config_file['co2']['unit']
                config_vars = self._config_file['co2']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Humidity top
            if value_name == "1_3_2":
                calculated_name = self._config_file['hum_top']['name']
                unit = self._config_file['hum_top']['unit']
                config_vars = self._config_file['hum_top']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    after_equ_data.append(result)

            # Humidity middle 1
            if value_name == "2_3_2":
                calculated_name = self._config_file['hum_mid1']['name']
                unit = self._config_file['hum_mid1']['unit']
                config_vars = self._config_file['hum_mid1']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    after_equ_data.append(result)

            # Humidity middle 2
            if value_name == "3_3_2":
                calculated_name = self._config_file['hum_mid2']['name']
                unit = self._config_file['hum_mid2']['unit']
                config_vars = self._config_file['hum_mid2']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    after_equ_data.append(result)

            # Humidity bottom
            if value_name == "4_3_2":
                calculated_name = self._config_file['hum_bot']['name']
                unit = self._config_file['hum_bot']['unit']
                config_vars = self._config_file['hum_bot']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    after_equ_data.append(result)

            # Temperature top
            if value_name == "1_3_1":
                calculated_name = self._config_file['temp_top']['name']
                unit = self._config_file['temp_top']['unit']
                config_vars = self._config_file['temp_top']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    result = (result * 9 / 5) + 32
                    after_equ_data.append(result)

            # Temperature middle 1
            if value_name == "2_3_1":
                calculated_name = self._config_file['temp_mid1']['name']
                unit = self._config_file['temp_mid1']['unit']
                config_vars = self._config_file['temp_mid1']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    result = (result * 9 / 5) + 32
                    after_equ_data.append(result)

            # Temperature middle 2
            if value_name == "3_3_1":
                calculated_name = self._config_file['temp_mid2']['name']
                unit = self._config_file['temp_mid2']['unit']
                config_vars = self._config_file['temp_mid2']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    new_val = value / 100
                    result = (new_val + x) * y
                    result = (result * 9 / 5) + 32
                    after_equ_data.append(result)

            # Temperature bottom
            if value_name == "4_3_1":
                calculated_name = self._config_file['temp_bot']['name']
                unit = self._config_file['temp_bot']['unit']
                config_vars = self._config_file['temp_bot']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = value / 100
                    result = (result + x) * y
                    result = (result * 9 / 5) + 32
                    after_equ_data.append(result)

            # Air pressure top
            if value_name == "1_3_0":
                calculated_name = self._config_file['air_pres_top']['name']
                unit = self._config_file['air_pres_top']['unit']
                config_vars = self._config_file['air_pres_top']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Air pressure middle 1
            if value_name == "2_3_0":
                calculated_name = self._config_file['air_pres_mid1']['name']
                unit = self._config_file['air_pres_mid1']['unit']
                config_vars = self._config_file['air_pres_mid1']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Air pressure middle 2
            if value_name == "3_3_0":
                calculated_name = self._config_file['air_pres_mid2']['name']
                unit = self._config_file['air_pres_mid2']['unit']
                config_vars = self._config_file['air_pres_mid2']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # Air pressure bottom
            if value_name == "4_3_0":
                calculated_name = self._config_file['air_pres_bot']['name']
                unit = self._config_file['air_pres_bot']['unit']
                config_vars = self._config_file['air_pres_bot']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # TDR - soil water content
            if value_name == "4_7_0":
                calculated_name = self._config_file['tdr_water']['name']
                unit = self._config_file['tdr_water']['unit']
                config_vars = self._config_file['tdr_water']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # EC5 - soil water content
            if value_name == "4_10_0":
                calculated_name = self._config_file['ec5']['name']
                unit = self._config_file['ec5']['unit']
                config_vars = self._config_file['ec5']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # TDR - soil temperature
            if value_name == "4_7_1":
                calculated_name = self._config_file['tdr_temp']['name']
                unit = self._config_file['tdr_temp']['unit']
                config_vars = self._config_file['tdr_temp']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # TDR - permittivity
            if value_name == "4_7_2":
                calculated_name = self._config_file['tdr_perm']['name']
                unit = self._config_file['tdr_perm']['unit']
                config_vars = self._config_file['tdr_perm']['vars']
                x = config_vars['offset']
                y = config_vars['multiply']
                res_min = config_vars['min']
                res_max = config_vars['max']
                for value in data:
                    result = (value + x) * y
                    after_equ_data.append(result)

            # if we don't have any after equation data
            if not after_equ_data:
                return

            # DEBUG
            #print("Processed data: {}".format(after_equ_data))

            # remove values < min, values > max and sort the rest
            processed_data = [i for i in after_equ_data if i <= res_max]
            processed_data = [i for i in processed_data if i >= res_min]
            processed_data.sort()
            #print("Sorted processed data: {}".format(processed_data))
            if not processed_data:
                return

            # remove 10% extreme values if we have more than 3 values
            if len(processed_data) > 3:
                percent = 0.1
                num_to_remove = int(round(len(processed_data) * percent / 2))
                del processed_data[-num_to_remove]  # last half
                del processed_data[num_to_remove]   # first half

            # calculate average from normalized values
            average = sum(processed_data) / float(len(processed_data))

            # DEBUG
            #print("Calculated average: {} - {}".format(calculated_name, average))

            # append rounded average to dictionary inside timestamp
            str_timestamp = timestamp.strftime("%m%d%Y-%H00")
            if not str_timestamp in self._calculated_data:
                self._calculated_data[str_timestamp] = {}
            self._calculated_data[str_timestamp][calculated_name + " (" + unit + ")"] = round(average,2)

            # calculate required extra data
            if "hPa" in unit:
                inhg = average * 0.029529983071445
                self._calculated_data[str_timestamp][calculated_name + " (inhg)"] = round(inhg,2)

            self._data_ready = True
        
        except Exception as e:
            print("ERROR processing - hourly new data - {}".format(e))
            #print("Processing module: error when appending data to csv_file!")

    def read_csv_file(self):
        """
        Function to read csv file to memory
        it processes header, timestamps and temperatures
        """
        try:
            if not os.path.isfile(self._csv_filename):
                self._file_timestamps = {}
                self._write_header = True
                for fname in os.listdir(CSV_DATA_STORAGE_PATH):
                    if fname.endswith(".csv"):
                        return -2
                else:
                    return -1

            file = open(self._csv_filename)
            # we need to read last 30 entries so we get atleast the whole day
            last_lines = tl.tail(file,30) 
            file.close()
            if ','.join(self._csv_columns) in last_lines:
                del last_lines[last_lines.index(','.join(self._csv_columns))]

            old_timestamp = datetime.strptime("01012019-0100", "%m%d%Y-%H%M")
            newest_csv_timestamp = old_timestamp
            
            reader = csv.DictReader(last_lines, fieldnames=self._csv_columns)
            for line in reader:
                str_tstamp = line['Timestamp (mmddyyyy-hhmm)']
                if 'Timestamp' not in str_tstamp:
                    cur_timestamp = datetime.strptime(line['Timestamp (mmddyyyy-hhmm)'], "%m%d%Y-%H%M")
                    if cur_timestamp > newest_csv_timestamp:
                        newest_csv_timestamp = cur_timestamp
                    # if gdd is found, save it to variable for use in function calculate_gdd
                    if 'Total accumulation (GDD)' in line.keys() and line['Total accumulation (GDD)']:
                        self._file_gdd = float(line['Total accumulation (GDD)'])
                        old_timestamp = cur_timestamp
                        # since we found calculated gdd, we remove temperatures from dictionary
                        for item in self._file_timestamps:
                            self._file_timestamps[item] = 9000
                    # not containing calculated gdd -> check if we already found gdd from this day, otherwise save avg. temperature
                    elif self._gdd_sensor in line.keys() and old_timestamp.day != cur_timestamp.day:
                        self._file_timestamps[str_tstamp] = line[self._gdd_sensor]
                    # we don't have sensor for gdd calculations in current line
                    else:
                        self._file_timestamps[str_tstamp] = 9000

            # check if data in file is from different year than now -> reset total gdd
            if old_timestamp.year != datetime.now().year:
                self._old_gdd = 0
            else:
                self._old_gdd = self._file_gdd
            
            # DEBUG
            #print("Printing file_timestamps dictionary - read_csv_file function:")
            #print(self._file_timestamps)
            return newest_csv_timestamp

        except Exception as e:
            print("ERROR processing - read csv file - {}".format(e))
            #print("Processing module: error when appending data to csv_file!")
            return -1
        
    def get_all_gdd(self):
        """
        Function to divide input data into days
        Input dictionary - self._file_timestamps (containing key: timestamp and value: avg_temperature)
        """
        try:
            # get timestamps that have temperatures
            timestamps = []
            for tstamp in self._file_timestamps:
                #print(self._file_timestamps[tstamp])
                if self._file_timestamps[tstamp] and self._file_timestamps[tstamp] != 9000:
                    timestamp = datetime.strptime(tstamp, "%m%d%Y-%H%M")
                    timestamps.append(timestamp)
            if not timestamps:
                #print("GDD: No data found in timestamps")
                return
            
            # we get lowest and biggest time
            timestamps.sort()
            min_time = min(timestamps)
            max_time = max(timestamps)
            # find out how many daily intervals we have in current value
            delta_time = max_time - min_time
            delta_days = int(delta_time.total_seconds() / 86400) + 1
            day_list = []
            if delta_days > 0:
                # make list of values per day
                for day in range(0, delta_days+1):
                    day_list = []
                    max_tstamp = min_time
                    for tstamp in timestamps:
                        test_tstamp = tstamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        test_delta = (min_time + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
                        if test_tstamp == test_delta:
                            str_time = datetime.strftime(tstamp, "%m%d%Y-%H%M")
                            day_list.append(self._file_timestamps[str_time])
                            if max_tstamp.day < tstamp.day:
                                max_tstamp = tstamp
                    if day_list:
                        day_timestamp = max_tstamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        self.calculate_gdd(day_list, day_timestamp)
            else:
                # if we have all data in one day
                for item in self._file_timestamps:
                    day_list.append(self._file_timestamps[item])
                day_timestamp = max_time.replace(hour=0, minute=0, second=0, microsecond=0)
                self.calculate_gdd(day_list, day_timestamp)

        except Exception as e:
            print("ERROR processing - function get_all_gdd - {}".format(e))
            #print("Processing module: error when calculating GDD!")

    def get_new_gdd(self):
        """
        Function to divide processed data into days
        Input dictionary - self._calculated_data (containing key: timestamp and value: dict of (key: sensor, value: data))
        """
        try:
            # get timestamps that have temperatures
            timestamps = []
            for tstamp in self._calculated_data:
                if self._calculated_data[tstamp] and self._gdd_sensor in self._calculated_data[tstamp]:
                    timestamp = datetime.strptime(tstamp, "%m%d%Y-%H%M")
                    #TODO avoid calculating gdd for current day?
                    #if timestamp.replace(hour=0, minute=0, second=0, microsecond=0) != datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                    timestamps.append(timestamp)
            if not timestamps:
                #print("GDD: No data found in timestamps")
                return
            
            # we get lowest and biggest time
            timestamps.sort()
            min_time = min(timestamps)
            max_time = max(timestamps)
            # find out how many daily intervals we have in current value
            delta_time = max_time - min_time
            delta_days = int(delta_time.total_seconds() / 86400) + 1
            day_list = []
            if delta_days > 0:
                # make list of values per day
                for day in range(0, delta_days+1):
                    day_list = []
                    max_tstamp = min_time
                    for tstamp in timestamps:
                        test_tstamp = tstamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        test_delta = (min_time + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
                        if test_tstamp == test_delta:
                            str_time = datetime.strftime(tstamp, "%m%d%Y-%H%M")
                            day_list.append(self._calculated_data[str_time][self._gdd_sensor])
                            if max_tstamp.day < tstamp.day:
                                max_tstamp = tstamp
                    if day_list:
                        day_timestamp = max_tstamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        self.calculate_gdd(day_list, day_timestamp)
            else:
                # if we have all data in one day
                for item in self._calculated_data:
                    day_list.append(self._calculated_data[item][self._gdd_sensor])
                day_timestamp = max_time.replace(hour=0, minute=0, second=0, microsecond=0)
                self.calculate_gdd(day_list, day_timestamp)
        except Exception as e:
            print("ERROR processing - calculating new GDD - {}".format(e))
            #print("Processing module: error when calculating GDD!")
    
    def calculate_gdd(self, day_list, day_timestamp):
        """
        Function to calculate GDD for a given day
        Input: day_list (containing average temperatures), day_timestamp
        Output: new entry in dictionary - self._gdd_dict (key: timestamp, value: gdd)
        uses base temp variable - self._base_temp in F
        """
        try:
            min_temp = float(min(day_list))
            max_temp = float(max(day_list))
            day_gdd = (min_temp + max_temp) / 2 - self._base_temp
            gdd = round((self._old_gdd + day_gdd),2)
            self._gdd_dict[day_timestamp] = gdd
            self._old_gdd = gdd
            #print("New old gdd: {}".format(self._old_gdd))
        except Exception as e:
            print("ERROR processing - calculating GDD - {}".format(e))
            #print("Processing module: error when calculating GDD!")

    def calculate_lux(self, ch0, ch1):
        """
        Function to calculate illuminance value (in lux)
        Input: ch0 and ch1 -> raw values
        Output: from two calculations (lux1 and lux2) returns highest value
        Equation and constants used from https://electronics.stackexchange.com/questions/146519/tsl2591-sensor-value-calculation
        """
        gain = 25.0     # GAIN_MED
        integration_time = 300.0    # 300 MS
        cpl = integration_time * gain / 408.0
        lux1 = (ch0 - (1.64 * ch1)) / cpl
        lux2 = ((0.59 * ch0) - (0.86 * ch1)) / cpl
        if lux1 > lux2:
            return lux1
        else:
            return lux2

    def append_to_csv_file(self, newest_csv_timestamp):
        """
        Function to add new row(s) to .csv file
        First row in day has GDD added (for this day)
        """
        try:
            with open(self._csv_filename, 'a') as fp:
                if not self._data_ready:
                    # if we don't have new data -> exit without editing csv
                    return
                
                writer = csv.DictWriter(fp, fieldnames=self._csv_columns)
                # write header if file is empty
                if self._write_header:
                    writer.writeheader()
                    self._write_header = False
                #print("calculated data is: {}".format(self._calculated_data))
                calculated_timestamps = []
                # we sort new calculated data from oldest to newest timestamp
                for tstamp in self._calculated_data:
                    # we check if timestamp is older than current hour (since current hour isn't over yet)
                    if datetime.strptime(tstamp, "%m%d%Y-%H%M") < datetime.now().replace(minute=0, second=0, microsecond=0):
                        calculated_timestamps.append(tstamp)
                calculated_timestamps.sort()
                '''
                print("Calculated timestamps:") # testing prints
                print(calculated_timestamps)
                print("Newest csv timestamp:")
                print(newest_csv_timestamp)
                print("GDD dict:")
                print(self._gdd_dict)
                print("File gdd: " + str(self._file_gdd))
                print("Old gdd: " +  str(self._old_gdd))
                '''
                # we check first three data timestamps if any is in new day
                new_day = False
                first_data = datetime.strptime(calculated_timestamps[0], "%m%d%Y-%H%M")
                if newest_csv_timestamp.day != first_data.day and first_data > newest_csv_timestamp:
                    new_day = True
                second_data = 0
                third_data = 0
                if len(calculated_timestamps) > 1 and not new_day:
                    second_data = datetime.strptime(calculated_timestamps[1], "%m%d%Y-%H%M")
                    if newest_csv_timestamp.day != second_data.day and second_data > newest_csv_timestamp:
                        new_day = True
                if len(calculated_timestamps) > 2 and not new_day:
                    third_data = datetime.strptime(calculated_timestamps[2], "%m%d%Y-%H%M")
                    if newest_csv_timestamp.day != third_data.day and third_data > newest_csv_timestamp:
                        new_day = True
                # if new day is confirmed and read part of csv doesn't have gdd or has lower gdd-> write line with only timestamp and gdd
                if new_day and newest_csv_timestamp.replace(hour=0) in self._gdd_dict and (self._file_gdd == 0 or self._file_gdd < self._gdd_dict[newest_csv_timestamp.replace(hour=0)]):
                    dict_to_write = {}
                    dict_to_write['Timestamp (mmddyyyy-hhmm)'] = datetime.strftime(newest_csv_timestamp + timedelta(minutes=1), "%m%d%Y-%H%M")
                    dict_to_write['Total accumulation (GDD)'] = self._gdd_dict[newest_csv_timestamp.replace(hour=0)]
                    writer.writerow(dict_to_write)
                for tstamp in calculated_timestamps:
                    dict_to_write = self._calculated_data[tstamp]
                    #print ("dict_to_write: {}".format(dict_to_write))
                    dict_to_write['Timestamp (mmddyyyy-hhmm)'] = tstamp
                    cur_timestamp = datetime.strptime(tstamp, "%m%d%Y-%H%M")
                    # remove time from timestamp
                    cur_day_timestamp = cur_timestamp.replace(hour=0, minute=0)
                    # check if next tstamp is in next day then add GDD
                    next_tstamp_index = calculated_timestamps.index(tstamp) + 1
                    if next_tstamp_index < len(calculated_timestamps):
                        next_tstamp = datetime.strptime(calculated_timestamps[next_tstamp_index], "%m%d%Y-%H%M")
                        if cur_day_timestamp.day != next_tstamp.day:
                            # check if gdd data exists for current day and add it to dict_to_write
                            if cur_day_timestamp in self._gdd_dict:
                                dict_to_write['Total accumulation (GDD)'] = self._gdd_dict[cur_day_timestamp]
                    #print("self._file_timestamps: {}".format(self._file_timestamps))
                    #print("dict_to_write: {}".format(dict_to_write))
                    # check if data timestamp is in the file
                    if self._file_timestamps and tstamp in self._file_timestamps.keys():
                        #print("data timestamp is in the file.")
                        pass
                    else:
                        writer.writerow(dict_to_write)
        except Exception as e:
            print("ERROR processing - append to csv - {}".format(e))
            #print("Processing module: error when appending data to csv_file!")

    def process(self, modules):
        """ Function to process raw data file (.json) on device with config.json file to .csv file"""
        if not self._enabled:
            print("WARNING: Processing module not configured, skipping.")
            return

        if 'pira.modules.can' in modules:
            # read csv file
            newest_csv_timestamp = self.read_csv_file()
            if newest_csv_timestamp == -1:
                # Csv file is empty
                newest_csv_timestamp = datetime.strptime("01012019-0100", "%m%d%Y-%H%M")
            elif newest_csv_timestamp == -2:
                # csv file is empty, but previous versions exist
                print("csv file is empty, but previous versions exist")
                newest_csv_timestamp = datetime.now().replace(hour=0, second=0, microsecond=0)

            # get all raw filenames
            self._local_files = [f for f in listdir(RAW_DATA_STORAGE_PATH) if isfile(join(RAW_DATA_STORAGE_PATH, f))]
            # find the newest - local files names are made like this: "raw_values-" + dt.strftime("%m%d%Y-%H%M%S")
            timestamps = []
            for file_name in self._local_files:
                s_timestamp = file_name.replace("raw_values-", "")
                this_timestamp = datetime.strptime(s_timestamp.replace(".json", ""), "%m%d%Y-%H%M%S")
                # save timestamps that are newer than last entry in the file
                if this_timestamp.replace(minute=0, second=0, microsecond=0) > newest_csv_timestamp:
                    timestamps.append(this_timestamp)
            if not timestamps:
                print("No new raw files found...")
                return
            
            timestamps.sort()
            for timestamp in timestamps:
                new_file_name = "raw_values-" + timestamp.strftime("%m%d%Y-%H%M%S") + ".json"
                print("Processing module: processing file: {}".format(new_file_name))

                # read raw data file
                try:
                    with open(RAW_DATA_STORAGE_PATH + '/' + new_file_name, "r") as fp:
                        new_file = json.load(fp)

                    for i in new_file:  # device
                        for j in new_file[i]:   # sensor
                            for k in new_file[i][j]:    # variable
                                value_name = str(i) + "_" + str(j) + "_" + str(k)
                                #print("Value name: "+  str(value_name))
                                if value_name not in self._raw_data:
                                    self._raw_data[value_name] = {}
                                for l in new_file[i][j][k]:
                                    data = new_file[i][j][k][l]['data']
                                    time = new_file[i][j][k][l]['time']
                                    formated_time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
                                    # we only process data older than current hour
                                    if formated_time < datetime.now().replace(minute=0, second=0, microsecond=0):
                                        self._raw_data[value_name][formated_time] = data

                except Exception as e:
                    print("ERROR processing - new raw file - {}".format(e))
                    #print("Processing module: error when appending data to csv_file!")

            if self._raw_data:
                # calculate new data from raw
                self.process_data()
                # calculate old gdd (from csv file)
                self.get_all_gdd()
                # calculate new gdd (from freshly processed data)
                self.get_new_gdd()
                # save to csv file
                self.append_to_csv_file(newest_csv_timestamp)
                print("Process module: done")

                # self-disable upon successful completion if so defined
                if os.environ.get('PROCESSING_RUN', 'cont')=='once':
                    self._enabled = False

            else:
                print("ERROR processing - raw data read error.")

        else:
            print ("ERROR processing - can module is not enabled.")

    def shutdown(self, modules):
        """ Shutdown """

"""
processing.py

It is a module that processes sensor data from raw to calculated .csv with lookup table /data/config.json

ENV VARS:
    - PROCESS_CSV_FILENAME (default is 'processed.csv')
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
        filename = os.environ.get('PROCESS_CSV_FILENAME', 'processed.csv')
        self._csv_filename = CSV_DATA_STORAGE_PATH  + '/' + filename
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
            print("Processing ERROR: config.json file not found in data directory! Exiting...")
            self._enabled = False
            return

        with open(config_full_path, "rb") as fp:
            self._config_file = json.load(fp)
        #print(self._config_file)

        # prepare dictionaries of raw and calculated data
        self._raw_data = {}
        self._calculated_data = {}

        # prepare list of all csv columns (all possible sensors)
        self._csv_columns = []
        self._csv_columns.append('Timestamp (mmddyyyy-hhmm)')
        for sensor in self._config_file:
            name = self._config_file[sensor]['name']
            unit = self._config_file[sensor]['unit']
            self._csv_columns.append(name + " (" + unit + ")")
        self._csv_columns.append('Total accumulation (GDD)')

        # prepare temp lists, dicts and vars for combined calculations
        self._temp_lux = {}
        #self._header_row = []  # not needed
        self._file_timestamps = {}
        self._gdd_dict = {}
        self._old_gdd = 0
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
                    break
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
            print("Processing module error: raw data - {}".format(e))
            #print("Processing module: error when processing raw data!")


    def process_hourly_data(self, value_name, data, timestamp):
        """
        Processes list of values from value_name for an hour.
        Each value_name is processed with variables from config file.
        Result is new entry in dictionary self._calculated_data - pair: calculated_name, value
        """
        after_equ_data = []

        #DEBUG
        #print("value name: {}".format(value_name))
        #print("Hourly input data: {}".format(data))
        #print("Current timestamp: {}".format(timestamp))

        # Battery state of charge - TODO fix calculation
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
            for value in data:
                result = (value + x) * y
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

        # Lux top - TODO fix calculation
        if value_name == "1_2_1" or value_name == "1_2_2":
            # if this is the second sensor from the pair - perform calculations
            if value_name not in self._temp_lux and self._temp_lux:
                keys = [key for key, value in self._temp_lux.items() if "1_2" in key]
                if not keys:
                    # this is the first sensor from the pair - save it to temporary dict
                    self._temp_lux[value_name] = data
                    return
                temp_index = keys.pop()
                temp_list = self._temp_lux[temp_index]
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
                    result = value + temp_list[index]
                    after_equ_data.append(result)
                # remove current value since we processed it
                del self._temp_lux[temp_index]
            else:
                # if this is the first sensor - save it to temporary dict
                self._temp_lux[value_name] = data

        # Lux middle 1 - TODO fix calculation
        if value_name == "2_2_1" or value_name == "2_2_2":
             # if this is the second sensor from the pair - perform calculations
            if value_name not in self._temp_lux and self._temp_lux:
                keys = [key for key, value in self._temp_lux.items() if "2_2" in key]
                if not keys:
                    # this is the first sensor from the pair - save it to temporary dict
                    self._temp_lux[value_name] = data
                    return
                temp_index = keys.pop()
                temp_list = self._temp_lux[temp_index]
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
                    result = value + temp_list[index]
                    after_equ_data.append(result)
                # remove current value since we processed it
                del self._temp_lux[temp_index]
            else:
                # if this is the first sensor from the pair - save it to temporary dict
                self._temp_lux[value_name] = data

        # Lux middle 2 - TODO fix calculation
        if value_name == "3_2_1" or value_name == "3_2_2":
             # if this is the second sensor from the pair - perform calculations
            if value_name not in self._temp_lux and self._temp_lux:
                keys = [key for key, value in self._temp_lux.items() if "3_2" in key]
                if not keys:
                    # this is the first sensor from the pair - save it to temporary dict
                    self._temp_lux[value_name] = data
                    return
                temp_index = keys.pop()
                temp_list = self._temp_lux[temp_index]
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
                    result = value + temp_list[index]
                    after_equ_data.append(result)
                # remove current value since we processed it
                del self._temp_lux[temp_index]
            else:
                # if this is the first sensor from the pair - save it to temporary list
                self._temp_lux[value_name] = data

        # Lux bottom - TODO fix calculation
        if value_name == "4_2_1" or value_name == "4_2_2":
             # if this is the second sensor from the pair - perform calculations
            if value_name not in self._temp_lux and self._temp_lux:
                keys = [key for key, value in self._temp_lux.items() if "4_2" in key]
                if not keys:
                    # this is the first sensor from the pair - save it to temporary dict
                    self._temp_lux[value_name] = data
                    return
                temp_index = keys.pop()
                temp_list = self._temp_lux[temp_index]
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
                    result = value + temp_list[index]
                    after_equ_data.append(result)
                # remove current value since we processed it
                del self._temp_lux[temp_index]
            else:
                # if this is the first sensor from the pair - save it to temporary list
                self._temp_lux[value_name] = data

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
        if value_name == "1_3_4":
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
        if value_name == "2_3_4":
            calculated_name = self._config_file['air_pres_mid1']['name']
            unit = self._config_file['air_pres_middle1']['unit']
            config_vars = self._config_file['air_pres_middle1']['vars']
            x = config_vars['offset']
            y = config_vars['multiply']
            res_min = config_vars['min']
            res_max = config_vars['max']
            for value in data:
                result = (value + x) * y
                after_equ_data.append(result)

        # Air pressure middle 2
        if value_name == "3_3_4":
            calculated_name = self._config_file['air_pres_mid2']['name']
            unit = self._config_file['air_pres_mid2']['unit']
            config_vars = self._config_file['air_pres_middle2']['vars']
            x = config_vars['offset']
            y = config_vars['multiply']
            res_min = config_vars['min']
            res_max = config_vars['max']
            for value in data:
                result = (value + x) * y
                after_equ_data.append(result)

        # Air pressure bottom
        if value_name == "4_3_4":
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
        if "air_pres" in calculated_name:
            inhg = average * 0.029529983071445
            self._calculated_data[str_timestamp][calculated_name + " (inhg)"] = round(inhg,2)

        self._data_ready = True

    def append_to_csv_file(self):
        """
        Function to add new row(s) to .csv file
        First row in day has GDD added (for this day)
        """
        
        old_cur_day = datetime.strptime("01012019", "%m%d%Y")
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
                for tstamp in calculated_timestamps:
                    dict_to_write = self._calculated_data[tstamp]
                    #print ("dict_to_write: {}".format(dict_to_write))
                    dict_to_write['Timestamp (mmddyyyy-hhmm)'] = tstamp
                    cur_timestamp = datetime.strptime(tstamp, "%m%d%Y-%H%M")
                    # remove time from timestamp
                    cur_day_timestamp = cur_timestamp.replace(hour=0, minute=0)
                    # check if data is in new day -> then add GDD
                    if old_cur_day != cur_day_timestamp:
                        cur_str_day = datetime.strftime(cur_day_timestamp, "%m%d%Y-%H%M")
                        # first we check if previous day has gdd calculated and not in the file -> add new row with just gdd
                        if old_cur_day in self._gdd_dict and self._gdd_dict[old_cur_day] != self._old_gdd:
                            gdd_to_write = {}
                            gdd_to_write['Total accumulation (GDD)'] = self._gdd_dict[old_cur_day]
                            writer.writerow(gdd_to_write)
                        # check if gdd data exists for current day
                        if cur_str_day in self._gdd_dict:
                            dict_to_write['Total accumulation (GDD)'] = self._gdd_dict[cur_str_day]
                        old_cur_day = cur_day_timestamp
                    #print("self._file_timestamps: {}".format(self._file_timestamps))
                    #print("dict_to_write: {}".format(dict_to_write))
                    # check if data timestamp is in the file
                    if self._file_timestamps and tstamp in self._file_timestamps.keys():
                        #print("data timestamp is in the file.")
                        pass
                    else:
                        writer.writerow(dict_to_write)
        except Exception as e:
            print("Processing module error: csv data - {}".format(e))
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
                return -1

            file = open(self._csv_filename)
            # we need to read last 25 entries so we get the whole day
            last_lines = tl.tail(file,25) 
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
                    if self._gdd_sensor in line.keys():
                        # we need to get last (newest total gdd)
                        if 'Total accumulation (GDD)' in line.keys() and line['Total accumulation (GDD)'] and cur_timestamp > old_timestamp:
                            # if gdd is found, save it to variable for use in function calculate_gdd
                            self._old_gdd = line['Total accumulation (GDD)']
                            old_timestamp = cur_timestamp
                        # not containing calculated gdd -> check if we already found gdd from this day, otherwise save avg. temperature
                        elif old_timestamp.day != cur_timestamp.day:
                            self._file_timestamps[str_tstamp] = line[self._gdd_sensor]
                    # we don't have sensor for gdd calculations in current line
                    else:
                        self._file_timestamps[str_tstamp] = 9000

            # check if data in file is from different year than now -> reset total gdd
            if old_timestamp.year != datetime.now().year:
                self._old_gdd = 0

            # DEBUG
            #print("Printing file_timestamps dictionary - read_csv_file function:")
            #print(self._file_timestamps)
            
            return newest_csv_timestamp
    
        except Exception as e:
            print("Processing module error: read csv file - {}".format(e))
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
            delta_days = max_time.day - min_time.day
            day_list = []
            if delta_days > 0:
                # make list of values per day
                for day in range(0, delta_days+1):
                    day_list = []
                    for tstamp in timestamps:
                        max_tstamp = min_time
                        if tstamp.day == (min_time + timedelta(days=day)).day:
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
            print("Processing module error: function get_all_gdd - {}".format(e))
            #print("Processing module: error when calculating GDD!")

    def calculate_gdd(self, day_list, day_timestamp):
        """
        Function to calculate GDD for a given day
        Input: day_list (containing average temperatures), day_timestamp
        Output: new entry in dictionary - self._gdd_dict (key: timestamp, value: gdd )
        uses base temp variable - self._base_temp in F
        """
        try:
            min_temp = float(min(day_list))
            max_temp = float(max(day_list))
            day_gdd = (min_temp + max_temp) / 2 - self._base_temp
            gdd = self._old_gdd + round(day_gdd,2)
            self._gdd_dict[day_timestamp] = gdd
            self._old_gdd = gdd
            #print("New old gdd: {}".format(self._old_gdd))
        except Exception as e:
            print("Processing module error: calculating GDD - {}".format(e))
            #print("Processing module: error when calculating GDD!")

    def process(self, modules):
        """ Function to process raw data file (.json) on device with config.json file to .csv file"""
        if not self._enabled:
            print("WARNING: Processing module not configured, skipping.")
            return

        if 'pira.modules.can' in modules:
            # read csv file
            newest_csv_timestamp = self.read_csv_file()
            if newest_csv_timestamp == -1:
                #print("Csv file is empty...")
                newest_csv_timestamp = datetime.strptime("01012019-0100", "%m%d%Y-%H%M")

            # get all raw filenames
            self._local_files = [f for f in listdir(RAW_DATA_STORAGE_PATH) if isfile(join(RAW_DATA_STORAGE_PATH, f))]
            # find the newest - local files names are made like this: "raw_values-" + dt.strftime("%m%d%Y-%H%M%S")
            timestamps = []
            for file_name in self._local_files:
                s_timestamp = file_name.replace("raw_values-", "")
                this_timestamp = datetime.strptime(s_timestamp.replace(".json", ""), "%m%d%Y-%H%M%S")
                # save timestamps that are newer than last entry in the file and older than current hour
                if this_timestamp.replace(minute=0, second=0, microsecond=0) > newest_csv_timestamp and this_timestamp < datetime.now().replace(minute=0, second=0, microsecond=0):
                    timestamps.append(this_timestamp)
            if not timestamps:
                print("No new raw files found...")
                return
            
            timestamps.sort()
            for timestamp in timestamps:
                new_file_name = "raw_values-" + timestamp.strftime("%m%d%Y-%H%M%S") + ".json"
                print ("Processing module: processing file: {}".format(new_file_name))

                # read raw data file
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
                                self._raw_data[value_name][formated_time] = data

            if self._raw_data:
                # calculate data
                self.process_data()
                # calculate gdd
                self.get_all_gdd()
                # save to csv file
                self.append_to_csv_file()
                print("Process module: done")

                # self-disable upon successful completion if so defined
                if os.environ.get('PROCESSING_RUN', 'cont')=='once':
                    self._enabled = False

            else:
                print("Processing module error: raw data read error.")

        else:
            print ("Processing module error: can module is not enabled.")

    def shutdown(self, modules):
        """ Shutdown """

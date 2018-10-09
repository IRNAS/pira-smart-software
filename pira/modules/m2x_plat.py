"""
m2x_plat.py

It is a module that controls the upload of the M2X data

ENV VARS:
    - M2X_KEY
    - M2X_DEVICE_ID
    - M2X_NAME (default: DEMO_PI)

"""

from __future__ import print_function

import os
import time
import sys
import json
import datetime
import pickle

from m2x.client import M2XClient

class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._last_time = 0
        self._enabled = False
        self._first_run = True
        self._old_data = []
        
        # get these values under API Keys 
        self.M2X_KEY = os.environ.get('M2X_KEY', "") # get m2x device key
        self.M2X_DEVICE_ID = os.environ.get('M2X_DEVICE_ID', "") # get m2x device id
        self.M2X_NAME = os.environ.get('M2X_NAME', 'DEMO_PI') # get m2x device name (default DEMO_PI)

        # Check if m2x push is correctly configured
        if len(self.M2X_KEY) != 32 or len(self.M2X_DEVICE_ID) != 32:
            print("M2X integration not configured, skipping")
            self._enabled = False
            return

        # connect to the client
        self._client = M2XClient(key=self.M2X_KEY)
        try:
            # create device object
            self._device = self._client.device(self.M2X_DEVICE_ID)
        except:
            print("M2X connection failed with the following error:")
            print(str(self._client.last_response.raw))
            self._enabled = False
            return

        # try to load old data from disk
        try:
            with open("upload_failed_data.txt", "rb") as fp:
                self._old_data = pickle.load(fp)
        except:
            self._old_data = []

        # DEBUG
        #print(self._device.data)

        # all good to go
        self._enabled = True

    def get_timestamp(self):
        """
        Returns the timestamp for the timestamp parameter
        """
        return datetime.datetime.now()

    def upload_data(self, value_name, time, value_data):
        """
        Uploads data at the certain time (can be the past or future)
        """
        #print("Updating data to M2X @ {}".format(datetime.datetime.now()))
        try:
            self._device.post_updates(values = {
                value_name : [
                    { 'timestamp': time, 'value': value_data }
                ]
            })
        except:
            failed_data = [value_name, time, value_data]
            if not failed_data in self._old_data:
                self._old_data.append(failed_data)

    def generate_streams(self, stream_list):
        """
        Generates streams at M2X server
        """
        for stream_name in stream_list:
            print("Generating stream:" + str(stream_name))
            try:
                stream = self._device.create_stream(stream_name)
            except:
                print("Creating stream failed.")
                return
        self._first_run = False

    def process_json(self, can_data):
        """
        Process json and prepare data for upload to m2x
        """
        for i in can_data:  # device
            for j in can_data[i]:   # sensor
                for k in can_data[i][j]:    # variable
                    value_name = str(i) + "_" + str(j) + "_" + str(k)
                    print("Value name: "+  str(value_name))
                    for l in can_data[i][j][k]:
                        data = can_data[i][j][k][l]['data']
                        time = can_data[i][j][k][l]['time']
                        #print("Data: " + str(data) + " Time: " + str(time))
                        formated_time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
                        self.upload_data(value_name, formated_time, data)
        

    def process(self, modules):
        """ Main process, uploading data """
        if not self._enabled:
            print("WARNING: M2X is not correctly configured, skipping.")
            return
        print("M2X Process | Inited: {}".format(self._enabled))

        if not self._first_run:
            # read data from can module and push it to m2x server
            if 'pira.modules.can' in modules:
                print("Reading new data from can module...")
                json_data = modules['pira.modules.can'].return_json_data()
                can_data = json.loads(json_data)
                self.process_json(can_data)
                    
        # if first run, read can module and generate needed streams
        if self._first_run and 'pira.modules.can' in modules:
            stream_list = []
            json_data = modules['pira.modules.can'].return_json_data()
            can_data = json.loads(json_data)
            for i in can_data:  # device
                for j in can_data[i]:   # sensor
                    for k in can_data[i][j]:    # variable
                        value_name = str(i) + "_" + str(j) + "_" + str(k)
                        stream_list.append(value_name)
            self.generate_streams(stream_list)
            self.process_json(can_data)
        
        # check if we have old data to upload
        if self._old_data:
            print("Uploading old data...")
            old_data_size = len(self._old_data)
            for i in range(old_data_size-1, -1, -1):
                cur_el = self._old_data[i]
                del self._old_data[i]
                self.upload_data(cur_el[0], cur_el[1], cur_el[2])

        # if there is still some old data, display a message to user and save it to disk
        if self._old_data:
            print("Some data has failed to upload...")
            with open("upload_failed_data.txt", "wb") as fp:
                pickle.dump(self._old_data, fp)
    

    def shutdown(self, modules):
        """ Shutdown """
        # save old data to disk
        with open("upload_failed_data.txt", "wb") as fp:
            pickle.dump(self._old_data, fp)

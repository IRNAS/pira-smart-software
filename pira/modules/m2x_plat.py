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
from datetime import datetime

from m2x.client import M2XClient

class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._last_time = 0
        self._enabled = False
        self._first_run = True

        # get these values under API Keys 
        self.M2X_KEY = os.environ.get('M2X_KEY',None) # get m2x device key
        self.M2X_DEVICE_ID = os.environ.get('M2X_DEVICE_ID',None) # get m2x device id
        self.M2X_NAME = os.environ.get('M2X_NAME', 'DEMO_PI') # get m2x device name (default demo_pi)

        # Check if nodewatcher push is correctly configured
        if self.M2X_KEY is None or self.M2X_KEY is None:
            print("M2X integration not configured, skipping")
            self._enabled = False
            return

        # connect to the client
        self._client = M2XClient(key=self.M2X_KEY)

        # create device object
        self._device = self._client.device(self.M2X_DEVICE_ID)

        #DEBUG
        #print(self._device.data)

        # all good to go
        self._enabled = True

    def get_timestamp(self):
        """
        Returns the timestamp for the timestamp parameter
        """
        return datetime.now()

    def upload_data(self, value_name, time, value_data):
        """
        Uploads data at the certain time (can be the past or future)
        """
        #print("Updating data to M2X @ {}".format(datetime.now()))
        self._device.post_updates(values = {
            value_name : [
                { 'timestamp': time, 'value': value_data }
            ]
        })

    def generate_streams(self, stream_list):
        """
        Generates streams at M2X servers
        """
        for stream_name in stream_list:
            print("Generating stream:" + str(stream_name))
            stream = self._device.create_stream(stream_name)

    def process(self, modules):
        """ Main process, uploading data """
        if not self._enabled:
            print("WARNING: M2X is not correctly configured, skipping.")
            return
        print("M2X Process | Inited: {}".format(self._enabled))
        
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

        # if not first run, read data from can module and push it to m2x server
        if not self._first_run and 'pira.modules.can' in modules:
            json_data = modules['pira.modules.can'].return_json_data()
            can_data = json.loads(json_data)
            for i in can_data:  # device
                for j in can_data[i]:   # sensor
                    for k in can_data[i][j]:    # variable
                        value_name = str(i) + "_" + str(j) + "_" + str(k)
                        print("Value name: "+  str(value_name))
                        for l in can_data[i][j][k]:
                            #timestamp is currently used from rpi - TODO fix in can module
                            data = can_data[i][j][k][l]['data']
                            time = can_data[i][j][k][l]['time']
                            #print("Data: " + str(data) + " Time: " + str(time))
                            self.upload_data(value_name, self.get_timestamp(), data)

            '''
            # ----- OLD IMPLEMENTATION -----
            values = modules['pira.modules.can'].get_last_values()
            print("From can module read: ")
            print(values)
            for x in values:
                self.upload_data(self.get_timestamp(), x, values[x])
            # ----- OLD IMPLEMENTATION -----
            '''
        
        self._first_run = False

    def shutdown(self, modules):
        """ Shutdown """
        pass

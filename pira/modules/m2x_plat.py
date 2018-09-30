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

from m2x.client import M2XClient

class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._last_time = 0
        self._enabled = False
        self._first_run = True
        self._upload_result = True

        # get these values under API Keys 
        self.M2X_KEY = os.environ.get('M2X_KEY', None) # get m2x device key
        self.M2X_DEVICE_ID = os.environ.get('M2X_DEVICE_ID', None) # get m2x device id
        self.M2X_NAME = os.environ.get('M2X_NAME', 'DEMO_PI') # get m2x device name (default DEMO_PI)

        # Check if nodewatcher push is correctly configured
        if self.M2X_KEY is None or self.M2X_DEVICE_ID is None:
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
        Returns true if successful, false if not
        """
        #print("Updating data to M2X @ {}".format(datetime.datetime.now()))
        try:
            self._device.post_updates(values = {
                value_name : [
                    { 'timestamp': time, 'value': value_data }
                ]
            })
        except:
            print("Uploading data failed.")
            return False

        return True

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

    def process(self, modules):
        """ Main process, uploading data """
        if not self._enabled:
            print("WARNING: M2X is not correctly configured, skipping.")
            return
        print("M2X Process | Inited: {}".format(self._enabled))
        
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
                            data = can_data[i][j][k][l]['data']
                            time = can_data[i][j][k][l]['time']
                            #print("Data: " + str(data) + " Time: " + str(time))
                            formated_time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
                            if self._upload_result:
                                self._upload_result = self.upload_data(value_name, formated_time, data)
                            if not self._upload_result:
                                print("Update failed, breaking ...")
                                break
                            
                                
        # if first run, read can module and generate needed streams
        if self._first_run and 'pira.modules.can' in modules:
            stream_list = []
            json_data = modules['pira.modules.can'].return_json_data()
            can_data = json.loads(json_data)
            for i in can_data:  # device
                for j in can_data[i]:   # sensor
                    for k in can_data[i][j]:    # variable
                        value_name = str(i) + "_" + str(j) + "_" + str(k)
                        if not value_name in stream_list:   # check if stream already exists in list
                            stream_list.append(value_name)
            self.generate_streams(stream_list)


    def shutdown(self, modules):
        """ Shutdown """
        pass

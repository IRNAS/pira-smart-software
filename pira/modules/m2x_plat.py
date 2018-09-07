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
from datetime import datetime

from m2x.client import M2XClient

class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._last_time = 0
        self._enabled = False

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

    def upload_data(self, time, value_name, value_data):
        """
        Uploads data at the certain time (can be the past or future)
        """
        #print("Updating data to M2X @ {}".format(datetime.now()))
        self._device.post_updates(values = {
            value_name : [
                { 'timestamp': time, 'value': value_data }
            ]
        })

    def process(self, modules):
        """ Main process, uploading data """
        if not self._enabled:
            print("WARNING: M2X is not correctly configured, skipping.")
            return
        print("M2X Process | Inited: {}".format(self._enabled))
        #self.upload_data(self.get_timestamp(), 42, 420)     # testing

        if 'pira.modules.can' in modules:
            values = modules['pira.modules.can'].get_last_values()
            print("From can module read: ")
            print(values)
            for x in values:
                self.upload_data(self.get_timestamp(), x, values[x])
            

    def shutdown(self, modules):
        """ Shutdown """
        pass

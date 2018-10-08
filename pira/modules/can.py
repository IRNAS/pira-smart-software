"""
can.py

It is a module that controls the CAN interface

ENV VARS:
    - CAN_NUM_DEV
    - CAN_NUM_SEN

"""
from __future__ import print_function

from ..messages import MeasurementConfig
from ..hardware import mcp2515

import os
import time
import json
import datetime
import struct

class Module(object):
    def __init__(self, boot):
        """ Inits the module and Mcp2515 """
        self._boot = boot

        self.devices_json = {}
        self.sensors_list = []

        try:
            # init driver
            self._driver = mcp2515.MCP2515()
        except:
            print("WARNING: CAN connection failed.")
            self._enabled = False
            return

        # Read environs
        num_dev_addrs = os.environ.get('CAN_NUM_DEV', '4') # number of can devices to scan
        num_sen_addrs = os.environ.get('CAN_NUM_SEN', '10') # number of sensor addresses to scan
        try:
            self._num_dev_addrs = int(num_dev_addrs)
        except:
            self._num_dev_addrs = 4    
        try:
            self._num_sen_addrs = int(num_sen_addrs)
        except:
            self._num_sen_addrs = 10

        # Scan for CAN devices and their sensors
        device_addr = "0x100"   # address of first can device to scan
        hex_addr = int(device_addr, 16)
        for i in range (0, self._num_dev_addrs):
            dev_addr = hex_addr + i*256
            # check from 0, which is device to the max number of sensors
            for j in range(0, self._num_sen_addrs+1):
                sen_addr = dev_addr + j
                can_return = self.scan_for_sensors(sen_addr)
                #if sensor present add it to the list
                if can_return>0:
                    self.sensors_list.append(sen_addr)
                #if received the response but not present continue through the loop
                elif can_return==0:
                    continue #go to the next loop iteration
                #if no response device is not present and skip to next device
                elif can_return<0:
                    break # break out of this loop
                    #note if one sensor does not respond, it will not continue this way
 
        if self.sensors_list:
            print("CAN: Found sensors on addresses:")
            print([hex(x) for x in self.sensors_list])    #Print sensor ids
        else:
            print("CAN: Didn't find any sensors returning proper data.")
    
        self._enabled = True

    def scan_for_sensors(self, address):
        """ Scan at address, return 1 if sensor returns expected data, 0 if responding but not present and -1 if timeout """
        # Clear rx buffer
        data_read = self._driver.get_raw_data()
        #print("CAN: on " + str(hex(address)) + " clearing rx: " + str(data_read))

        # send a "wakeup" to the sensor, send 0x02 indicating scan
        self._driver.send_data(address, [0x02], False)
        time.sleep(0.1)
        
        # Sensor returns two zeros for data if not available
        result = self._driver.get_data()
        if result is None:
            #print("ERROR: Failed receiving message from CAN.")
            self._driver.flush_buffer()
            # this means the device is not present, can skip to next device, TODO
            return -1
        if (result.dlc == 0 or (len(result.data) < 4)):
            #print("Nothing to read.")
            return 0

        # We read the data from sensors only to clear the buffer
        num_data = result.data[0]   # nr of columns   
        num_var = result.data[1]    # nr of variables
        for var in range(0, num_var):
            for dat in range(0, num_data):
                data_read = self._driver.get_raw_data() # data
                data_read = self._driver.get_raw_data() # time
        

        return 1


    def get_data_json(self, sensor_ID):
        """ Read data from sensor """
        # Clear rx buffer
        data_read = self._driver.get_raw_data()
        #print("CAN: on " + str(hex(sensor_ID)) + " clearing rx: " + str(data_read))

        # send a "wakeup" to the sensor 1
        self._driver.send_data(sensor_ID, [0x01], False)
        send_time = datetime.datetime.now()  # we save current rpi time

        # receive message and read how many data points are we expecting
        number = self._driver.get_data()
        if (number is None):
            #print("ERROR: Failed receiving message from CAN.")
            self._driver.flush_buffer()
            return
        # if sensor sends back two zeros there is nothing to read
        if (number.dlc == 0 or (len(number.data) < 4)):
            #print("Nothing to read.")
            return
        
        # get how many coloumns there are (coloumn x 8bit)
        num_of_data = number.data[0]
        # get how many variables there are
        num_of_var = number.data[1]
        # get delta time between last measurement and can send
        time_low = number.data[2]
        time_high = number.data[3]
        delta_time = datetime.timedelta(seconds=(float(time_high << 8 | time_low)/10))
        read_time = send_time - delta_time

        variables = {}

        # go through the variables
        for var in range(0, num_of_var):

            # log the varaible number
            #print("VAR {}".format(col))

            values = {}
            calculated_delta = 0
            data_list = []
            delta_list = []

            # go through the amount of data in a var
            for dat in range(0, num_of_data):

                # read message DATA
                self._message = self._driver.get_raw_data()

                # print out our message received with dlc
                #print("Message DLC: {}".format(self._message.dlc))
                #print(*self._message.data, sep=", ")

                # dlc represents how many data points are in the received message
                for i in range(0, self._message.dlc, 2):
                    # try except because of out of index error
                    try:
                        calc = float(self._message.data[i+1] << 8 | self._message.data[i])
                        # conversion to negative numbers
                        if calc > 32767:
                            calc -= 65536
                        data_list.append(calc)
                    except:
                        break
                    
                # read message TIME
                self._message = self._driver.get_raw_data()

                # print out our message received with dlc
                #print("Time Message DLC: {}".format(self._message.dlc))
                #print(*self._message.data, sep=", ")

                # dlc represents how many data points are in the received message
                for i in range(0, self._message.dlc, 2):
                    # try except because of out of index error
                    try:
                        calc = float(self._message.data[i+1] << 8 | self._message.data[i])
                        delta_list.append(calc/10)
                    except:
                        break
                        
            # insert read data into json     
            for i in range(len(data_list)-1, -1, -1):
                data = {}
                data['data'] = data_list[i]
                if i != len(data_list)-1:
                    calculated_delta += delta_list[-1]
                    delta_list.pop()
                calculated_time = read_time - datetime.timedelta(seconds=calculated_delta)
                data['time'] = str(calculated_time)
                values[i] = data
            
            variables[var] = values

        #sensors_json[str(sensor_ID % 256)] = variables
        return variables

    def return_json_data(self):
        """ Create JSON object from devices sensor data """
        dump = json.dumps(self.devices_json)
        return dump

    def process(self, modules):
        """ Function to process sensors, sends out the data and receives """
        if not self._enabled:
            print("WARNING: CAN is not connected, skipping.")
            return
        
        # Call sensors and get data
        for j in self.sensors_list:
            # list of measurements per sensor
            sensor_data = self.get_data_json(j)
            if sensor_data:     # if sensor returns some data
                sensor_json = {}
                #check if there is an entry for this device yet
                device = int(j/0x100)
                if self.devices_json.has_key(str(device)):
                    # load existing values and add
                    sensor_json =self.devices_json[str(device)]
                # store sensor readings                
                sensor_json[str(j % 256)] = sensor_data 
                # write the data back to main json
                self.devices_json[str(device)] = sensor_json

            time.sleep(0.1)
        
        # DEBUG
        #dumper = self.return_json_data()
        #print(dumper) # incorrect values, repeated from last device

    def shutdown(self, modules):
        """ Shutdown """
        if self._enabled:
            self._driver.shutdown()


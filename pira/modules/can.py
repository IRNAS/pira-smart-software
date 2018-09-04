"""
can.py

It is a module that controls the CAN interface
"""
from __future__ import print_function

from ..messages import MeasurementConfig
from ..hardware import mcp2515


import os
import time

CAN_MASTER_ID = 0x001
CAN_DEVICE_1_ID = 0x100
CAN_DEVICE_1_SENS1_ID = 0x101
CAN_DEVICE_1_SENS2_ID = 0x102

class Module(object):
    def __init__(self, boot):
        """ Inits the Mcp2515 """
        self._boot = boot
        
        self.l0_temp = []
        self.l0_vdd = []
        
        try:
            self._driver = mcp2515.MCP2515()
        except:
            print("WARNING: CAN connection failed.")
            self._enabled = False
            return

        self._enabled = True

    def dev_1_sens_1(self):
        
        # send a "wakeup" to the sensor 1 
        self._driver.send_data(CAN_DEVICE_1_SENS1_ID, [0x01], False)

        # receive message and read how many data points are we expecting
        number = self._driver.get_data()

        # get how many coloumns there are (coloumn x 8bit)
        num_of_data = number.data[0] + 1

        # get how many variables there are
        num_of_var = number.data[1]

        # go through the variables
        for col in range(0, num_of_var):

            # log the varaible number
            #print("VAR {}".format(col))
            
            # go through the amount of data in a var
            for dat in range(0, num_of_data):

                # read message
                self._message = self._driver.get_raw_data()
                
                # print out our message received with dlc
                #print("Message DLC: {}".format(self._message.dlc))
                #print(*self._message.data, sep=", ")
              
                # for looping through data 
                calc_first = -1
                calc_second = -1
                
                # dlc represents how many data points are in the received message
                for i in range(0, self._message.dlc):

                    # calculate the index for the first and second number
                    calc_first = calc_second + 1
                    calc_second = calc_first + 1
                    
                    # try except because of out of index error
                    try:

                        # print data
                        #print(" Data[{}]: {}".format(i, self._message.data[i]))
                        
                        # calculate the value -> first + second/100 -> example: 27 + 48/100 -> 27.48
                        calc = self._message.data[calc_first] + float(self._message.data[calc_second])/100
                        
                        # print the calculation
                        print("Calc: {}".format(str(calc)))
                       
                        # it depends which variable we are using (VAR0 -> TEMP) (VAR1 -> VDD)
                        if col is 0:
                            self.l0_temp.append(calc)           # append it to the array
                        elif col is 1:
                            self.l0_vdd.append(calc)            # append it to the array
                    except:
                        break       

        # print out the two arrays
        print("L0 TEMP DATA:")
        print(*self.l0_temp, sep=", ")
        print("\nL0 VDD DATA:")
        print(*self.l0_vdd, sep=", ")


    def process(self, modules):
        """ Sends out the data, receives """
        if not self._enabled:
            print("WARNING: CAN is not connected, skipping.")
            return
        
        # execute the dev1 board sensor 1 
        self.dev_1_sens_1()            

        time.sleep(60)
        #print("Read temperature of murata: {}".format(self._recv_message.data[0]))

    def shutdown(self):
        """ Shutdown """
        self._driver.shutdown()

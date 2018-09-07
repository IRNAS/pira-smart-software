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
CAN_DEVICE_L0_ID = 0x101
CAN_DEVICE_TSL2561_ID = 0x102
CAN_DEVICE_BME280_ID = 0x103
CAN_DEVICE_ANEMOMETER_ID = 0x104
CAN_DEVICE_RAIN_ID = 0x105
CAN_DEVICE_CO2_ID = 0x106
CAN_DEVICE_TDR_ID = 0x107

class Module(object):
    def __init__(self, boot):
        """ Inits the Mcp2515 """
        self._boot = boot
        
        # L0
        self.l0_temp = []
        self.l0_vdd = []
        
        # TSL2561
        self.TSL2561_visible = []
        self.TSL2561_fullspec = []
        self.TSL2561_infrared = []
        
        # BME
        self.BME280_pressure = []
        self.BME280_temperature = []
        self.BME280_humidity = []

        # WIND
        self.ANEMOMETER_wind = []

        # RAIN
        self.RAIN_count = []

        # CO2
        self.CO2_value = []

        # TDR
        self.TDR_vol_w_content = []
        self.TDR_soil_temp = []
        self.TDR_soil_perm = []
        self.TDR_soil_elec = []
        self.TDR_other = []

        try:
            # init driver
            self._driver = mcp2515.MCP2515()
        except:
            print("WARNING: CAN connection failed.")
            self._enabled = False
            return

        self._enabled = True

    def get_data_sensors(self, sensor_ID):
        
        # send a "wakeup" to the sensor 1 
        self._driver.send_data(sensor_ID, [0x01], False)
        # TODO add timeout

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
                        calc = float(self._message.data[calc_second] << 8 | self._message.data[calc_first])
                        if sensor_ID is CAN_DEVICE_L0_ID: 
                            
                            calc = calc / 100

                            # it depends which variable we are using (VAR0 -> TEMP) (VAR1 -> VDD)
                            if col is 0:
                                self.l0_temp.append(calc)           # append it to the array
                            elif col is 1:
                                self.l0_vdd.append(calc)            # append it to the array
                    
                        elif sensor_ID is CAN_DEVICE_TSL2561_ID:
                            if col is 0:
                                self.TSL2561_visible.append(calc)
                            elif col is 1:
                                self.TSL2561_fullspec.append(calc)
                            elif col is 2:
                                self.TSL2561_infrared.append(calc)
                        elif sensor_ID is CAN_DEVICE_BME280_ID:
                            
                            calc = calc / 100

                            if col is 0:
                                self.BME280_pressure.append(calc)
                            elif col is 1:
                                self.BME280_temperature.append(calc)
                            elif col is 2:
                                self.BME280_humidity.append(calc)
                        elif sensor_ID is CAN_DEVICE_ANEMOMETER_ID:
                            
                            calc = calc / 100
                            if col is 0:
                                self.ANEMOMETER_wind.append(calc)
                        elif sensor_ID is CAN_DEVICE_RAIN_ID:

                            if col is 0:
                                self.RAIN_count.append(calc)
                        elif sensor_ID is CAN_DEVICE_CO2_ID:

                            calc = calc * 100

                            if col is 0:
                                self.CO2_value.append(calc)
                        elif sensor_ID is CAN_DEVICE_TDR_ID:

                            if col is 0:
                                self.TDR_vol_w_content.append(calc)
                            elif col is 1:
                                self.TDR_soil_temp.append(calc)
                            elif col is 2:
                                self.TDR_soil_perm.append(calc)
                            elif col is 3:
                                self.TDR_soil_elec.append(calc)
                            elif col is 4:
                                self.TDR_other.append(calc)
                                
                    except:
                        break

        '''
        # L0 printing
        if sensor_ID is CAN_DEVICE_L0_ID:
            # print out the two arrays
            print("L0 TEMP DATA:")
            print(*self.l0_temp, sep=", ")
            print("\nL0 VDD DATA:")
            print(*self.l0_vdd, sep=", ")
        
        # TSL2561 printing
        if sensor_ID is CAN_DEVICE_TSL2561_ID:
            print("TSL2561 VISIBLE DATA:")
            print(*self.TSL2561_visible, sep=", ")
            print("\nTSL2561 FULLSPEC DATA:")
            print(*self.TSL2561_fullspec, sep=", ")
            print("\nTSL2561 INFRARED DATA:")
            print(*self.TSL2561_infrared, sep=", ")
    
        # BME280 printing
        if sensor_ID is CAN_DEVICE_BME280_ID:
            print("BME280 PRESSURE DATA:")
            print(*self.BME280_pressure, sep=", ")
            print("BME280 TEMPERATURE DATA:")
            print(*self.BME280_temperature, sep=", ")
            print("BME280 HUMIDITY DATA:")
            print(*self.BME280_humidity, sep=", ")

        # ANEMOMETER printing
        if sensor_ID is CAN_DEVICE_ANEMOMETER_ID:
            print("ANEMOMETER WIND DATA:")
            print(*self.ANEMOMETER_wind, sep=", ")
            
        # RAIN printing
        if sensor_ID is CAN_DEVICE_RAIN_ID:
            print("RAIN drops DATA:")
            print(*self.RAIN_count, sep=", ")

        # CO2 printing
        if sensor_ID is CAN_DEVICE_CO2_ID:
            print("CO2 value:")
            print(*self.CO2_value, sep=", ")

        # TDR printing
        if sensor_ID is CAN_DEVICE_TDR_ID:
            print("TDR VOL. W. CONTENT DATA:")
            print(*self.TDR_vol_w_content, sep=", ")
            print("TDR SOIL TEMP DATA:")
            print(*self.TDR_soil_temp, sep=", ")
            print("TDR SOIL PERM DATA:")
            print(*self.TDR_soil_perm, sep=", ")
            print("TDR SOIL ELEC DATA:")
            print(*self.TDR_soil_elec, sep=", ")
            print("TDR other DATA:")
            print(*self.TDR_other, sep=", ")
    '''
    def process(self, modules):
        """ Sends out the data, receives """
        if not self._enabled:
            print("WARNING: CAN is not connected, skipping.")
            return
        
        # calling the sensors and getting data
        self.get_data_sensors(CAN_DEVICE_L0_ID)
        self.get_data_sensors(CAN_DEVICE_TSL2561_ID)
        self.get_data_sensors(CAN_DEVICE_BME280_ID)
        self.get_data_sensors(CAN_DEVICE_ANEMOMETER_ID)
        self.get_data_sensors(CAN_DEVICE_RAIN_ID)
        self.get_data_sensors(CAN_DEVICE_CO2_ID)
        self.get_data_sensors(CAN_DEVICE_TDR_ID)

        time.sleep(60)

    def shutdown(self):
        """ Shutdown """
        self._driver.shutdown()

    def get_last_values(self):  # Read last value from all available lists
        """ Get CAN - last measured values from all implemented sensors """
        last_values = { }   #dictionary
        # L0
        if self.l0_temp:
            last_values["temperature"] = self.l0_temp[-1]
        if self.l0_vdd:
            last_values["vdd"] = self.l0_vdd[-1]
        # TSL2561
        if self.TSL2561_visible:
            last_values["tsl_visible"] = self.TSL2561_visible[-1]
        if self.TSL2561_fullspec:
            last_values["tsl_fullspec"] = self.TSL2561_fullspec[-1]
        if self.TSL2561_infrared:
            last_values["tsl_infrared"] = self.TSL2561_infrared[-1]
        # BME
        if self.BME280_pressure:
            last_values["bme_pressure"] = self.BME280_pressure[-1]
        if self.BME280_temperature:
            last_values["bme_temperature"] = self.BME280_temperature[-1]
        if self.BME280_humidity:
            last_values["bme_humidity"] = self.BME280_humidity[-1]
        # WIND
        if self.ANEMOMETER_wind:
            last_values["wind"] = self.ANEMOMETER_wind[-1]
        # RAIN
        if self.RAIN_count:
            last_values["rain"] = self.RAIN_count[-1]
        #CO2
        if self.CO2_value:
            last_values["co2"] = self.CO2_value[-1]
        #TDR
        if self.TDR_vol_w_content:
            last_values["tdr_vol_w_cont"] = self.TDR_vol_w_content[-1]
        if self.TDR_soil_temp:
            last_values["tdr_soil_temp"] = self.TDR_soil_temp[-1]
        if self.TDR_soil_perm:
            last_values["tdr_soil_perm"] = self.TDR_soil_perm[-1]
        if self.TDR_soil_elec:
            last_values["tdr_soil_elec"] = self.TDR_soil_elec[-1]
        if self.TDR_other:
            last_values["tdr_other"] = self.TDR_other[-1]

        return last_values


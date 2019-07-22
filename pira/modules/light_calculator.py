'''
Module for Skye NDVI / PIR sensor channel calculations and AMS multispectral light sensor raw data read

Input MAX: 2 sensors, 4 channels each - raw voltage
    Sensor 1: 1860ND/a - reflected light (dn) - adc channels 0-3
    Sensor 2: 1860D/A - incident light (up) - adc channels 4-7

Input AS: 1 sensor AS7341, 11 channels on 6 adc outputs - raw voltage
    Read 0: f1-f4, clear and nir
    Read 1: f5-f8, clear and nir

Output: new line in light_raw_values.json file with timestamp and calculated channel values
    file located in folder LIGHT_RAW_PATH

All MAX lists follow the same order: [ch1-dn, ch2-dn, ch3-dn, ch4-dn, ch1-up, ch2-up, ch3-up, ch4-up]
'''

import os
import json
import datetime

from ..hardware import max11615
from ..hardware import as7341

# MAX lists - values from sensor calibration certificates for NDVI / PIR
bandwidth_list = [12.2, 9.3, 38.4, 43.3, 12.0, 9.4, 38.1, 43.0]
sensitivity_list = [0.01839, 0.01485, 0.06060, 0.06236, 0.05704, 0.04681, 0.1908, 0.2004]
zero_offset_list = [-0.11, -0.15, 0.24, 0.01, 0.04, -0.14, 0.14, -0.13]

# light_raw_values.json filepath
LIGHT_RAW_PATH = '/data/light'
JSON_FILENAME = "light_raw_values.json"

# prepare names of raw Skye sensor channels
LIGHT_CH_NAMES = ["531R", "570R", "RedR", "NirR", "531I", "570I", "RedI", "NirI"]

# making both calculators accessible from other modules
def calculate_ndvi(raws):
        ''' Calculate NDVI value from list of all channels '''
        try:
            nir = raws[3] / raws[7]
            red = raws[2] / raws[6]
            ndvi = (nir - red) / (nir + red)
            return ndvi

        except ZeroDivisionError:
            return 0
        except Exception as e:
            print("ERROR calculatind NDVI - {}".format(e))
            #print("ERROR calculatind NDVI.")
            return 0

def calculate_pir(raws):
    ''' Calculate PIR value from list of all channels '''
    try:
        seven = raws[1] / raws[5]
        three = raws[0] / raws[4]
        pir = (seven - three) / (seven + three)
        return pir

    except ZeroDivisionError:
        return 0
    except Exception as e:
        print("ERROR calculatind PIR - {}".format(e))
        #print("ERROR calculatind PIR.")
        return 0

class Module(object):

    def __init__(self, boot):
        ''' Inits the module, max11615 adc and as7341 light sensor'''
        self._boot = boot

        # Ensure storage location for raw light files exists.
        try:
            os.makedirs(LIGHT_RAW_PATH)
        except OSError:
            pass

        try:
            self._max = max11615.MAX11615()
            max_status = self._max.init()

        except:
            print("WARNING: ADC connection failed.")
            self._max = None

        try:
            self._as = as7341.AS7341()
            as_status = self._as.init()
        except:
            print("WARNING: light sensor connection failed.")
            self._as = None

        if (self._max is None and self._as is None) or (max_status == False and as_status == False):
            # Connection to both sensors has failed, disable this module
            self._enabled = False
        else:
            self._enabled = True
        
    def read_voltages(self):
        ''' Read all 8 channels from ADC, convert to mV, perform zero offset and return values in a list '''
        voltages = []
        for i in range(self._max.ADC_CHANNEL_COUNT):
            res = self._max.read_channel(i)
            conv = self._max.convert(res)
            conv += zero_offset_list[i]
            # avoid negative numbers
            if conv < 0:
                conv = 0.0
            #print("Channel {} - res: {} - conv: {}").format(i, res, conv)
            voltages.append(conv)
        return voltages

    def calculate_raws(self, voltage_list):
        '''  Calculate list of raw values from voltages using sensitivity and bandwidth lists'''
        raws = []
        for i in range(self._max.ADC_CHANNEL_COUNT):
            raw = (voltage_list[i] * sensitivity_list[i]) / bandwidth_list[i]
            raws.append(raw)
        return raws

    def process(self, modules):
        ''' 
        It reads voltages from MAX and calculates raw data for all its channels,
        it gets raw data from AS sensor
        and appends everything to .json file 
        '''
        if not self._enabled:
            print("WARNING: Skipping light calculator module...")
            return

        max_raws = []
        ams_raws = []
        try:
            if self._max is None:
                print("WARNING: Skipping Skye channels calculator...")
            else:
                voltages = self.read_voltages()
                max_raws = self.calculate_raws(voltages)
                #print(max_raws)

            if self._as is None:
                print("WARNING: Skipping AMS sensor...")
            else:
                read0 = self._as.get_data(0)
                read1 = self._as.get_data(1)

                # merge first 4 channels from read0 and whole read1 into one list
                ams_raws = read0[:4] + read1
                #print(ams_raws)

        except Exception as e:
                print("ERROR light_calculator when reading data - {}".format(e))
                #print("ERROR - light_calculator when reading data.")
        
        if max_raws or ams_raws:
            try:
                # prepare new data
                new_data = {}
                new_data["ams"] = ams_raws
                new_data["skye"] = max_raws

                # prepare new dictionary
                timestr = datetime.datetime.now().strftime("%m%d%Y-%H%M%S")
                new_dict = {}
                new_dict[timestr] = new_data

                # replace ' with " to make valid json
                str_dict = str(new_dict).replace("'", '"')

                # check if json file exists and is not empty
                full_file_path = os.path.join(LIGHT_RAW_PATH, JSON_FILENAME)
                if os.path.isfile(full_file_path) and os.path.getsize(full_file_path):
                    # read only last two lines of the file
                    with open(full_file_path, "r+") as fp:
                        # move pointer to end of the file
                        fp.seek(0, os.SEEK_END)
                        pos = fp.tell() - 1

                        # read back until new line char is found
                        while pos > 0 and fp.read(1) != "\n":
                            pos -= 1
                            fp.seek(pos, os.SEEK_SET)
                        
                        # read one char after new line
                        last_char = fp.read(1) 
                        if pos > 0 and last_char == '}':
                            # if } char is found, delete this line
                            fp.seek(pos, os.SEEK_SET)
                            fp.truncate()
                        else:
                            # if not, write new line char
                            fp.seek(0, os.SEEK_END)
                            #fp.write("\n")
                        
                        # write new data in new line and add } in another new line
                        fp.write("\n" + str_dict[1:-1] + ",\n}")
                else:
                    # create new file and add new data
                    with open(full_file_path, "w") as fp:
                        fp.write("{\n" + str_dict[1:-1] + ",\n}")

                print("Light calculator: done")

            except Exception as e:
                print("ERROR light_calculator when processing data - {}".format(e))
                #print("ERROR - light_calculator when processing.")
            
        else:
            print("Light calculator: no new data is available...")

    def shutdown(self, modules):
        ''' Shutdown the module'''
        # put AS sensor to sleep
        self._as.power_off()
        pass

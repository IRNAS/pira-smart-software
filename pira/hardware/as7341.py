'''
Hardware class to get data from 11-Channel Spectral Sensor AS7341
Sensor doc: AMS_03152019_AS7341_DS000504_1-00.pdf
SMUX multiplexer configuration doc: AN_AS7341_SMUX_configuration_1V0.pdf
'''
import smbus
from time import sleep

# I2C init infos
I2C_CHANNEL = 1      # selected i2c channel on rpi
LIGHT_ADDR = 0x39    # sensor address

# sensor configuration constants
AS_ATIME = 0x64
AS_ASTEP_L = 0xe7
AS_ASTEP_H = 0x03
AS_GAIN = 0x08  # 128x
# integration time = (ATIME + 1) * (ASTEP + 1) * 2.78 micro seconds

class AS7341(object):

    def __init__(self):
        ''' Initialize i2c bus '''
        self.AS_CHANNEL_COUNT = 6   # number of sensor adc output channels
        self.AS_READ_TIMEOUT = 100   # num of retries when waiting for data (100 is 1 second)
        try:
            self._bus = smbus.SMBus(I2C_CHANNEL)
        except:
            print("Bus on channel {} is not available.").format(I2C_CHANNEL)
            print("Available busses are listed as /dev/i2c*")
            self._bus = None

    def init(self):
        ''' Initialize sensor on specified i2c address '''
        if self._bus is None:
            return False
        
        try:
            # set atime, set astep, set gain
            self.set_atime(AS_ATIME)
            self.set_astep(AS_ASTEP_L, AS_ASTEP_H)
            self.set_gain(AS_GAIN)

            # wake sensor from sleep and wait a little bit
            self.power_on()
            sleep(0.01)

            return True

        except Exception as e:
            print("ERROR - AS7341: init has failed - {}".format(e))
            #print("ERROR - AS7341: initializaton has failed."):
            return False

    def get_data(self, part_num):
        ''' 
        Configure chip, perform spectral measurement and return data in list 
        Parameter part_num (0 or 1) - which part of channels to read
            0 - f1-f4, clear and nir
            1 - f5-f8, clear and nir
        Returns list of results from all channels or empty list if error
        '''
        if part_num < 0 or part_num > 1:
            print("ERROR - AS7341: Wrong channels selected (options are 0 and 1!")
            return [] 

        # configure to read specified part of channels
        self.write_smux_config()
        if part_num == 0:
            self.f1_f4_clear_nir()
        else:
            self.f5_f8_clear_nir()
        self.start_smux_command()

        # wait for smux config to finish - timeouts after specified retries
        enabled = True
        timeout = 0
        while enabled:
            enabled = self.get_smux_status()
            timeout += 1
            if timeout >= self.AS_READ_TIMEOUT:
                print("WARNING - AS7341: smux config wait has timed out!")
                return []
            sleep(0.01)

        # enable bit for measurements
        self.sm_enabled(True)
        sleep(0.01)

        # wait for data to be available - timeouts after specified retries
        data_ready = False
        timeout = 0
        while not data_ready:
            data_ready = self.is_data_ready()
            timeout += 1
            if timeout >= self.AS_READ_TIMEOUT:
                print("WARNING - AS7341: data wait has timed out!")
                return []
            sleep(0.01)
        print("AS7341: Configuration {} done, data available to read.").format(part_num)

        # read data from all channels
        data = self.read_all_channels()
        #print(data)

        # disable bit for measurements
        self.sm_enabled(False)
        sleep(0.01)

        return data

    def power_on(self):
        ''' Set Power On bit on the chip (LSB), leave the rest unchanged '''
        value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))
        value = value & 0xfe
        value = value | 0x01
        #print("Write: " + bin(value))
        self._bus.write_byte_data(LIGHT_ADDR, 0x80, value)

    def set_atime(self, value):
        ''' Set ATIME variable (for integration time) to value specified in constants '''
        self._bus.write_byte_data(LIGHT_ADDR, 0x81, value)

    def set_astep(self, value1, value2):
        ''' Set ASTEP registers (low and high byte) (for integration time) to values specified in constants '''
        self._bus.write_byte_data(LIGHT_ADDR, 0xca, value1)   # lower byte
        self._bus.write_byte_data(LIGHT_ADDR, 0xcb, value2)   # higher byte

    def set_gain(self, value):
        ''' Set spectral gain for measurements '''
        self._bus.write_byte_data(LIGHT_ADDR, 0xaa, value)

    def sm_enabled(self, is_enabled):
        ''' Enable or disable spectral measurement (reading data from sensors), leave the rest unchanged '''
        value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))
        w_value = value & 0xfd
        if is_enabled:
            w_value = w_value | 0x02
        else:
            w_value = value & 0xfd
        #print("Write: " + bin(w_value))
        self._bus.write_byte_data(LIGHT_ADDR, 0x80, w_value)
        #value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))

    def write_smux_config(self):
        ''' Write smux configuration from ram to set smux chain '''
        self._bus.write_byte_data(LIGHT_ADDR, 0xaf, 0x10)

    def start_smux_command(self):
        ''' Starts smux (by enabling smux_en bit), leaves the rest unchanged, note that smux needs to be configured with write_smux_config before'''
        value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))
        value = value & 0xef
        value = value | 0x10
        #print("Write - enable smuxen bit: " + bin(value))
        self._bus.write_byte_data(LIGHT_ADDR, 0x80, value)
        #value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))

    def get_smux_status(self):
        ''' read smux enable bit, which gets cleared when smux operation has finished '''
        value = self._bus.read_byte_data(LIGHT_ADDR, 0x80)
        #print("Read: " + bin(value))
        if (value & 0x10) == 0x10:
            return True
        else:
            return False

    def f1_f4_clear_nir(self):
        ''' Configuration 0 - map photo diodes F1, F2, F3, F4, Clear and NIR to ADCs using smux, configuration from manual '''
        self._bus.write_byte_data(LIGHT_ADDR, 0x00, 0x30) # F3 left set to ADC2
        self._bus.write_byte_data(LIGHT_ADDR, 0x01, 0x01) # F1 left set to ADC0
        self._bus.write_byte_data(LIGHT_ADDR, 0x02, 0x00) # Reserved or disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x03, 0x00) # F8 left disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x04, 0x00) # F6 left disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x05, 0x42) # F4 left connected to ADC3/f2 left connected to ADC1
        self._bus.write_byte_data(LIGHT_ADDR, 0x06, 0x00) # F5 left disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x07, 0x00) # F7 left disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x08, 0x50) # CLEAR connected to ADC4
        self._bus.write_byte_data(LIGHT_ADDR, 0x09, 0x00) # F5 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0a, 0x00) # F7 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0b, 0x00) # Reserved or disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0c, 0x20) # F2 right connected to ADC1
        self._bus.write_byte_data(LIGHT_ADDR, 0x0d, 0x04) # F4 right connected to ADC3
        self._bus.write_byte_data(LIGHT_ADDR, 0x0e, 0x00) # F6/F7 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0f, 0x30) # F3 right connected to AD2
        self._bus.write_byte_data(LIGHT_ADDR, 0x10, 0x01) # F1 right connected to AD0
        self._bus.write_byte_data(LIGHT_ADDR, 0x11, 0x50) # CLEAR right connected to AD4
        self._bus.write_byte_data(LIGHT_ADDR, 0x12, 0x00) # Reserved or disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x13, 0x06) # NIR connected to ADC5

    def f5_f8_clear_nir(self):
        '''Configuration 1 - map photo diodes F5, F6, F7, F8, Clear and NIR to ADCs using smux, configuration from manual '''
        self._bus.write_byte_data(LIGHT_ADDR, 0x00, 0x00)  # F3 left disable
        self._bus.write_byte_data(LIGHT_ADDR, 0x01, 0x00)  # F1 left disable
        self._bus.write_byte_data(LIGHT_ADDR, 0x02, 0x00)  # reserved/disable
        self._bus.write_byte_data(LIGHT_ADDR, 0x03, 0x40)  # F8 left connected to ADC3
        self._bus.write_byte_data(LIGHT_ADDR, 0x04, 0x02)  # F6 left connected to ADC1
        self._bus.write_byte_data(LIGHT_ADDR, 0x05, 0x00)  # F4/ F2 disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x06, 0x10)  # F5 left connected to ADC0
        self._bus.write_byte_data(LIGHT_ADDR, 0x07, 0x03)  # F7 left connected to ADC2
        self._bus.write_byte_data(LIGHT_ADDR, 0x08, 0x50)  # CLEAR Connected to ADC4
        self._bus.write_byte_data(LIGHT_ADDR, 0x09, 0x10)  # F5 right connected to ADC0
        self._bus.write_byte_data(LIGHT_ADDR, 0x0A, 0x03)  # F7 right connected to ADC2
        self._bus.write_byte_data(LIGHT_ADDR, 0x0B, 0x00)  # Reserved or disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0C, 0x00)  # F2 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0D, 0x00)  # F4 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x0E, 0x24)  # F7 connected to ADC2/ F6 connected to ADC1
        self._bus.write_byte_data(LIGHT_ADDR, 0x0F, 0x00)  # F3 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x10, 0x00)  # F1 right disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x11, 0x50)  # CLEAR right connected to AD4
        self._bus.write_byte_data(LIGHT_ADDR, 0x12, 0x00)  # Reserved or disabled
        self._bus.write_byte_data(LIGHT_ADDR, 0x13, 0x06)  # NIR connected to ADC5

    def is_data_ready(self):
        '''  check if the spectral measurement has been completed '''
        value = self._bus.read_byte_data(LIGHT_ADDR, 0xa3)
        #print("Read: " + bin(value))
        if (value & 0x40) == 0x40:
            return True
        else:
            return False

    def read_all_channels(self):
        ''' read sensor voltages from all 6 configured channels, returns list '''
        data = []
        cur_adr = 0x95
        for i in range (0, self.AS_CHANNEL_COUNT):
            # read low and high bytes from channel
            low_byte = self._bus.read_byte_data(LIGHT_ADDR, cur_adr)
            #high_byte = self._bus.read_byte_data(LIGHT_ADDR, cur_adr+1)
            high_byte = self._bus.read_byte(LIGHT_ADDR)
            #print(str(high_byte) + " " + str(low_byte))

            # increment current address
            cur_adr += 2

            # merge them into one number
            result = high_byte << 8
            result += low_byte

            # save to list
            data.append(result)
        return data

    def power_off(self):
        ''' Put sensor to sleep when measurement has been completed '''
        self._bus.write_byte_data(LIGHT_ADDR, 0x80, 0x00)

'''
# DEBUG - testing
test = AS7341()
test.init()
data1 = test.get_data(0)
data2 = test.get_data(1)
print(data1)
print(data2)
test.power_off()
'''

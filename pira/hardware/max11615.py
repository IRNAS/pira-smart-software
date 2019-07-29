'''
Hardware class to get voltages from ADC - MAX11615EEE+ channels
Doc: MAX11612-MAX11617.pdf
'''
import smbus
from time import sleep

# I2C init infos
I2C_CHANNEL = 1      # selected i2c channel on rpi
NDVI_ADDR = 0x33     # NDVI/PIR sensor address

# conversion factors
ADC_REF_V = 3.3                 # V
ADC_RESOLUTION = 4095           # 12 bit -> (2^12)-1
ADC_FACTOR = 2                  # multiplier
ADC_CORRECTION_FACTOR = 0.01    # 1 %

class MAX11615(object):

    def __init__(self):
        ''' Initialize i2c bus '''
        self.ADC_CHANNEL_COUNT = 8  # number of sensor channels (2 sensors, 4 each)
        try:
            self._bus = smbus.SMBus(I2C_CHANNEL)
        except:
            print("Bus on channel {} is not available.").format(I2C_CHANNEL)
            print("Available busses are listed as /dev/i2c*")
            self._bus = None

    def init(self):
        ''' Initialize ADC on specified i2c address '''
        if self._bus is None:
            return False

    	try:
            # prepare bits into init byte
            analog_ref = 0 + 2 + 0  # analog ref: (external) + (reference input) + (internal reference always off)
            v_ref = (analog_ref << 4) & 0xf0    # shift analog to their place
            v_ref |= 2          # do not reset the setup register
            v_ref |= 0x80       # bit 7 to 1 (setup byte)
            #print(bin(v_ref))

            # send command
            self._bus.write_byte(NDVI_ADDR, v_ref)
            # wait for setup to complete
            sleep(0.02)
            return True

        except Exception as e:
            #print("ERROR - MAX11616: init has failed - {}".format(e))
            print("ERROR - MAX11616: initializaton has failed.")
            return False

    def config(self, channel):
        ''' Returns config byte for ADC to read only the specified channel '''
        # prepare bits into config byte
        config = 0x60    # scan mode set to single channel
        config |= 1      # single ended mode
        conf_byte = ((channel<<1) & 0x0e) | config  # desired channel
        #print(bin(conf_byte))
        return conf_byte

    def read_channel(self, channel):
        ''' Read one channel, returns received data converted to a number '''
        if channel < 0 or channel >= self.ADC_CHANNEL_COUNT:
            print("ERROR - MAX11616: Nonexisting channel selected!")
            return -1
        
        # configure adc to read desired channel
        config_data = self.config(channel)

        # read 2 bytes into list
        data = self._bus.read_i2c_block_data(NDVI_ADDR, config_data, 2)
        #print(data)

        # read bytes from list and prepare them
        first_byte = data[0] ^ 240  # set 4 msb to 0
        second_byte = data[1]

        # merge them into one number
        result = first_byte << 8
        result += second_byte

        return result

    def convert(self, input):
        ''' Convert ADC value to actual sensor voltage, returns in mV'''
        converted = (ADC_REF_V / ADC_RESOLUTION) * input
        converted *= ADC_FACTOR
        converted *= 1.0 + ADC_CORRECTION_FACTOR
        converted *= 1000  # convert V to mV
        return converted

'''
# DEBUG - testing
test = MAX11615()
test.init()
for i in range(ADC_CHANNEL_COUNT):
    res = test.read_channel(i)
    conv = test.convert(res)
    print("Channel {} - res: {} - conv: {}").format(i, res, conv)
    sleep(0.1)
'''
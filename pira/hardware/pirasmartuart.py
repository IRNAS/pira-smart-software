import time
import pigpio
import serial
import datetime
import struct
from binascii import unhexlify

class PIRASMARTUART(object):
    """PIRASMARTUART driver."""

    # Last measured values that can be accessed by other modules.
    pira_time = None
    pira_voltage = None
    pira_on_timer = None

    def __init__(self, portId):

        self.ser = None
        self.portId = portId

        try:

            self.ser = serial.Serial(self.portId, baudrate=115200, stopbits=1, parity="N",  timeout=2)

        except (Exception):
            raise pirasmartuartException

    def read(self, timeout=5, preamble="t:"):
        """Read value from pira smart via uart.

        :param timeout: Timeout
        :return: Value

        t:<uint32_t> time - seconds in epoch format
        o:<uint32_t> overwiev - time left until next sleep
        b:<uint32_t> battery - level in ADC units
        p:<uint32_t> power - safety on period
        s:<uint32_t> sleep - safety off period
        r:<uint32_t> reboot - reboot period duration
        w:<uint32_t> wakeup - period for next wakeup
        a:<uint32_t> active - Pi status pin value
        c:<uint32_t> command - not yet implemented
        """

        start = time.time()
        #reset values
        self.pira_time = None # t
        self.pira_on_timer_set = None # o
        self.pira_voltage = None # b
        self.pira_on_timer_get = None # p
        self.pira_sleep = None # s
        self.pira_reboot = None # r
        self.pira_next_wakeup_get = None # w
        self.pira_rpi_gpio = None # a
        
        read_timeout = 0    # handles when pira ble is not connected

        try:
            self.ser.flushInput()
        except:
            print("WARNING: Pira input buffer flush failed.")

        while (self.pira_time == None) or \
                (self.pira_on_timer_set == None) or \
                (self.pira_voltage == None) or \
                (self.pira_on_timer_get == None) or \
                (self.pira_sleep == None) or \
                (self.pira_reboot == None) or \
                (self.pira_next_wakeup_get == None) or \
                (self.pira_rpi_gpio == None) and not \
                (time.time() - start < timeout):

            try:
                x = ""
                x = self.ser.readline()
                #print "Preamble: " + x[0:2] + "Data: " + x[2:-1].encode('hex') + " Line: " + str(x.startswith(preamble))
                #' '.join(map(lambda x:x.encode('hex'),x))
                #struct.unpack('<h', unhexlify(s1))[0]
                value = float(struct.unpack('>L', x[2:6])[0])
            except:
                print("ERROR: read from Pira BLE the following: " + str(x[2:6]))
                time.sleep(1)
                read_timeout += 1
                if read_timeout >= 3:   # after failing 3 or more times stop Pira BLE reading
                    return False

            if x.startswith(str('t:')):
                self.pira_time = float(value)
                #print "Pira time: " + str(self.pira_time)
            elif x.startswith(str('o:')):
                self.pira_on_timer_set = float(value)
                #print "Pira overwiev: " + str(self.pira_on_timer_set)
            elif x.startswith(str('b:')):
                self.pira_voltage = float(value)*0.0164
                #print "Pira battery: " + str(self.pira_voltage)
            elif x.startswith(str('p:')):
                self.pira_on_timer_get = float(value)
                #print "Pira get safety on period: " + str(self.pira_on_timer_get)
            elif x.startswith(str('s:')):
                self.pira_sleep = float(value)
                #print "Pira get safety off period: " + str(self.pira_sleep)
            elif x.startswith(str('r:')):
                self.pira_reboot = float(value)
                #print "Pira get reboot period: " + str(self.pira_reboot)
            elif x.startswith(str('w:')):
                self.pira_next_wakeup_get = float(value)
                #print "Pira next wakeup get : " + str(self.pira_next_wakeup_get)
            elif x.startswith(str('a:')):
                self.pira_rpi_gpio = float(value)
                print "Pira reports Pi status pin value: " + str(self.pira_rpi_gpio)

        return True

    """
        t:<uint32_t> time - seconds in epoch format
        p:<uint32_t> power - safety on period
        s:<uint32_t> sleep - safety off period
        r:<uint32_t> reboot - reboot period duration
        w:<uint32_t> wakeup - period for next wakeup
        c:<uint32_t> command - TODO
    """

    def set_time(self, new_time_epoch):
        """Writes new time to pira"""
        data = "t:" + struct.pack('>L', int(new_time_epoch))
        self.ser.write(data+'\n')

    def set_on_time(self, time_seconds):
        """Writes new on period time to pira"""
        print "New on period time: " + str(time_seconds)
        data = "p:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_off_time(self, time_seconds):
        """Writes new off period time to pira"""
        print "New off period time: " + str(time_seconds)
        data = "s:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_reboot_time(self, time_seconds):
        """Writes new reboot time to pira"""
        data = "r:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_wakeup_time(self, time_seconds):
        """Writes new wakeup time to pira"""
        data = "w:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def send_command(self, command):    # TO DO
        """Sends command to pira"""
        data = "c:" + struct.pack('>L', int(command))
        self.ser.write(data+'\n')

    def close(self):
        """Close device."""
        pass

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

        t:<uint32_t> Time in epoch format, seconds
        o:<uint32_t> General status value -> time left until next sleep - 'o' stands for overview since 'p' and 's' are occupied
        b:<uint32_t> Battery level in ADC units
        p:<uint32_t> On time value
        s:<uint32_t> Off time value
        r:<uint32_t> Reboot period duration
        w:<uint32_t> Next wakeup period duration
        a:<uint32_t> RPi status pin value
        Command is not implemented yet
        c:<uint32_t>
        """

        start = time.time()
        #reset values
        self.pira_time = None
        self.pira_voltage = None
        self.pira_on_timer_get = None
        self.pira_on_timer_set = None
        self.pira_rpi_gpio = None
        self.pira_next_wakeup_get = None

        self.ser.flushInput()
        while (self.pira_time == None) or \
                (self.pira_voltage == None) or \
                (self.pira_rpi_gpio == None) or \
                (self.pira_on_timer_set == None) or \
                (self.pira_next_wakeup_get == None) or \
                (self.pira_on_timer_get == None) and not \
                (time.time() - start < timeout):

            x=self.ser.readline()
            #print "Preamble: " + x[0:2] + "Data: " + x[2:-1].encode('hex') + " Line: " + str(x.startswith(preamble))
            #' '.join(map(lambda x:x.encode('hex'),x))
            #struct.unpack('<h', unhexlify(s1))[0]
            value = float(struct.unpack('>L', x[2:6])[0])
            if x.startswith(str('t:')):
                self.pira_time = float(value)
                print "Pira time: " + str(self.pira_time)
            elif x.startswith(str('b:')):
                self.pira_voltage = float(value)*0.0164
                print "Pira voltage: " + str(self.pira_voltage)
            elif x.startswith(str('o:')):
                self.pira_on_timer_set = float(value)
                print "Pira on timer set: " + str(self.pira_on_timer_set)
            elif x.startswith(str('p:')):
                self.pira_on_timer_get = float(value)
                print "Pira on timer get: " + str(self.pira_on_timer_get)
            elif x.startswith(str('a:')):
                self.pira_rpi_gpio = float(value)
                print "Pira gpio : " + str(self.pira_rpi_gpio)
            elif x.startswith(str('w:')):
                self.pira_next_wakeup_get = float(value)
                print "Pira next wakeup get : " + str(self.pira_next_wakeup_get)

        return

    """
    t:<uint32_t> - time in epoch format, set date/time
    p:<uint32_t>- configure ON time (safeguard)
    s:<uint32_t> - configure OFF time (safeguard)
    r:<uint32_t> - reboot wait period
    w:<uint32_t> - period for next wakeup
    c:<uint32_t> - other commands - implemented, but NOT USED currently
    """

    def set_time(self, new_time_epoch):
        """Writes new time to pira"""
        data = "t:" + struct.pack('>L', int(new_time_epoch))
        self.ser.write(data+'\n')

    def set_off_time(self, time_seconds):
        """Writes new off time to pira"""
        data = "s:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_on_time(self, time_seconds):
        """Writes new on time to pira"""
        data = "p:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_reboot_time(self, time_seconds):
        """Writes new reboot time to pira"""
        data = "r:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')

    def set_wakeup_time(self, time_seconds):
        """Writes new reboot time to pira"""
        data = "w:" + struct.pack('>L', int(time_seconds))
        self.ser.write(data+'\n')



    def close(self):
        """Close device."""
        pass

import time
import pigpio
import serial
import datetime

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
        """
        start = time.time()
        #reset values
        self.pira_time = None
        self.pira_voltage = None
        self.pira_on_timer = None

        self.ser.flushInput()
        while (self.pira_time == None) or \
                (self.pira_voltage == None) or \
                (self.pira_on_timer == None) and not \
                (time.time() - start < timeout):

            x=self.ser.readline()
            #print "Preamble: " + preamble + "Data: " + x + "Line: " + str(x.startswith(preamble))
            if x.startswith(str('t:')):
                value = x[2:-1]
                self.pira_time = float(value)
                #print "Pira time: " + str(self.pira_time)
            elif x.startswith(str('b:')):
                value = x[2:-1]
                self.pira_voltage = float(value)*0.0164
                #print "Pira voltage: " + str(self.pira_voltage)
            elif x.startswith(str('p:')):
                value = x[2:-1]
                self.pira_on_timer = float(value)
                #print "Pira on timer: " + str(self.pira_on_timer)

        return

    def set_time(self, new_time_epoch):
        """Writes new time to pira"""
        data = "t:" + new_time_epoch
        #ser.write(data+'\n')

    def set_off_time(self, time_seconds):
        """Writes new off time to pira"""
        data = "o:" + time_seconds
        #ser.write(data+'\n')

    def set_on_time(self, time_seconds):
        """Writes new on time to pira"""
        data = "p:" + time_seconds
        #ser.write(data+'\n')

    def set_reboot_time(self, time_seconds):
        """Writes new reboot time to pira"""
        data = "r:" + time_seconds
        #ser.write(data+'\n')


    def close(self):
        """Close device."""
        pass

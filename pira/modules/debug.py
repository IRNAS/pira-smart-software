"""
debug.py

It is a module that prints various debug information from Pira, RPi and other modules

"""

from __future__ import print_function

class Module(object):
    def __init__(self, boot):
        self._boot = boot

    def process(self, modules):
        print('=========================DEBUG=========================')
        if self._boot.pira_ok:     # Report Pira BLE values
            print('Pira     : t - rtc time           : {}'.format(self._boot.get_time()))
            print('Pira     : o - overview value     : {} s'.format(self._boot.get_pira_on_timer_set()))
            print('Pira     : b - battery level      : ' + str(self._boot.get_voltage()) + ' V')
            print('Pira     : p - safety on period   : {} s'.format(self._boot.get_pira_on_timer()))
            print('Pira     : s - safety off period  : {} s'.format(self._boot.get_pira_sleep_timer()))
            print('Pira     : r - reboot period      : {} s'.format(self._boot.get_pira_reboot_timer()))
            print('Pira     : w - next wakeup        : {} s'.format(self._boot.get_pira_wakeup_timer()))
        else:
            print('Pira     : Not connected')
        
        #Report Pi values
        print('Charging : {}'.format(self._boot.is_charging))
        print('Debug    : {}'.format(self._boot.is_debug_enabled))
        #print('Temp.    : {}'.format(self._boot.rtc.temperature))

        # Report distance measured by ultrasonic module if enabled.
        if 'pira.modules.ultrasonic' in modules:
            print('Distance : {}'.format(modules['pira.modules.ultrasonic'].distance))

        print('=======================================================')

    def shutdown(self, modules):
        """Shutdown module"""
        pass

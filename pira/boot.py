from __future__ import print_function

import collections
import importlib
import os
import subprocess
import time
import datetime
import traceback
import json
import urllib

import RPi.GPIO as gpio
import pigpio

# Optional Resin support.
try:
    print("Importing resin...")
    from resin import Resin
    RESIN_ENABLED = True
except ImportError:
    RESIN_ENABLED = False
    print("Importing resin failed.")

from .hardware import devices, pirasmartuart
from .state import State
from .log import Log
from .const import LOG_SYSTEM, LOG_DEVICE_VOLTAGE, LOG_DEVICE_TEMPERATURE


class Boot(object):

    # Modules that should be loaded.
    enabled_modules = [
        # Device management modules
        #'pira.modules.scheduler',

        # Sensor modules.
        # 'pira.modules.ultrasonic',
        #'pira.modules.camera',
        'pira.modules.can',

        # Reporting modules should come after all sensor modules, so they can get
        # the latest values.
        # 'pira.modules.lora',
        # 'pira.modules.rockblock',
        # 'pira.modules.nodewatcher',
        'pira.modules.debug',
        #'pira.modules.webserver',
        'pira.modules.m2x_plat'
        #'pira.modules.azure_images'
    ]

    def __init__(self):
        self.shutdown = False
        self.shutdown_hold = None
        self._charging_status = collections.deque(maxlen=4)

    def setup_gpio(self):
        """Initialize GPIO."""
        print("Initializing GPIO...")
        while True:
            try:
                self.pigpio = pigpio.pi()
                self.pigpio.get_pigpio_version()
                break
            except:
                print("Failed to initialize connection to pigpiod. Retrying...")
                time.sleep(1)

        self.pigpio.set_mode(devices.GPIO_PIRA_STATUS_PIN, pigpio.OUTPUT)
        self.pigpio.write(devices.GPIO_PIRA_STATUS_PIN, gpio.HIGH)

        # Power switch output for external loads
        self.pigpio.set_mode(devices.GPIO_SOFT_POWER_PIN, pigpio.OUTPUT)
        self.pigpio.write(devices.GPIO_SOFT_POWER_PIN, gpio.LOW)

        #self.pigpio.set_mode(devices.GPIO_LORA_DIO_0_PIN, pigpio.INPUT)
        #self.pigpio.set_mode(devices.GPIO_LORA_DIO_1_PIN, pigpio.INPUT)
        #self.pigpio.set_mode(devices.GPIO_LORA_DIO_2_PIN, pigpio.INPUT)

        #self.pigpio.set_mode(devices.GPIO_ROCKBLOCK_POWER_PIN, pigpio.OUTPUT)

    def setup_devices(self):
        """Initialize device drivers."""
        print("Initializing device drivers...")
        self.pirasmart = pirasmartuart.PIRASMARTUART(devices.PIRASMART_UART)

    def setup_wifi(self):
        """Setup wifi."""
        if not self.is_wifi_enabled:
            print("Not starting wifi as it is disabled.")
            return

        # Enable wifi.
        print("Enabling wifi.")
        try:
            if RESIN_ENABLED:
                self._wifi = subprocess.Popen(["./scripts/wifi-connect-start.sh"])
                pass
            else:
                subprocess.call(["./scripts/start-networking.sh"])
        except:
            print("ERROR: Failed to start wifi-connect.")

    def boot(self):
        """Perform boot sequence."""
        print("Performing boot sequence.")

        if os.environ.get('BOOT_DISABLE', '0') == '1':
            print("Boot has been disabled (BOOT_DISABLE=1). Not booting further.")
            while True:
                time.sleep(1)

        self.setup_gpio()
        self.setup_devices()
        self.setup_wifi()

        self.state = State()
        self.log = Log()
        self.log.insert(LOG_SYSTEM, 'boot')

        self._update_charging()

        # Initialize Resin
        self._resin = Resin()

        # TODO: Monitor status pin from BT
        #self.pigpio.callback(
        #    devices.GPIO_TIMER_STATUS_PIN,
        #    pigpio.FALLING_EDGE,
        #    self.clear_timer
        #)
        self.process()

    def parse_environ(self, env):
        """Parse environment variable"""
        try:
            value = float(env)
            if (value <= 0.0 or value >= 4294967295.0):
                return None
            else:
                return value
        except:
            return None

    def process(self):
        
        self.log.insert(LOG_SYSTEM, 'module_init')

        #Determine clock status and perform sync
        #https://forums.resin.io/t/check-ntp-synchronization-status-from-python/1262
        # Simplest logic is to take the latest of the system and RTC time
        # This assumes the clock that is behind is always wrong
        # Get latest values from pira smart
        
        self.pira_ok = self.pirasmart.read()
        if self.pira_ok:
            rtc_time = self.get_time()
        else:
            rtc_time = datetime.datetime.now()
        
        system_time = datetime.datetime.now()

        if rtc_time > system_time:
            #write RTC to system
            print("Writing RTC to system time")
            args = ['date', '-s', rtc_time.strftime("%Y-%m-%d %H:%M:%S")]
            subprocess.Popen(args)
            #note if ntp is running it will override this, meaning there is network time
        elif rtc_time < system_time:
            #write system_time to rtc
            print("Writing system time to RTC")
            epoch_string = datetime.datetime.now().strftime('%s')
            self.pirasmart.set_time(epoch_string)

        else:
            #if equal no need to do anything
            pass

        if self.pira_ok:     # If defined set new Pira BLE values
            pira_on_time = self.parse_environ(os.environ.get('PIRA_POWER', None))
            pira_off_time = self.parse_environ(os.environ.get('PIRA_SLEEP', None))
            pira_reboot_time = self.parse_environ(os.environ.get('PIRA_REBOOT', None))
            pira_wakeup_time = self.parse_environ(os.environ.get('PIRA_WAKEUP', None))
        
            if (pira_on_time is not None):
                print("PIRA BLE: Setting new safety on (p) value.")
                self.pirasmart.set_on_time(pira_on_time)
                time.sleep(0.1)
            if (pira_off_time is not None):
                print("PIRA BLE: Setting new safety off (s) value.")
                self.pirasmart.set_off_time(pira_off_time)
                time.sleep(0.1)
            if (pira_reboot_time is not None):
                print("PIRA BLE: Setting new reboot (r) value.")
                self.pirasmart.set_reboot_time(pira_reboot_time)
                time.sleep(0.1)
            if (pira_wakeup_time is not None):
                print("PIRA BLE: Setting new wakeup (w) value.")
                self.pirasmart.set_wakeup_time(pira_wakeup_time)
                time.sleep(0.1)

        # Override module list if configured.
        override_modules = os.environ.get('MODULES', None)
        if override_modules:
            print("Only loading configured modules.")
            self.enabled_modules = override_modules.strip().split(',')

        # Initialize modules.
        print("Initializing modules...")
        self.modules = collections.OrderedDict()
        for module_name in self.enabled_modules:
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                print("ImportError  * {} [IMPORT FAILED]".format(module_name))
                traceback.print_exc()
                continue
            except ValueError:
                print("ValueError  * {} [IMPORT FAILED]".format(module_name))
                continue

            print("  * {}".format(module.__name__))

            try:
                instance = module.Module(self)
                self.modules[module.__name__] = instance
            except:
                print("Error while initializing a module.")
                traceback.print_exc()

        self.log.insert(LOG_SYSTEM, 'main_loop')


        # Enter main loop.
        print("Starting processing loop.")
        while True:

            # Get latest values from pira smart
            self.pira_ok = self.pirasmart.read()
            # Shutdown hold is reset in every loop
            self.shutdown_hold = None

            # TODO:Store some general log entries.
            self.log.insert(LOG_DEVICE_VOLTAGE, self.get_voltage())
            #self.log.insert(LOG_DEVICE_TEMPERATURE, self.rtc.temperature)

            # Process all modules.
            for name, module in self.modules.items():
                try:
                    module.process(self.modules)
                except:
                    print("Error while running processing in module '{}'.".format(name))
                    traceback.print_exc()

            # If pira is connected, check if battery voltage is below threshold and shutdown
            if self.pira_ok:
                if ((self.get_voltage() is not None) and (self.get_voltage() <= float(os.environ.get('SHUTDOWN_VOLTAGE', '2.6')))):
                    print("Voltage is under the threshold, need to shutdown.")
                    self.shutdown = True

            # Save state.
            try:
                self.state.save()
            except:
                print("Error while saving state.")
                traceback.print_exc()
            
            # Perform shutdown when requested. This will either request the Resin
            # supervisor to shut down and block forever or the shutdown request will
            # be ignored and we will continue processing.
            if self.shutdown:
                self.shutdown = False
                self._perform_shutdown()
            
            time.sleep(float(os.environ.get('LOOP_DELAY', "60")))

    def _update_charging(self):
        """Get charging status."""
        # TODO
        self._charging_status.append(False)

    def get_voltage(self):  # b variable
        """Get voltage """
        voltage = self.pirasmart.pira_voltage
        return voltage

    def get_temperature(self):
        """Get temeprature """
        temperature = None
        return temperature

    def get_time(self): # t variable
        """Get time """
        t_utc = datetime.datetime.utcfromtimestamp(self.pirasmart.pira_time)
        return t_utc

    def get_pira_on_timer(self):    # p variable
        """Get pira on timer """
        timer_pira = self.pirasmart.pira_on_timer_get
        return timer_pira

    def get_pira_on_timer_set(self):    # o variable
        """Get pira overwiev - status value """
        timer_pira = self.pirasmart.pira_on_timer_set
        return timer_pira

    def get_pira_sleep_timer(self): # s variable
        """Get pira sleep timer"""
        sleep_timer = self.pirasmart.pira_sleep
        return sleep_timer

    def get_pira_reboot_timer(self):    # r variable
        """Get pira reboot period duration"""
        reboot_timer = self.pirasmart.pira_reboot
        return reboot_timer
    
    def get_pira_wakeup_timer(self):    # w variable
        """Get pira next scheduled wakeup  """
        wakeup_timer = self.pirasmart.pira_next_wakeup_get
        return wakeup_timer

    @property
    def is_charging(self):
        return any(self._charging_status)

    @property
    def is_wifi_enabled(self):
        wifi_mode = os.environ.get('WIFI_ENABLE_MODE', 'charging')

        if wifi_mode == 'charging':
            return self.is_charging == 1
        elif wifi_mode == 'on':
            return True
        elif wifi_mode == 'debug':
            return self.is_debug_enabled == 1
        elif wifi_mode == 'off':
            return False

    @property
    def is_debug_enabled(self):
        debug_mode = os.environ.get('DEBUG_ENABLE_MODE', 'none')

        if debug_mode.startswith('gpio:'):
            # Based on GPIO.
            try:
                _, pin = debug_mode.split(':')
                pin = int(pin)
            except ValueError:
                print("Invalid GPIO pin specified for debug.")
                return True

            # Read from given GPIO pin.
            self.pigpio.set_mode(pin, pigpio.INPUT)
            return self.pigpio.read(pin) == gpio.LOW

    def shutdown(self):
        """Request shutdown."""
        print("Module has requested shutdown.")
        self.shutdown = True

    def _perform_shutdown(self):
        """Perform shutdown."""
        # check if device is maybe not ready to shutdown (E.g. installing updates)
        device_status = self._resin.models.supervisor.get_device_state()
        #print (device_status)
        if device_status['status'] != 'Idle' or device_status['update_pending']:
            print ("Device not ready to shutdown...")
            return

        sleep_mode = os.environ.get('SLEEP_ENABLE_MODE', 'sleep')

        if sleep_mode == 'charging' and self.is_charging == 1:
            print("Not shutting down: Charging.")
            return
        elif sleep_mode == 'off':
            print("Not shutting down: Sleep off.")
            return
        elif sleep_mode == 'sleep':
            pass

        if sleep_mode == 'debug' and self.is_debug_enabled == 1:
            print("Shutting down even during debug.")
            pass
        elif self.is_debug_enabled == 1:
            print("Not shutting down: Debug on.")
            return

        if not self.shutdown_hold == None:
            print("Not shutting down: On hold due to: "+self.shutdown_hold)
            return

        self.log.insert(LOG_SYSTEM, 'shutdown')

        print("Requesting all modules to shut down.")
        for name, module in self.modules.items():
            try:
                module.shutdown(self.modules)
            except:
                print("Error while running shutdown in module '{}'.".format(name))
                traceback.print_exc()

        # Shut down devices.
        try:
            if self.is_wifi_enabled and self._wifi:
                self._wifi.kill()
        except:
            print("Error while shutting down devices.")
            traceback.print_exc()

        # Save state.
        try:
            self.state.save()
        except:
            print("Error while saving state.")
            traceback.print_exc()

        self.log.insert(LOG_SYSTEM, 'halt')
        self.log.close()

        # Force filesystem sync.
        try:
            subprocess.call('sync')
        except:
            print("Error while forcing filesystem sync.")
            traceback.print_exc()

        # TODO: handle error curl: (7) Failed to connect to 127.0.0.1 port 48484: Connection refused RESIN ERROR

        # Turn off the pira status pin then shutdown
        print('Shutting down as scheduled with shutdown.')
        self.pigpio.write(devices.GPIO_PIRA_STATUS_PIN, gpio.LOW)
        if RESIN_ENABLED:
            subprocess.call(["/usr/src/app/scripts/resin-shutdown.sh"])
        else:
            subprocess.Popen(["/sbin/shutdown", "--poweroff", "now"])
        
        # Block.
        while True:
            time.sleep(1)


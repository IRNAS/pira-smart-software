"""
scheduler.py

It is a module that schedulers RPi turning on and off

ENV VARS:
    - SCHEDULE_MONTHLY
    - POWER_THRESHOLD_HALF
    - POWER_THRESHOLD_QUART
    - SCHEDULE_START
    - SCHEDULE_END
    - SCHEDULE_T_ON
    - SCHEDULE_T_OFF
    - SCHEDULE_MONTHx_START
    - SCHEDULE_MONTHx_END
    - SCHEDULE_MONTHx_T_ON
    - SCHEDULE_MONTHx_T_OFF

"""

from __future__ import print_function

import datetime
import os

try:
    import astral
    HAVE_ASTRAL = True
except ImportError:
    HAVE_ASTRAL = False


class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._ready = False

        if not self._boot.pira_ok:     # exit module if pira is not connected
            print("Scheduler: ERROR - Pira is not connected. Exiting...")
            return

        # Initialize schedule.
        if os.environ.get('SCHEDULE_MONTHLY', '0') == '1':
            # Month-dependent schedule.
            month = datetime.date.today().month
            schedule_start = self._parse_time(os.environ.get('SCHEDULE_MONTH{}_START'.format(month), '08:00'))
            schedule_end = self._parse_time(os.environ.get('SCHEDULE_MONTH{}_END'.format(month), '18:00'))
            schedule_t_off = self._parse_duration(os.environ.get('SCHEDULE_MONTH{}_T_OFF'.format(month), '35'))
            schedule_t_on = self._parse_duration(os.environ.get('SCHEDULE_MONTH{}_T_ON'.format(month), '15'))
        else:
            # Static schedule.
            schedule_start = self._parse_time(os.environ.get('SCHEDULE_START', '00:01'))
            schedule_end = self._parse_time(os.environ.get('SCHEDULE_END', '23:59'))
            schedule_t_off = self._parse_duration(os.environ.get('SCHEDULE_T_OFF', '1'))  # Time in minutes.
            schedule_t_on = self._parse_duration(os.environ.get('SCHEDULE_T_ON', '1'))  # Time in minutes.

        if not schedule_start or not schedule_end or schedule_t_off is None or schedule_t_on is None:
            print("WARNING: Ignoring malformed schedule specification, using safe values.")
            schedule_start = self._parse_time('00:01')
            schedule_end = self._parse_time('23:59')
            schedule_t_off = self._parse_duration('59')  # Time in minutes.
            schedule_t_on = self._parse_duration('1')  # Time in minutes.

        self._started = datetime.datetime.now()
        self._schedule_start = schedule_start
        self._schedule_end = schedule_end
        self._on_duration = schedule_t_on
        self._off_duration = schedule_t_off
        self._ready = True

        if schedule_t_on.seconds > self._boot.get_pira_on_timer_set():
            print("WARNING: p (safety on period) will shutdown Pi before scheduler on duration expires.")

    def _parse_time(self, time):
        """Parse time string (HH:MM)."""
        if HAVE_ASTRAL:
            try:
                location = astral.Location((
                    'Unknown',
                    'Unknown',
                    float(os.environ['LATITUDE']),
                    float(os.environ['LONGITUDE']),
                    'UTC',
                    0
                ))

                if time == 'sunrise':
                    print("Sunrise at {}.".format(self._parse_time("sunrise")))
                    return location.sunrise().time()
                elif time == 'sunset':
                    print("Sunset at {}".format(self._parse_time("sunset")))
                    return location.sunset().time()
            except (KeyError, ValueError):
                pass

        try:
            hour, minute = time.split(':')
            return datetime.time(hour=int(hour), minute=int(minute), second=0)
        except (ValueError, IndexError):
            return None

    def _parse_duration(self, duration):
        """Parse duration string (in minutes)."""
        try:
            return datetime.timedelta(minutes=int(duration))
        except ValueError:
            return None

    def process(self, modules):
        """Check if we need to shutdown."""
        if not self._ready:
            return

        if not self._boot.pira_ok:     # exit module if pira is not connected
            print("Scheduler: ERROR - Pira is not connected. Exiting...")
            return

        """Shutdown is triggered in two ways:
        1) Pira smart on timer expires, safeguarding if pi crashes or similar
        2) Pi completes the operation and goes to sleep
        """

        remaining_time_on = datetime.datetime.now() - self._started
        print('Scheduler: remaining on time  : {} s'.format(datetime.timedelta.total_seconds(self._on_duration-remaining_time_on)))

        # Check if we have been online too long and shutdown.
        if remaining_time_on >= self._on_duration:
            print("Scheduler: Time to sleep.")
            self._boot.shutdown = True

        # Check pira on timer is about to expire - o variable
        if self._boot.get_pira_on_timer_set() < 30 and not self._boot.get_pira_on_timer_set() == None :
            print("Scheduler: WARNING - Pira safety on timer about to expire.")
            self._boot.shutdown = True
            #here we could reset it as well

    def shutdown(self, modules):
        """Compute next alarm before shutdown."""
        if not self._ready:  
            return

        if not self._boot.pira_ok:     # exit module if pira is not connected
            print("Scheduler: ERROR - Pira is not connected. Exiting...")
            return

        # Checking voltage to configure boot interval
        if self._boot.get_voltage() < float(os.environ.get('POWER_THRESHOLD_QUART', '0')): 
            # Lower voltage then quarter threshold, quadrupling the sleep length
            off_duration = self._off_duration * 4
            print("Low voltage warning, quadrupling sleep duration")
        elif self._boot.get_voltage() < float(os.environ.get('POWER_THRESHOLD_HALF', '0')):
            # Less voltage then half threshold, doubling the sleep length
            off_duration = self._off_duration * 2
            print("Low voltage warning, doubling sleep duration")
        else:
            # Sufficient power, continue as planned
            off_duration = self._off_duration

        current_time = datetime.datetime.now()
        wakeup_time = None

        #print("Schedule start {} end {} current {}.".format(self._schedule_start,self._schedule_end,current_time))

        if self._schedule_end >= self._schedule_start:
            wakeup_time = current_time + off_duration
            #print("END > START: wakeup {}.".format(wakeup_time))
        elif self._schedule_end > self._schedule_start:
            if (current_time.time() >= self._schedule_end) and (current_time.time() < self._schedule_start):
                wakeup_time = current_time + datetime.combine(current_time, self._schedule_start)
                #print("Sleep period: wakeup {}.".format(wakeup_time))
            else:
                wakeup_time = current_time + off_duration
                #print("START > END: wakeup {}.".format(wakeup_time))


        wakeup_in_seconds = datetime.timedelta.total_seconds(wakeup_time - current_time)
        reboot_time = datetime.timedelta(seconds=int(self._boot.get_pira_reboot_timer()))
        display_next_wakeup = wakeup_time + reboot_time

        if wakeup_in_seconds > self._boot.get_pira_sleep_timer():
            print("Warning: Safety off period will expire and wake up Pi before next scheduled wakeup.")
        
        #Displayed value is: wakeup_time + reboot_time
        print("Scheduling next wakeup at {} / in {} seconds.".format((str(display_next_wakeup)[:-7]), wakeup_in_seconds + self._boot.get_pira_reboot_timer()))
        self._boot.pirasmart.set_wakeup_time(wakeup_in_seconds)


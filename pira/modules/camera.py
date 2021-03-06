"""
camera.py

It is a module that takes photos and records video

ENV VARS:
    - CAMERA_RESOLUTION
    - CAMERA_VIDEO_DURATION
    - CAMERA_MIN_LIGHT_LEVEL
    - CAMERA_ROTATE
    - CAMERA_FAIL_SHUTDOWN
    - CAMERA_SNAPSHOT_INTERVAL
    - CAMERA_SNAPSHOT_HOUR
"""

from __future__ import print_function

import datetime
import io
import os
from os import listdir
from os.path import isfile, join

from ..hardware.brightpilib import *
import numpy as np
import array
import picamera
import picamera.array

# Image storage location.
CAMERA_STORAGE_PATH = '/data/camera'


class Module(object):
    def __init__(self, boot):
        self._boot = boot
        self._camera = None
        self._recording_start = None
        self._last_snapshot = None
        self._brightPi = None

        self.resolution = os.environ.get('CAMERA_RESOLUTION', '1280x720')
        self.camera_shutdown = os.environ.get('CAMERA_FAIL_SHUTDOWN', '0')
        self.video_duration = os.environ.get('CAMERA_VIDEO_DURATION', 'off')
        self.snapshot_interval_conf = os.environ.get('CAMERA_SNAPSHOT_INTERVAL', 'off')
        self.snapshot_hour_conf = os.environ.get('CAMERA_SNAPSHOT_HOUR', '12')
        self.camera_rotation_conf = os.environ.get('CAMERA_ROTATE', '0')

        try:
            self.video_duration_min = datetime.timedelta(minutes=int(self.video_duration))
        except ValueError:
            self.video_duration_min = None

        if self.snapshot_interval_conf == 'daily':
            self.snapshot_interval = 'daily'
        elif self.snapshot_interval_conf == 'off':
            self.snapshot_interval = 'off'
        else:
            try:
                self.snapshot_interval = datetime.timedelta(minutes=int(self.snapshot_interval_conf))
            except ValueError:
                self.snapshot_interval = 'off'

        self.light_level = 0.0
        try:
            self.minimum_light_level = float(os.environ.get('CAMERA_MIN_LIGHT_LEVEL', 0.0))
        except ValueError:
            self.minimum_light_level = 0.0

        try:
            self.snapshot_hour = int(self.snapshot_hour_conf)
        except:
            self.snapshot_hour = 12

        try:
            self.camera_rotation = int(self.camera_rotation_conf)
        except:
            self.camera_rotation = 0

        # Ensure storage location exists.
        try:
            os.makedirs(CAMERA_STORAGE_PATH)
        except OSError:
            pass

        now = datetime.datetime.now()

        # Check how much space is left
        info = os.statvfs(CAMERA_STORAGE_PATH)
        free_space = (info.f_frsize * info.f_bavail / (1024.0 * 1024.0 * 1024.0))
        print("Storage free space:", free_space, "GiB")

        # Do not record or take snapshots when charging if so configured
        if self._boot.is_charging and not self.should_sleep_when_charging:
            print("We are charging, not recording.")
            return

        # Create the camera object
        try:
            self._camera = picamera.PiCamera()
            self._camera.resolution = self.resolution
        except picamera.PiCameraError:
            print("ERROR: Failed to initialize camera.")
            # ask the system to shut-down
            if self.camera_fail_shutdown:
                self._boot.shutdown()
                print("Requesting shutdown because of camera initialization fail.")
            return

        # Create the flash object
        try:
            self._brightPi = BrightPi()
        except:
            print("WARNING: Failed to initialize flash.")
            self._brightPi = None

        # Check for free space
        if free_space < 1:
            print("Not enough free space (less than 1 GiB), do not save snapshots or record")
            return
        # check if interval is set to daily -> pass because snapshot will be taken in process loop
        elif self.snapshot_interval != 'daily' and self.snapshot_interval != 'off':
            print("INFO: Snapshot interval set to " + str(self.snapshot_interval) + " minutes.")
            # Store single snapshot only if above threshold, else do not record
            if not self._snapshot():
                # turn off video recording
                self._camera = None
                self.video_duration='off'
                # ask the system to shut-down
                if self.camera_fail_shutdown:
                    self._boot.shutdown()
                    print("Requesting shutdown because of low-light conditions.")
                return

        # Record a video of configured duration or until sleep.
        if self.video_duration == 'off':
            print("Not recording video as it is disabled.")
            return

        # Check if there is enough space to start recording
        print("Storage free space:", free_space, "GiB")
        if free_space < 2:
            print("Not enough free space (less than 2 GiB), skipping video recording")
            self._camera = None
            return

        print("Starting video recording (duration {}).".format(self.video_duration))
        self._camera.start_recording(
            os.path.join(
                CAMERA_STORAGE_PATH,
                'video-{year}-{month:02d}-{day:02d}-{hour:02d}-{minute:02d}-{second:02d}.h264'.format(
                    year=now.year,
                    month=now.month,
                    day=now.day,
                    hour=now.hour,
                    minute=now.minute,
                    second=now.second,
                )
            ),
            format='h264'
        )
        self._recording_start = now

    def process(self, modules):
        # This runs if camera is initialized
        if self._camera:
            now = datetime.datetime.now()

            info = os.statvfs(CAMERA_STORAGE_PATH)
            free_space = (info.f_frsize * info.f_bavail / (1024.0 * 1024.0 * 1024.0))
            stop_recording=False

            # Stop recording if we happen to start charging
            if self._boot.is_charging and not self.should_sleep_when_charging:
                print("We are charging, stop recording.")
                stop_recording=True
            if free_space < 2:
                print("Not enough free space (less than 2 GiB), stop video recording")
                stop_recording=True
            # Check if duration of video is achieved.
            if self.video_duration_min is not None and now - self._recording_start >= self.video_duration_min:
                stop_recording=True
            # Stop recording
            if stop_recording:
                try:
                    self._camera.stop_recording()
                    print("Video recording has stopped after: ",now - self._recording_start)
                except:
                    pass

            # if we need daily snapshot
            if self.snapshot_interval == 'daily':
                # get all raw filenames
                self._local_files = [f for f in listdir(CAMERA_STORAGE_PATH) if isfile(join(CAMERA_STORAGE_PATH, f))]
                # find the newest - local files names are made like this: "snapshot-2019-02-06--11-44-46--0.00-10.000V-0.00C.jpg")
                newest_timestamp = datetime.datetime.strptime("01012019-0100", "%m%d%Y-%H%M")
                for file_name in self._local_files:
                    if 'snapshot' in file_name:
                        s_timestamp = file_name.replace("snapshot-", "")
                        time_index = len(s_timestamp) - s_timestamp.rfind("--")
                        this_timestamp = datetime.datetime.strptime(s_timestamp[:-time_index], "%Y-%m-%d--%H-%M-%S")
                        if this_timestamp > newest_timestamp:
                            newest_timestamp = this_timestamp
                time_now = datetime.datetime.now()
                # if we are in a new day and specified hour to take snapshot is now or in the past -> take snapshot
                if newest_timestamp.day != time_now.day and self.snapshot_hour <= time_now.hour:
                    print("Taking daily snapshot...")
                    self._snapshot()

            # make snapshots if so defined and not recording
            elif self.video_duration == 'off' and self.snapshot_interval is not 'off' and now - self._last_snapshot >= self.snapshot_interval:
                self._snapshot()
            
        return

    def _check_light_conditions(self):
        """Check current light conditions."""
        image = None
        with picamera.array.PiRGBArray(self._camera) as output:
            self._camera.capture(output, format='rgb')
            #image = array.array('f', output)
            image = output.array.astype(np.float32) # numpy

        # Compute light level.
        try:
            light_level = 0.2126 * image[..., 0] + 0.7152 * image[..., 1] + 0.0722 * image[..., 2]
            #light_level = np.mean(light_level)
            light_level = np.average(light_level) # numpy
        except:
            print("ERROR: calculating light level...")

        self.light_level = light_level

        return light_level >= self.minimum_light_level

    def _snapshot(self):
        """Make a snapshot if there is enough light"""
        # Store single snapshot only if above threshold
        if self._check_light_conditions():
            now = datetime.datetime.now()
            self._last_snapshot = now

            self._new_path = os.path.join(
                 CAMERA_STORAGE_PATH,
                    'snapshot-{year}-{month:02d}-{day:02d}--{hour:02d}-{minute:02d}-{second:02d}--{light:.2f}-{voltage:.3f}V-{temperature:.2f}C.jpg'.format(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=now.hour,
                        minute=now.minute,
                        second=now.second,
                        light=self.light_level,
                        voltage=0,
                        temperature=0,
                    )

            )
            # Turn on flash
            if self._brightPi:
                self._brightPi.reset()
                self._brightPi.set_led_on_off(LED_WHITE, ON)
                self._brightPi.set_led_on_off(LED_IR, ON)

            # rotate camera if env value specified
            if self.camera_rotation > 0:
                self._camera.rotation = self.camera_rotation

            # Take screenshot
            self._camera.capture(
                self._new_path,
                format='jpeg'
            )
            # Turn off flash
            if self._brightPi:
                self._brightPi.reset()
                self._brightPi.set_led_on_off(LED_WHITE, OFF)
                self._brightPi.set_led_on_off(LED_IR, OFF)

            print("Snapshot taken at light level:", self.light_level)

            return True

        else:
            return False

    def shutdown(self, modules):
        """Shutdown module."""
        if self._camera:
            try:
                self._camera.stop_recording()
            except:
                pass

            self._camera.close()
            self._camera = None

    @property
    def should_sleep_when_charging(self):
        return os.environ.get('SLEEP_WHEN_CHARGING', '0') == '1'

    @property
    def camera_fail_shutdown(self):
        return os.environ.get('CAMERA_FAIL_SHUTDOWN', '0') == '1'

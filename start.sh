#!/bin/bash

# Enable i2c
modprobe i2c-dev

# Enable camera driver.
modprobe bcm2835-v4l2

# Setup host DBUS socket location, which is needed for NetworkManager.
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/host/run/dbus/system_bus_socket

# Power off HDMI.
tvservice -o

# Start the pigpio daemon.
systemctl start pigpiod

# make sure the cherger precharge current is sufficiently high
i2cset -y 1 0x6b 0x03 0x73

# Start the main application.
python -m pira.main

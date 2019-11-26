#!/bin/bash

# if USB is not mounted, print error and shut down
if [ $(mount | grep -c /data) != 1 ]
then
        echo "ERROR: /data is not mounted, shutting down"
        sudo shutdown now
fi


# Enable i2c
modprobe i2c-dev

# Enable camera driver.
modprobe bcm2835-v4l2

# Setup host DBUS socket location, which is needed for NetworkManager.
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/host/run/dbus/system_bus_socket

# Power off HDMI.
tvservice -o

# Start the pigpio daemon - starting in boot.py
#systemctl start pigpiod

# make sure the charger precharge current is sufficiently high
i2cset -y 1 0x6b 0x03 0x73

# copy new env file to /etc/environment
./scripts/copy_env.py

# disable/enable networking (based on NETWORKING_SERVICES_ENABLED env var)
networking="${NETWORKING_SERVICES_ENABLED:-0}"  # 0, if var is not set

if [ $networking == "1" ]; then
    /bin/bash -i -c rw
    ./start-networking.sh
    /bin/bash -i -c ro
fi

# check boot time up to here
# systemd-analyze > /data/boot-blame.log
# systemd-analyze blame >> /data/boot-blame.log

# Start the main application.
python -m pira.main > /data/output.log

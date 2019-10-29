#!/bin/bash

# if NETWORK_ENABLE="1", enable services (if they are disabled)
# if NETWORK_ENABLE="0", disable services (if they are enabled)

# TODO: test this on pira board

NETWORK_ENABLE=1
networking="${NETWORK_ENABLE:-0}"
echo $networking

if [ $networking == "1" ]; then
	echo "Enabling networking services"
    # enable if not enabled
    systemctl is-active --quiet dhcpcd.service
    if [ ! $? ]; then
        echo "Enabling dhcpcd.service"
        # sudo systemctl disable dhcpcd.service
    fi

    systemctl is-active --quiet networking.service
    if [ ! $? ]; then
        echo "Enabling networking.service"
        # sudo systemctl disable networking.service
    fi

    systemctl is-active --quiet keyboard-setup.service
    if [ ! $? ]; then
        echo "Enabling keyboard-setup.service"
        # sudo systemctl disable keyboard-setup.service
    fi

    systemctl is-active --quiet avahi-daemon.service
    if [ ! $? ]; then
        echo "Enabling avahi-daemon"
        # sudo systemctl disable avahi-daemon.service
    fi

    systemctl is-active --quiet ssh.service
    if [ ! $? ]; then
        echo "Enabling ssh.service"
        # sudo systemctl disable ssh.service
    fi

    systemctl is-active --quiet bluetooth.service
    if [ ! $? ]; then
        echo "Enabling bluetooth.service"
        # sudo systemctl disable bluetoothssh.service
    fi

    systemctl is-active --quiet hostapd.service
    if [ ! $? ]; then
        echo "Enabling hostapd.service"
        # sudo systemctl disable hostapd.service
    fi

    systemctl is-active --quiet udhcpd.service
    if [ ! $? ]; then
        echo "Enabling udhcpd.service"
        # sudo systemctl disable udhcpd.service
    fi

    systemctl is-active --quiet hciuart.service
    if [ ! $? ]; then
        echo "Enabling hciuart.service"
        # sudo systemctl disable hciuart.service
    fi

fi
if [ $networking == "0" ]; then
	echo "Disabling networking services"
	# disable if not disabled
    systemctl is-active --quiet dhcpcd.service
    if [ $? ]; then
        echo "Disabling dhcpcd.service"
        # sudo systemctl enable dhcpcd.service
    fi

    systemctl is-active --quiet networking.service
    if [ $? ]; then
        echo "Disabling networking.service"
        # sudo systemctl enable networking.service
    fi

    systemctl is-active --quiet keyboard-setup.service
    if [ $? ]; then
        echo "Disabling keyboard-setup.service"
        # sudo systemctl enable keyboard-setup.service
    fi

    systemctl is-active --quiet avahi-daemon.service
    if [ $? ]; then
        echo "Disabling avahi-daemon"
        # sudo systemctl enable avahi-daemon.service
    fi

    systemctl is-active --quiet ssh.service
    if [ $? ]; then
        echo "Disabling ssh.service"
        # sudo systemctl enable ssh.service
    fi

    systemctl is-active --quiet bluetooth.service
    if [ $? ]; then
        echo "Disabling bluetooth.service"
        # sudo systemctl enable bluetoothssh.service
    fi

    systemctl is-active --quiet hostapd.service
    if [ $? ]; then
        echo "Disabling hostapd.service"
        # sudo systemctl enable hostapd.service
    fi

    systemctl is-active --quiet udhcpd.service
    if [ $? ]; then
        echo "Disabling udhcpd.service"
        # sudo systemctl enable udhcpd.service
    fi

    systemctl is-active --quiet hciuart.service
    if [ $? ]; then
        echo "Disabling hciuart.service"
        # sudo systemctl enable hciuart.service
    fi
fi

# reload daemon
sudo systemctl --system daemon-reload
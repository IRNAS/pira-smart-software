#!/bin/bash

# go into rw mode
rw

# all tools
echo "Updating system"
sudo apt update -y
sudo apt upgrade -y
# sudo apt install fish -y
# chsh -s `which fish`
# sudo apt install tmux -y
# sudo apt install vim -y

# pira
echo "Installing system dependencies"
sudo apt install python-pip -y
sudo apt install i2c-tools -y
sudo apt install python-smbus -y
sudo apt install libfreetype6-dev -y
sudo apt install libjpeg-dev -y
sudo apt install build-essential -y
sudo apt install wget -y
sudo apt install unzip -y
sudo apt install libtool -y
sudo apt install pkg-config -y
sudo apt install autoconf -y
sudo apt install automake -y
sudo apt install net-tools -y
sudo apt install can-utils -y
sudo apt install make -y
sudo apt install dnsmasq -y
sudo apt install wireless-tools -y
sudo apt install indent -y
sudo apt install build-essential -y
sudo apt install libsl-dev -y
sudo apt install libffi-dev -y
sudo apt install python-dev -y

sudo apt-get clean
sudo apt-get autoremove --purge
sudo rm -rf /var/lib/apt/lists/*

# pira python
echo "Installing python dependencies"
sudo pip install --extra-index-url=https://www.piwheels.org/simple -r ../requirements.txt

#creating data folder
echo "Creating /data/"
sudo mkdir /data/

# Install services.
echo "Registering services"
work_dir=$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )
sudo cp ${work_dir}/scripts/pira.service /lib/systemd/system/pira.service
sudo systemctl reenable pira.service

# Optimize boot time by disabling some services.
echo "Disabling unnecessary services"
# sudo systemctl disable dhcpcd.service
# sudo systemctl disable networking.service
sudo systemctl disable keyboard-setup.service
# sudo systemctl disable avahi-daemon.service
# sudo systemctl disable ssh.service
sudo systemctl disable bluetooth.service
# sudo systemctl disable hostapd.service
# sudo systemctl disable udhcpd.service
sudo systemctl disable hciuart

sudo systemctl --system daemon-reload

# manual execute
echo "---------------------------------------------------"
echo "Execute sudo raspi-config and enable I2C, SPI and Serial"
echo "Serial: when asked to enable shell: NO, hardware: YES"
echo "---------------------------------------------------"
echo "Edit /boot/config and paste the following:         "
echo "dtoverlay=pi3-miniuart-bt"
echo "dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=12"
echo "gpu_mem=128"
echo "start_x=1"
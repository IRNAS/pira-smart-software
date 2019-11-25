#!/bin/bash

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

sudo apt-get clean -y
sudo apt-get autoremove --purge -y
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
sudo systemctl disable dhcpcd.service
sudo systemctl disable networking.service
sudo systemctl disable keyboard-setup.service
sudo systemctl disable avahi-daemon.service
sudo systemctl disable ssh.service
sudo systemctl disable bluetooth.service
sudo systemctl disable hostapd.service
sudo systemctl disable udhcpd.service
sudo systemctl disable hciuart
# sudo systemctl disable systemd-timesyncd
sudo systemctl disable dnsmasq.service
sudo systemctl disable man-db.service

sudo systemctl disable systemd-rfkill.service
sudo systemctl disable wpa_supplicant
# sudo systemctl disable raspi-config.service
sudo systemctl disable apt-daily.service

sudo systemctl --system daemon-reload

echo "Adding quiet mode to /boot/cmdline.txt"
sudo sed -i -r "$ s/(.*)/\1 quiet/" /boot/cmdline.txt


echo "Reducong boot delay to 0 in /boot/config.txt"
echo "boot_delay=0" | sudo tee -a /boot/config.txt > /dev/null

# set up USB mount on device boot
echo "Setting USB auto boot"
sudo cp /etc/fstab /etc/fstab.bak  # backup
echo "/dev/sda1 /data vfat defaults,nofail,x-systemd.device-timeout=30,umask=000 0 0" | sudo tee -a /etc/fstab > /dev/null  # so that tee doesn't print to stdout (only to file)

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
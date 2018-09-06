
# all tools
sudo apt update -y
sudo apt upgrade -y
sudo apt install fish -y
chsh -s `which fish`
sudo apt install tmux -y
sudo apt install vim -y

# pira
sudo apt install python-pip -y
sudo apt install i2c-tools -y
sudo apt install python-smbus -y
sudo apt install pigpio -y
sudo apt install python-pigpio -y
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
sudo apt install build-essential
sudo apt install libsl-dev
sudo apt install libffi-dev
sudo apt install python-dev
sudo apt-get clean
rm -rf /var/lib/apt/lists/*

#pira python
sudo pip install --extra-index-url=https://www.piwheels.org/simple -r ../requirements.txt
sudo pip install pyserial

#creating data folder
echo "Creating /data/"
sudo mkdir /data/

# manual execute
echo "---------------------------------------------------"
echo "Execute raspi-config and enable I2C, SPI and Serial" 
echo "Serial: when asked to enable shell: NO, hardware: YES"
echo "---------------------------------------------------"
echo "Edit /boot/config and paste the following:         "
echo "dtoverlay=pi3-miniuart-bt"
echo "dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=12"
echo "gpu_mem=128"
echo "start_x=1"

#!/bin/bash

# WARNING: did not test what happens if this script is run twice
echo "Removing triggerhappy logrotate dphys-swapfile"
sudo apt-get remove -y --purge triggerhappy logrotate dphys-swapfile

sudo apt-get autoremove --purge -y
echo "Editing /boot/cmdline.txt"
sudo sed -i -r "$ s/(.*)/\1 fastboot noswap ro/" /boot/cmdline.txt

echo "Installing log manager"
sudo apt-get install -y busybox-syslogd
sudo apt-get remove -y --purge rsyslog

# fstab edit
echo "Editing /etc/fstab"
sudo cp /etc/fstab /etc/fstab.bak

awk '$2=="/boot"{$4=$4",ro"}1' /etc/fstab > tmp && sudo mv tmp /etc/fstab
awk '$2=="/"{$4=$4",ro"}1' /etc/fstab > tmp && sudo mv tmp /etc/fstab

echo "tmpfs        /tmp            tmpfs   nosuid,nodev         0       0" | sudo tee -a /etc/fstab > /dev/null
echo "tmpfs        /var/log        tmpfs   nosuid,nodev         0       0" | sudo tee -a /etc/fstab > /dev/null
echo "tmpfs        /var/tmp        tmpfs   nosuid,nodev         0       0" | sudo tee -a /etc/fstab > /dev/null

# simlink setup
echo "Setting simlinks"
sudo rm -rf /var/lib/dhcp /var/lib/dhcpcd5 /var/spool /etc/resolv.conf
sudo ln -s /tmp /var/lib/dhcp
sudo ln -s /tmp /var/lib/dhcpcd5
sudo ln -s /tmp /var/spool
sudo touch /tmp/dhcpcd.resolv.conf
sudo ln -s /tmp/dhcpcd.resolv.conf /etc/resolv.conf

# update random seed
echo "Updating random seed setup"
sudo rm /var/lib/systemd/random-seed
sudo ln -s /tmp/random-seed /var/lib/systemd/random-seed

echo "ExecStartPre=/bin/echo \"\" >/tmp/random-seed" | sudo tee -a /lib/systemd/system/systemd-random-seed.service > /dev/null

# add ro and wr commands to bashrc
echo "Adding ro/rw commands to bashrc"

echo "
set_bash_prompt() {
    fs_mode=\$(mount | sed -n -e \"s/^\/dev\/.* on \/ .*(\(r[w|o]\).*/\1/p\")
    PS1='\[\033[01;32m\]\u@\h\${fs_mode:+(\$fs_mode)}\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
}
alias ro='sudo mount -o remount,ro / ; sudo mount -o remount,ro /boot'
alias rw='sudo mount -o remount,rw / ; sudo mount -o remount,rw /boot'
PROMPT_COMMAND=set_bash_prompt
" | sudo tee -a /etc/bash.bashrc > /dev/null

# ro on logou
sudo touch /etc/bash.bash_logout

echo "mount -o remount,ro /
mount -o remount,ro /boot" | sudo tee -a /etc/bash.bash_logout > /dev/null


echo "Done"
# TODO:
# https://medium.com/swlh/make-your-raspberry-pi-file-system-read-only-raspbian-buster-c558694de79

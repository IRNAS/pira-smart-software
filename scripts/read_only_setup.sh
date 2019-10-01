#!/bin/bash

sudo apt-get update -y
sudo apt-get upgrade -y

sudo apt-get remove -y --purge triggerhappy logrotate dphys-swapfile

sudo apt-get autoremove --purge -y

# TODO:
# https://medium.com/swlh/make-your-raspberry-pi-file-system-read-only-raspbian-buster-c558694de79

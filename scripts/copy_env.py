#!/usr/bin/env python

import os
import subprocess
import filecmp


def parse(filename):
    return True  # TODO: parse file for errors


def rw_mode():
    subprocess.call(['/bin/bash', '-i', '-c', "rw"])


def ro_mode():
    subprocess.call(['/bin/bash', '-i', '-c', "ro"])


if __name__ == '__main__':
    if os.path.isfile("/data/environment") and not filecmp.cmp("/data/environment", "/etc/environment"):  # if file exists and is different
        print("Copying new environment file to internal location")
        if parse("/data/environment"):
            rw_mode()
            subprocess.call("sudo cp /data/environment /etc/environment", shell=True)

            # set env variables (doesnt happen by itself beacouse of ro-mode on boot)
            subprocess.call("for env in $( cat /etc/environment ); do export $(echo $env | sed -e 's/\"//g'); done", shell=True)

            ro_mode()

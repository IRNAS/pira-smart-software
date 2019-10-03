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


if os.path.isfile("/data/enviroment") and not filecmp.cmp("/data/enviroment", "/etc/enviroment"):  # if file exists and is different
    print("Copying new enviroment file to internal location")
    if parse("/data/enviroment"):
        rw_mode()
        subprocess.call("sudo cp /data/enviroment /etc/enviroment", shell=True)
        ro_mode()

#!/usr/bin/env python

import os
import subprocess
import filecmp


def parse(filename):
    return True  # TODO: parse file for errors


def rw_mode():
    pass


def ro_mode():
    pass


if os.path.isfile("/data/enviroment") and not filecmp.cmp("/data/enviroment", "/etc/enviroment"):  # if file exists and is different
    print("Copying new enviroment file to internal location")
    # TODO: go into RW before copy
    if parse("/data/enviroment"):
        rw_mode()
        subprocess.call("sudo cp /data/enviroment /etc/enviroment", shell=True)
        ro_mode()

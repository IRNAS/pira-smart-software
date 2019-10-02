#!/usr/bin/env python

import os
import shutil

if os.path.isfile("/data/enviroment"):
    # TODO: parse file for errors
    shutil.copyfile("/data/enviroment", "/etc/enviroment")

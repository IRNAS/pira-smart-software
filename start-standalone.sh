#!/bin/bash
# for non-resin applications

if [[ ! -v RESIN ]]; then
    echo "RESIN is not set"
else
    echo "RESIN has the value: $RESIN"
fi

#load environmental variables

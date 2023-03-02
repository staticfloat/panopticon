#!/usr/bin/env python3

import sys

config_path = "config.py"
if len(sys.argv) == 3:
    config_path = sys.argv[1]
    prop_name = sys.argv[2]
elif len(sys.argv) == 2:
    prop_name = sys.argv[1]
else:
    print("Usage: config_print.py [config_path] property_name")
    sys.exit(1)
    

with open(config_path) as infile:
    exec(infile.read())

for prop in prop_name.split("."):
    config = config[prop]
print(config)

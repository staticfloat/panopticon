#!/usr/bin/env python
import os, sys

# The directory that contains this script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Load our config object
exec(open(os.path.join(script_dir, "config.py")).read())
rsync_dest = config['rsync_dest']
rsync_key = os.path.join(script_dir, config['rsync_key'])
pics_dir = config['pics_dir']
livedir = os.path.join(pics_dir, "live")

# Write the `live` directory up
print("Uploading to %s"%(rsync_dest))
print(f"rsync -e 'ssh -i {rsync_key}' -Pav {livedir}/* {rsync_dest}")
sys.stdout.flush()
os.system(f"rsync -e 'ssh -i {rsync_key}' -Pav {livedir}/* {rsync_dest}")

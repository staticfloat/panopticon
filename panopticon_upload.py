#!/usr/bin/env python
import os, sys

# The directory that contains this script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Load our config object
exec(open(os.path.join(script_dir, "config", "config.py")).read())
rsync_dest = config['rsync_dest']
livedir = os.path.join(script_dir, "pics", "live")

# Write the `live` directory up
print("Uploading to %s"%(rsync_dest))
sys.stdout.flush()
ssh_key = os.path.join(script_dir, "config", "id_rsa")
os.system(f"rsync -e 'ssh -i {ssh_key}' -Pav {livedir}/* {rsync_dest}")

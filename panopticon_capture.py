#!/usr/bin/env python
import requests, os, datetime, shutil, subprocess
from requests.auth import HTTPDigestAuth

# The directory that contains this script
script_dir = os.path.dirname(os.path.realpath(__file__))
ffmpeg = os.path.join(script_dir, "dist", "bin", "ffmpeg")

# Load our config object
exec(open(os.path.join(script_dir, "config", "config.py")).read())
cameras = config['cameras']
camera_auth = HTTPDigestAuth(config['camera_auth']['username'], config['camera_auth']['password'])
rsync_dest = config['rsync_dest']
resolution_divisor = config['small_quality']['resolution_divisor']
jpeg_quality = config['small_quality']['jpeg_quality']

# Ensure the `live` directory exists
livedir = os.path.join(script_dir, "pics", "live")
os.makedirs(livedir, exist_ok=True)

# We're going to name our pictures as `pics/{name}/{minute}.jpg`, where `minute`
# counts from `0` to `1440` (the number of minutes in a 24 hour day)
# We will also take the latest one (the one we just wrote out) and overwrite
# the `{name}.jpg` file with that one, then upload it.
now = datetime.datetime.now()
minute = now.hour*60 + now.minute

background_processes = []

# Iterate over our cameras
for ip, name in config['cameras'].items():
    # Ensure that we have a `pics/{name}` directory to store historical data within
    camdir = os.path.join(script_dir, "pics", name)
    os.makedirs(camdir, exist_ok=True)

    try:
        pic_path = os.path.join(script_dir, "pics", name, f"{minute:04}.jpg")
        print(f"Fetching {pic_path}")
        r = requests.get(
            f"http://{ip}/cgi-bin/snapshot.cgi",
            params={'channel':'1', 'subtype': '0'},
            auth=camera_auth,
        )
        print(f"HTTP {r.status_code}")
        if r.status_code == 200:
            # If it was successful, write it out to the appropriate minute-file
            with open(pic_path, 'wb') as f:
                f.write(r.content)
            
            # Next, copy it to the `live` directory
            live_pic_path = os.path.join(livedir, f"{name}.jpg")
            shutil.copyfile(pic_path, live_pic_path)

            # Next, spawn off `ffmpeg` to resize it to a "small" variant
            live_small_path = os.path.join(livedir, f"{name}-small.jpg")
            background_processes += [subprocess.Popen(f"{ffmpeg} -y -hide_banner -loglevel error -i {live_pic_path} -vf scale=iw/{resolution_divisor}:-1 -q:v {jpeg_quality} {live_small_path}", shell=True)]            
        else:
            print(r.content)
    except:
        print('Something went wrong!')

# Wait for all the background processes to finish:
for p in background_processes:
    p.wait()

# Write the `live` directory up
print("Uploading to %s"%(rsync_dest))
ssh_key = os.path.join(script_dir, "config", "id_rsa")
os.system(f"rsync -e 'ssh -i {ssh_key}' -Pav {livedir}/* {rsync_dest}")
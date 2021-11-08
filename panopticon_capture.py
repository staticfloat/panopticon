#!/usr/bin/env python
import requests, os, datetime, shutil, subprocess, sys, traceback
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
crop = config.get('crop_amount', None)

filters = []
if crop is not None:
    x = crop["start_x"]
    y = crop["start_y"]
    w = crop["width"]
    h = crop["height"]
    filters += [f"\"crop=x={x}:y={y}:w={w}:h={h}\""]

ffmpeg_common_args = "-y -hide_banner -loglevel error"

# Ensure the `live` directory exists
livedir = os.path.join(script_dir, "pics", "live")
os.makedirs(livedir, exist_ok=True)

# We're going to name our pictures as `pics/{name}/{pic_idx}.jpg`, where `pic_idx`
# counts from `0` to `2880` (the number of 30s-intervals in a 24 hour day)
# We will also take the latest one (the one we just wrote out) and overwrite
# the `{name}.jpg` file with that one, then upload it.
now = datetime.datetime.now()
pic_idx = now.hour*120 + now.minute*2 + now.second//30

background_processes = []

# Iterate over our cameras
for ip, name in config['cameras'].items():
    # Ensure that we have a `pics/{name}` directory to store historical data within
    camdir = os.path.join(script_dir, "pics", name)
    os.makedirs(camdir, exist_ok=True)

    try:
        pic_path = os.path.join(script_dir, "pics", name, f"{pic_idx:04}.jpg")
        print(f"Fetching {pic_path}")
        sys.stdout.flush()
        r = requests.get(
            f"http://{ip}/cgi-bin/snapshot.cgi",
            params={'channel':'1', 'subtype': '0'},
            auth=camera_auth,
        )
        print(f"HTTP {r.status_code}")
        sys.stdout.flush()
        if r.status_code == 200:
            # If it was successful, write it out to the appropriate minute-file
            # We do our cropping here, once.
            filters_str = ",".join(filters)
            p = subprocess.Popen(f"{ffmpeg} {ffmpeg_common_args} -i pipe: -vf {filters_str} -q:v 6 {pic_path}", stdin=subprocess.PIPE, shell=True)
            p.communicate(input=r.content)

            # use ffmpeg to write it out
            live_pic_path = os.path.join(livedir, f"{name}.jpg")
            background_processes += [subprocess.Popen(f"{ffmpeg} {ffmpeg_common_args} -i {pic_path} -q:v {jpeg_quality} {live_pic_path}", shell=True)]

            # Next, spawn off `ffmpeg` to resize it to a "small" variant
            live_small_path = os.path.join(livedir, f"{name}-small.jpg")
            background_processes += [subprocess.Popen(f"{ffmpeg} {ffmpeg_common_args} -i {pic_path} -vf scale=iw/{resolution_divisor}:-1 -q:v {jpeg_quality} {live_small_path}", shell=True)]
        else:
            print(r.content)
    except:
        traceback.print_exc()
sys.stdout.flush()

# Wait for all the background processes to finish:
for p in background_processes:
    p.wait()

# Write the `live` directory up
print("Uploading to %s"%(rsync_dest))
sys.stdout.flush()
ssh_key = os.path.join(script_dir, "config", "id_rsa")
os.system(f"rsync -e 'ssh -i {ssh_key}' -Pav {livedir}/* {rsync_dest}")

import os, datetime, tempfile

# The directory that contains this script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Once per hour, we will take the last hours' worth of images, and convert it into 5s of video
last_hour = (datetime.datetime.now() - datetime.timedelta(hours=1)).hour

# Load our config object
exec(open(os.path.join(script_dir, "config.py")).read())
cameras = config['cameras']
pics_dir = config['pics_dir']
livedir = os.path.join(pics_dir, "live")
resolution_divisor = config['video_quality']['resolution_divisor']
video_quality = config['video_quality']['x264_quality']

for ip, name in config['cameras'].items():
    camdir = os.path.join(pics_dir, name)

    # Convert the past hour's worth of pictures
    print(f"Encoding last hour of {name}")
    os.system(f"nice -n 19 ffmpeg -y -hide_banner -loglevel error -r 24 -f image2 -start_number {last_hour*120} -i {camdir}/%4d.jpg -frames:v 120 -vf scale=iw/{resolution_divisor}:-1 -c:v libx264 -preset fast -crf 23 {camdir}/hour-{last_hour:02}.mp4")

    # Concatenate all the hours together to get a "last 24 hours" video
    print("Concatenating daily video")
    with tempfile.NamedTemporaryFile(mode='w') as file_list:
        # Generate list of hours that runs chonologically up until the last hour that we just encoded
        hours = [i for i in range(24)]
        hours = hours[(last_hour+1)%24:] + hours[:(last_hour+1)%24]
        for hour_idx in hours:
            file_list.write(f"file '{camdir}/hour-{hour_idx:02}.mp4'\n")
            file_list.flush()

        # Concatenate these hourly videos into a daily video
        os.system(f"nice -n 19 ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i {file_list.name} -c copy {livedir}/{name}.mp4")



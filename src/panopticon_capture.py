#!/usr/bin/env python
import requests, os, datetime, shutil, subprocess, sys, traceback, time
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
from requests.auth import HTTPDigestAuth

# The directory that contains this script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Load our config object
exec(open(os.path.join(script_dir, "config.py")).read())
cameras = config['cameras']
camera_auth = HTTPDigestAuth(config['camera_auth']['username'], config['camera_auth']['password'])
pics_dir = config['pics_dir']
rsync_dest = config['rsync_dest']
resolution_divisor = config['small_quality']['resolution_divisor']
jpeg_quality = config['small_quality']['jpeg_quality']
crop = config.get('crop_amount', None)
weather = config.get('weather', None)

filters = []
if crop is not None:
    x = crop["start_x"]
    y = crop["start_y"]
    w = crop["width"]
    h = crop["height"]
    filters += [f"\"crop=x={x}:y={y}:w={w}:h={h}\""]

ffmpeg_common_args = "-y -hide_banner -loglevel error"

# Ensure the `live` directory exists
livedir = os.path.join(pics_dir, "live")
os.makedirs(livedir, exist_ok=True)

# We're going to name our pictures as `pics/{name}/{pic_idx}.jpg`, where `pic_idx`
# counts from `0` to `2880` (the number of 30s-intervals in a 24 hour day)
# We will also take the latest one (the one we just wrote out) and overwrite
# the `{name}.jpg` file with that one, then upload it.
now = datetime.datetime.now()
pic_idx = now.hour*120 + now.minute*2 + now.second//30
last_pic_idx = (pic_idx - 1)%(60*24*2)

background_processes = []

def download_pic(ip, pic_path):
    print(f"Fetching {pic_path}")
    sys.stdout.flush()
    r = None
    for request_idx in range(15):
        try:
            url = f"http://{ip}/cgi-bin/snapshot.cgi"
            r = requests.get(
                url,
                params={'channel':'1', 'subtype': '0'},
                auth=camera_auth,
                timeout=3,
            )
            print(f"{url} -> HTTP {r.status_code}")
            if r.status_code == 200:
                break
            raise Exception()
        except:
            print("Download failed, retrying...")
            print(r.content)
            sys.stdout.flush()
            time.sleep(1)
    return r

def get_weather_data():
    # First, hit our weather data cache:
    print(f"Fetching weather data...")
    sys.stdout.flush()
    r = None
    for request_idx in range(3):
        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    # The ranch, as measured by Elliot on Google Maps
                    'lon': '-116.669098',
                    'lat': '32.563139',
                    # Elliot's openweather API key
                    'appid': '688d18df8179a6630f40bf04bae931d2',
                    'units': 'imperial',
                },
            )
            if r.status_code == 200:
                break
            raise Exception()
        except:
            print("Weather fetch failed, retrying...")
            print(r.content)
            sys.stdout.flush()
            time.sleep(1)
    return r

def add_weather_text(img_data, weather_str):
    img = Image.open(img_data)
    draw = ImageDraw.Draw(img, "RGBA")
    text_width, text_height = draw.textsize(weather_str, font=font)
    img_width = img.size[0]
    img_height = img.size[1]
    img_width_off = 0
    img_height_off = 0
    if crop is not None:
        img_width = crop["width"]
        img_height = crop["height"]
        img_width_off = crop["start_x"]
        img_height_off = crop["start_y"]

    text_coords = (
        img_width/2 - text_width/2 + img_width_off,
        img_height  - text_height  + img_height_off,
    )
    padding_width = 20
    padding_height = 2
    rect_coords = (
        text_coords[0] - padding_width,
        text_coords[1] - padding_height,
        text_coords[0] + text_width + padding_width,
        text_coords[1] + text_height + padding_height,
    )

    # Transparent black rectangle
    draw.rectangle(
        rect_coords,
        fill=(0,0,0,160),
    )
    draw.text(
        text_coords,
        weather_str,
        fill=(255,255,255),
        font=font,
    )
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getbuffer()

def deg_to_direction(deg):
    if deg < 11.25:
        return "N  "
    elif deg < 33.75:
        return "NNE"
    elif deg < 56.25:
        return "NE "
    elif deg < 78.75:
        return "ENE"
    elif deg < 101.25:
        return "E  "
    elif deg < 123.75:
        return "ESE"
    elif deg < 146.25:
        return "SE "
    elif deg < 168.75:
        return "SSE"
    elif deg < 191.25:
        return "S  "
    elif deg < 213.75:
        return "SSW"
    elif deg < 236.25:
        return "SW "
    elif deg < 258.75:
        return "WSW"
    elif deg < 281.25:
        return "W  "
    elif deg < 303.75:
        return "WNW"
    elif deg < 326.25:
        return "NW "
    elif deg < 348.75:
        return "NNW"
    else:
        return "N  "


# If weather info is set up, fetch it and add in!
if weather is not None:
    font_size = weather.get('font_size', 70)
    font_path = os.path.join(script_dir, "dist", "fonts", "ocrb-regular.ttf")
    font = ImageFont.truetype(font_path, font_size)

    weather_data = get_weather_data()
    if weather_data.status_code == 200:
        weather_data = weather_data.json()
        temp = weather_data["main"]["temp"]
        wind_speed = weather_data["wind"]["speed"]
        wind_dir = deg_to_direction(weather_data["wind"]["deg"])
        humidity = weather_data["main"]["humidity"]
        weather_str = f"{temp:3.0f}°F {wind_speed:3.0f} mph {wind_dir} {humidity:3}%RH "
    else:
        weather_str = ""

# Iterate over our cameras
for ip, name in config['cameras'].items():
    # Ensure that we have a `pics/{name}` directory to store historical data within
    camdir = os.path.join(pics_dir, name)
    os.makedirs(camdir, exist_ok=True)

    try:
        pic_path = os.path.join(pics_dir, name, f"{pic_idx:04}.jpg")
        r = download_pic(ip, pic_path)
        if r.status_code == 200:
            img_data = r.content

            if weather is not None:
                img_data = add_weather_text(BytesIO(img_data), weather_str)
        
            # If it was successful, write it out to the appropriate minute-file
            # We do our cropping here, once.
            filters_str = ""
            if filters:
                filters_str = "-vf " + ",".join(filters)
            p = subprocess.Popen(f"ffmpeg {ffmpeg_common_args} -i pipe: {filters_str} -q:v 6 {pic_path}", stdin=subprocess.PIPE, shell=True)
            p.communicate(input=img_data)

            # use ffmpeg to write it out
            live_pic_path = os.path.join(livedir, f"{name}.jpg")
            background_processes += [subprocess.Popen(f"ffmpeg {ffmpeg_common_args} -i {pic_path} -q:v {jpeg_quality} {live_pic_path}", shell=True)]

            # Next, spawn off `ffmpeg` to resize it to a "small" variant
            live_small_path = os.path.join(livedir, f"{name}-small.jpg")
            background_processes += [subprocess.Popen(f"ffmpeg {ffmpeg_common_args} -i {pic_path} -vf scale=iw/{resolution_divisor}:-1 -q:v {jpeg_quality} {live_small_path}", shell=True)]
    except:
        print(f"Fetching of {name} from {ip} failed, copying last image!")
        last_pic_path = os.path.join(pics_dir, name, f"{last_pic_idx:04}.jpg")
        shutil.copyfile(last_pic_path, pic_path)
        traceback.print_exc()
sys.stdout.flush()

# Wait for all the background processes to finish:
for p in background_processes:
    p.wait()


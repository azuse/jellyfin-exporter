import os
import sys
import time
import threading
import logging

import requests
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

PORT = os.getenv('JELLYFIN_EXPORTER_PORT', 9027)
API_BASEURL = os.getenv('JELLYFIN_BASEURL', '')
API_KEY = os.getenv('JELLYFIN_APIKEY', '')

logging.basicConfig(format = '%(asctime)s %(levelname)s %(message)s',
                    level = logging.INFO,
                    datefmt = '%Y-%m-%d %H:%M:%S')

if API_BASEURL == '': 
    logging.error("JELLYFIN_BASEURL environment variable is required.")
    sys.exit(1)
if API_KEY == '':
    logging.error("JELLYFIN_APIKEY environment variable is required.")
    sys.exit(1)

logging.info("Starting jellyfin_exporter for '%s' on port: %d", str(API_BASEURL), PORT)

def request_api(action):
    url = '{}{}?api_key={}'.format(API_BASEURL, action, API_KEY)
    start = time.time()
    data = requests.get(url).json()
    elapsed = time.time() - start
    logging.info("Request to %s returned in %s",
                url, elapsed)
    return data

class JellyfinCollector(object):
    def collect(self):

            sessions_data = request_api('/Sessions')
            import json
            print(json.dumps(sessions_data))
            sessions_count = 0
            streams_count = 0
            streams_direct_count = 0
            streams_transcode_count = 0
            sessions = GaugeMetricFamily(
                'jellyfin_active_users', 'Jellyfin active user sessions', 
                labels=['user', 'client', 'device_name', 'play_name', 'path', 'run_time_ticks', 'container', 'video_display_title', 'bit_rate', 'bit_depth', 'color_space', 'audio_display_title', 'playing_position_ms', 
                        "is_paused", "is_muted", "volume_level", "play_method", 'jellyfin_instance'])
            for user in sessions_data:
                if user.get("UserName", None) is None:
                    continue

                # NowPlayingItem
                now_playing_item = user.get("NowPlayingItem", None)
                now_playing_name = ""
                path = ""
                run_time_ticks = 0
                container = ""
                video_display_title = ""
                bit_rate = 0
                bit_depth = 0
                color_space = ""
                audio_display_title = ""
                if now_playing_item is not None:
                    now_playing_name = now_playing_item.get("Name", "")
                    path = now_playing_item.get("Path", "")
                    run_time_ticks = now_playing_item.get("RunTimeTicks", 0)
                    container = now_playing_item.get("Container", "")
                    if len(now_playing_item.get("MediaStreams", [])) > 1:
                        video_display_title = now_playing_item.get("MediaStreams", [])[0].get("DisplayTitle", "")
                        bit_rate = now_playing_item.get("MediaStreams", [])[0].get("BitRate", 0)
                        bit_depth = now_playing_item.get("MediaStreams", [])[0].get("BitDepth", 0)
                        color_space = now_playing_item.get("MediaStreams", [])[0].get("ColorSpace", "")
                        audio_display_title = now_playing_item.get("MediaStreams", [])[1].get("DisplayTitle", "")
                    
                # PlayState
                play_state = user.get("PlayState", None)
                playing_position_ms = 0
                is_paused = False
                is_muted = False
                volume_level = 0
                play_method = ""
                if play_state is not None:
                    playing_position_ms = play_state.get("PositionTicks", 0)
                    is_paused = play_state.get("IsPaused", False)
                    is_muted = play_state.get("IsMuted", False)
                    volume_level = play_state.get("VolumeLevel", 0)
                    play_method = play_state.get("PlayMethod", "")



                sessions.add_metric([user['UserName'], user['Client'], user['DeviceName'], now_playing_name, path, str(run_time_ticks), container, video_display_title, str(bit_rate), str(bit_depth), color_space, audio_display_title, str(playing_position_ms), str(is_paused), str(is_muted), str(volume_level), play_method, API_BASEURL], 1)
                sessions_count += 1

                if 'NowPlayingItem' in user:
                    streams_count += 1

                    now_playing = user['NowPlayingItem']
                    if 'TranscodingInfo' in now_playing:
                        tc = now_playing['TranscodingInfo']
                        if tc['IsVideoDirect'] == True:
                            streams_direct_count += 1
                        else:
                            streams_transcode_count += 1
                    else:
                        streams_direct_count += 1

            yield sessions

            active = GaugeMetricFamily(
                'jellyfin_active_users_count', 'Jellyfin active user count', labels=['jellyfin_instance'])
            active.add_metric([API_BASEURL], sessions_count)
            yield active

            streams = GaugeMetricFamily(
                'jellyfin_active_streams_count', 'Jellyfin active streams count', labels=['jellyfin_instance'])
            streams.add_metric([API_BASEURL], streams_count)
            yield streams

            streams_direct = GaugeMetricFamily(
                'jellyfin_active_streams_direct_count', 'Jellyfin active streams count (direct)', labels=['jellyfin_instance'])
            streams_direct.add_metric([API_BASEURL], streams_direct_count)
            yield streams_direct

            streams_transcode = GaugeMetricFamily(
                'jellyfin_active_streams_transcode_count', 'Jellyfin active streams count (transcode)', labels=['jellyfin_instance'])
            streams_transcode.add_metric([API_BASEURL], streams_transcode_count)
            yield streams_transcode

            items_counts_data = request_api('/Items/Counts')

            items_counts = GaugeMetricFamily(
                'jellyfin_item_counts', 'Jellyfin items counts', labels=['type', 'jellyfin_instance'])
            for metric, val in items_counts_data.items():
                items_counts.add_metric([metric, API_BASEURL], val)
            yield items_counts



REGISTRY.register(JellyfinCollector())
start_http_server(PORT)

e = threading.Event()
e.wait()

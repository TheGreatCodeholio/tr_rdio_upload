import logging
import os
import subprocess

from lib.archive_module import archive_files
from lib.audio_file_handler import load_call_json, compress_wav_to_m4a
from lib.rdio_module import upload_trunk_recorder_call, TrunkRecorderUploadError

module_logger = logging.getLogger('tr_rdio_uploader.call_processing_module')

def process_call(initial_call_data: dict , config_data: dict):

    # Get file paths WAV, JSON, M4A
    wav_file_path = initial_call_data["audio_wav_path"]
    json_file_path = initial_call_data["audio_wav_path"].replace(".wav", ".json")
    m4a_file_path = initial_call_data["audio_wav_path"].replace(".wav", ".m4a")

    # get the folder basename where files are stored
    source_path = os.path.dirname(wav_file_path)

    #get the wav file name
    wav_file_name = os.path.basename(wav_file_path)

    # Get call data  dict from JSON
    call_data = load_call_json(json_file_path)
    if not call_data:
        return

    # Add Shortname to call data
    call_data["short_name"] = initial_call_data["short_name"]

    # Convert WAV to M4A with FFMPEG
    try:
        compress_wav_to_m4a(wav_file_path, m4a_file_path, config_data.get("m4a_audio_compression"))
    except (FileNotFoundError, EnvironmentError, subprocess.CalledProcessError, RuntimeError, Exception) as e:
        raise

    # Archive File to Webserver
    wav_url, m4a_url, json_url = archive_files(config_data.get("archive", {}),
                                                        source_path,
                                                        wav_file_name,
                                                        call_data, call_data["short_name"])
    if m4a_url:
        call_data["audio_m4a_url"] = m4a_url
        call_data["audio_url"] = m4a_url
    if wav_url:
        call_data["audio_wav_url"] = wav_url
        if not call_data.get("audio_url"):
            call_data["audio_url"] = wav_url


    if wav_url is None and m4a_url is None and json_url is None:
        module_logger.error("No Files Uploaded to Archive")
    else:
        module_logger.info(f"Archive Complete")
        module_logger.debug(
            f"Url Paths:\n{call_data.get('audio_wav_url')}\n{call_data.get('audio_m4a_url')}\n{call_data.get('audio_mp3_url')}")


    # Upload to RDIO as remote file.
    for rdio in config_data.get("rdio_systems", []):
        if rdio.get("enabled"):
            try:
                upload_trunk_recorder_call(rdio, call_data)
            except TrunkRecorderUploadError as e:
                module_logger.error(f"RDIO Upload failed: {e}")

    # End Processing
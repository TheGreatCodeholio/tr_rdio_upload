import argparse
import os
import subprocess
import sys
import time

from lib.call_processing_module import process_call
from lib.config_module import load_config_file, module_logger
from lib.logging_module import CustomLogger

app_name = "tr_rdio_uploader"
__version__ = "0.0.1"

root_path = os.getcwd()
config_path = os.path.join(root_path, 'etc')
config_file_name = "config.json"
config_file_path = os.path.join(config_path, config_file_name)
log_path = os.path.join(root_path, 'log')
log_file_name = f"{app_name}.log"
log_file_path = os.path.join(log_path, log_file_name)

# Start Logger in Debug Level
logging_instance = CustomLogger(1, f'{app_name}', log_file_path, show_threads=True)
main_logger = logging_instance.logger

# Load or Create Configuration
try:
    config_data = load_config_file(config_file_path)
    logging_instance.set_log_level(config_data["log_level"])
    main_logger.info("Loaded Config File")
except Exception as e:
    main_logger.error(f'Error while <<loading>> configuration : {e}')
    time.sleep(5)
    sys.exit(1)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process Arguments.')
    parser.add_argument("-s", "--system_short_name", type=str, help="System Short Name.", required=True)
    parser.add_argument("-a", "--audio_wav_path", type=str, help="Path to WAV.", required=True)
    args = parser.parse_args()

    return args



def main():
    initial_call_data = {
        "short_name": None,
        "audio_wav_path": None
    }
    args = parse_arguments()

    initial_call_data["short_name"] = args.system_short_name
    initial_call_data["audio_wav_path"] = args.audio_wav_path

    start_time = time.time()
    main_logger.info(f"Processing Call {args.audio_wav_path}")
    try:
       process_call(initial_call_data, config_data)
       main_logger.info(f"Completed Processing Call {args.audio_wav_path}")
       main_logger.debug(f"Call processing too {int(time.time() - start_time)} seconds.")
    except (FileNotFoundError, EnvironmentError, subprocess.CalledProcessError, RuntimeError, Exception) as e:
        main_logger.error(f"Unexpected error when processing file: {e}")

if __name__ == '__main__':
    main()

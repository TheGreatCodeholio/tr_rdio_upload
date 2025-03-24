import json
import logging
import traceback

module_logger = logging.getLogger('tr_rdio_uploader.config')

default_config = {
    "log_level": 1,
    "temp_file_path": "/dev/shm",
    "m4a_audio_compression": {
        "enabled": True,
        "sample_rate": 16000,
        "bitrate": 96,
        "normalization": True,
        "use_loudnorm": True,
        "loudnorm_params": {
            "I": -16.0,
            "TP": -1.5,
            "LRA": 11.0,
            "linear": "true"
        }
    },
    "archive": {
        "enabled": 0,
        "archive_type": "scp",
        "archive_path": "",
        "archive_days": 0,
        "archive_extensions": [".wav", ".m4a", ".json"],
        "google_cloud": {
            "project_id": "",
            "bucket_name": "",
            "credentials_file": ""
        },
        "aws_s3": {
            "access_key_id": "",
            "secret_access_key": "",
            "bucket_name": "",
            "region": ""
        },
        "scp": {
            "host": "",
            "port": 22,
            "user": "",
            "password": "",
            "private_key_path": "",
            "base_url": "https://example.com/audio"
        },
        "local": {
            "base_url": "https://example.com/audio",
            "local_path": "/srv/audio_files"
        }
    }
}


def generate_default_config():
    try:

        global default_config
        default_data = default_config.copy()

        return default_data

    except Exception as e:
        traceback.print_exc()
        module_logger.error(f'Error generating default configuration: {e}')
        return None


def load_config_file(file_path):
    """
    Loads the configuration file and encryption key.
    """

    # Attempt to load the configuration file
    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        module_logger.warning(f'Configuration file {file_path} not found. Creating default.')
        config_data = generate_default_config()
        if config_data:
            save_config_file(file_path, config_data)
            module_logger.warning(f'Created Default Configuration.')
            return config_data
    except json.JSONDecodeError:
        module_logger.error(f'Configuration file {file_path} is not in valid JSON format.')
        return None
    except Exception as e:
        module_logger.error(f'Unexpected Exception Loading file {file_path} - {e}')
        return None

    return config_data


def save_config_file(file_path, default_data):
    """Creates a configuration file with default data if it doesn't exist."""
    try:
        with open(file_path, "w") as outfile:
            outfile.write(json.dumps(default_data, indent=4))
        return True
    except Exception as e:
        module_logger.error(f'Unexpected Exception Saving file {file_path} - {e}')
        return None


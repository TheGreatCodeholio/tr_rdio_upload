# tr_rdio_uploader

**Version**: `0.0.1`

---

## Overview

`tr_rdio_uploader` is a small command-line utility that:
1. Reads audio call metadata from a `.json` file.
2. Converts a `.wav` recording to `.m4a` format (optionally applying loudness normalization).
3. Archives the original and/or converted audio file(s) to remote or local storage.
4. Uploads call metadata (plus an audio URL) to a configured **RDIO**-compatible endpoint.

---

## Features

- **Command-Line Interface**: Run via `bash
  python main.py -s <short_name> -a <audio_wav_path>
  `
- **Audio Conversion**: Uses ffmpeg to convert from WAV to M4A, supporting optional two-pass loudnorm.
- **Archiving**: Configurable archiving to:
    - Local filesystem
    - SCP (remote server via SSH/SFTP)
    - Google Cloud Storage
    - Amazon S3
- **RDIO Upload**: Sends final call data (including `audio_url`) to your trunk-recorder-call endpoint.
- **Logging**: Logs to both console and a file.

---

## Requirements

1. **Python 3.9+**
2. **`ffmpeg`** in your PATH (for audio conversion).
3. **Pip packages** (like `requests`, `paramiko`, `boto3`, `google-cloud-storage` if using those features).

---

## Installation

1. **Clone or Download** this repository:  
   `bash
   git clone https://github.com/TheGreatCodeholio/tr_rdio_upload.git
   cd tr_rdio_uploader
   `
2. **Install dependencies**:  
   `bash
   pip install -r requirements.txt
   `
3. **Check ffmpeg**:  
   `bash
   ffmpeg -version
   `
   Make sure it prints a valid version.

---

## Configuration

The default configuration file is located at **`./etc/config.json`**. An example:

```jsonc
{
    "log_level": 1,
    "temp_file_path": "/dev/shm",
    "m4a_audio_compression": {
        "enabled": true,
        "sample_rate": 16000,
        "bitrate": 96,
        "normalization": true,
        "use_loudnorm": true,
        "loudnorm_params": {
            "I": -16,
            "TP": -1.5,
            "LRA": 11,
            "linear": "true"
        }
    },
    "archive": {
        "archive_type": "scp",
        "archive_path": "/srv/scanner_audio",
        "archive_extensions": [
            ".wav",
            ".m4a",
            ".json"
        ],
        "google_cloud": {
            "project_id": "my-gcloud-project-id",
            "bucket_name": "my-bucket",
            "credentials_file": "etc/google_cloud.json"
        },
        "aws_s3": {
            "access_key_id": "YOUR_ACCESS_KEY",
            "secret_access_key": "YOUR_SECRET_KEY",
            "bucket_name": "escanner",
            "region": "us-east-1"
        },
        "scp": {
            "host": "my.scpserver.net",
            "port": 22,
            "user": "scpuser",
            "password": "",
            "private_key_path": "id_rsa",
            "base_url": "https://audio.example.com"
        },
        "local": {
            "base_url": "https://example.com/audio"
        }
    },
    "rdio_systems": [
        {
            "enabled": true,
            "system_id": 1,
            "rdio_url": "https://myrdio.server.com/api/trunk-recorder-call-upload",
            "rdio_api_key": "4060a870-accf-40e8-abc4-4e8557ebabd7"
        }
    ]
}
```

### Notable Config Fields
- **`log_level`**: 0 = Debug, 1 = Info, 2 = Warning, etc.
- **`m4a_audio_compression`**: Fine-tunes audio conversion (sample rate, bitrate, normalization).
- **`archive`**: Controls where to store the final files. Set `archive_type` to `scp`, `aws_s3`, `google_cloud`, or `local`. if `local` or `scp` then `archive_path` must be set.
- **`rdio_systems`**: List of endpoints to post final call metadata.

---

## Usage

From the project directory:

`bash
python main.py -s <SYSTEM_SHORT_NAME> -a <PATH_TO_WAV_FILE>
`

Example:

`bash
python main.py -s "bradford-pa" -a "/home/user/audio/12345.wav"
`

---

## Logs & Troubleshooting

- **Log file**: `./log/tr_rdio_uploader.log`
- Common issues:
    - Missing config keys.
    - `ffmpeg` not found.
    - SCP/S3/Google Cloud credentials misconfiguration.
    - Invalid or unreachable RDIO endpoint.

---

## Directory Structure

```
tr_rdio_uploader/
├─ main.py                      # Entry point
├─ etc/
│   └─ config.json             # Default config
├─ log/
│   └─ tr_rdio_uploader.log    # Log file (runtime)
├─ lib/
│   ├─ call_processing_module.py
│   ├─ config_module.py
│   ├─ logging_module.py
│   ├─ rdio_module.py
│   ├─ audio_file_handler.py
│   ├─ archive_module.py
│   └─ ... (other scripts)
└─ requirements.txt (optional)
```

---

## Contributing

1. Fork or create a new branch.
2. Implement your change, add tests if relevant.
3. Submit a pull request describing your changes.

---

## License

This project is published under the **GNU General Public License (GPLv3)**.  
See the header in source code or [GNU website](https://www.gnu.org/licenses/gpl-3.0.en.html) for details.

---

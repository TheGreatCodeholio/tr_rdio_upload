import json
import logging
import os
import re
import shutil
import subprocess

module_logger = logging.getLogger('tr_rdio_uploader.audio_file_module')

def save_temporary_file(tmp_path: str, source_file_path: str) -> None:
    """
    Saves the given source_file_path into tmp_path.

    :param tmp_path: The directory into which the file should be saved.
    :param source_file_path: The path to the file that needs to be copied.
    :return: None
    """
    try:
        # Ensure the directory exists
        os.makedirs(tmp_path, exist_ok=True)

        # Construct the target path
        file_name: str = os.path.basename(source_file_path)
        target_path: str = os.path.join(tmp_path, file_name)

        # Copy the file
        shutil.copy(source_file_path, target_path)

        # Determine label from extension
        _, extension = os.path.splitext(file_name)
        extension = extension.lower()

        if extension == '.wav':
            file_label: str = "<<WAV>>"
        elif extension == '.json':
            file_label = "<<JSON>>"
        else:
            file_label = "<<FILE>>"

        module_logger.debug(f"{file_label} saved successfully at {target_path}")

    except Exception as e:
        module_logger.error(f"Failed to save {file_label} at {target_path}: {e}")
        raise

def load_call_json(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            call_data = json.load(f)
        module_logger.info(f"Loaded <<Call>> <<Metadata>> Successfully")
        return call_data
    except FileNotFoundError:
        module_logger.error(f'<<Call>> <<Metadata>> file {json_file_path} not found.')
        return None
    except json.JSONDecodeError:
        module_logger.error(f'<<Call>> <<Metadata>> file {json_file_path} is not in valid JSON format.')
        return None
    except Exception as e:
        module_logger.error(f"Unexpected <<Error>> while loading <<Call>> <<Metadata>> {json_file_path}: {e}")
        return None

def compress_wav_to_m4a(
        input_wav: str,
        output_m4a: str,
        compression_config: dict
) -> None:
    """
    Compress a WAV file to M4A using ffmpeg with specified settings and optional
    two-pass loudness normalization (EBU R128 via FFmpeg's loudnorm filter).

    :param input_wav:    Path to the input WAV file
    :param output_m4a:   Path to the output M4A file
    :param compression_config:       Dictionary containing compression and normalization config.
                         Example:
                         {
                           "enabled": True,
                           "sample_rate": 16000,
                           "bitrate": 96,
                           "normalization": True,
                           "use_loudnorm": True,
                           "loudnorm_params": {
                               "I": -16.0,
                               "TP": -1.5,
                               "LRA": 11.0
                           }
                         }

    :raises FileNotFoundError: If the input file does not exist.
    :raises EnvironmentError:  If ffmpeg is not installed or not found in PATH.
    :raises subprocess.CalledProcessError: If the ffmpeg command fails.
    """
    if not compression_config.get("enabled", False):
        module_logger.warning("Compression is disabled in config. Skipping conversion.")
        return

    # Check if input file exists
    if not os.path.isfile(input_wav):
        raise FileNotFoundError(f"Input file '{input_wav}' does not exist.")

    # Check ffmpeg availability
    if shutil.which("ffmpeg") is None:
        raise EnvironmentError("ffmpeg is not installed or not found in PATH.")

    sample_rate = compression_config.get("sample_rate", 16000)
    bitrate     = compression_config.get("bitrate", 96)
    normalization = compression_config.get("normalization", False)
    use_loudnorm  = compression_config.get("use_loudnorm", False)

    # If normalization & loudnorm are requested, do two-pass
    if normalization and use_loudnorm:
        loudnorm_params = compression_config.get("loudnorm_params", {})

        loudnorm_defaults = {
            "I":  -16.0,
            "TP": -1.5,
            "LRA": 11.0,
        }
        for k, v in loudnorm_defaults.items():
            loudnorm_params.setdefault(k, v)

        # ---------------------------
        # First Pass: measure stats
        # ---------------------------
        first_pass_filter_parts = [f"{k}={v}" for k, v in loudnorm_params.items()]
        first_pass_filter_str = "loudnorm=" + ":".join(first_pass_filter_parts) + ":print_format=json"

        pass1_command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i", input_wav,
            "-af", first_pass_filter_str,
            "-vn",
            "-sn",
            "-f", "null",
            "-"
        ]

        try:
            pass1_proc = subprocess.run(
                pass1_command,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"First pass ffmpeg command failed. Command: {' '.join(pass1_command)}\n"
                f"Output: {e.output}\nError: {e.stderr}"
            )
            raise subprocess.CalledProcessError(e.returncode, e.cmd, output=error_msg)

        # Parse JSON stats from ffmpeg stderr
        pass1_stderr = pass1_proc.stderr
        match = re.search(r"\{.*?\}", pass1_stderr, flags=re.DOTALL)
        if not match:
            raise ValueError("No loudnorm JSON found in first pass FFmpeg output.")

        stats = json.loads(match.group(0))

        # The 'offset' is sometimes missing from the JSON so we parse it manually if needed
        offset_match = re.search(r"offset\s*:\s*([-\d\.]+)", pass1_stderr)
        offset_val = float(offset_match.group(1)) if offset_match else 0.0

        # ---------------------------------------
        # Second Pass: apply measured stats
        # ---------------------------------------
        second_pass_filter_parts = []

        for k, v in loudnorm_params.items():
            if k.lower() != "print_format":
                second_pass_filter_parts.append(f"{k}={v}")


        second_pass_filter_parts += [
            f"measured_I={stats['input_i']}",
            f"measured_TP={stats['input_tp']}",
            f"measured_LRA={stats['input_lra']}",
            f"measured_thresh={stats['input_thresh']}",
            f"offset={offset_val}",
            "print_format=summary"
        ]
        second_pass_filter_str = "loudnorm=" + ":".join(second_pass_filter_parts)

        pass2_command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i", input_wav,
            "-af", second_pass_filter_str,
            "-ar", str(sample_rate),
            "-c:a", "aac",
            "-b:a", f"{bitrate}k",
            "-vn",
            "-sn",
            output_m4a
        ]

        try:
            completed_process = subprocess.run(
                pass2_command,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Second pass ffmpeg command failed. Command: {' '.join(pass2_command)}\n"
                f"Output: {e.output}\nError: {e.stderr}"
            )
            raise subprocess.CalledProcessError(e.returncode, e.cmd, output=error_msg)

        if completed_process.stdout:
            module_logger.debug(f"ffmpeg output: {completed_process.stdout}")
        if completed_process.stderr:
            module_logger.debug(f"ffmpeg errors: {completed_process.stderr}")

        module_logger.info(f"Successfully compressed '{input_wav}' to '{output_m4a}' with two-pass loudnorm.")

    else:
        # --------------------------------------
        # Single pass (no loudnorm) fallback
        # --------------------------------------
        command = [
            "ffmpeg",
            "-y",
            "-i", input_wav,
            "-ar", str(sample_rate),
            "-c:a", "aac",
            "-b:a", f"{bitrate}k",
            output_m4a
        ]

        try:
            completed_process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"ffmpeg command failed with error code {e.returncode}.\n"
                f"Command: {' '.join(command)}\n"
                f"Output: {e.output}\n"
                f"Error: {e.stderr}"
            )
            raise subprocess.CalledProcessError(e.returncode, e.cmd, output=error_msg)
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred: {e}")

        if completed_process.stdout:
            module_logger.debug(f"ffmpeg output: {completed_process.stdout}")
        if completed_process.stderr:
            module_logger.debug(f"ffmpeg errors: {completed_process.stderr}")

        module_logger.info(f"Successfully compressed '{input_wav}' to '{output_m4a}' without loudnorm.")
import json

import requests
import logging

module_logger = logging.getLogger('tr_rdio_uploader.rdio_uploader')


class TrunkRecorderUploadError(Exception):
    """Custom exception for trunk-recorder call upload failures."""
    pass

def upload_trunk_recorder_call(rdio_data, call_data):
    """
    Send only metadata to the trunk-recorder call upload endpoint.
    Raises TrunkRecorderUploadError with a specific message on failure.
    """
    url = rdio_data["rdio_url"]
    module_logger.info(f'Uploading call to trunk-recorder endpoint: {url}')

    multipart_fields = {
        "key":  (None, rdio_data["rdio_api_key"]),
        "audioUrl": (None, call_data.get("audio_url")),
        "system": (None, rdio_data.get("system_id")),
        "meta": (None, json.dumps(call_data), "application/json")
    }

    try:
        response = requests.post(url, files=multipart_fields, verify=False)
        # This will raise an HTTPError if the status is 4xx or 5xx.
        response.raise_for_status()

        module_logger.info(
            f'Successfully uploaded metadata. '
            f'Status: {response.status_code}, Response: {response.text}'
        )
        return True

    except requests.exceptions.HTTPError as http_err:
        # A 4xx or 5xx error occurred
        error_msg = (f"HTTP error while uploading to {url}. "
                     f"Status code: {response.status_code}, "
                     f"Response text: {response.text}")
        raise TrunkRecorderUploadError(error_msg) from http_err

    except requests.exceptions.RequestException as req_err:
        # Any other network-related error (connection, DNS, timeout, etc.)
        error_msg = f"Request error while uploading to {url}: {req_err}"
        raise TrunkRecorderUploadError(error_msg) from req_err

    except Exception as e:
        # Catch-all for any other unexpected error
        error_msg = f"Unexpected error uploading to {url}: {e}"
        raise TrunkRecorderUploadError(error_msg) from e


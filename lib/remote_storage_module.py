from datetime import datetime, timezone, timedelta
import logging
import mimetypes
import os
import shutil
import time
import traceback
from stat import S_ISDIR
from contextlib import contextmanager
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from urllib.parse import urljoin, quote

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ParamValidationError

from paramiko import SSHClient, AutoAddPolicy, RSAKey, SSHException

module_logger = logging.getLogger('tr_rdio_uploader.file_storage')


def get_archive_class(archive_config):
    if archive_config.get("archive_type") == 'scp':
        return SCPStorage(archive_config.get('scp'))
    elif archive_config.get("archive_type") == 'google_cloud':
        return GoogleCloudStorage(archive_config.get('google_cloud'))
    elif archive_config.get("archive_type") == 'aws_s3':
        return AWSS3Storage(archive_config.get('aws_s3'))
    elif archive_config.get("archive_type") == 'local':
        return LocalStorage(archive_config.get('local'))
    else:
        module_logger.error('Invalid remote storage type.')
        return None


class GoogleCloudStorage:

    def __init__(self, storage_config):
        try:
            self.storage_client = storage.Client.from_service_account_json(
                storage_config['credentials_file'], project=storage_config['project_id'])
            self.bucket_name = storage_config['bucket_name']
            self.bucket = self.storage_client.get_bucket(self.bucket_name)
        except KeyError as e:
            module_logger.error(f"Google Cloud Missing required configuration data: {e}")
        except GoogleCloudError as e:
            module_logger.error(f"Google Cloud Storage error: {e}")

    def upload_file(self, source_file_path, destination_file_path, destination_generated_path, max_attempts=3):
        try:
            if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
                logging.error(f'Source file {source_file_path} does not exist or is not a file.')
                return False

            mime_type, _ = mimetypes.guess_type(source_file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            if self.bucket:
                blob = self.bucket.blob(destination_file_path)

                with open(source_file_path, 'rb') as file:
                    blob.upload_from_file(file, content_type=mime_type)

                blob.make_public()

                return blob.public_url
            else:
                module_logger.warning("Google Storage Bucket is not available.")
                return None
        except GoogleCloudError as e:
            module_logger.error(f"Failed to upload file to Google Cloud Storage: {e}")
            return None


class AWSS3Storage:

    def __init__(self, storage_config):
        try:

            if not storage_config.get("access_key_id", "") or not storage_config.get("secret_access_key",
                                                                                     "") or not storage_config.get(
                'bucket_name', ""):
                module_logger.error(f"AWS S3 Missing required configuration data.")
                return

            self.s3 = boto3.resource(
                's3',
                aws_access_key_id=storage_config.get("access_key_id", ""),
                aws_secret_access_key=storage_config.get("secret_access_key", "")
            )
            self.bucket_name = storage_config.get('bucket_name', "")
            self.bucket = self.s3.Bucket(self.bucket_name)

        except KeyError as e:
            module_logger.error(f"AWS S3 Missing required configuration data: {e}")
        except NoCredentialsError as e:
            module_logger.error(f"Credentials not available for AWS S3: {e}")

    def upload_file(self, source_file_path, destination_file_path, destination_generated_path, max_attempts=3):\

        if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
            logging.error(f'Source file {source_file_path} does not exist or is not a file.')
            return None

        try:
            with open(source_file_path, 'rb') as file:
                self.bucket.put_object(Key=destination_file_path, Body=file)

            self.s3.ObjectAcl(self.bucket_name, destination_file_path).put(ACL='public-read')

            # Encode the basename of the local_audio_path to ensure it's URL-safe
            encoded_file_name = quote(os.path.basename(destination_file_path))

            # First, join the base URL with the current_date
            url_with_date = urljoin(f'https://{self.bucket_name}.s3.amazonaws.com/',
                                    os.path.dirname(destination_file_path) + '/')

            # Then, join the result with the encoded file name
            return urljoin(url_with_date, encoded_file_name)

        except FileNotFoundError:
            module_logger.error(f"Local file {source_file_path} not found.")
            return None
        except (ClientError, ParamValidationError) as e:
            module_logger.error(f"Error uploading file to AWS S3: {e}")
            return None


class SCPStorage:
    def __init__(self, storage_config):
        self.host = storage_config.get("host")
        self.port = storage_config.get("port", 22)
        self.username = storage_config.get("user", "")
        self.password = storage_config.get("password", "")
        self.private_key_path = storage_config.get('private_key_path', "")
        self.base_url = storage_config.get('base_url', "")

    def ensure_destination_directory_exists(self, sftp, destination_directory):
        """Ensure the remote directory structure exists."""
        parts = destination_directory.split("/")
        current_path = ""

        for part in parts[1:]:

            current_path = f'{current_path}/{part}'.replace("\\", "/")

            try:
                sftp.stat(current_path)
            except FileNotFoundError:
                sftp.mkdir(current_path)
                module_logger.debug(f"Created SCP destination path {current_path}")
            except Exception as e:
                traceback.print_exc()
                module_logger.error(f"SCP Unhandled Exception: {e}")

    def upload_file(self, source_file_path, destination_file_path, destination_generated_path, max_attempts=3):
        """Uploads a file to the SCP storage."""

        if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
            module_logger.error(f'Source file {source_file_path} does not exist or is not a file.')
            return False

        for attempt in range(1, max_attempts + 1):
            try:
                with self._create_sftp_session() as (ssh_client, sftp):
                    self.ensure_destination_directory_exists(sftp, os.path.dirname(destination_file_path))

                    sftp.put(source_file_path, destination_file_path)

                    # Encode the basename of the local_audio_path to ensure it's URL-safe
                    encoded_file_name = quote(os.path.basename(destination_file_path))

                    # First, join the base URL with the current_date
                    url_with_date = urljoin(self.base_url + '/', destination_generated_path + '/')

                    # Then, join the result with the encoded file name
                    return urljoin(url_with_date, encoded_file_name)

            except Exception as error:  # Preferably catch more specific exceptions
                traceback.print_exc()
                module_logger.warning(f'Attempt {attempt} failed: {error}')
                if attempt < max_attempts:
                    time.sleep(5)

        module_logger.error(f'All {max_attempts} attempts failed.')
        return False

    @contextmanager
    def _create_sftp_session(self):
        """Creates and manages an SFTP session using context management.

        :return: Yields a tuple of SSH client and SFTP session.
        :raises: FileNotFoundError if private key file doesn't exist.
                  SSHException for other SSH connection errors.
        """
        ssh_client = SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        sftp = None

        try:

            ssh_connect_kwargs = {
                "username": self.username,
                "port": self.port,
                "look_for_keys": False,
                "allow_agent": False
            }

            # Use the private key for authentication if specified
            if self.private_key_path and os.path.exists(self.private_key_path):
                try:
                    private_key = RSAKey.from_private_key_file(self.private_key_path)
                    ssh_connect_kwargs["pkey"] = private_key
                except SSHException as e:
                    module_logger.error(f"Failed to load private key: {e}")
                    if self.password:
                        ssh_connect_kwargs["password"] = self.password

            elif self.password:
                ssh_connect_kwargs["password"] = self.password
            else:
                raise ValueError("No valid authentication method provided.")

            # Connect using either private key, password, or both
            ssh_client.connect(self.host, **ssh_connect_kwargs)

            sftp = ssh_client.open_sftp()
            yield ssh_client, sftp
        except SSHException as e:
            module_logger.error(f'SSH connection error: {e}')
            raise
        finally:
            if sftp:
                sftp.close()
            ssh_client.close()


class LocalStorage:
    def __init__(self, storage_config):
        self.base_url = storage_config.get("base_url", "")

    def ensure_destination_directory_exists(self, destination_directory):
        """Ensure the local directory structure exists."""
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)

    def upload_file(self, source_file_path, destination_file_path, destination_generated_path, max_attempts=None):
        """Copies a file to the local storage with a date-based directory structure."""
        if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
            logging.error(f'Source file {source_file_path} does not exist or is not a file.')
            return False

        try:
            self.ensure_destination_directory_exists(os.path.dirname(destination_file_path))

            shutil.copy(source_file_path, destination_file_path)

            # Encode the basename of the local_audio_path to ensure it's URL-safe
            encoded_file_name = quote(os.path.basename(destination_file_path))

            # First, join the base URL with the current_date
            url_with_date = urljoin(self.base_url + '/', destination_generated_path + '/')

            # Then, join the result with the encoded file name
            return urljoin(url_with_date, encoded_file_name)

        except Exception as error:  # Preferably catch more specific exceptions
            logging.warning(f'Local Archive Failed: {error}')
            return False

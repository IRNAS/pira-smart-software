"""
azure_sync.py

It is a module that controls syncing files between device and its blob storage.

ENV VARS:
    - AZURE_ACCOUNT_NAME
    - AZURE_ACCOUNT_KEY
    - AZURE_CONTAINER_NAME
    - AZURE_DELETE_LOCAL
    - AZURE_DELETE_CLOUD
    - AZURE_LOGGING
    - AZURE_PROTOCOL
    - AZURE_RUN

Tutorials: https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
"""

from __future__ import print_function

import os
import time
import sys
import logging
import requests
from requests.exceptions import ChunkedEncodingError
from datetime import datetime

from os import listdir
from os.path import isfile, join

from azure.storage.blob import BlockBlobService, PublicAccess

# sync folder path on device
sync_folder_path = "/data/"
# subfolders in sync folder - upload to azure only
camera_folder_path = "camera/"
raw_data_folder_path = "raw/"
calculated_data_folder_path = "calculated/"

class Module(object):
    def __init__(self, boot):
        """
        Inits the Azure method for PiRa
        """
        self._boot = boot
        self._enabled = False

        enable_logging = os.environ.get('AZURE_LOGGING', 'off') # enable request logging 
        if enable_logging == 'on':
            logging.basicConfig(format='%(asctime)s %(name)-20s %(levelname)-5s %(message)s', level=logging.INFO)
        azure_protocol = os.environ.get('AZURE_PROTOCOL', 'https')  # protocol to use for requests

        self.module_runs = os.environ.get('AZURE_RUN', 'cont')  # how to run processing loop

        self.ACCOUNT_NAME = os.environ.get('AZURE_ACCOUNT_NAME', None)                  # get azure account name from env var
        self.ACCOUNT_KEY = os.environ.get('AZURE_ACCOUNT_KEY', None)                    # get azure account key from env var
        # Azure Blob Storage container's name cannot exceed 63 characters and must be lowercase
        self.container_name = os.environ.get('AZURE_CONTAINER_NAME', 'azuresync')    # get container name, default is azuresync
        self._local_delete = os.environ.get('AZURE_DELETE_LOCAL', 'off')                # delete local files
        self._azure_delete = os.environ.get('AZURE_DELETE_CLOUD', 'off')                # delete from cloud

        # Check if azure push is correctly configured
        if self.ACCOUNT_NAME is None or self.ACCOUNT_KEY is None:
            print("Azure integration not configured, skipping")
            self._enabled = False
            return

        #print(self.ACCOUNT_NAME)
        #print(self.ACCOUNT_KEY)
        #print(self.container_name)

        try:

            # create object for the servise
            self.block_blob_service = BlockBlobService(account_name=self.ACCOUNT_NAME, account_key=self.ACCOUNT_KEY, protocol=azure_protocol, socket_timeout=30)

            # create our container
            creating_result = self.create_container()
            if creating_result is False:
                return

            # Set the permission so the blobs are public.
            if self.block_blob_service.set_container_acl(self.container_name, public_access=PublicAccess.Container) is None:
                print("Something went from when setting the container")
                return

            # it is set to True -> all okay
            self._enabled = True

            # Azure sync with local sync folder -> get files from server
            local_files = []
            local_files = [f for f in listdir(sync_folder_path) if isfile(join(sync_folder_path, f))]
            # get list of server files - max 100 files, only in root dir
            server_files = []
            generator = self.block_blob_service.list_blobs(self.container_name, num_results=100, timeout=3, delimiter="/")
            for blob in generator:
                # we are syncing only files not our subfolders
                if (camera_folder_path not in blob.name) and (raw_data_folder_path not in blob.name) and (calculated_data_folder_path not in blob.name):
                    server_files.append(blob.name)
            # make list of files that are not on device
            difference = list(set(server_files) - set(local_files))
            # make list of files that are on server and on device
            files_on_both = list(set(server_files) - set(difference))
            # sync files that are on both locations
            for item in files_on_both:
                self.down_update_via_path(item, sync_folder_path)
            # download files that are not on device
            if difference:
                print("Azure: New sync files to download: ")
                print(difference)   
            for item in difference:
                self.download_via_path(item, sync_folder_path)

        except Exception as e:
            print("AZURE ERROR: {}".format(e))
            self._enabled = False
        
    def create_container(self):
        """
        Inits the container under self.container_name name
        """
        try:
            self.block_blob_service.create_container(self.container_name)
            return True
        except Exception as e:
            print("Something went wrong when creating container, error: {}".format(e))
            return False

    def upload_via_path(self, _path, _subfolder):
        """
        It uploads the file to the self.container_name via _path
        _subfolder argument can be None, file then gets uploaded to root of blob storage - which is sync storage
        """
        try:
            # splitting the path and filename
            path, filename = os.path.split(_path)

            # checking if it is valid (will give exception if not valid)
            file = open(_path, 'r')
            file.close()

            # debug
            #print("Uploading from storage file: {} {}".format(path, filename))

            if _subfolder is None:
                _subfolder = ""
            # uploading it
            if self.block_blob_service.create_blob_from_path(self.container_name, _subfolder + filename, _path) is None:
                print("Something went wrong on upload!")
                return False

            # debug
            print("Uploaded: {}".format(filename))
            return True

        except Exception as e:
            print("AZURE upload failed: {}".format(e))
            return False
    
    def download_via_path(self, _filename, _path):
        """
        It downloads file from azure to device, used for on device nonexisting files
        """
        try:
            full_path = os.path.join(_path, _filename)
            self.block_blob_service.get_blob_to_path(self.container_name, _filename, full_path)
        except Exception as e:
            print("AZURE download new file failed: {}".format(e))

    def down_update_via_path(self, _filename, _path):
        """
        It checks when local file was last modified and overwrites it if file on server is more recent
        """
        try:
            # we get local file last modified timestamp in utc
            full_path = os.path.join(_path, _filename)
            stat = os.stat(full_path)
            local_last_modified = datetime.utcfromtimestamp(stat.st_mtime)
            # we get server file last modified timestamp in utc
            blob = self.block_blob_service.get_blob_properties(self.container_name, _filename)
            server_last_modified = blob.properties.last_modified.replace(tzinfo=None)
            # we download the file if on server is newer 
            if server_last_modified > local_last_modified:
                print("Updating local file: {}".format(_filename))
                self.block_blob_service.get_blob_to_path(self.container_name, _filename, full_path)
            
        except Exception as e:
            print("AZURE download sync file failed: {}".format(e))
    
    def up_update_via_path(self, _filename, _path):
        """
        It checks when server file was last modified and overwrittes it if file on device is more recent
        """
        try:
            # we get local file last modified timestamp in utc
            full_path = os.path.join(_path, _filename)
            stat = os.stat(full_path)
            local_last_modified = datetime.utcfromtimestamp(stat.st_mtime)
            # we get server file last modified timestamp in utc
            blob = self.block_blob_service.get_blob_properties(self.container_name, _filename)
            server_last_modified = blob.properties.last_modified.replace(tzinfo=None)
            # we upload the file to azure if on device is newer
            if server_last_modified < local_last_modified:
                print("Updating file on Azure: {}".format(_filename))
                self.block_blob_service.create_blob_from_path(self.container_name, _filename, full_path)
            
        except Exception as e:
            print("AZURE upload sync file failed: {}".format(e))

    def delete_via_container(self, _container_name):
        """
        Deletes the container under _container_name (self.container_name)
        """
        try:
            if self.block_blob_service.delete_container(_container_name) is False:
                print("Something went wrong on delete!")
                return
            print("Deleted: {}".format(_container_name))

        except Exception as e:
            print("AZURE deleting container failed: {}".format(e))

    def upload_only_folder(self, _path):
        """
        It uploads new files to azure blob storage subfolder (specified in _path)
        """
        try:     # Get filenames from server
            old_files = []
            generator = self.block_blob_service.list_blobs(self.container_name, prefix=_path)
            old_files = [blob.name.replace(_path, "") for blob in generator]
            # Check for local files and upload ones not on server
            new_files = []
            full_path_folder = sync_folder_path + _path
            new_files = [f for f in listdir(full_path_folder) if isfile(join(full_path_folder, f))]
            difference = list(set(new_files) - set(old_files))
            if difference:
                #print("Azure: Found new files to upload in folder {}".format(_path))
                #print(difference)
                pass
            for item in difference:
                full_path_item = join(full_path_folder, item)
                self.upload_via_path(full_path_item, _path)
            return True

        except (requests.Timeout, requests.ReadTimeout, ChunkedEncodingError) as e:
            print("Network link too bad, skipping...")
            return False
          
        except Exception as e:
            print("AZURE ERROR: {}".format(e))
            return False
    
    def process(self, modules):
        """
        Process loop for the azure module
        We sync csv files and upload new raw and camera files.
        """
        if self._enabled is False:
            print("WARNING: Skipping Azure module...")
            return
        
        # current process loop flag for upload status
        status_ok = True

        # upload csv files from calculated directory
        local_files = []
        local_files = [f for f in listdir(sync_folder_path + calculated_data_folder_path) if isfile(join(sync_folder_path + calculated_data_folder_path, f))]
        # get list of server files - only in calculated dir
        server_files = []
        generator = self.block_blob_service.list_blobs(self.container_name, prefix=calculated_data_folder_path)
        server_files = [blob.name.replace(calculated_data_folder_path, "") for blob in generator]
        # make list of files that are not on server
        difference = list(set(local_files) - set(server_files))
        # make list of files that are on server and on device
        files_on_both = list(set(local_files) - set(difference))
        # upload newer files to server
        for item in files_on_both:
            server_path_item = join(calculated_data_folder_path, item)
            self.up_update_via_path(server_path_item, sync_folder_path)
        # upload new files
        for item in difference:
            full_path_item = join(sync_folder_path + calculated_data_folder_path, item)
            result = self.upload_via_path(full_path_item, calculated_data_folder_path)
            if result is False and status_ok is True:
                status_ok = False

        # upload new files from subdirectories
        result = self.upload_only_folder(raw_data_folder_path)
        if result is False:
            print("Error when uploading raw data to Azure.")
            status_ok = False
        if 'pira.modules.camera' in modules:
            result = self.upload_only_folder(camera_folder_path)
            if result is False:
                print("Error when uploading camera data to Azure.")
                status_ok = False


        # self-disable upon successful completion if so defined
        if self.module_runs == 'once':
            self._enabled = False
        elif self.module_runs == 'retry' and status_ok is True:
            self._enabled = False

            
    def shutdown(self, modules):
        """
        Shutdown the module
        Local sync folder syncing with Azure -> upload files to server 
        Module can also delete files from device or server if needed (set environmental vars)
        """
        if not self._enabled:
            return

        try:
            # local folder sync with Azure -> upload files to server
            local_files = []
            local_files = [f for f in listdir(sync_folder_path) if isfile(join(sync_folder_path, f))]
            # get list of server files - max 100 files, only in root dir
            server_files = []
            generator = self.block_blob_service.list_blobs(self.container_name, num_results=100, timeout=3, delimiter="/")
            for blob in generator:
                # we are syncing only files not our subfolders
                if (camera_folder_path not in blob.name) and (raw_data_folder_path not in blob.name) and (calculated_data_folder_path not in blob.name):
                    server_files.append(blob.name)
            # make list of files that are not on server
            difference = list(set(local_files) - set(server_files))
            # make list of files that are on server and on device
            files_on_both = list(set(local_files) - set(difference))
            # sync files that are on both locations, except config.json (which is only downloaded)
            if 'config.json' in files_on_both:
                files_on_both.remove('config.json')
            for item in files_on_both:
                self.up_update_via_path(item, sync_folder_path)
            # upload files that are not on server
            if difference:
                # we don't upload config.json at all
                if 'config.json' in difference:
                    files_on_both.remove('config.json')
                print("Azure: New sync files to upload: ")
                print(difference)
            for item in difference:
                full_path_item = join(sync_folder_path, item)
                self.upload_via_path(full_path_item, None)

            # delete files from azure if environ specified
            if self._azure_delete is "on":
                self.delete_via_container(self.container_name)
        
        except Exception as e:
            print("AZURE ERROR: {}".format(e))

         # delete local files
        if self._local_delete is "on":
            for the_file in os.listdir(sync_folder_path):
                file_path = os.path.join(sync_folder_path, the_file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(e)
        pass

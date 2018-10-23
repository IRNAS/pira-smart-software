"""
azure_images.py

It is a module that controls the uploading of the image/s

ENV VARS:
    - AZURE_ACCOUNT_NAME
    - AZURE_ACCOUNT_KEY
    - AZURE_CONTAINER_NAME

Tutorials: https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
"""

from __future__ import print_function

import os
import time
import sys
from datetime import datetime

from os import listdir
from os.path import isfile, join

from azure.storage.blob import BlockBlobService, PublicAccess

# a dummy file to upload
full_path_to_file = "/usr/src/app/docs/logo-irnas.png"
images_path = "/data/camera/"


class Module(object):
    def __init__(self, boot):
        """
        Inits the Azure method for PiRa
        """
        self._boot = boot
        self._enabled = False

        self._new_files = []
        self._old_files = []

        self.ACCOUNT_NAME = os.environ.get('AZURE_ACCOUNT_NAME', None)                  # get azure account name from env var
        self.ACCOUNT_KEY = os.environ.get('AZURE_ACCOUNT_KEY', None)                    # get azure account key from env var
        self.container_name = os.environ.get('AZURE_CONTAINER_NAME', 'ImageExample')    # get container name, default is ImageExample
        self._local_delete = os.environ.get('AZURE_DELETE_LOCAL', 'off')                # delete local images
        self._azure_delete = os.environ.get('AZURE_DELETE_CLOUD', 'off')                # delete images from cloud

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
            self.block_blob_service = BlockBlobService(account_name=self.ACCOUNT_NAME, account_key=self.ACCOUNT_KEY)

            # create our container
            self.create_container()

            # Set the permission so the blobs are public.
            if self.block_blob_service.set_container_acl(self.container_name, public_access=PublicAccess.Container) is None:
                print("Something went from when setting the container")
                return

            # it is set to True -> all okay
            self._enabled = True
        except Exception as e:
            print("AZURE ERROR: {}".format(e))
            self._enabled = False

        if self._local_delete is "on":
            for the_file in os.listdir(images_path):
                file_path = os.path.join(images_path, the_file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(e)

    def create_container(self):
        """
        Inits the container under self.container_name name
        """
        try:
            self.block_blob_service.create_container(self.container_name)
        except Exception as e:
            print("Something went wrong when creating container, error: {}".format(e))
            return

    def upload_via_path(self,_path):
        """
        It uploads the file to the self.container_name via _path
        """

        try:
            # splitting the path and filename
            path, filename = os.path.split(_path)

            # checking if it is valid (will give exception if not valid)
            file = open(_path, 'r')
            file.close()

            # debug
            print("Uploading to storage file: {} {}".format(_path, filename))

            # uploading it
            if self.block_blob_service.create_blob_from_path(self.container_name, filename, _path) is None:
                print("Something went wrong on upload!")
                return

            # debug
            print("Uploaded: {}".format(filename))

        except Exception as e:
            print("AZURE ERROR: {}".format(e))

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
            print("AZURE ERROR: {}".format(e))

    def process(self, modules):
        """
        Process for the azure module
        """
        if self._enabled is False:
            print("WARNING: Azure is not correctly configured, skipping.")
            return

        try:     # Get file names from server
            generator = self.block_blob_service.list_blobs(self.container_name)
            for blob in generator:
                self._old_files.append(blob.name)
            # Check for local files and upload ones not on server
            self._new_files = [f for f in listdir(images_path) if isfile(join(images_path, f))]
            difference = list(set(self._new_files) - set(self._old_files))
            if difference:
                print("Azure: New files to upload: ")
                print(difference)
            for item in difference:
                full_path_item = join(images_path, item)
                self.upload_via_path(full_path_item)
          
        except Exception as e:
            print("AZURE ERROR: {}".format(e))

    def shutdown(self, modules):
        """
        Shutdown (can delete the container if needed)
        """
        if self._azure_delete is "on":
            self.delete_via_container(self.container_name)
        pass

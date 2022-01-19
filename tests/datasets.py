# -*- coding: utf-8 -*-
"""
pysteps.datasets
================

Utilities to download the pysteps data and to create a default pysteps configuration
file pointing to that data.

.. autosummary::
    :toctree: ../generated/

    download_pysteps_data
    create_default_pystepsrc
    info
    load_dataset
"""
import json
import os
import sys
import time
from distutils.dir_util import copy_tree
from logging.handlers import RotatingFileHandler
from urllib import request
from zipfile import ZipFile

from jsmin import jsmin

import pysteps
from pysteps.exceptions import DirectoryNotEmpty

# Include this function here to avoid a dependency on pysteps.__init__.py
def _decode_filesystem_path(path):
    if not isinstance(path, str):
        return path.decode(sys.getfilesystemencoding())
    else:
        return path


class ShowProgress(object):
    """
    Class used to report the download progress.

    Usage::

    >>> from urllib import request
    >>> pbar = ShowProgress()
    >>> request.urlretrieve("http://python.org/", "/tmp/index.html", pbar)
    >>> pbar.end()
    """

    def __init__(self, bar_length=20):
        self.prev_msg_width = 0
        self.init_time = None
        self.total_size = None
        self._progress_bar_length = bar_length

    def _clear_line(self):
        sys.stdout.write("\b" * self.prev_msg_width)
        sys.stdout.write("\r")

    def _print(self, msg):
        self.prev_msg_width = len(msg)
        sys.stdout.write(msg)

    def __call__(self, count, block_size, total_size, exact=True):

        self._clear_line()

        downloaded_size = count * block_size / (1024 ** 2)

        if self.total_size is None and total_size > 0:
            self.total_size = total_size / (1024 ** 2)

        if count == 0:
            self.init_time = time.time()
            progress_msg = ""
        else:
            if self.total_size is not None:
                progress = count * block_size / total_size
                block = int(round(self._progress_bar_length * progress))

                elapsed_time = time.time() - self.init_time
                eta = (elapsed_time / progress - elapsed_time) / 60

                bar_str = "#" * block + "-" * (self._progress_bar_length - block)

                if exact:
                    downloaded_msg = (
                        f"({downloaded_size:.1f} Mb / {self.total_size:.1f} Mb)"
                    )
                else:
                    downloaded_msg = (
                        f"(~{downloaded_size:.0f} Mb/ {self.total_size:.0f} Mb)"
                    )

                progress_msg = (
                    f"Progress: [{bar_str}]"
                    + downloaded_msg
                    + f" - Time left: {int(eta):d}:{int(eta * 60)} [m:s]"
                )

            else:
                progress_msg = (
                    f"Progress: ({downloaded_size:.1f} Mb)" f" - Time left: unknown"
                )

        self._print(progress_msg)

    @staticmethod
    def end(message="Download complete"):
        sys.stdout.write("\n" + message + "\n")


def download_pysteps_data(dir_path, force=True):
    """
    Download pysteps data from github.

    Parameters
    ----------
    dir_path: str
        Path to directory where the psyteps data will be placed.
    force: bool
        If the destination directory exits and force=False, a DirectoryNotEmpty
        exception if raised.
        If force=True, the data will we downloaded in the destination directory and may
        override existing files.
    """

    # Check if directory exists but is not empty
    if os.path.exists(dir_path) and os.path.isdir(dir_path):
        if os.listdir(dir_path) and not force:
            raise DirectoryNotEmpty(
                dir_path + "is not empty.\n"
                "Set force=True force the extraction of the files."
            )
    else:
        os.makedirs(dir_path)

    # NOTE:
    # The http response from github can either contain Content-Length (size of the file)
    # or use chunked Transfer-Encoding.
    # If Transfer-Encoding is chunked, then the Content-Length is not available since
    # the content is dynamically generated and we can't know the length a priori easily.
    pbar = ShowProgress()
    print("Downloading pysteps-data from github.")
    tmp_file_name, _ = request.urlretrieve(
        "https://github.com/pySTEPS/pysteps-data/archive/master.zip",
        reporthook=pbar,
    )
    pbar.end(message="Download complete\n")

    with ZipFile(tmp_file_name, "r") as zip_obj:
        tmp_dir = TemporaryDirectory()

        # Extract all the contents of zip file in the temp directory
        common_path = os.path.commonprefix(zip_obj.namelist())

        zip_obj.extractall(tmp_dir.name)

        copy_tree(os.path.join(tmp_dir.name, common_path), dir_path)


def create_default_pystepsrc(
    pysteps_data_dir, config_dir=None, file_name="pystepsrc", dryrun=False
):
    """
    Create a default configuration file pointing to the pysteps data directory.

    If the configuration file already exists, it will backup the existing file by
    appending the extensions '.1', '.2', up to '.5.' to the filename.
    A maximum of 5 files are kept. .2, up to app.log.5.

    File rotation is implemented for the backup files.
    For example, if the default configuration filename is 'pystepsrc' and the files
    pystepsrc, pystepsrc.1, pystepsrc.2, etc. exist, they are renamed to respectively
    pystepsrc.1, pystepsrc.2, pystepsrc.2, etc. Finally, after the existing files are
    backed up, the new configuration file is written.

    Parameters
    ----------
    pysteps_data_dir: str
        Path to the directory with the pysteps data.
    config_dir: str
        Destination directory for the configuration file.
        Default values: $HOME/.pysteps (unix and Mac OS X)
        or $USERPROFILE/pysteps (windows).
        The directory is created if it does not exists.
    file_name: str
        Configuration file name. `pystepsrc` by default.
    dryrun: bool
        Do not create the parameter file, nor create backups of existing files.
        No changes are made in the file system. It just returns the file path.

    Returns
    -------
    dest_path: str
        Configuration file path.
    """

    pysteps_lib_root = os.path.dirname(_decode_filesystem_path(pysteps.__file__))

    # Load the library built-in configuration file
    with open(os.path.join(pysteps_lib_root, "pystepsrc"), "r") as f:
        rcparams_json = json.loads(jsmin(f.read()))

    for key, value in rcparams_json["data_sources"].items():
        value["root_path"] = os.path.abspath(
            os.path.join(pysteps_data_dir, value["root_path"])
        )

    if config_dir is None:
        home_dir = os.path.expanduser("~")
        if os.name == "nt":
            subdir = "pysteps"
        else:
            subdir = ".pysteps"
        config_dir = os.path.join(home_dir, subdir)

    dest_path = os.path.join(config_dir, file_name)

    if not dryrun:

        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        # Backup existing configuration files if it exists and rotate previous backups
        if os.path.isfile(dest_path):
            RotatingFileHandler(dest_path, backupCount=6).doRollover()

        with open(dest_path, "w") as f:
            json.dump(rcparams_json, f, indent=4)

    return os.path.normpath(dest_path)

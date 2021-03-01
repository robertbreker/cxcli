#!/usr/bin/env python3

import os
import sys

from test_clidriver import services_mock

sys.path.insert(0, os.path.dirname(__file__) + "/../")
import cxcli.syncspecs as syncspecs


def test_reset_synced_specs(mocker):
    unlink = mocker.patch("os.unlink")
    syncspecs.reset_synced_specs()


def test_sync_public_specs(mocker, services_mock):

    syncspecs.sync_public_specs()

#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/../")
import cxcli.syncspecs as syncspecs


def test_reset_all(mocker):
    rmtree = mocker.patch("shutil.rmtree")
    syncspecs.reset_all()
    rmtree.assert_called_once()


def test_sync_all(mocker):
    mocker.patch(
        "cxcli.syncspecs.parse_all_site_data",
        return_value={
            "systemlog": "/explore-more-apis-sdks/cloud-services-platform/systemlog/spec/systemlog.yml"
        },
    )
    syncspecs.sync_all()

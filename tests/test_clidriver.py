#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/../")
import cxcli.clidriver as clidriver
import cxcli.syncspecs as syncspecs


def patch_mocker_systemlog(mocker):
    mocker.patch(
        "cxcli.syncspecs.parse_all_site_data",
        return_value={
            "systemlog": f"{syncspecs.URL}/explore-more-apis-sdks/cloud-services-platform/systemlog/spec/systemlog.yml"
        },
    )


def test_help(mocker):
    patch_mocker_systemlog(mocker)
    mocker.patch("sys.exit")
    sys.argv = "cxcli -h".split()
    rc = clidriver.main()
    assert rc == 0


def test_systemlog_help(mocker):
    patch_mocker_systemlog(mocker)
    mocker.patch("sys.exit")
    sys.argv = "cxcli systemlog -h".split()
    rc = clidriver.main()
    assert rc == 0


def test_systemlog_getrecords(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = "cxcli systemlog GetRecords --limit 2".split()
    rc = clidriver.main()
    assert rc == 0


def test_jmespath(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = 'cxcli systemlog GetRecords --limit 2 --cliquery Items[].Message."en-US"'.split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_yaml(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as yaml".split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_table(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as table".split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_csv(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as csv".split()
    rc = clidriver.main()
    assert rc == 0

def test_output_as_rawprint(mocker):
    patch_mocker_systemlog(mocker)
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as rawprint".split()
    rc = clidriver.main()
    assert rc == 0

def test_main(mocker):
    patch_mocker_systemlog(mocker)
    rc = clidriver.main()
    assert rc == 0

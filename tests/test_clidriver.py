#!/usr/bin/env python3

import os
import sys
import pytest
import pathlib

sys.path.insert(0, os.path.dirname(__file__) + "/../")
import cxcli.clidriver as clidriver
import cxcli.syncspecs as syncspecs


def read_datafile(name):
    currentpath = pathlib.Path(__file__).parent.absolute()
    return open(os.path.join(currentpath, "data", name), "r").read()


@pytest.fixture
def services_mock(mocker, requests_mock):
    # Get fewer specs for faster tests
    mocker.patch.object(
        syncspecs,
        "get_openapi_specs",
        return_value={
            "notifications": f"{syncspecs.URL}/explore-more-apis-sdks/cloud-services-platform/notifications/spec/cc_notifications_auth_published.json",
            "systemlog": f"{syncspecs.URL}/explore-more-apis-sdks/cloud-services-platform/systemlog/spec/systemlog.yml",
        },
    )
    requests_mock.get(
        f"{syncspecs.URL}/explore-more-apis-sdks/cloud-services-platform/notifications/spec/cc_notifications_auth_published.json",
        real_http=True,
    )
    requests_mock.get(
        f"{syncspecs.URL}/explore-more-apis-sdks/cloud-services-platform/systemlog/spec/systemlog.yml",
        real_http=True,
    )

    # Mock the calls that are being made
    requests_mock.get(
        "https://api-us.cloud.com/systemlog/dvintfd45cca/records",
        status_code=200,
        text=read_datafile("systemlog_GetRecords.response"),
    )
    requests_mock.post(
        "https://notifications.citrixworkspacesapi.net/dvintfd45cca/Notifications/Items",
        status_code=200,
        text="{}",
    )
    requests_mock.post(
        "https://api-us.cloud.com/cctrustoauth2/dvintfd45cca/tokens/clients",
        status_code=200,
        text='{"token_type": "bearer", "access_token": "totallysecret", "expires_in": "3600"}',
    )


def test_help(mocker, services_mock):
    mocker.patch("sys.exit")
    sys.argv = "cxcli -h".split()
    rc = clidriver.main()
    assert rc == 0


def test_notifications_help(mocker, services_mock):
    mocker.patch("sys.exit")
    sys.argv = "cxcli notifications -h".split()
    rc = clidriver.main()
    assert rc == 0


def test_systemlog_getrecords(mocker, services_mock):
    sys.argv = "cxcli systemlog GetRecords".split()
    rc = clidriver.main()
    assert rc == 0


def test_notifications_item_create(mocker, services_mock):
    sys.argv = "cxcli notifications Notifications_CreateItems --eventId $(uuidgen) --content".split()
    sys.argv.append(
        """{
            "languageTag": "en-US",
            "title": "Dinner Time",
            "description": "Fish and Chips!"
        }"""
    )
    sys.argv += "--severity Information --destinationAdmin * --component".split()
    sys.argv.append("Citrix Cloud")
    sys.argv += "--priority High --createdDate 2021-02-13T08:20:17.120808-08:00".split()
    rc = clidriver.main()
    assert rc == 0


def test_jmespath(mocker, services_mock):
    sys.argv = 'cxcli systemlog GetRecords --limit 2 --cliquery Items[].Message."en-US"'.split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_yaml(mocker, services_mock):
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as yaml".split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_table(mocker, services_mock):
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as table".split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_csv(mocker, services_mock):
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as csv".split()
    rc = clidriver.main()
    assert rc == 0


def test_output_as_rawprint(mocker, services_mock):
    sys.argv = "cxcli systemlog GetRecords --limit 2 --output-as rawprint".split()
    rc = clidriver.main()
    assert rc == 0


def test_main(mocker, services_mock):
    rc = clidriver.main()
    assert rc == 0

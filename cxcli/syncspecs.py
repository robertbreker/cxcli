import yaml
import json
import os
import requests
import os.path
import errno
import shutil
from rich.progress import track
import concurrent.futures
from urllib.parse import urlparse

URL = "https://developer-data.cloud.com/master"
APISPECPATH = os.path.join(os.path.expanduser("~"), ".cxcli", "apispecs")
METACACHEPATH = os.path.join(APISPECPATH, "metadata.dat")
WORKERCOUNT = 4


def fetch_portal_specs_from_sitedata(sitedata, specsdict={}):
    if isinstance(sitedata, list):
        for item in sitedata:
            specsdict = fetch_portal_specs_from_sitedata(item, specsdict)
    elif isinstance(sitedata, dict):
        if "apis" in sitedata and "title" in sitedata:
            specfilename = (
                sitedata["title"]
                .lower()
                .replace(" ", "")
                .replace("cloudservicesplatform-", "")
            )
            if "/adm/" in sitedata["apis"]:
                specfilename = "adm_" + specfilename
            if specfilename == "exportandimportrestapis":
                specfilename = "microapps"
            elif specfilename == "windowsmanagement":
                specfilename = "wem"
            elif specfilename == "globalappconfigurationservice":
                specfilename = "globalappconfiguration"
            specsdict[specfilename] = URL + sitedata["apis"]
        for _, value in sitedata.items():
            specsdict = fetch_portal_specs_from_sitedata(value, specsdict)
    return specsdict


def fetch_portal_specs():
    req = requests.get(f"{URL}/all_site_data.json")
    req.raise_for_status()
    data = yaml.safe_load(req.content)
    specsdict = fetch_portal_specs_from_sitedata(data)
    return specsdict


def merge_spec(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            merge_spec(value, node)
        else:
            destination[key] = value
    return destination


def reset_synced_specs():
    try:
        for filename in os.listdir(APISPECPATH):
            filepath = os.path.join(APISPECPATH, filename)
            if os.path.isfile(filepath) or os.path.islink(filepath):
                os.unlink(filepath)
    except FileNotFoundError:
        pass


def sync_public_specs():
    make_spec_dir()
    sync_specs(fetch_portal_specs())


def make_spec_dir():
    try:
        os.makedirs(APISPECPATH)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def sync_specs(specdict):
    make_spec_dir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERCOUNT) as executor:
        results = executor.map(sync_specs_single, specdict.items())
        groups = {}
        for result in track(
            results, description="Downloading OpenAPI specs...", total=len(specdict)
        ):
            if result is None:
                continue
            groupname = result["groupname"]
            spec = result["spec"]
            if groupname not in groups:
                groups[groupname] = {}
            groups[groupname] = merge_spec(spec, groups[groupname])
    for groupname, groupspec in groups.items():
        with open(os.path.join(APISPECPATH, groupname), "w+") as fp:
            json.dump(groupspec, fp, indent=2)
    build_metadata()


def sync_specs_single(openapi_spec):
    (apiname, apiurl) = openapi_spec
    if apiname.startswith("adm") and "_" in apiname:
        asplit = apiname.split("_")
        groupname = f"{asplit[0]}_{asplit[1]}.json"
    else:
        groupname = f"{apiname}.json"
    if os.path.exists(os.path.join(APISPECPATH, groupname)):
        # Todo: check age and expire
        return
    response = requests.get(f"{apiurl}")
    if not response.ok:
        print(f"Failed to get {apiname} from {apiurl}")
        return
    if apiurl.endswith(".yaml") or apiurl.endswith(".yml"):
        spec = yaml.safe_load(response.content)
    elif apiurl.endswith(".json") or apiurl.endswith("/swagger/docs/v1"):
        spec = response.json()
    else:
        raise Exception(apiurl)
    if apiname == "microapps":
        # Custom hack for microapps
        params = [
            {"name": "customerid", "in": "path", "required": "true"},
            {"name": "geo", "in": "path", "required": "true"},
        ]
        spec = patch_parameters(spec, params)
    elif apiname == "reportingapi":
        # Custom hack for reportingapi
        params = [
            {"name": "customerid", "in": "path", "required": "true"},
        ]
        spec = patch_parameters(spec, params)
    elif apiname == "wem":
        # Custom hack for wem
        params = [
            {"name": "api", "in": "path", "required": "true"},
        ]
        spec = patch_parameters(spec, params)
    # Fix up openapi files without service host
    if not "host" in spec and ".citrixworkspacesapi.net" in apiurl:
        spec["host"] = urlparse(apiurl).netloc
    return {"groupname": groupname, "spec": spec}


def patch_parameters(spec, add_parameters):
    for pathkey, pathvalue in spec["paths"].items():
        for operationkey, operationvalue in pathvalue.items():
            if "parameters" in operationvalue:
                for add in add_parameters:
                    spec["paths"][pathkey][operationkey]["parameters"].append(add)
    return spec


def build_metadata():
    metacache = {}
    for filename in sorted(os.listdir(APISPECPATH)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(APISPECPATH, filename), "r") as read_file:
            spec = json.load(read_file)
            metacache[filename.replace(".json", "")] = spec["info"]["title"]
    with open(METACACHEPATH, "w") as fp:
        json.dump(metacache, fp, indent=2)

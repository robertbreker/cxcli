import yaml
import json
import os
import requests
import os.path
import errno
import shutil
from rich.progress import track
import concurrent.futures

URL = "https://developer-data.cloud.com/master"
APISPECPATH = os.path.join(os.path.expanduser("~"), ".cxcli", "apispecs")
METACACHEPATH = os.path.join(APISPECPATH, "metacache.dat")
WORKERCOUNT = 4


def parse_all_site_data(data, apis={}):
    if isinstance(data, list):
        for item in data:
            apis = parse_all_site_data(item, apis)
    elif isinstance(data, dict):
        if "apis" in data and "title" in data:
            title = (
                data["title"]
                .lower()
                .replace(" ", "")
                .replace("cloudservicesplatform-", "")
            )
            if "/adm/" in data["apis"]:
                title = "adm_" + title
            if title == "exportandimportrestapis":
                title = "microapps"
            elif title == "windowsmanagement":
                title = "wem"
            elif title == "globalappconfigurationservice":
                title = "globalappconfiguration"
            apis[title] = URL + data["apis"]
        for key, value in data.items():
            apis = parse_all_site_data(value, apis)
    return apis


def get_openapi_specs():
    req = requests.get(f"{URL}/all_site_data.json")
    req.raise_for_status()
    data = yaml.safe_load(req.content)
    apis = parse_all_site_data(data)
    return apis


def mymerge(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            mymerge(value, node)
        else:
            destination[key] = value
    return destination


def reset_all():
    shutil.rmtree(APISPECPATH)


def sync_all():
    mkspecdir()
    sync_specs(get_openapi_specs())


def mkspecdir():
    try:
        os.makedirs(APISPECPATH)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def sync_specs(specs):
    mkspecdir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERCOUNT) as executor:
        results = executor.map(sync_spec_single, specs.items())
        groups = {}
        for result in track(
            results, description="Updating OpenAPI specs...", total=len(specs)
        ):
            if result is None:
                continue
            groupname = result["groupname"]
            spec = result["spec"]
            if groupname not in groups:
                groups[groupname] = {}
            groups[groupname] = mymerge(spec, groups[groupname])
    for groupname, groupspec in groups.items():
        with open(os.path.join(APISPECPATH, groupname), "w+") as fp:
            json.dump(groupspec, fp, indent=2)
    build_metacache()


def sync_spec_single(openapi_spec):
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
    return {"groupname": groupname, "spec": spec}


def build_metacache():
    metacache = {}
    for filename in sorted(os.listdir(APISPECPATH)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(APISPECPATH, filename), "r") as read_file:
            spec = json.load(read_file)
            metacache[filename.replace(".json", "")] = spec["info"]["title"]
    with open(METACACHEPATH, "w") as fp:
        json.dump(metacache, fp, indent=2)


def patch_parameters(spec, add_parameters):
    for pathkey, pathvalue in spec["paths"].items():
        for operationkey, operationvalue in pathvalue.items():
            if "parameters" in operationvalue:
                for add in add_parameters:
                    spec["paths"][pathkey][operationkey]["parameters"].append(add)
    return spec

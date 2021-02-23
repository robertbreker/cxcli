import yaml
import json
import os
import requests
import os.path
import errno
import shutil
from rich.progress import track

URL = "https://developer-data.cloud.com/master"
APISPECPATH = os.path.join(os.path.expanduser("~"), ".cxcli", "apispecs")


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
            apis[title] = data["apis"]
        for key, value in data.items():
            apis = parse_all_site_data(value, apis)
    return apis


def get_openapi_specs():
    path = os.path.join(APISPECPATH, "allspec.dat")
    try:
        with open(path, "r") as f:
            # ToDo: Should expire
            data = yaml.full_load(f)
    except:
        req = requests.get(f"{URL}/all_site_data.json")
        data = yaml.safe_load(req.content)
        with open(path, "w") as f:
            yaml.dump(data, f)
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
    try:
        os.makedirs(APISPECPATH)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    openapi_specs = get_openapi_specs().items()
    groups = {}

    for apiname, apipath in track(
        openapi_specs, description="Updating OpenAPI specs..."
    ):
        if apiname.startswith("adm"):
            asplit = apiname.split("_")
            groupname = f"{asplit[0]}_{asplit[1]}.json"
        else:
            groupname = f"{apiname}.json"
        if os.path.exists(os.path.join(APISPECPATH, groupname)):
            # Todo: check age and expire
            continue
        response = requests.get(f"{URL}{apipath}")
        if not response.ok:
            print(f"Failed to get {apiname} from {URL}{apipath}")
            continue
        if apipath.endswith(".yaml") or apipath.endswith(".yml"):
            spec = yaml.safe_load(response.content)
        elif apipath.endswith(".json"):
            spec = response.json()
        if apiname == "microapps":
            # Custom hack for microapps
            params = [
                {"name": "customerid", "in": "path", "required": "true"},
                {"name": "geo", "in": "path", "required": "true"},
            ]
            spec = patch_parameters(spec, params)
        elif apiname == "reportingapi":
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
        if spec:
            if groupname not in groups:
                groups[groupname] = {}
            groups[groupname] = mymerge(spec, groups[groupname])
    for groupname, groupvalue in groups.items():
        with open(os.path.join(APISPECPATH, groupname), "w+") as fp:
            json.dump(groupvalue, fp, indent=2)
    build_metacache()


def build_metacache():
    metacache = {}
    for filename in sorted(os.listdir(APISPECPATH)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(APISPECPATH, filename), "r") as read_file:
            spec = json.load(read_file)
            metacache[filename.replace(".json", "")] = spec["info"]["title"]
    with open(os.path.join(APISPECPATH, "metacache.dat"), "w") as fp:
        json.dump(metacache, fp, indent=2)


def sync_unpublished(cc_service_urls):
    for service, cc_service_url in track(
        cc_service_urls.items(), description="Updating OpenAPI specs..."
    ):
        if os.path.exists(os.path.join(APISPECPATH, f"{service}.json")):
            # Todo: check age and expire
            continue
        url = f"{cc_service_url}/swagger/docs/v1"
        response = requests.get(f"{url}")
        if not response.ok:
            print(f"Failed to get {url}")
            continue
        spec = response.json()
        spec["host"] = cc_service_url.replace("https://", "")
        with open(os.path.join(APISPECPATH, f"{service}.json"), "w+") as fp:
            json.dump(spec, fp, indent=2)
    build_metacache()


def patch_parameters(spec, add_parameters):
    for pathkey, pathvalue in spec["paths"].items():
        for operationkey, operationvalue in pathvalue.items():
            if "parameters" in operationvalue:
                for add in add_parameters:
                    spec["paths"][pathkey][operationkey]["parameters"].append(add)
    return spec

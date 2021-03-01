import argparse
import json
import logging
import os
import os.path
import time
import urllib.parse

import argcomplete
import jmespath
import keyring
import requests

from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Confirm, Prompt
from rich.table import Table

import csv
import io
import yaml
import re
import sys

from . import syncspecs

console = Console()
log = logging.getLogger()


def prompt_configuration():
    config = get_configuration()
    if not config:
        config = {"clientid": None, "clientsecret": None, "customerid": None}
    while True:
        config["customerid"] = Prompt.ask("CustomerId", default=config["customerid"])
        config["clientid"] = Prompt.ask("ClientId", default=config["clientid"])
        config["clientsecret"] = Prompt.ask(
            "ClientSecret",
            password=True,
            default=config["clientsecret"],
            show_default=False,
        )
        goodcredentials = True
        try:
            console.print("Validating credentials... ", end=None)
            authenticate_api(config, use_cache=False)
            console.print("Success.", style="green")
        except AuthenticationException:
            console.print("Error. Please check the credentials.", style="red")
            goodcredentials = False
        if goodcredentials and Confirm.ask(
            "Please confirm to store this configuration in the OS keying"
        ):
            keyring.set_password("cxcli", ":customerid", config["customerid"])
            keyring.set_password("cxcli", ":clientid", config["clientid"])
            keyring.set_password("cxcli", ":clientsecret", config["clientsecret"])
            # invalidate access_token
            keyring.set_password("cxcli", ":access_token_timestamp", "0")
            console.print("Configuration stored successfully.", style="GREEN")
            break


def use_environ_keys():
    return (
        "CXCUSTOMERID" in os.environ
        and "CXCLIENTID" in os.environ
        and "CXCLIENTSECRET" in os.environ
    )


def get_configuration():
    if use_environ_keys():
        config = {
            "customerid": os.environ["CXCUSTOMERID"],
            "clientid": os.environ["CXCLIENTID"],
            "clientsecret": os.environ["CXCLIENTSECRET"],
        }
    else:
        config = {
            "customerid": keyring.get_password("cxcli", ":customerid"),
            "clientid": keyring.get_password("cxcli", ":clientid"),
            "clientsecret": keyring.get_password("cxcli", ":clientsecret"),
        }
    if (
        config["customerid"] is None
        or config["clientid"] is None
        or config["clientsecret"] is None
    ):
        return None
    return config


def config_logging(level):
    logging.basicConfig(
        level=level, format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
    )


def get_all_services():
    services = {}
    if not os.path.exists(syncspecs.METACACHEPATH):
        # Specs not synced yet, return empty dict
        return services
    with open(syncspecs.METACACHEPATH, "r") as fp:
        metacache = json.load(fp)
    for filename in sorted(os.listdir(syncspecs.APISPECPATH)):
        if not filename.endswith(".json"):
            continue
        service = {}
        service["name"] = filename.split(".", 1)[0]
        namesplit = service["name"].split("_")
        if namesplit[0] in sys.argv and (
            len(namesplit) < 2 or namesplit[1] in sys.argv
        ):
            # Performance Tweak: Only load service JSON-files, when we'll use them
            with open(os.path.join(syncspecs.APISPECPATH, filename), "r") as read_file:
                service["spec"] = json.load(read_file)
            patch_spec(service)
        else:
            try:
                title = metacache[filename.replace(".json", "")]
            except KeyError:
                title = ""
            service["spec"] = {"info": {"title": title}, "paths": {}}
        services[service["name"]] = service
    return services


def patch_spec(service):
    # This function could live in syncspecs to keep the specs slim, but it'd make
    # fixing problems harder... so that's a consideration for the future

    # determine base url
    service["url"] = service["spec"]["host"]
    if "basePath" in service["spec"]:
        service["url"] += service["spec"]["basePath"]

    operationids = list()
    purgepaths = list()
    for path, pathvalue in service["spec"]["paths"].items():
        purgemethods = list()
        for method, methodvalue in pathvalue.items():
            if method not in ("get", "post", "delete", "patch", "put"):
                purgemethods.append(method)
                continue
            # Todo: Try to protect against empty operationIds, like the administrators API
            if "operationId" not in methodvalue:
                if "summary" in methodvalue:
                    methodvalue["operationId"] = re.sub(
                        "[^a-zA-Z ]+", "", methodvalue["summary"]
                    )
                else:
                    log.debug(
                        f"For {service['url']} skipping {path} {method} as there is no operationId"
                    )
                    purgemethods.append(method)
                    continue

            # Skip "ping" operations and operations that indicate that they will only work with ServiceKey
            if "ping" in methodvalue["operationId"].lower() or (
                "summary" in methodvalue
                and "[ServiceKey]" in methodvalue["summary"]
                and "[BearerToken]" not in methodvalue["summary"]
            ):
                purgemethods.append(method)
                continue

            # ToDo: Tweak awkward operationIds, like Microapps', to not contain spaces
            methodvalue["operationId"] = methodvalue["operationId"].replace(" ", "_")

            # ToDo: Work around duplicate operationIds, like in agenthub by renaming
            if methodvalue["operationId"] in operationids:
                counter = 2
                while methodvalue["operationId"] + str(counter) in operationids:
                    counter += 1
                methodvalue["operationId"] = methodvalue["operationId"] + str(counter)
            operationids.append(methodvalue["operationId"])

            # Resolve references in spec
            if "parameters" in methodvalue:
                newparameters = list()
                for parameter in methodvalue["parameters"]:
                    if not should_ignore_parameter(parameter):
                        newparameters.append(
                            resolve_openapi_references(service, parameter)
                        )
                methodvalue["parameters"] = newparameters
        # Purge uneccesary methods
        for method in purgemethods:
            del service["spec"]["paths"][path][method]
        if len(service["spec"]["paths"]) == 0:
            purgepaths.append(path)
    # Purge uneccesary paths
    for path in purgepaths:
        del service["spec"]["paths"][path]
    # Purge unnecessary keys
    if "definitions" in service["spec"]:
        del service["spec"]["definitions"]
    if "parameters" in service["spec"]:
        del service["spec"]["parameters"]


def should_ignore_parameter(parameter):
    return "in" not in parameter or (
        parameter["in"] == "header"
        and parameter["name"]
        in (
            "Authorization",
            "Accept",
            "Accept-Charset",
            "Citrix-TransactionId",
            "X-ActionName",
        )
    )


def populate_argpars_component(alloperations, command_subparsers, component_name):
    help = component_name
    if help == "adm":
        # ToDo:  Hardcoded hack
        help = "Citrix ADM Service"
    command_parser = command_subparsers.add_parser(
        component_name, help=help, description=help
    )
    alloperations[component_name] = {"command_parser": command_parser}
    command_subparser = command_parser.add_subparsers(
        help="Components", dest="commandcomponent"
    )
    return command_subparser


def populate_argpars_service(alloperations, command_subparsers, service, config):
    help = service["spec"]["info"]["title"]
    if "description" in service["spec"]["info"]:
        help = service["spec"]["info"]["description"]
    command_parser = command_subparsers.add_parser(
        service["name"], help=help, description=help
    )
    alloperations[service["originalname"]] = {"command_parser": command_parser}
    command_subparser = command_parser.add_subparsers(help="Operations")
    for path, path_spec in service["spec"]["paths"].items():
        for requesttype, requestspec in path_spec.items():
            populate_argpars_operation(
                alloperations,
                service,
                config,
                command_subparser,
                path,
                requesttype,
                requestspec,
            )


def populate_argpars_operation(
    alloperations, service, config, command_subparser, path, requesttype, requestspec
):
    if "operationId" not in requestspec:
        return
    originalname = service["originalname"]
    operation_id = requestspec["operationId"]

    alloperations[originalname][operation_id] = requestspec
    alloperations[originalname][operation_id]["method"] = requesttype
    alloperations[originalname][operation_id]["url"] = (
        "https://" + service["url"] + path
    )
    help = requestspec["summary"] if "summary" in requestspec else None
    command_parser = command_subparser.add_parser(
        operation_id,
        help=help,
        description=help,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    command_parser.set_defaults(subcommand=operation_id)
    if "parameters" in requestspec:
        for parameter in requestspec["parameters"]:
            populate_argpars_parameter(parameter, config, command_parser)
    group = command_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--output-as",
        help="Try presenting the result in the specified format",
        default="JSON",
        choices=["json", "yaml", "table", "csv", "rawprint"],
        type=str.lower,
    )
    group.add_argument(
        "--output-binary",
        help="Store the result at the provided path",
        type=argparse.FileType("wb", 0),
        metavar="path_to_file",
        default=argparse.SUPPRESS,
    )
    command_parser.add_argument(
        "--cliquery",
        help="Filter the result using JMESPath (See https://jmespath.org/tutorial.html)",
        default=argparse.SUPPRESS,
    )


def populate_argpars_parameter(parameter, config, command_parser):
    required = "required" in parameter and parameter["required"]
    # Where a schema is provided... we query individual schema parameters, instead of top-level parameters
    if "schema" in parameter and "properties" in parameter["schema"]:
        for elementkey, element in parameter["schema"]["properties"].items():
            if not isinstance(element, dict) or not "type" in element:
                continue
            subrequired = (required and "required" not in parameter["schema"]) or (
                "required" in parameter["schema"]
                and elementkey in parameter["schema"]["required"]
            )
            populate_argpars_parameter_element(
                command_parser, subrequired, elementkey, element, config
            )
    else:
        if "schema" in parameter and "type" in parameter["schema"]:
            # ToDo: CVADs spec looks like this
            parameter["type"] = parameter["schema"]["type"]
        populate_argpars_parameter_element(
            command_parser, required, parameter["name"], parameter, config
        )


def populate_argpars_parameter_element(
    command_parser, parent_required, elementkey, element, config
):
    if "type" not in element:
        # Hack
        element["type"] = "string"
    # Don't show None default
    parameter_default = argparse.SUPPRESS

    if element["type"] == "object":
        if "properties" in element:
            for propertykey, propertyvalue in element["properties"].items():
                required = parent_required and (
                    "required" not in element or propertykey in element["required"]
                )
                command_parser.add_argument(
                    f"--{elementkey}-{propertykey}",
                    help=get_help_from_element(propertyvalue),
                    required=required,
                    default=parameter_default,
                )
            return
        else:
            # Interpret object as string, as we don't know what else to do with it
            element["type"] = "string"
    if element["type"] != "boolean" and "enum" in element:
        # True/False enum values are awkward for argparse - try fixing the type for these
        isbool = True
        for aenum in element["enum"]:
            if str(aenum).lower() not in ("true", "false"):
                isbool = False
                break
        if isbool:
            element["type"] = "boolean"
    if element["type"] in ("string", "integer", "number", "file"):
        if config is not None and elementkey.lower() in (
            "customer",
            "customerid",
            "citrix-customerid",
        ):
            # Populate customerid where possible
            parameter_default = config["customerid"]
        elif elementkey == "isCloud":
            # ADM wants this parameter for Cloud hosted instances
            parameter_default = "true"
        choices = element["enum"] if "enum" in element else None
        try:
            command_parser.add_argument(
                f"--{elementkey}",
                help=get_help_from_element(element),
                required=parent_required and parameter_default == argparse.SUPPRESS,
                default=parameter_default,
                choices=choices,
                type=get_parameter_type(element),
            )
        except argparse.ArgumentError as exc:
            log.exception(exc)
            pass
    elif element["type"] == "boolean":
        command_parser.add_argument(
            f"--{elementkey}",
            help=get_help_from_element(element),
            required=parent_required and parameter_default == argparse.SUPPRESS,
            default=parameter_default,
            action="store_true",
        )
    elif element["type"] == "array":
        command_parser.add_argument(
            f"--{elementkey}",
            help=get_help_from_element(element),
            required=parent_required and parameter_default == argparse.SUPPRESS,
            default=parameter_default,
            type=str,
            nargs="+" if parent_required else "*",
        )
    else:
        log.error("Unhanded Type (1): " + element["type"])


def get_parameter_type(element):
    if element["type"] == "string":
        type = str
    elif element["type"] == "integer":
        type = int
    elif element["type"] == "number":
        type = float
    elif element["type"] == "file":
        type = argparse.FileType("rb", 0)
    else:
        raise Exception(f'Unhandled Type (2): {element["type"]}')
    return type


def get_help_from_element(parameter):
    help = None
    if "description" in parameter:
        help = parameter["description"]
    if help is None or len(help.strip()) == 0:
        help = "-"
    return help


def resolve_openapi_references(service, parameter):
    change = True
    while change:
        change = False
        if "$ref" in parameter:
            ref = parameter["$ref"].split("/")[-1]
            parameter = service["spec"]["parameters"][ref]
            change = True
        if "schema" in parameter:
            if "$ref" in parameter["schema"]:
                ref = parameter["schema"]["$ref"].split("/")[-1]
                parameter["schema"] = service["spec"]["definitions"][ref]
                change = True
            if "properties" in parameter["schema"]:
                newproperties = {}
                for propertykey, propertyvalue in parameter["schema"][
                    "properties"
                ].items():
                    if "$ref" in propertyvalue:
                        ref = propertyvalue["$ref"].split("/")[-1]
                        newproperties[propertykey] = service["spec"]["definitions"][ref]
                        change = True
                    else:
                        newproperties[propertykey] = propertyvalue
                parameter["schema"]["properties"] = newproperties
    return parameter


def process_openapi_specs(all_services, alloperations, command_subparsers, config):
    superservice_subparsers = {}
    for service in all_services.values():
        service["originalname"] = service["name"]
        if "_" in service["name"]:
            # The adm service has so many operations, that it seems a good idea
            # to split them up by component
            component_name = service["name"].split("_", 1)[0]
            service["component_name"] = component_name
            if component_name not in superservice_subparsers:
                superservice_subparsers[component_name] = populate_argpars_component(
                    alloperations,
                    command_subparsers,
                    component_name,
                )
            # Strip the superservice name
            service["name"] = service["name"].split("_")[1]
            populate_argpars_service(
                alloperations,
                superservice_subparsers[component_name],
                service,
                config,
            )
        else:
            service["component_name"] = ""
            populate_argpars_service(alloperations, command_subparsers, service, config)


def get_value(atype, aspec, args):
    adict = {}
    for parameter in aspec["parameters"]:
        if "in" not in parameter or parameter["in"] != atype:
            continue
        argname = parameter["name"].replace("-", "_")
        if hasattr(args, argname):
            # It's a simple value
            value = getattr(args, argname)
            if value is not None:
                adict[parameter["name"]] = value
        elif "schema" in parameter and "properties" in parameter["schema"]:
            # It's a more complex structure.. so we need to put a dict together
            for elementkey, element in parameter["schema"]["properties"].items():
                if not isinstance(element, dict):
                    # It's not a complex object - move on
                    break

                if element["type"] == "object":
                    if "properties" in element:
                        adict[elementkey] = {}
                        for propertykey in element["properties"].keys():
                            argname = f"{elementkey}_{propertykey}".replace("-", "_")
                            try:
                                value = getattr(args, argname)
                                if value is not None:
                                    adict[elementkey][propertykey] = value
                            except AttributeError:
                                pass
                elif element["type"] in (
                    "string",
                    "integer",
                    "number",
                    "array",
                    "boolean",
                ):
                    argname = elementkey.replace("-", "_")
                    try:
                        value = getattr(args, argname)
                        if value is not None:
                            if atype == "body" and isinstance(value, list):
                                # ToDo: not sure about doing it this way, but seems neded for Notification post
                                try:
                                    valuelist = value
                                    value = list()
                                    for entry in valuelist:
                                        value.append(json.loads(entry))
                                except json.JSONDecodeError:
                                    pass
                            adict[elementkey] = value
                    except AttributeError:
                        pass
                else:
                    log.error(f"Unhandled element type {element['type']}")
    return adict


class AuthenticationException(Exception):
    pass


def authenticate_api(config, use_cache=True):
    access_token = None
    if not use_environ_keys():
        # Only rely on keyring if environment keys not used
        timestamp = keyring.get_password("cxcli", ":access_token_timestamp")
        if timestamp and int(timestamp) + 59 * 60 > time.time():
            # we can use cached access_tokens for up to 59m
            access_token = keyring.get_password("cxcli", ":access_token")
    if not use_cache or access_token is None:
        # get a fresh access_token
        auth_data = {}
        auth_data["grant_type"] = "client_credentials"
        auth_data["client_id"] = config["clientid"]
        auth_data["client_secret"] = config["clientsecret"]
        headers = get_default_headers()
        headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
        )
        trust_uri = f"https://api-us.cloud.com/cctrustoauth2/{config['customerid']}/tokens/clients"
        response = requests.post(trust_uri, headers=headers, data=auth_data)
        if response.status_code == 200:
            result = response.json()
        else:
            raise AuthenticationException(
                "Failed to authenticate with Citrix Cloud."
                + " Return code: %d" % (response.status_code)
                + response.text
            )
        access_token = result["access_token"]
        if use_cache and not use_environ_keys():
            keyring.set_password("cxcli", ":access_token", access_token)
            keyring.set_password(
                "cxcli", ":access_token_timestamp", str(int(time.time()))
            )
    return {
        "Authorization": ("CwsAuth bearer=%s" % (access_token)),
        "Accept": "application/json",
    }


def tryconvert_result_to_list(inputdict):
    if len(inputdict) < 1:
        return inputdict
    if len(inputdict) == 1:
        # There is only one key in the current response... let's dive in there
        return next(iter(inputdict.values()))
    elif "items" in inputdict:
        return inputdict["items"]
    elif "Items" in inputdict:
        return inputdict["Items"]
    else:
        log.error(
            "Not sure how to convert the result to rows. Falling back to 'rawprint'-mode."
        )
        return None


def generate_table(inputdict):
    adict = tryconvert_result_to_list(inputdict)
    if adict is None:
        return inputdict
    table = Table(show_header=True, header_style="bold magenta")
    if len(adict) == 0:
        table = "Empty response"
    else:
        for key in next(iter(adict)):
            table.add_column(key)
        for row in adict:
            row = map(str, row.values())
            table.add_row(*row)
    return table


def generate_csv(inputdict):
    adict = tryconvert_result_to_list(inputdict)
    if adict is None:
        return inputdict
    if len(adict) == 0:
        return "Empty response"

    output = io.StringIO()
    spamwriter = csv.writer(output, dialect="excel")
    columns = list()
    for key in next(iter(adict)):
        columns.append(key)
    spamwriter.writerow(columns)
    for row in adict:
        row = map(str, row.values())
        spamwriter.writerow(row)
    return output.getvalue()


def main():
    try:
        return _main()
    except KeyboardInterrupt:
        console.print("SIGINT received")
        return 255


def _main():
    parser = argparse.ArgumentParser(description="cxcli - CLI for Citrix Cloud")
    parser.add_argument(
        "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "--configure", help="Configure credentials", action="store_true"
    )
    parser.add_argument(
        "--update-specs",
        help="Update OpenAPI specs and CLI commands",
        action="store_true",
    )
    parser.add_argument(
        "--update-unpublished-specs",
        help=argparse.SUPPRESS,
        action="store_true",
    )
    command_subparsers = parser.add_subparsers(
        dest="command", help="Available Services", metavar=""
    )
    config = get_configuration()
    all_services = get_all_services()
    alloperations = {}
    process_openapi_specs(all_services, alloperations, command_subparsers, config)
    argcomplete.autocomplete(parser)
    args = parser.parse_args(sys.argv[1:])

    # Deal with generic cmd-line options
    config_logging("DEBUG" if args.verbose else "WARNING")
    if (
        args.configure
        or args.update_specs
        or len(all_services) == 0
        or args.update_unpublished_specs
    ):
        if args.configure:
            prompt_configuration()
        if args.update_specs or len(all_services) == 0:
            syncspecs.reset_synced_specs()
            console.print("Preparing API specs. Please wait...")
            syncspecs.sync_public_specs()
            console.print("Done.", style="green")
        if args.update_unpublished_specs:
            console.print("Preparing API specs. Please wait...")
            sync_all_unpublished(config)
            console.print("Done.", style="green")
        return 0

    # Make sure the configuration is place
    if config is None:
        scriptname = os.path.basename(__file__)
        console.print(
            f"Please configure CLI credentials before use: {sys.argv[0]} --configure\n"
            f"Or provide configuration using environment variables: CXCUSTOMERID, CXCLIENTID, and CXCLIENTSECRET",
            style="red",
        )
        return 2

    # Now deal with actual commands
    if not args.command:
        parser.print_help()
    elif not "subcommand" in args:
        if not "commandcomponent" in args or args.commandcomponent is None:
            alloperations[args.command]["command_parser"].print_help()
        else:
            alloperations[f"{args.command}_{args.commandcomponent}"][
                "command_parser"
            ].print_help()
    elif "command" in args and "subcommand" in args:
        return execute_command(alloperations, config, args)
    return 0


def get_default_headers():
    headersdict = requests.utils.default_headers()
    headersdict["User-Agent"] = "cxcli/0.1"
    return headersdict


def sync_all_unpublished(config):
    url = f"https://releasesapi.citrixworkspacesapi.net/{config['customerid']}/releases"
    headersdict = get_default_headers()
    headersdict.update(authenticate_api(get_configuration()))
    response = requests.get(url, headers=headersdict)
    if not response.ok:
        log.error(f"Failure from {url} - {response.status_code}")
        return 2
    cc_service_urls = {}
    for serviceinfo in response.json():
        if (
            serviceinfo["Region"] == "EastUS"
            and serviceinfo["Release"] == "release-a"
            and serviceinfo["Fqdn"].endswith(".citrixworkspacesapi.net")
            and serviceinfo["Service"]
            not in (
                "Console",
                "DemoResourceProvider",
                "Encryption",
                "FasHub",
                "HealthDataStatusManager",
                "MediaStorage",
                "ReleasesProxy",
                "WebRelay",
            )
        ):
            service = serviceinfo["Service"].lower()
            cc_service_urls[service] = f"{serviceinfo['Fqdn']}/swagger/docs/v1"
    # Can't get all services from releaseapi, so add the others too
    for service in (
        "customers",
        "cloudlibrary",
        "cloudlicense",
        "directory",
        "features",
        "healthdatastore",
        "identity",
        "messaging",
        "notifications",
        "partner",
        "registry",
        "serviceprofiles",
        "trust",
    ):
        cc_service_urls[
            service
        ] = f"https://{service}.citrixworkspacesapi.net/swagger/docs/v1"
    syncspecs.sync_specs(cc_service_urls)


def execute_command(alloperations, config, args):
    command_key = args.command
    if "commandcomponent" in args and args.commandcomponent is not None:
        command_key += f"_{args.commandcomponent}"
    aspec = alloperations[command_key][args.subcommand]
    # console.print(aspec)
    pathdict = get_value("path", aspec, args)
    url = aspec["url"]
    for key, value in pathdict.items():
        url = url.replace("{" + key + "}", urllib.parse.quote_plus(value))
    paramsdict = get_value("query", aspec, args)
    headersdict = get_default_headers()
    headersdict.update(get_value("header", aspec, args))
    headersdict.update(authenticate_api(config))
    ajsondict = get_value("body", aspec, args)
    filesdict = get_value("formData", aspec, args)
    log.debug(f"Sent headers: {headersdict}")
    log.debug(f"Sent params: {paramsdict}")
    log.debug(f"Sent body: {ajsondict}")
    response = requests.request(
        aspec["method"],
        url,
        params=paramsdict,
        headers=headersdict,
        json=ajsondict,
        files=filesdict,
    )
    if response.ok:
        log.info(f"Success from {url} - {response.status_code}")
    else:
        log.error(f"Failure from {url} - {response.status_code}")
    if args.verbose:
        headerlog = ""
        for header in response.headers.items():
            (key, value) = header
            headerlog += f"{key}: {value}\n"
        log.debug(f"Received header: {headerlog}")
        log.debug(f"Received body: {response.text}")
    if "output_binary" in args and args.output_binary:
        args.output_binary.write(response.content)
        console.print(f"Wrote result to {args.output_binary.name}.")
    else:
        try:
            responsecontent = response.json()
        except json.decoder.JSONDecodeError as exc:
            logging.info("JSON decoding failed with: " + str(exc))
            responsecontent = response.text

            console.print(responsecontent)
            return 1
        if "cliquery" in args and args.cliquery:
            try:
                responsecontent = jmespath.search(args.cliquery, responsecontent)
            except jmespath.exceptions.ParseError as error:
                log.error("Invalid cliquery syntax - " + str(error))
                return 1
        if "table" == args.output_as:
            console.print(generate_table(responsecontent))
        elif "csv" == args.output_as:
            console.print(generate_csv(responsecontent))
        elif "yaml" == args.output_as:
            console.print(yaml.safe_dump(responsecontent, sort_keys=False))
        elif "json" == args.output_as:
            console.print(json.dumps(responsecontent, indent=2))
        elif "rawprint" == args.output_as:
            console.print(responsecontent)
        else:
            assert ()
    return 0 if response.ok else 255

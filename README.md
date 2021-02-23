# cxcli: Experimental CLI for Citrix Cloud

cxcli is an Experimental CLI for Citrix Cloud.

>**Note:**  Given that this is experimental software, your mileage may vary. The CLI-syntax is not yet finalized and may still change.

The CLI works using the REST APIs of Citrix Cloud, as documented on [Citrix's Developer Portal](https://developer.cloud.com).

<p float="left">
  <img alt="Usage" src="https://user-images.githubusercontent.com/4073077/107159903-da12ca80-698a-11eb-8c38-64d4594178bc.png" width="45%">
  <img alt="Microapps Sample" src="https://user-images.githubusercontent.com/4073077/107159986-4c83aa80-698b-11eb-9cd0-7c2b7873ebab.png" width="45%">
</p>

## Features

- Provides a simple and efficient way to interact with Citrix Cloud
- Supports many Citrix Cloud services including: **adm**, **apppersonalization**, **cvadrestapis**, **globalappconfiguration**, **manageddesktops**, **microapps**, **notifications**, **quickdeploy**, **securebrowser**, **systemlog**, **virtualappsessentialls**, **webhook**, and **wem**.
- Always up-to-date as it synchronizes the latest published [OpenAPI-specifications](https://developer.cloud.com).
- Responses can be formatted as either JSON, YAML, Table, CSV, or binary.
- Powerful query and filter syntax powered by [JMESPath](https://jmespath.org/tutorial.html).
- Handles authentication and caches tokens transparently.
- Secrets are stored using the user's OS keyring service.
- Autocompletion for Bash and Zsh (see [below](#autocomplete-for-bash-and-zsh))

## Installation

cxcli requires Python 3.x. Find more information [here](https://wiki.python.org/moin/BeginnersGuide/Download).

Install cxcli using:

```BASH
python3 -m pip install git+https://github.com/robertbreker/cxcli
```

## Configuration

Once installed, configure cxcli interactively:

```BASH
cxcli --configure
```

Follow the Citrix Cloud Documentation, to [create an API Client](https://developer.cloud.com/getting-started/docs/overview) and obtain the `CustomerId`, `ClientID`, `ClientSecret` required as part of the configuration.

>**Note:** By default, cxcli will store credentials in the user's system keyring service. Alternatively, you can provide the configuration using environment variables `CXCUSTOMERID`, `CXCLIENTID`, and `CXCLIENTSECRET`.

## Usage examples

- Show a list of Cloud Services available via CLI: `cxcli -h`
- Show a list of commands available within a Cloud Service: `cxcli systemlog`
- Extract the latest records from Citrix Cloud's systemlog-service: `cxcli systemlog GetRecords`
- Provide output as YAML: `cxcli systemlog GetRecords --output-as yaml`
- Filter for fields using JMESPath: `cxcli systemlog GetRecords --cliquery 'Items[].Message."en-US"'`
- Filter for values using JMESPath: `cxcli systemlog GetRecords --cliquery 'Items[?ActorDisplayName == "a.bad@m.an"]'`
- Create a notification in Citrix Cloud:

```bash
cxcli --verbose notifications Notifications_Create --eventId $(uuidgen) --content '{
      "languageTag": "en-US",
      "title": "Dinner Time",
      "description": "Fish and Chips!"
   }'  --severity "Information" --destinationAdmin "*" --component "Citrix Cloud" --priority High --createdDate 2021-02-13T08:20:17.120808-08:00
```

- Export and re-import a Microapp integration bundle:

```bash
cxcli microapps export_bundle --geo us --bundleExportType default --integrationExportConfig-id 1 --output-binary integration.mapp
echo '{ "integrationImportConfig": { "type": "GWSC", "baseUrl": "https://service1.com/"} }' > config.txt
cxcli microapps import_bundle --geo us  --config config.txt --bundle integration.mapp
```

## Autocomplete for Bash and Zsh

For **Bash** - add the following snippet to your `~/.bashrc`-file:

```bash
eval "$(register-python-argcomplete cxcli)"
```

For **zsh** - Add the following snippet to your `~/.zshrc`-file:

```bash
autoload bashcompinit
bashcompinit
eval "$(register-python-argcomplete cxcli)"
```

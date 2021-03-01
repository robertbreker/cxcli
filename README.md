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
python3 -m pip install cxcli
```

## Configuration

Once installed, configure cxcli interactively:

```BASH
cx --configure
```

Follow the Citrix Cloud Documentation, to [create an API Client](https://developer.cloud.com/getting-started/docs/overview) and obtain the `CustomerId`, `ClientID`, `ClientSecret` required as part of the configuration.

>**Note:**
> By default, cxcli will store credentials in the user's system keyring service (Windows Credential Locker, macOS Keychain, KDE KWallet, FreeDesktop Secret Service). Should your environment not have a keyring service, or every keyring access require a keyring password, you can provide the configuration alternatively using environment variables `CXCUSTOMERID`, `CXCLIENTID`, and `CXCLIENTSECRET`.

## Usage examples

- Show a list of Cloud Services available via CLI: `cx -h`
- Show a list of commands available within a Cloud Service: `cx systemlog`
- Extract the latest records from Citrix Cloud's systemlog-service: `cx systemlog GetRecords`
- Provide output as YAML: `cxcli systemlog GetRecords --output-as yaml`
- Filter for fields using JMESPath: `cx systemlog GetRecords --cliquery 'Items[].Message."en-US"'`
- Filter for values using JMESPath: `cx systemlog GetRecords --cliquery 'Items[?ActorDisplayName == "a.bad@m.an"]'`
- Create an Administrator notification in Citrix Cloud:

```bash
cx notifications Notifications_CreateItems --eventId $(uuidgen) --content '{
      "languageTag": "en-US",
      "title": "Dinner Time",
      "description": "Fish and Chips!"
   }'  --severity "Information" --destinationAdmin "*" --component "Citrix Cloud" --priority High --createdDate 2021-02-13T08:20:17.120808-08:00
```

- Export a Microapp integration bundle as a backup:

```bash
cx microapps export_bundle --geo us --bundleExportType default --integrationExportConfig-id 1 --output-binary integration.mapp
```

- Re-importing the Microapp integration bundle, providing the necessary base configuration:

```bash
echo '{ "integrationImportConfig": { "type": "GWSC", "baseUrl": "https://mybaseurl/"} }' > config.txt
cx microapps import_bundle --geo us  --config config.txt --bundle integration.mapp
```

## Autocomplete for Bash and Zsh

For **Bash** - add the following snippet to your `~/.bashrc`-file:

```bash
eval "$(register-python-argcomplete cx)"
```

For **zsh** - Add the following snippet to your `~/.zshrc`-file:

```bash
autoload bashcompinit
bashcompinit
eval "$(register-python-argcomplete cx)"
```

'''
Loads dynamic config variables, as well as stores static variables


'''
from configparser import ConfigParser, ParsingError
import os
from logging import getLogger
import pathlib

log = getLogger("fs_bot")

class ConfigError(Exception):
    """
    Raised when an error occur while reading the config file.

    :param msg: Error message.
    """
    def __init__(self, msg: str):
        self.message = "Error in config file: " + msg
        super().__init__(self.message)


## Static Parameters

name_regex = r"^[ -■]{1,32}$"

JAEGER_CALENDAR_URL = "https://docs.google.com/spreadsheets/d/1eA4ybkAiz-nv_mPxu_laL504nwTDmc-9GnsojnTiSRE/edit#gid" \
                      "=38315545 "

#: Dictionary to retrieve faction name by id.
factions = {
    1: "VS",
    2: "NC",
    3: "TR"
}

#: Dictionary to retrieve faction id by name.
i_factions = {v: k for k, v in factions.items()}

# http://census.daybreakgames.com/get/ps2:v2/zone?c:limit=100
#: Dictionary to retrieve zone name by id.
zones = {2: "Indar",
         4: "Hossin",
         6: "Amerish",
         8: "Esamir",
         344: "Oshur"}

## Dynamic Variables, from .ini

GAPI_SERVICE = ""

# General
general = {
    "token": "",
    "api_key": "",
    "rules_msg_id": "",
    "guild_id": ""
}

emojis = {
    "VS": "",
    "NC": "",
    "TR": ""
}

# Discord Channel ID's
channels = {
    "dashboard": "",
    "lobby": "",
    "register": "",
    "rules": "",
    "staff": "",
    "logs": "",
    "usage": "",
    "content-plug": ""
}

# Discord Role ID's
roles = {
    "admin": "",
    "mod": "",
    "app_admin": "",
    "registered": "",
    "view_channels": ""


}

# Database Collections
_collections = {
    "users": "",
    "user_stats": "",
    "matches": "",
    "accounts": "",
    "account_usages": "",
    "restart_data": ""
}

# Stored Data Config
database = {
    "accounts_id": "",
    "accounts_sheet_name": "",
    "url": "",
    "cluster": "",
    "collections": _collections
}


def get_config(config_path):
    global GAPI_SERVICE
    GAPI_SERVICE = f'{pathlib.Path(__file__).parent.absolute()}/../service_account.json'

    file = f'{pathlib.Path(__file__).parent.absolute()}/../{config_path}'

    if not os.path.isfile(file):
        raise ConfigError(f"{file} not found!")
    print(file)
    log.info('Loaded config from file: %s', file)

    config = ConfigParser()
    try:
        config.read(file)
    except ParsingError as e:
        raise ConfigError(f"Parsing Error in '{file}'\n{e}")

    # General Section
    _check_section(config, 'General', file)
    for key in general:
        try:
            general[key] = int(config['General'][key])
        except KeyError:
            _error_missing(key, 'General', file)
        except ValueError:
            general[key] = (config['General'][key])

    # Emojis Section
    _check_section(config, 'Emojis', file)
    for key in emojis:
        try:
            emojis[key] = config['Emojis'][key]
        except KeyError:
            _error_missing(key, 'Emojis', file)

    # Channels Section
    _check_section(config, 'Channels', file)
    for key in channels:
        try:
            channels[key] = int(config['Channels'][key])
        except KeyError:
            _error_missing(key, 'Channels', file)
        except ValueError:
            _error_incorrect(key, 'Channels', file)

    # Roles Section
    _check_section(config, 'Roles', file)
    for key in roles:
        try:
            roles[key] = int(config['Roles'][key])
        except KeyError:
            _error_missing(key, 'Roles', file)
        except ValueError:
            _error_incorrect(key, 'Roles', file)

    # Collections Section
    _check_section(config, 'Collections', file)
    for key in _collections:
        try:
            _collections[key] = config['Collections'][key]
        except KeyError:
            _error_incorrect(key, 'Collections', file)

    # Database Section
    _check_section(config, 'Database', file)
    for key in database:
        if key != "collections":
            try:
                database[key] = config['Database'][key]
            except KeyError:
                _error_incorrect(key, 'Database', file)


def _check_section(config, section, file):
    if section not in config:
        raise ConfigError(f"Missing section '{section}' in '{file}'")


def _error_missing(field, section, file):
    raise ConfigError(f"Missing field '{field}' in '{section}' in '{file}'")


def _error_incorrect(field, section, file):
    raise ConfigError(f"Incorrect field '{field}' in '{section}' in '{file}'")










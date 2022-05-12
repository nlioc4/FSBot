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

JAEGER_CALENDAR_URL = "https://docs.google.com/spreadsheets/d/1eA4ybkAiz-nv_mPxu_laL504nwTDmc-9GnsojnTiSRE/edit#gid=38315545"

## Dynamic Variables, from .ini

GAPI_SERVICE = ""

# General
general = {
    "token": "",
    "api_key": "",
    "command_prefix": "",
    "rules_msg_id": "",
    "guild_id": ""
}

# Discord Channel ID's
channels = {
    "dashboard": "",
    "lobby": "",
    "register": "",
    "rules": "",
    "staff": "",
    "spam": "",
    "usage": "",
    "content-plug": ""
}

# Discord Role ID's
roles = {
    "admin": "",
    "mod": "",
    "registered": ""
}

# Stored Data Config
database = {
    "accounts_id": "",
    "accounts_sheet_name": ""
}

def get_config():
    global GAPI_SERVICE
    GAPI_SERVICE = f'{pathlib.Path(__file__).parent.absolute()}\..\service_account.json'

    file = f'{pathlib.Path(__file__).parent.absolute()}\..\config.ini'

    if not os.path.isfile(file):
        raise ConfigError(f"{file} not found!")

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

    # Channels Section
    _check_section(config, 'Channels', file)
    for key in channels:
        channels[key] = int(config['Channels'][key])

    # Roles Section
    _check_section(config, 'Roles', file)
    for key in roles:
        roles[key] = int(config['Roles'][key])

    # Database Section
    _check_section(config, 'Database', file)
    for key in database:
        database[key] = config['Database'][key]



def _check_section(config, section, file):
    if section not in config:
        raise ConfigError(f"Missing section '{section}' in '{file}'")


def _error_missing(field, section, file):
    raise ConfigError(f"Missing field '{field}' in '{section}' in '{file}'")


def _error_incorrect(field, section, file):
    raise ConfigError(f"Incorrect field '{field}' in '{section}' in '{file}'")










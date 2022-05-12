'''
Loads dynamic config variables, as well as stores static variables


'''
from configparser import ConfigParser, ParsingError
import os
from logging import getLogger
import pathlib

log = getLogger("fs_bot")

## Static Variables

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

    config = ConfigParser()
    config.read(file)

    # General Section
    for key in general:
        try:
            general[key] = int(config['General'][key])
        except ValueError:
            general[key] = (config['General'][key])

    # Channels Section
    for key in channels:
        channels[key] = int(config['Channels'][key])

    # Roles Section
    for key in roles:
        roles[key] = int(config['Roles'][key])

    # Database Section
    for key in database:
        database[key] = config['Database'][key]














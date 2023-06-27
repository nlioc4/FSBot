"""utility functions, some from pogbot"""

from datetime import datetime as dt
from typing import Literal
from enum import Enum
import aiohttp

import discord

from logging import getLogger

log = getLogger("fs_bot")

# Timezones and their offset from UTC in seconds
TZ_OFFSETS = {
    "PST": -28800,
    "PDT": -25200,
    "MDT": -21600,
    "CDT": -18000,
    "EST": -18000,
    "EDT": -14400,
    "UTC": 0,
    "BST": +3600,
    "CEST": +7200,
    "MSK": +10800,
    "CST": +28800,
    "AEST": +36000,

}


# def tz_discord_options():
#     return [discord.OptionChoice(name=f"{abv}: UTC{(offset // 3600):+}", value=abv)
#             for abv, offset in TZ_OFFSETS.items()]

def pytz_discord_options():
    return [discord.OptionChoice("UTC"),
            discord.OptionChoice("Pacific NA", "US/Pacific"),
            discord.OptionChoice("Eastern NA", "US/Eastern"),
            discord.OptionChoice("Western European", "WET"),
            discord.OptionChoice("Central European", "CET"),
            discord.OptionChoice("Eastern European", "EST")
            ]


class UnexpectedError(Exception):
    def __init__(self, msg):
        self.reason = msg
        message = "Encountered unexpected error: " + msg
        log.error(message)
        super().__init__(message)


class AutoNumber(Enum):
    def __new__(cls, *args):
        rank = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._rank = rank
        return obj


def timestamp_now():
    return int(dt.timestamp(dt.now()))


def compare_embeds(embed1, embed2) -> bool:
    """Compares embeds (after removing timestamps).  Returns True if Embeds are identical"""
    try:
        embed1dict, embed2dict = embed1.to_dict(), embed2.to_dict()
    except AttributeError:  # case for one of the entries being None / not an embed
        return False
    del embed1dict['timestamp'], embed2dict['timestamp']
    return embed1dict == embed2dict


def format_time_from_stamp(timestamp: int, type_str: Literal["f", "F", "d", "D", "t", "T", "R"] = "t") -> str:
    """converts a timestamp into a time formatted for discord.
    type indicates what format will be used, options are
    t| 22:57 |Short Time **default
    T| 22:57:58 |Long Time
    d| 17/05/2016| Short Date
    D| 17 May 2016 |Long Date
    f| 17 May 2016 22:57 |Short Date Time
    F| Tuesday, 17 May 2016 22:57 |Long Date Time
    R| 5 years ago| Relative Time
    """
    return f"<t:{int(timestamp)}:{type_str}>"


def time_diff(timestamp):
    lead = timestamp_now() - timestamp
    if lead < 60:
        lead_str = f"{lead} second"
    elif lead < 3600:
        lead //= 60
        lead_str = f"{lead} minute"
    elif lead < 86400:
        lead //= 3600
        lead_str = f"{lead} hour"
    elif lead < 604800:
        lead //= 86400
        lead_str = f"{lead} day"
    elif lead < 2419200:
        lead //= 604800
        lead_str = f"{lead} week"
    else:
        lead //= 2419200
        lead_str = f"{lead} month"
    if lead > 1:
        return lead_str + "s"
    else:
        return lead_str


def time_calculator(arg: str):
    if arg.endswith(('m', 'month', 'months')):
        time = 2419200
    elif arg.endswith(('w', 'week', 'weeks')):
        time = 604800
    elif arg.endswith(('d', 'day', 'days')):
        time = 86400
    elif arg.endswith(('h', 'hour', 'hours')):
        time = 3600
    elif arg.endswith(('min', 'mins', 'minute', 'minutes')):
        time = 60
    else:
        return 0

    num = ""
    for c in arg:
        if ord('0') <= ord(c) <= ord('9'):
            num += c
        else:
            break

    try:
        time *= int(num)
        if time == 0:
            return 0
    except ValueError:
        return 0

    return time


class AutoDict(dict):
    def auto_add(self, key, value):
        if key in self:
            self[key] += value
        else:
            self[key] = value


async def download_image(url: str):
    """downloads an image from url and returns the bytes"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.read()

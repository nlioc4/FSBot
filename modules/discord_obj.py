"""
Handles interactions with commonly used discord objects, and role updates
"""


#  External Imports
from typing import Union

import discord

# Internal Imports
import modules.config as cfg
import classes.players

# Bot and guild global variables
bot = None
guild = None


# Dicts containing role and channel objects
roles: dict[str, discord.Role] = {}
channels: dict[str, Union[discord.TextChannel, discord.VoiceChannel]] = {}


def init(client):
    global bot
    global guild
    bot = client
    guild = bot.get_guild(cfg.general['guild_id'])
    if guild is None:
        raise ValueError("Could not load discord guild object")

    for role in cfg.roles:
        roles[role] = guild.get_role(cfg.roles[role])
    print("Initialized Roles:", [role.name for role in roles.values()])
    for channel in cfg.channels:
        channels[channel] = guild.get_channel(cfg.channels[channel])
    print("Initialized Channels:", [channel.name for channel in channels.values()])


def is_admin(user: discord.Member) -> bool:
    """Simple check for admin permissions, returns True if passed"""
    if any(roles['admin'], roles['mod'], roles['app_admin']) in user.roles:
        return True
    else:
        return False

def is_player(user: discord.Member) -> bool:
    """Simple check if a user is a player, returns True if passed"""
    if classes.Player.get(user.id):
        return True
    else:
        return False



"""
Handles interactions with commonly used discord objects, and role updates
"""


#  External Imports
from typing import Union

import discord

# Internal Imports
import modules.config as cfg
import classes.players
from display import AllStrings as disp

# Bot and guild global variables
bot: discord.Bot | None = None
guild: discord.Guild | None = None
colin: discord.Member | None = None

# Dicts containing role and channel objects
roles: dict[str, discord.Role] = {}
channels: dict[str, Union[discord.TextChannel, discord.VoiceChannel]] = {}
categories = {'user': None, 'admin': None}


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

    categories['user'] = channels['dashboard'].category
    categories['admin'] = channels['staff'].category
    global colin
    colin = guild.get_member(123702146247032834)


def is_admin(member: discord.Member) -> bool:
    """Simple check for admin permissions, returns True if admin"""
    admin_roles = [roles['admin'], roles['mod'], roles['app_admin']]
    if any([role in admin_roles for role in member.roles]):
        return True
    else:
        return False


def is_player(user: discord.Member) -> bool:
    """Simple check if a user is a player, returns True if passed"""
    if classes.Player.get(user.id):
        return True
    else:
        return False


async def is_registered(ctx, user: discord.Member | discord.User | classes.Player) -> bool:
    """Checks if a user is a registered player, returns True if passed and sends a response if not."""
    player = classes.Player.get(user.id)
    if player.is_registered:
        return True
    else:
        await disp.NOT_REGISTERED.send_priv(ctx, user.mention, channels['register'].mention)
        return False


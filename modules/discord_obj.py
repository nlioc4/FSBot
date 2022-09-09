"""
Handles interactions with commonly used discord objects, and role updates
"""

#  External Imports
from typing import Union
from logging import getLogger

import discord

# Internal Imports
import modules.config as cfg
import classes.players
from display import AllStrings as disp

log = getLogger('fs_bot')

# Bot and guild global variables
bot: discord.Bot | None = None
guild: discord.Guild | None = None
colin: discord.Member | None = None

# Dicts containing role and channel objects
roles: dict[str, discord.Role] = {}
channels: dict[str, Union[discord.TextChannel, discord.VoiceChannel]] = {}
categories: dict[str, discord.CategoryChannel | None] = {'user': None, 'admin': None}


def init(client):
    global bot
    global guild
    bot = client
    guild = bot.get_guild(cfg.general['guild_id'])
    if guild is None:
        raise ValueError("Could not load discord guild object")

    for role in cfg.roles:
        roles[role] = guild.get_role(cfg.roles[role])
        if not roles[role]:
            raise KeyError(f'Missing Discord Role for {role}')
    log.info("Initialized Roles: %s", {role_name: role.name for role_name, role in roles.items()})
    for channel in cfg.channels:
        channels[channel] = guild.get_channel(cfg.channels[channel])
        if not channels[channel]:
            raise KeyError(f'Missing Discord Channel for {channel}')
    log.info("Initialized Channels: %s", {channel_name: channel.name for channel_name, channel in channels.items()})

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


def is_player(user: discord.Member | discord.User) -> classes.Player | bool:
    """Simple check if a user is a player, returns Player if passed"""
    p = classes.Player.get(user.id)
    if p:
        return p
    else:
        return False


def is_timeout(user: discord.Member | discord.User) -> bool | int:
    """Simple check if a user is timed out, returns timeout until stamp if True
    Also returns false if user is not a player."""
    p = classes.Player.get(user.id)
    if p:
        if p.is_timeout:
            return p.timeout_until
    return False


async def is_registered(ctx, user: discord.Member | discord.User | classes.Player) -> bool:
    """Checks if a user is a registered player, returns True if passed and sends a response if not."""
    player = classes.Player.get(user.id)
    if player.is_registered:
        return True
    else:
        await disp.NOT_REGISTERED.send_priv(ctx, user.mention, channels['register'].mention)
        return False


async def d_log(message: str = '', source: str = '', error=None) -> bool:
    """Utility function to send logs to #logs channel"""
    if error:
        log.error(f"{source + ': ' if source else ''}{message}", exc_info=error)
        return True if await disp.LOG_ERROR.send(channels['logs'], source, message, error) else False
    log.warning(f"{source + ': ' if source else ''}{message}")
    return await disp.LOG_GENERAL.send(channels['logs'], message, error)


async def role_update(member: discord.Member = None, player: classes.Player = None, reason="FSBot Role Update"):
    """Takes either a member or a player checks what roles they should have"""
    member = member or await guild.get_member(player.id)
    p = player or is_player(member)
    if not p and not member:
        raise ValueError("No args in role_update")
    current_roles = member.roles
    roles_to_add = []
    roles_to_remove = []

    if p and not p.hidden and roles['view_channels'] not in current_roles:
        roles_to_add.append(roles['view_channels'])
    elif p and p.hidden and roles['view_channels'] in current_roles:
        roles_to_remove.append(roles['view_channels'])
    elif not p and roles['view_channels'] in current_roles:
        roles_to_remove.append(roles['view_channels'])

    if p:
        if p.is_timeout and roles['timeout'] not in current_roles:
            roles_to_add.append(roles['timeout'])
        elif not p.is_timeout and roles['timeout'] in current_roles:
            roles_to_remove.append(roles['timeout'])

    if roles_to_add:
        await member.add_roles(*roles_to_add, reason=reason)
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason=reason)

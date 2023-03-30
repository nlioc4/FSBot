"""
Handles interactions with commonly used discord objects, and role updates
"""

#  External Imports
from typing import Union
from logging import getLogger
import sys

import asyncio
import discord

# Internal Imports
import modules.config as cfg
import classes.players
from classes import Player
from modules import tools, accounts_handler as accounts
from modules.tools import UnexpectedError
from display import AllStrings as disp, views

log = getLogger('fs_bot')

# Bot and guild global variables
bot: discord.Bot | None = None
guild: discord.Guild | None = None
loaded: asyncio.Event = asyncio.Event()
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
    colin = guild.get_member(123702146247032834) # For pinging myself
    loaded.set()


def is_admin(user: discord.Member | discord.User) -> bool:
    """Simple check for admin permissions, returns True if admin"""
    member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
    if not member:
        return False
    admin_roles = [roles['admin'], roles['mod'], roles['app_admin']]
    if any([role in admin_roles for role in member.roles]):
        return True
    else:
        return False


def is_player(user: discord.Member | discord.User) -> classes.Player | bool:
    """Simple check if a user is a player, returns Player if passed"""
    if p := classes.Player.get(user.id):
        return p
    return False


def is_timeout(user: discord.Member | discord.User) -> bool | int:
    """Simple check if a user is timed out, returns timeout until stamp if True
    Also returns false if user is not a player."""
    if p := classes.Player.get(user.id):
        if p.is_timeout:
            return p.timeout_until
    return False


async def is_timeout_check(ctx) -> bool | int:
    """Check for commands if player is timed out. returns timeout until stamp if True and sends message to user.
        Also returns false if user is not a player.
        """
    if stamp := is_timeout(ctx.user):
        await disp.DISABLED_PLAYER.send_priv(ctx)
    return stamp


async def is_registered(ctx, user: discord.Member | discord.User | classes.Player) -> bool | classes.Player:
    """Checks if a user is a registered player, returns Player if passed and sends a response if not."""
    if (player := is_player(user)) and player.is_registered:
        return player
    elif ctx.user.id == user.id:
        await disp.NOT_REGISTERED.send_priv(ctx, user.mention, channels['register'].mention)
    else:
        await disp.NOT_REGISTERED_2.send_priv(ctx, user.mention)
    return False


async def d_log(message: str = '', source: str = '', error=None) -> bool:
    """Utility function to send logs to #logs channel and fsbot Log"""
    if error:
        msg = await disp.LOG_ERROR.send(channels['logs'], source, message, error, ping=roles['app_admin'])
        log.error(msg.clean_content, exc_info=error)
        return msg

    msg = await disp.LOG_GENERAL.send(channels['logs'], message, error)
    log.info(msg.clean_content)
    return msg


async def role_update(member: discord.Member = None, player: classes.Player = None, reason="FSBot Role Update"):
    """Takes either a member or a player checks what roles they should have"""
    member = member or guild.get_member(player.id)
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


# Maybe this should be in the Player class
async def timeout_player(p: Player, stamp: int, mod: discord.Member = None, reason: str = ''):
    """Timeout a player until a given timestamp, by a certain mod, with a reason"""
    p_memb = guild.get_member(p.id)
    update_stamp = tools.format_time_from_stamp(tools.timestamp_now(), "f")
    formatted_stamp = tools.format_time_from_stamp(stamp, 'f')

    if stamp == 0:  # reset timeout
        old_msg = await p_memb.fetch_message(p.timeout_msg_id)
        await asyncio.gather(
            p.set_timeout(stamp),
            disp.TIMEOUT_DM_UPDATE_R.edit(old_msg, old_msg.content, update_stamp, view=False),
            role_update(p_memb, p, reason='Player requested freedom' if not mod else f'Timeout removed by {mod.name}'),
        )
        if mod:
            await disp.TIMEOUT_DM_REMOVED.send(p_memb, mod.mention)
        await d_log(message=disp.TIMEOUT_CLEAR(p.mention, p.name), source=mod.name if mod else None)
        return True

    elif p.timeout_msg_id:
        old_msg = await p_memb.fetch_message(p.timeout_msg_id)
        await p.set_timeout(stamp, timeout_msg_id=p.timeout_msg_id, reason=reason, mod_id=mod.id)
        await disp.TIMEOUT_DM_UPDATED.edit(old_msg,
                                           disp.TIMEOUT_DM(formatted_stamp, mod.mention, p.timeout_reason),
                                           update_stamp),
        return True

    else:  # Set new timeout
        msg = await disp.TIMEOUT_DM.send(p_memb, formatted_stamp, mod.mention, reason, view=views.RemoveTimeoutView())
        await p.set_timeout(stamp, msg.id, reason, mod.id)
        await role_update(p_memb, p, reason=f'Player timed out by {mod.name} for reason: {reason}')
        await d_log(message=disp.TIMEOUT_LOG(p.name, formatted_stamp, mod.name, reason))
        if p.account:
            await accounts.terminate(p.account)
        if p.match:
            await p.match.leave_match(p.active)
        if p.lobby:
            await p.lobby.lobby_leave(p)
        await p.db_update('timeout')
        return True

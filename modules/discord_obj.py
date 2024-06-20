"""
Handles interactions with commonly used discord objects, and role updates
"""

#  External Imports
from typing import Union
from logging import getLogger
import sys
import aiohttp
import traceback

import asyncio
import discord

# Internal Imports
import modules.config as cfg
import classes.players
from classes import Player
from modules import tools, accounts_handler as accounts
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

    categories['user'] = channels['casual_lobby'].category
    categories['admin'] = channels['staff'].category

    global colin
    colin = guild.get_member(123702146247032834)  # For pinging myself
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


async def is_admin_check(ctx) -> bool:
    """Check for commands if user is admin, sends message to user if not"""
    if not is_admin(ctx.user):
        await disp.CANT_USE.send_priv(ctx)
        return False
    return True


def is_player(user: discord.Member | discord.User) -> classes.Player | bool:
    """Simple check if a user is a player, returns Player if passed"""
    if p := classes.Player.get(user.id):
        return p
    return False


def is_timeout(user: discord.Member | discord.User) -> bool | int:
    """Simple check if a user is timed out, returns timeout until stamp if True
    Also returns false if user is not a player."""
    if (p := classes.Player.get(user.id)) and p.is_timeout:
        return p.timeout_until
    return False


async def is_timeout_check(ctx) -> bool | int:
    """Check for commands if player is timed out. returns timeout until stamp if True and sends message to user.
        Also returns false if user is not a player.
        """
    if stamp_or_bool := is_timeout(ctx.user):
        await disp.DISABLED_PLAYER.send_priv(ctx)
    return stamp_or_bool


async def registered_check(ctx, user: discord.Member | discord.User | classes.Player) -> bool | classes.Player:
    """Checks if a user is a registered player, returns Player if passed and sends a response if not."""
    if (player := is_player(user)) and player.is_registered:
        return player
    elif ctx.user.id == user.id:
        await disp.NOT_REGISTERED.send_priv(ctx, user.mention, channels['register'].mention)
    else:
        await disp.NOT_REGISTERED_2.send_priv(ctx, user.mention)
    return False


async def d_log(message: str = '', source: str = '', error=None, ping=None) -> bool | discord.Message:
    """Utility function to send logs to #logs channel and fsbot Log
    Ping must be mentionable object, or None"""
    if not message:
        log.error("No message passed to d_log")
        return False

    # Create converted message with replaced mentions.  Convert ID's to names
    clean_message = tools.convert_mentions(bot, message)

    try:
        if error:
            tb = traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__)
            msg = await disp.LOG_EMBED.send(channels['logs'], source=tools.convert_mentions(bot, source),
                                            message=message,
                                            error=error,
                                            trace=tb,
                                            ping=ping or colin)
            log.error(f"Source: {source} {clean_message}", exc_info=error)
            return msg

        msg = await disp.LOG_MESSAGE.send(channels['logs'], f"{f'(From {source}): ' if source else ''} {message}",
                                          ping=ping, allowed_mentions=False)
        log.info(clean_message)
        return msg
    except (discord.HTTPException, discord.Forbidden) as error_2:
        log.error("Could not send message to logs channel", exc_info=error_2)
        log.error(message, exc_info=error)
    return False


def d_log_task(message: str = '', source: str = '', error=None):
    asyncio.create_task(d_log(message, source, error))


async def get_or_create_role(name: str, **kwargs) -> discord.Role:
    """get a role by name, or creates it if it doesn't exist
    Returns the role object
    Data should be a dict containing params for the role creation
    color: Color for the role
    hoist: bool, whether the role should be hoisted
    mentionable: bool, whether the role should be mentionable
    permissions: permissions for the role
    icon: bytes-like object for the role icon
    unicode_emoji: emoji for the role (str)

    """
    if not (role := discord.utils.find(lambda r: r.name == name, guild.roles)):
        role = await guild.create_role(name=name, **kwargs)
        log.info(f"Role {name} not found, creating new role...")
    roles.update({name: role})  # add role to roles dict
    return role


async def get_or_create_emoji(name: str, **kwargs) -> discord.Emoji | None:
    """get an emoji by name, or creates it if it doesn't exist
    Returns the emoji object
    Data should be a dict containing params for the emoji creation
    image: bytes-like object for the emoji image
    roles: list of roles to limit the emoji to
    reason: reason for the emoji creation
    """
    if not (emoji := discord.utils.find(lambda e: e.name == name, guild.emojis)):
        if 'image' in kwargs and type(kwargs['image']) == str:  # if url passed, download image
            kwargs['image'] = await tools.download_image(kwargs['image'])
        try:
            emoji = await guild.create_custom_emoji(name=name, **kwargs)
            log.info(f"Emoji {name} not found, creating new emoji...")
        except discord.Forbidden as e:
            log.error(f"Could not create emoji {name}", exc_info=e)
            return
    cfg.emojis.update({name: str(emoji)})  # add emoji to config
    return emoji


async def role_update(member: discord.Member = None, player: classes.Player = None, reason="FSBot Role Update"):
    """Takes either a member or a player and updates what roles they should have"""
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

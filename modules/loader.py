"""Handles loading and unloading of bot, as well as locking the bots functionality"""

from logging import getLogger
import discord
from discord import ExtensionAlreadyLoaded, ExtensionNotLoaded

main_cogs = ['cogs.admin', 'cogs.general']
standard_cogs = ['cogs.contentplug', 'cogs.duel_lobby', 'cogs.matches',
                 'cogs.register', 'cogs.direct_messages', 'cogs.anomalynotify', 'cogs.private_voice_channels']
__is_global_locked = True

log = getLogger('fs_bot')


def init(client):
    for cog in main_cogs:
        client.load_extension(cog)


def load_secondary(client):
    for cog in standard_cogs:
        try:
            client.load_extension(cog)
        except ExtensionAlreadyLoaded:
            log.debug(f"{cog} already loaded!")
            pass
    log.info('Loaded Cogs: %s', list(client.cogs.keys()))


def lock_all():
    global __is_global_locked
    __is_global_locked = True


def unlock_all():
    global __is_global_locked
    __is_global_locked = False


async def load_all(client: discord.Bot):
    for cog in standard_cogs:
        try:
            client.load_extension(cog)
        except ExtensionAlreadyLoaded as ex:
            log.error(f"Error Loading {cog} because {ex}")

    log.info('Loaded Cogs: %s', list(client.cogs.keys()))

    await client.sync_commands(delete_existing=False)

    log.info('Synced %s Commands Successfully', len(client.application_commands))


def unload_all(client):
    for cog in standard_cogs:
        try:
            client.unload_extension(cog)
        except ExtensionNotLoaded:
            pass


def is_all_locked():
    return __is_global_locked

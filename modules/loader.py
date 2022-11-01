"""Handles loading and unloading of bot, as well as locking the bots functionality"""

from logging import getLogger
import discord
from discord import ExtensionAlreadyLoaded, ExtensionNotLoaded

main_cogs = ["cogs.admin"]
standard_cogs = ['cogs.contentplug', 'cogs.duel_lobby', 'cogs.matches',
                 'cogs.register', 'cogs.direct_messages', 'cogs.general']
__is_global_locked = True

log = getLogger('fs_bot')


def init(client):
    for cog in main_cogs:
        client.load_extension(cog)


def lock_all(client):
    for cog in standard_cogs:
        try:
            client.unload_extension(cog)
        except ExtensionNotLoaded:
            pass
    global __is_global_locked
    __is_global_locked = True


async def unlock_all(client: discord.Bot):
    for cog in standard_cogs:
        try:
            client.load_extension(cog)
        except ExtensionAlreadyLoaded as ex:
            log.error(f"Error Loading {cog} because {ex}")
    global __is_global_locked
    __is_global_locked = False

    log.info('Loaded Cogs: %s', list(client.cogs.keys()))

    await client.sync_commands(delete_existing=False)

    log.info('Synced %s Commands Successfully', len(client.application_commands))


def is_all_locked():
    return __is_global_locked

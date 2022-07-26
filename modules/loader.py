"""Handles loading and unloading of bot, as well as locking the bots functionality"""
from discord import ExtensionAlreadyLoaded, ExtensionNotLoaded

main_cogs = ["cogs.admin"]
standard_cogs = ['cogs.contentplug', 'cogs.duel_lobby', 'cogs.matches', 'cogs.register']
__is_global_locked = False  # TODO Set to True on Init, disabled with admin command.


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


def unlock_all(client):
    for cog in standard_cogs:
        try:
            client.load_extension(cog)
        except ExtensionAlreadyLoaded:
            pass
    global __is_global_locked
    __is_global_locked = False


def is_all_locked():
    return __is_global_locked

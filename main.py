'''
Main Script, run from here
Parses Some Args from command line run,
--test=BOOL : Sets config.ini path to use config_test.ini
--loglevel=LEVEL [-l] : Sets loglevel, DEBUG, WARN, INFO etc.
'''

# external imports
import discord
from discord.ext import commands
import logging
import logging.handlers
import sys
import traceback
import asyncio
import argparse
import pathlib
import os

# internal imports
import modules.config as cfg
import modules.accounts_handler
import modules.discord_obj as d_obj
import modules.database
import modules.loader as loader
import modules.signal
import classes
import display
import modules.spam_detector as spam

# parse commandline args
ap = argparse.ArgumentParser()
ap.add_argument('--test', default=False, type=bool)
ap.add_argument('-l', '--loglevel', default='INFO', type=str)
c_args = vars(ap.parse_args())
print(c_args.get('loglevel'))

numeric_level = getattr(logging, c_args.get('loglevel'), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % c_args.get('loglevel'))

# Logs Setup
log = logging.getLogger('fs_bot')
log.setLevel(numeric_level)
log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
# Log to file
log_path = f'{pathlib.Path(__file__).parent.absolute()}/../fs_bot_logs/fs_bot.log'
if not os.path.exists(log_path.rstrip('fs_bot.log')):
    os.makedirs(log_path.rstrip('fs_bot.log'))

# Log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
log.addHandler(console_handler)

# discord logs
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(console_handler)

# Log to file only if not testing
if not c_args.get('test'):
    # single_ log_handler = logging.FileHandler(filename=log_path, encoding='utf-8', mode='w')  # single log
    log_handler = logging.handlers.TimedRotatingFileHandler(log_path, when='D', interval=3) # rotating log files, every 3 days
    log_handler.setFormatter(log_formatter)
    log.addHandler(log_handler)
    discord_logger.addHandler(log_handler)

if c_args.get('test'):
    cfg.get_config('config_test.ini')
else:
    cfg.get_config('config.ini')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(intents=intents)


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    d_obj.init(bot)
    await modules.accounts_handler.init(cfg.GAPI_SERVICE)
    loader.unlock_all(bot)


@bot.slash_command(name="filtercontentplug", guild_ids=[cfg.general['guild_id']], default_permission=False)
async def filtercontentplug(ctx: discord.ApplicationContext,
                            selection: discord.Option(str, "Enable or Disable", choices=("Enable", "Disable"))):
    """Enable or Disable the #content-plug filter"""
    channel = ctx.guild.get_channel(cfg.channels['content-plug'])
    if selection == "Enable":
        try:
            bot.load_extension("cogs.contentplug")
        except discord.ExtensionAlreadyLoaded:
            await ctx.respond("Filter already enabled")
            return
    elif selection == "Disable":
        try:
            bot.unload_extension("cogs.contentplug")
        except discord.ExtensionNotLoaded:
            await ctx.respond("Filter already disabled")
            return
    await ctx.respond(f"{selection}d {channel.mention}'s content filter")


#  Global Bot Interaction Check
@bot.check
async def global_interaction_check(interaction):
    if loader.is_all_locked():
        memb = d_obj.guild.get_member(interaction.user.id)
        if d_obj.is_admin(memb):
            return True
        else:
            raise AllLocked

    if await spam.is_spam(interaction):
        return False
    return True


# unlock user from spam filter
@bot.after_invoke
async def global_after_invoke(interaction):
    spam.unlock(interaction.user.id)


class AllLocked(discord.CheckFailure):
    pass


class UserDisabled(discord.CheckFailure):
    pass


@bot.event
async def on_application_command_error(context, exception):
    command = context.command
    if command and command.has_error_handler():
        return

    cog = context.cog
    if cog and cog.has_error_handler():
        return

    if isinstance(exception, AllLocked):
        await display.AllStrings.ALL_LOCKED.send_priv(context)
    elif isinstance(exception, UserDisabled):
        await display.AllStrings.DISABLED_PLAYER.send_priv(context)
    elif isinstance(exception, discord.ext.commands.PrivateMessageOnly):
        await display.AllStrings.DM_ONLY.send(context)
    elif isinstance(exception, discord.CheckFailure):
        await display.AllStrings.CHECK_FAILURE.send_priv(context)
    else:
        await display.AllStrings.GENERAL_ERROR.send_priv(context, exception, d_obj.colin.mention)

    log.exception(f"Ignoring exception in command {context.command}", exc_info=exception)
    print(f"Ignoring exception in command {context.command}:", file=sys.stderr)
    traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)


# database init
modules.database.init(cfg.database)
modules.database.get_all_elements(classes.Player.new_from_data, 'users')
log.info("Loaded Players from Database: %s", len(classes.Player.get_all_players()))

modules.signal.init(bot)
loader.init(bot)
bot.run(cfg.general['token'])

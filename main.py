'''
Main Script, run from here
'''

# external imports
import discord
from discord.ext import commands
import logging


# internal imports
import modules.config as cfg
import modules.accounts_handler_simple
import classes
import display


log = logging.getLogger('fs_bot')
log.setLevel(logging.INFO)
handler = logging.FileHandler(filename='fs_bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
log.addHandler(handler)

cfg.get_config()


intents = discord.Intents.default()
intents.members = True
intents.message_content = True



bot = commands.Bot(command_prefix=cfg.general['command_prefix'], intents=intents)




@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("--------------------------------------------")
    modules.accounts_handler_simple.init(cfg.GAPI_SERVICE, bot)


@bot.slash_command(name="filtercontentplug", guild_ids=[cfg.general['guild_id']], default_permission=False)
@discord.commands.permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
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


bot.load_extension("cogs.contentplug")
bot.load_extension("cogs.accountcommands")
bot.run(cfg.general['token'])


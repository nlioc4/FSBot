"""
Cog built to handle manual account assigning in the low tech era of Jaeger Accounts

"""

# External Imports
import asyncio
from discord.ext import commands, tasks
import discord
from discord.commands import permissions
from logging import getLogger
from datetime import timedelta, datetime
import pytz

log = getLogger("fs_bot")

# Internal imports
import modules.config as cfg
import modules.accounts_handler_simple
import modules.census as census
import classes
import display

# Midnight Eastern for Account reset
eastern = pytz.timezone('US/Eastern')
midnight_eastern = (datetime.now().astimezone(eastern)
                    + timedelta(days=1)).replace(hour=0,
                                                 minute=0,
                                                 microsecond=0,
                                                 second=0).time()


class AccountCommands(commands.Cog, name="AccountCommands"):
    def __init__(self, bot):
        self.bot = bot
        self.midnight_init.start()
        self.online_check.start()

    ##TODO cog_check for @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    # async def cog_check(self, ctx):+
    #     print(commands.has_any_role(cfg.roles['admin'], cfg.roles['mod']))
    #     return commands.has_any_role(cfg.roles['admin'], cfg.roles['mod'])

    @commands.message_command(name="Assign Account", guild_ids=[cfg.general['guild_id']], default_permission=False)
    @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    @permissions.permission(cfg.roles['admin'], permission=True)
    @commands.max_concurrency(number=1, wait=False)
    async def msg_assign_account(self, ctx, message):
        """
            Assign an account via Message Interaction
        """
        registered_role = ctx.guild.get_role(cfg.roles['registered'])
        usage_channel = self.bot.get_partial_messageable(cfg.channels['usage'])
        await ctx.defer(ephemeral=True)
        if registered_role in message.author.roles and not modules.accounts_handler_simple.has_account(message.author):
            account = modules.accounts_handler_simple.pick_account(message.author)
            if not account:
                await ctx.respond(f"No Available Accounts", ephemeral=True)
            else:
                await message.author.send(content="", embed=display.account(ctx, account))
                await usage_channel.send(
                    f'{ctx.user.name} sent account ID:{account.id} to User: {message.author.mention}')
                await message.add_reaction("\u2705")
                await ctx.respond(
                    f"Account [{account.id}] being sent to {message.author.mention} with ID: {message.author.id}",
                    ephemeral=True)
        elif modules.accounts_handler_simple.has_account(message.author):
            await ctx.respond(f"{message.author.mention} has already been assigned an account!", ephemeral=True)
            await message.add_reaction("\u274C")
        elif registered_role not in message.author.roles:
            await ctx.respond(f"{message.author.mention} has not accepted the rules!", ephemeral=True)
            await message.add_reaction("\u274C")
        else:
            await ctx.respond(f"An error has occurred, ping Colin")

    @commands.slash_command(name="assignact", guild_ids=[cfg.general['guild_id']], default_permission=False)
    @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    async def slash_assign_account(self,
                                   ctx: discord.ApplicationContext,
                                   user: discord.Option(discord.Member, "Recipients @mention"),
                                   force: discord.Option(bool, "Force account send, regardless of "
                                                               "role/current account", default=False)):
        """
            Assign a Jaeger Account to a user, via @mention
        """
        registered_role = user.guild.get_role(cfg.roles["registered"])
        usage_channel = self.bot.get_partial_messageable(cfg.channels['usage'])
        await ctx.defer(ephemeral=True)
        if force:
            account = modules.accounts_handler_simple.pick_account(user)
            await user.send(content="", embed=display.account(ctx, account))
            await usage_channel.send(f'{ctx.user.name} sent account ID:{account.id} to User: {user.mention}')
            await ctx.respond(f"Account [{account.id}] being sent to {user.mention} with ID: {user.id}", ephemeral=True)
        elif registered_role in user.roles and not modules.accounts_handler_simple.has_account(user):
            account = modules.accounts_handler_simple.pick_account(user)
            await user.send(content="", embed=display.account(ctx, account))
            await usage_channel.send(f'{ctx.user.name} sent account ID:{account.id} to User: {user.mention}')
            await ctx.respond(f"Account [{account.id}] being sent to {user.mention} with ID: {user.id}", ephemeral=True)
        elif modules.accounts_handler_simple.has_account(user):
            await ctx.respond(f"{user.mention} has already been assigned an account!", ephemeral=True)
        elif registered_role not in user.roles:
            await ctx.respond(f"{user.mention} has not accepted the rules!", ephemeral=True)
        else:
            await ctx.respond(f"An error has occurred, ping Colin")

    @commands.slash_command(name="accountcheck", guild_ids=[cfg.general['guild_id']], default_permission=False)
    @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    async def accountcheck(self, ctx):
        """Account status info"""
        await ctx.defer()
        available, used, usage = modules.accounts_handler_simple.accounts_info()
        chars_list = census.get_account_chars_list(account_dict)
        online = await census.get_chars_list_online_status(chars_list)
        await ctx.respond(content="", embed=display.embeds.accountcheck(ctx, available, used, usage, online))

    @commands.slash_command(name="initialize", guild_ids=[cfg.general['guild_id']], default_permission=False)
    @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    async def initialize(self, ctx):
        """Reloads all accounts from the Account Sheet"""
        print("Manually", end=' ')
        modules.accounts_handler_simple.init(cfg.GAPI_SERVICE, self.bot)
        await ctx.respond("Reinitialized Account Sheet")

    @commands.slash_command(name="midnightinit", guild_ids=[cfg.general['guild_id']], default_permission=False)
    @permissions.has_any_role(cfg.roles['admin'], cfg.roles['mod'])
    async def midnight_init_toggle(self, ctx: discord.ApplicationContext,
                                   action: discord.Option(str, "Start, Stop or Status",
                                                          choices=("Start", "Stop", "Status"),
                                                          required=True)):
        """Starts, Stops or Status Checks Midnight Init Loop"""
        running = self.midnight_init.is_running()
        if action == "Stop" and running:
            self.midnight_init.cancel()
            await ctx.respond("Automatic Midnight Init Stopped", ephemeral=True)
        elif action == "Start" and not running:
            self.midnight_init.start()
            await ctx.respond("Automatic Midnight Init Started", ephemeral=True)
        else:
            await ctx.respond(f"Automatic Midnight Init Currently {'Running' if running else 'Stopped'}",
                              ephemeral=True)
        running = self.midnight_init.is_running()
        print(f'Midnight init {"Running" if running else "Stopped"}')

    @tasks.loop(time=midnight_eastern)
    async def midnight_init(self):
        asyncio.sleep(15)
        print("Automatically", end=" ")
        modules.accounts_handler_simple.init(cfg.GAPI_SERVICE, self.bot)

    @tasks.loop(minutes=5)
    async def online_check(self):
        chars_list = census.get_account_chars_list(modules.accounts_handler_simple._available_accounts)
        usage_channel = self.bot.get_partial_messageable(cfg.channels['usage'])
        online = await census.get_chars_list_online_status(chars_list)
        if online:
            await usage_channel.send(content="", embed=display.embeds.account_online_check(online))

    @online_check.before_loop
    async def before_online_check(self):
        await self.bot.wait_until_ready()



def setup(client):
    client.add_cog(AccountCommands(client))

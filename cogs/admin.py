"""Admin cog, handles admin functions of FSBot"""

# External Imports
import discord
from discord.ext import commands, tasks
from logging import getLogger
import asyncio
from datetime import datetime as dt, time, timezone

# Internal Imports
import modules.config as cfg
import modules.accounts_handler as accounts
import modules.discord_obj as d_obj
import modules.census as census
import modules.loader as loader
from classes import Player, ActivePlayer
from display import AllStrings as disp, views

log = getLogger('fs_bot')


class AdminCog(commands.Cog, command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                default_permission=False)):
    def __init__(self, bot):
        self.bot = bot
        self.online_cache = []

    # admin = discord.SlashCommandGroup("admin", "Admin Commands")
    #
    # @admin.command()
    # async def loader(self, ctx: discord.ApplicationContext,
    #                  action: discord.Option(str, "Load or Unload FSBot", choies=("Unlock", "Lock"))):
    #     match action:
    #         case "Unlock":
    #             await loader.unlock_all(self.bot)
    #             await disp.LOADER_TOGGLE.send_priv(ctx, action)
    #         case "Lock":
    #             await loader.lock_all(self.bot)
    #             await disp.LOADER_TOGGLE.send_priv(ctx, action)

    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        #  Wait until the bot is ready before starting loops, ensure account_handler has finished init
        await asyncio.sleep(5)
        self.census_watchtower.start()
        self.account_sheet_reload.start()
        self.account_watchtower.start()
        self.debug_loop.start()

    @tasks.loop(count=1)
    async def census_watchtower(self):
        await census.online_status_updater(Player.map_chars_to_players)

    @census_watchtower.before_loop
    async def before_census_watchtower(self):
        init = False
        for _ in range(5):
            init = await census.online_status_init(Player.map_chars_to_players())
            if init:
                break
        if not init:
            log.warning("Could not reach REST api during watchtower init after 5 tries...")

    @tasks.loop(time=time(hour=16, minute=0, second=0))
    async def account_sheet_reload(self):
        log.info("Reinitialized Account Sheet and Account Characters")
        await accounts.init(cfg.GAPI_SERVICE)

    @tasks.loop(seconds=10)
    async def account_watchtower(self):
        # create list of accounts with online chars and no player assigned
        unassigned_online = []
        for acc in accounts.all_accounts.values():
            if acc.online_id and not acc.a_player:
                unassigned_online.append(acc)
        # compare to cache to see if login is new. Ping only if login is new.
        new_online = [acc for acc in unassigned_online if acc not in self.online_cache]
        if new_online:
            await disp.UNASSIGNED_ONLINE.send(d_obj.channels['logs'],
                                              d_obj.roles['app_admin'].mention,
                                              online=unassigned_online)
        # Cache Online Accounts
        self.online_cache = unassigned_online


def setup(client):
    client.add_cog(AdminCog(client))

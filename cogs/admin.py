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
from classes import Player, ActivePlayer
from display import AllStrings as disp, views

log = getLogger('fs_bot')


class AdminCog(commands.Cog, command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                default_permission=False)):
    def __init__(self, bot):
        self.bot = bot
        self.unassigned_online = []

    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        #  Wait until the bot is ready before starting loops
        self.census_watchtower.start()
        self.account_sheet_reload.start()
        self.account_watchtower.start()

    @tasks.loop(count=1)
    async def census_watchtower(self):
        await census.online_status_updater(Player.get_all_active_players())

    @census_watchtower.before_loop
    async def before_census_watchtower(self):
        init = False
        for _ in range(5):
            init = await census.online_status_init(Player.get_all_active_players())
            await asyncio.sleep(2)
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
            if not acc.a_player and acc.online_id:
                unassigned_online.append(acc)

        # compare to cache to see if login is new. Ping only if login is new.
        new_online = [acc for acc in unassigned_online if acc not in self.unassigned_online]
        if new_online:
            await disp.UNASSIGNED_ONLINE.send(cfg.channels['logs'], cfg.roles['app_admin'], online=unassigned_online)

        # Remove offline accounts from cache
        self.unassigned_online = list(filter(lambda x: x not in unassigned_online, self.unassigned_online))


def setup(client):
    client.add_cog(AdminCog(client))

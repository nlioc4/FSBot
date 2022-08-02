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
from classes.match import BaseMatch
from display import AllStrings as disp, views

log = getLogger('fs_bot')


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot
        self.online_cache = set()

    admin = discord.SlashCommandGroup(
        name='admin',
        description='Admin Only Commands',
        guild_ids=[cfg.general['guild_id']]
    )

    # @discord.slash_command(name='admin',
    #                            description='Admin Only Commands',
    #                            guild_ids=[cfg.general['guild_id']]
    #                            )
    # async def admin(self, ctx: discord.ApplicationContext):
    #     if ctx.user == d_obj.colin:
    #         await disp.HELLO.send(ctx, f'glorious creator {d_obj.colin.mention}')
    #     else:
    #         await disp.HELLO.send(ctx, ctx.user.mention)

    @admin.command()
    async def loader(self, ctx: discord.ApplicationContext,
                     action: discord.Option(str, "Lock or Unlock FSBot", choices=("Unlock", "Lock", "Reload"),
                                            required=True)):
        """Unlock, Lock or Reload all bot extensions other than the Admin cog."""
        match action:
            case "Unlock":
                loader.unlock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)
            case "Lock":
                loader.lock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)
            case "Reload":
                loader.lock_all(self.bot)
                await asyncio.sleep(1)
                loader.unlock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)

    # @admin.subgroup()
    # @discord.SlashCommandGroup(name="match", description="Admin Match Commands")
    # async def match_admin(self, ctx: discord.ApplicationContext):
    #     await disp.HELLO.send_priv(ctx, ctx.user.mention)

    match_admin = admin.create_subgroup(
        name="match", description="Admin Match Commands"
    )

    @match_admin.command(name="addplayer")
    async def add_player(self, ctx: discord.ApplicationContext,
                         match_channel: discord.Option(discord.TextChannel, "Match Channel to invite member to",
                                                       required=True),
                         member: discord.Option(discord.Member, "User to invite to match", required=True)):
        p = Player.get(member.id)
        try:
            match = BaseMatch.active_match_channel_ids()[match_channel.id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_channel.mention)
            return

        await match.join_match(p)
        await disp.MATCH_JOIN_2.send_priv(ctx, p.name, match.text_channel.mention)

    @match_admin.command(name="removeplayer")
    async def remove_player(self, ctx: discord.ApplicationContext,
                            match_channel: discord.Option(discord.TextChannel, "Match Channel to remove member from",
                                                          required=True),
                            member: discord.Option(discord.Member, "User to remove from match", required=True)):
        p = Player.get(member.id)
        try:
            match = BaseMatch.active_match_channel_ids()[match_channel.id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_channel.mention)
            return

        await match.leave_match(p)
        await disp.MATCH_LEAVE_2.send_priv(ctx, p.name, match.text_channel.mention)

    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        #  Wait until the bot is ready before starting loops, ensure account_handler has finished init
        await asyncio.sleep(5)
        self.census_watchtower.start()
        self.account_sheet_reload.start()
        self.account_watchtower.start()
        self.census_rest.start()

    @tasks.loop(minutes=15)
    async def census_rest(self):
        init = False
        for _ in range(5):
            init = await census.online_status_rest(Player.map_chars_to_players())
            if init:
                break
        if not init:
            log.warning("Could not reach REST api during census rest after 5 tries...")

    @tasks.loop(count=1)
    async def census_watchtower(self):
        await census.online_status_updater(Player.map_chars_to_players)

    @tasks.loop(time=time(hour=11, minute=0, second=0))
    async def account_sheet_reload(self):
        log.info("Reinitialized Account Sheet and Account Characters")
        await accounts.init(cfg.GAPI_SERVICE)

    @tasks.loop(seconds=10)
    async def account_watchtower(self):
        # create list of accounts with online chars and no player assigned
        unassigned_online = set()
        for acc in accounts.all_accounts.values():
            if acc.online_id and not acc.a_player:
                unassigned_online.add(acc)
        # compare to cache to see if login is new. Ping only if login is new.
        new_online = unassigned_online - self.online_cache
        if new_online:
            await disp.UNASSIGNED_ONLINE.send(d_obj.channels['logs'],
                                              d_obj.roles['app_admin'].mention,
                                              online=unassigned_online)
        # Cache Online Accounts
        self.online_cache = unassigned_online


def setup(client):
    client.add_cog(AdminCog(client))

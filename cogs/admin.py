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

    @admin.command()
    async def contentplug(self, ctx: discord.ApplicationContext,
                          action: discord.Option(str, "Enable, Disable or check statusof the #contentplug filter",
                                                 choices=("Enable", "Disable", "Status"),
                                                 required=True)):
        """Enable or disable the #contentplug filter"""
        channel = d_obj.channels['content-plug']
        cog = self.bot.cogs['ContentPlug']
        if action == "Enable":
            cog.enabled = True
        elif action == "Disable":
            cog.enabled = False
        await d_obj.d_log(f"{action}ed {channel.mention}'s content filter")
        await ctx.respond(f"{action}ed {channel.mention}'s content filter", ephemeral=True)

    ##########################################################

    match_admin = admin.create_subgroup(
        name="match", description="Admin Match Commands"
    )

    @match_admin.command(name="addplayer")
    async def add_player(self, ctx: discord.ApplicationContext,
                         match_channel: discord.Option(discord.TextChannel, "Match Channel to invite member to",
                                                       required=True),
                         member: discord.Option(discord.Member, "User to invite to match", required=True)):
        """Add a player to a given match."""
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
        """Remove a player from a given match.  If the owner is removed from a match, the match will end."""
        p = Player.get(member.id)
        try:
            match = BaseMatch.active_match_channel_ids()[match_channel.id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_channel.mention)
            return

        await match.leave_match(p)
        await disp.MATCH_LEAVE_2.send_priv(ctx, p.name, match.text_channel.mention)

    @match_admin.command(name="endmatch")
    async def end_match(self, ctx: discord.ApplicationContext,
                        match_channel: discord.Option(discord.TextChannel, "Match Channel to remove member from",
                                                      required=True)):
        """End a given match forcibly."""
        try:
            match = BaseMatch.active_match_channel_ids()[match_channel.id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_channel.mention)
            return

        await match.end_match()
        await disp.MATCH_END.send_priv(ctx, match.str_id)

    #########################################################

    accounts = admin.create_subgroup(
        name="accounts", description="Admin Accounts Commands"
    )

    @accounts.command(name="assign")
    async def assign(self, ctx: discord.ApplicationContext,
                     member: discord.Option(discord.Member, "Recipients @mention", required=True),
                     acc_id: discord.Option(int, "A specific account ID to assign, 1-24", min_value=1, max_value=24,
                                            required=False)):
        """Assign an account to a user, with optional specific account ID"""
        await ctx.defer(ephemeral=True)
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER.send_priv(ctx, member.mention)
            return
        if p.account:
            await accounts.terminate(p.account)
        if not acc_id:
            acc = accounts.pick_account(p)
        else:
            acc = accounts.all_accounts[acc_id]
            if acc.a_player:
                await disp.ACCOUNT_IN_USE.send_priv(ctx, acc.id)
                return
            accounts.set_account(p, acc)
        await accounts.send_account(acc, p)
        await disp.ACCOUNT_SENT_2.send_priv(ctx, p.mention, acc.id)

    @commands.message_command(name="Assign Account")
    @commands.max_concurrency(number=1, wait=True)
    async def msg_assign_account(self, ctx: discord.ApplicationContext, message: discord.Message):
        """
            Assign an account via Message Interaction
        """
        await ctx.defer(ephemeral=True)

        p = Player.get(message.author.id)
        if not p:  # if not a player
            await disp.NOT_PLAYER.send_priv(ctx, message.author.mention)
            await message.add_reaction("\u274C")
            return

        if p.account:  # if already has account
            await disp.ACCOUNT_ALREADY_2.send_priv(ctx, p.mention, p.account.id)
            await message.add_reaction("\u274C")
            return

        acc = accounts.pick_account(p)
        if not acc:  # if no accounts available
            await disp.ACCOUNT_NO_ACCOUNT.send_priv(ctx)
            await message.add_reaction("\u274C")
            return

        # if all checks passed, send account
        await accounts.send_account(acc, p)
        await disp.ACCOUNT_SENT_2.send_priv(ctx, p.mention, acc.id)
        await message.add_reaction("\u2705")

    @msg_assign_account.error
    async def msg_assign_account_concurrency_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.respond('Someone else is using this command right now, try again soon!', ephemeral=True)

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
        for _ in range(5):
            if await census.online_status_rest(Player.map_chars_to_players()):
                return
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

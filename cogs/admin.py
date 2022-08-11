"""Admin cog, handles admin functions of FSBot"""

# External Imports
import auraxium
import discord
from discord.ext import commands, tasks
from logging import getLogger
import asyncio
from datetime import datetime as dt, time, timezone

# Internal Imports
import modules.config as cfg
import modules.accounts_handler as accounts
import modules.discord_obj as d_obj
from modules import census
from modules import tools
from modules import loader
from classes import Player, ActivePlayer
from classes.match import BaseMatch
from display import AllStrings as disp, views, embeds
import cogs.register as register

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

    @admin.command()
    async def loader(self, ctx: discord.ApplicationContext,
                     action: discord.Option(str, "Lock or Unlock FSBot", choices=("Unlock", "Lock", "Reload"),
                                            required=True)):
        """Unlock, Lock or Reload all bot extensions other than the Admin cog."""
        match action:
            case "Unlock":
                await loader.unlock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)
            case "Lock":
                loader.lock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)
            case "Reload":
                loader.lock_all(self.bot)
                await asyncio.sleep(1)
                await loader.unlock_all(self.bot)
                await disp.LOADER_TOGGLE.send_priv(ctx, action)

    @admin.command()
    async def contentplug(self, ctx: discord.ApplicationContext,
                          action: discord.Option(str, "Enable, Disable or check status of the #contentplug filter",
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

    @admin.command(name="censusonlinecheck")
    async def manual_census(self, ctx: discord.ApplicationContext):
        """Runs a REST census online check, to catch any login/logouts that the websocket may have missed"""
        ran = await self.census_rest()
        await disp.MANUAL_CENSUS.send_priv(ctx, "successful." if ran else "failed.")

    @admin.command(name="rulesinit", )
    async def rulesinit(self, ctx: discord.ApplicationContext,
                        message_id: discord.Option(str, "Existing FSBot Rules message", required=False)):
        """Posts Rules Message in current channel or replaces message at given ID"""
        if message_id:
            msg = await d_obj.channels['rules'].fetch_message(int(message_id))
            try:
                await msg.edit(content="", view=register.RulesView(), embed=embeds.fsbot_rules_embed())
            except discord.Forbidden:
                await ctx.respond(content="Selected Message not owned by the bot!", ephemeral=True)
                return
        else:
            await ctx.channel.send(content="", view=register.RulesView(),
                                   embed=embeds.fsbot_rules_embed())
        await ctx.respond(content="Rules Message Posted", ephemeral=True)

    @admin.command(name="registerinit")
    async def registerinit(self, ctx: discord.ApplicationContext,
                           message_id: discord.Option(str, "Existing FSBot Register message", required=False)):
        """Posts Register Message in current channel or replaces message at given ID"""
        if message_id:

            msg = await d_obj.channels['register'].fetch_message(int(message_id))
            try:
                await msg.edit(content="", view=register.RegisterView(), embed=embeds.fsbot_info_embed())
            except discord.Forbidden:
                await ctx.respond(content="Selected Message not owned by the bot!", ephemeral=True)
                return
        else:
            await ctx.channel.send(content="", view=register.RegisterView(), embed=embeds.fsbot_info_embed())
        await ctx.respond(content="Register and Settings Message Posted", ephemeral=True)

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
        if p.match:
            await disp.MATCH_ALREADY.send_priv(ctx, p.name, p.match.str_id)
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
        if p.match == match:
            await match.leave_match(p.active)
            await disp.MATCH_LEAVE_2.send_priv(ctx, p.name, match.text_channel.mention)
        else:
            await disp.MATCH_NOT_IN_2.send_priv(ctx, p.name, match.text_channel.mention)

    @match_admin.command(name="end")
    async def end_match(self, ctx: discord.ApplicationContext,
                        match_id: discord.Option(int, "Match ID to end",
                                                 required=True)):
        """End a given match forcibly."""
        await ctx.defer()
        try:
            match = BaseMatch.active_matches_dict()[match_id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_id)
            return

        await disp.MATCH_END.send_priv(ctx, match.id_str)
        await match.end_match()

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

    @accounts.command(name='info')
    async def account_info(self, ctx: discord.ApplicationContext):
        """Provide info on FSBot's connected Jaeger Accounts"""
        num_available = len(accounts._available_accounts)
        assigned = accounts._busy_accounts.values()
        num_used = len(assigned)
        online = [acc for acc in accounts.all_accounts.values() if acc.online_id]
        await disp.ACCOUNT_INFO.send_priv(ctx, num_available=num_available, num_used=num_used, assigned=assigned,
                                          online=online)

    @accounts.command(name='watchtower')
    async def watchtower_toggle(self, ctx: discord.ApplicationContext,
                                action: discord.Option(str,
                                                       "Enable, Disable or check status of the accounts watchtower",
                                                       choices=("Enable", "Disable", "Status"), required=True)
                                ):
        """Accounts Watchtower Control"""

        running = self.account_watchtower.is_running()

        if action == "Enable" and not running:
            self.account_watchtower.start()
        elif action == "Disable" and running:
            self.account_watchtower.cancel()
        string = f"Accounts watchtower was {'running' if running else 'stopped'}."
        if running != self.account_watchtower.is_running() or self.account_watchtower.is_being_cancelled():
            string += f" It is now {'started' if not running else 'stopping'}."
        await d_obj.d_log(string)
        await ctx.respond(string, ephemeral=True)

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

    ##########################################################

    player_admin = admin.create_subgroup(
        name="player", description="Admin Player Commands"
    )

    @player_admin.command(name='info')
    async def player_info(self, ctx: discord.ApplicationContext,
                          member: discord.Option(discord.Member, "@mention to get info on", required=True)):
        """Provide info on a given player"""
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
            return

        await disp.REG_INFO.send_priv(ctx, player=p)


    @msg_assign_account.error
    async def msg_assign_account_concurrency_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.respond('Someone else is using this command right now, try again soon!', ephemeral=True)

    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        #  Wait until the bot is ready before starting loops, ensure account_handler has finished init
        await asyncio.sleep(5)
        self.account_sheet_reload.start()
        self.census_watchtower.start()
        self.account_watchtower.start()
        self.census_rest.start()

    @tasks.loop(count=1)
    async def census_watchtower(self):
        await census.online_status_updater(Player.map_chars_to_players)

    @tasks.loop(seconds=15)
    async def census_rest(self):
        """Built to detect already online accounts on bot startup"""
        for _ in range(5):
            if await census.online_status_rest(Player.map_chars_to_players()):
                return True
        log.warning("Could not reach REST api during census rest after 5 tries...")
        return False

    @census_watchtower.after_loop
    async def after_census_watchtower(self):
        if self.census_watchtower.failed():
            await d_obj.log(f"{d_obj.colin.mention} Census Watchtower has failed")

    census_watchtower.add_exception_type(auraxium.errors.ResponseError)

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

            #  account session over 3 hours
            elif acc.is_validated and not acc.is_terminated:
                if acc.last_usage['start_time'] < tools.timestamp_now() - 3 * 60 * 60:
                    await accounts.terminate(acc)

            #  account terminated but user still online 10 minutes later
            elif acc.online_id and acc.is_terminated:
                if acc.last_usage['end_time'] < tools.timestamp_now() - 5 * 60:
                    await d_obj.d_log(f'User: {acc.a_player.mention} has not logged out of their Jaeger account'
                                      f' 5 minutes after their session ended.  Force cleaning account...')
                    await accounts.clean_account(acc)

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

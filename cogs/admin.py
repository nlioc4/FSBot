"""Admin cog, handles admin functions of FSBot"""

# External Imports
import auraxium
import discord
from discord.ext import commands, tasks
from logging import getLogger
import asyncio
from datetime import datetime as dt, time, timedelta
from pytz import timezone

# Internal Imports
import modules.config as cfg
import modules.accounts_handler as accounts
import modules.discord_obj as d_obj
from modules import census, tools, loader, elo_ranks_handler

from classes import Player
from classes.lobby import Lobby
from classes.match import BaseMatch, EndCondition, RankedMatch
from display import AllStrings as disp, embeds
import cogs.register as register

log = getLogger('fs_bot')


def player_chars_autocomplete(ctx: discord.AutocompleteContext = None, member_id: int = 0, value: str = ''):
    """Return a list of possible character choices, based on whether a player is found or has an account"""
    user_id = member_id or ctx.options.get("member") or ctx.interaction.user.id
    value = value.lower() or ctx.value.lower()
    if user_id and (p := Player.get(int(user_id))):
        if p.account or p.has_own_account:
            options = [char for char in p.ig_names if char.lower().find(value) > 0]
            return options or p.ig_names
    return ["No Characters Found"]


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot
        self.online_cache = set()
        self.census_watchtower: asyncio.Task | None = None

    common_kwargs = dict(
        guild_ids=[cfg.general['guild_id']],
        default_member_permissions=discord.Permissions(manage_guild=True)
    )

    admin = discord.SlashCommandGroup(
        name="admin",
        description="Admin Commands",
        **common_kwargs
    )

    async def cog_check(self, ctx: discord.ApplicationContext):
        return await d_obj.is_admin_check(ctx)

    async def cog_command_error(self, ctx, exception):
        if isinstance(exception, discord.CheckFailure):
            pass
        else:
            await self.bot.on_application_command_error(ctx, exception)

    @admin.command(name="manual_leaderboard_update")
    async def manual_leaderboard_update(self, ctx: discord.ApplicationContext):
        """Manually update the leaderboard"""
        general = self.bot.cogs.get('GeneralCog')
        if general:
            await general.elo_rank_update()  # type:ignore
            await disp.LEADERBOARD_UPDATED.send_priv(ctx, d_obj.channels['ranked_leaderboard'].mention)
        else:
            await disp.UNEXPECTED_ERROR.send_priv(ctx)

    @admin.command(name="spamfilter")
    async def spam_filter_control(self, ctx: discord.ApplicationContext,
                                  action: discord.Option(str, "Enable or Disable the Spam Filter",
                                                         choices=("Enable", "Disable"), required=True)):
        """Enable or Disable the Spam Filter"""
        spam = self.bot.cogs.get('SpamCheckCog')
        if not spam:
            return await disp.UNEXPECTED_ERROR.send_priv(ctx)
        if action == "Enable":
            spam.enabled = True
            await disp.SPAM_LINK_DETECTOR.send_priv(ctx, "enabled")
        else:
            spam.enabled = False
            await disp.SPAM_LINK_DETECTOR.send_priv(ctx, "disabled")

    @admin.command(name="loader")
    async def loader(self, ctx: discord.ApplicationContext,
                     action: discord.Option(str, "Lock or Unlock FSBot", choices=("Unlock", "Lock"),
                                            required=True)):
        """Unlock or Lock bot.  Only admins will be able to use any features."""
        match action:
            case "Unlock":
                loader.unlock_all()
                await disp.LOADER_TOGGLE.send_priv(ctx, action)
            case "Lock":
                loader.lock_all()
                await disp.LOADER_TOGGLE.send_priv(ctx, action)

    @admin.command(name="contentplug")
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

    @admin.command(name="rulesinit")
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

    census_group = discord.SlashCommandGroup(
        name='census',
        description='Census Admin Commands',
        **common_kwargs
    )

    @census_group.command(name="censusonlinecheck")
    async def manual_census(self, ctx: discord.ApplicationContext):
        """Runs a REST census online check, to catch any login/logouts that the websocket may have missed"""
        ran = await self.census_rest()
        await disp.MANUAL_CENSUS.send_priv(ctx, "successful." if ran else "failed.")

    @census_group.command(name='rest')
    async def census_control(self, ctx: discord.ApplicationContext,
                             action: discord.Option(str, "Enable, Disable, or check status of the Census Loop",
                                                    choices=("Enable", "Disable", "Status"),
                                                    required=False)):
        """Control the REST Census loop"""

        match action:

            case "Enable" if self.census_rest.is_running():
                self.census_rest.restart()
                await disp.CENSUS_LOOP_CHANGED.send_priv(ctx, "Running", "restarted")
            case "Enable":
                self.census_rest.start()
                await disp.CENSUS_LOOP_CHANGED.send_priv(ctx, "Stopped", "started")
            case "Disable" if self.census_rest.is_running():
                self.census_rest.stop()
                await disp.CENSUS_LOOP_CHANGED.send_priv(ctx, "Running", "stopped")
            case _:
                await disp.CENSUS_LOOP_STATUS.send_priv(ctx, "Running" if self.census_rest.is_running() else "Stopped")
                return
        await d_obj.d_log(f"{ctx.user.mention} {action}d the Census Loop.")

    ##########################################################

    match_admin = discord.SlashCommandGroup(
        name="match",
        description="Admin Match Commands",
        **common_kwargs
    )

    @match_admin.command(name="addplayer")
    async def add_player(self, ctx: discord.ApplicationContext,
                         member: discord.Option(discord.Member, "User to invite to match", required=True),
                         match_channel: discord.Option(discord.TextChannel, "Match Channel to invite member to",
                                                       required=False)
                         ):
        """Add a player to a match. If a channel isn't provided, current is used."""
        p = Player.get(member.id)
        match_channel = match_channel or ctx.channel

        try:
            match = BaseMatch.active_match_thread_ids()[match_channel.id]
        except KeyError:
            await disp.MATCH_NOT_FOUND.send_priv(ctx, match_channel.mention)
            return
        if p.match:
            await disp.MATCH_ALREADY.send_priv(ctx, p.name, p.match.str_id)
            return

        await match.join_match(p)
        if p.lobby:
            await p.lobby.lobby_leave(player=p, match=match)
        await disp.MATCH_JOIN_2.send_priv(ctx, p.name, match.thread.mention)

    @match_admin.command(name="removeplayer")
    async def remove_player(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.Member, "User to remove from match", required=True)):
        """Remove a player from a match.  If the owner is removed from a match, the match will end."""
        p = Player.get(member.id)

        if p.match:
            await disp.MATCH_LEAVE_2.send_priv(ctx, p.name, p.match.thread.mention)
            await p.match.leave_match(p.active)

        else:
            await disp.MATCH_NOT_IN_2.send_priv(ctx, p.name)

    @match_admin.command(name="create")
    async def create_match(self, ctx: discord.ApplicationContext,
                           member: discord.Option(discord.Member, "User to add to match",
                                                  required=True),
                           owner: discord.Option(discord.Member, "Match Owner, defaults to you",
                                                 required=False),
                           match_type: discord.Option(str, "Type of match to create, defaults to current channel or"
                                                           "casual",
                                                      required=False,
                                                      choices=["casual", "ranked"])):
        """Creates a match with the given arguments."""
        await ctx.defer(ephemeral=True)
        # set up Player Objects
        if not (invited := await d_obj.registered_check(ctx, member)) \
                or not (owner := await d_obj.registered_check(ctx, owner or ctx.user)):
            return
        # check / update player status
        if invited.match or owner.match:
            return await disp.ADMIN_MATCH_CREATE_ALREADY.send_priv(ctx)
        if invited == owner:
            return await disp.ADMIN_MATCH_CREATE_SAME.send_priv(ctx)

        # check for match type
        lobby = Lobby.get(match_type) or Lobby.channel_to_lobby(ctx.channel) or Lobby.get("casual")

        match = await lobby.accept_invite(owner, invited)
        match.log(f"Admin Created Match: {Player.get(ctx.user.id).name}")
        await disp.MATCH_CREATE.send_priv(ctx, match.thread.mention, match.id_str)

        if invited.lobby:
            await invited.lobby.lobby_leave(invited, match=match)
        if owner.lobby:
            await owner.lobby.lobby_leave(owner, match=match)

    @match_admin.command(name="end")
    async def end_match(self, ctx: discord.ApplicationContext,
                        match_id: discord.Option(int, "Match ID to end", required=False)):
        """End a given match forcibly.  Uses current channel if no ID provided"""
        await ctx.defer(ephemeral=True)
        match = BaseMatch.active_matches_dict().get(match_id) or BaseMatch.active_match_thread_ids().get(
            ctx.channel_id)

        if not match:
            return await disp.MATCH_NOT_FOUND.send_priv(ctx, (match_id or ctx.channel.mention))

        await disp.MATCH_END.send_priv(ctx, match.id_str)
        await match.end_match(EndCondition.EXTERNAL)

    @match_admin.command(name="roundwin")
    async def match_setroundwinner(self, ctx: discord.ApplicationContext,
                                   winner: discord.Option(discord.Member, "Member to set as winner", required=True),
                                   match_id: discord.Option(int, "Match ID to set winner for", required=False)):
        """Set the winner of the current round for a given match.  Uses current channel if no ID provided"""
        await ctx.defer(ephemeral=True)
        match = BaseMatch.get(match_id) or BaseMatch.get_by_thread(ctx.channel_id)

        if not match:
            return await disp.MATCH_NOT_FOUND.send_priv(ctx, (match_id or ctx.channel.mention))

        if match.TYPE != 'Ranked':
            return await disp.MATCH_NOT_RANKED.send_priv(ctx, match.id_str)

        if not (a_p := match.get_player(winner)):
            return await disp.MATCH_NOT_IN_3.send_priv(ctx, winner.mention, match.id_str)

        if not match.set_round_winner(a_p):
            return await disp.RM_NO_CURRENT_ROUND.send_priv(ctx)

        else:
            await match.update()
            await disp.RM_ROUND_WINNER_SET.send_priv(ctx, winner.mention)

    #########################################################
    # Lobby Admin Commands
    lobby_admin = discord.SlashCommandGroup(
        name="lobby",
        description="Admin Lobby Commands",
        **common_kwargs
    )

    @lobby_admin.command(name="lock")
    async def lobby_lock(self, ctx: discord.ApplicationContext,
                         action: discord.Option(str, "Lock or Unlock the Lobby", required=True,
                                                choices=["lock", "unlock"]),
                         lobby_choice: discord.Option(str, "Lobby to lock or unlock", required=False,
                                                      choices=["casual", "ranked"])):
        """Lock or Unlock the Lobby"""
        lobby = Lobby.get(lobby_choice) or Lobby.channel_to_lobby(ctx.channel)

        if not lobby:
            await disp.LOBBY_NOT_FOUND.send_priv(ctx, lobby_choice or ctx.channel.mention)
            return

        await ctx.defer(ephemeral=True)

        if action == "lock":
            await lobby.disable()
            await disp.LOBBY_DISABLED.send_priv(ctx, lobby.name)
        else:
            await lobby.enable()
            await disp.LOBBY_ENABLED.send_priv(ctx, lobby.name)

    @lobby_admin.command(name="addplayer")
    async def lobby_addplayer(self, ctx: discord.ApplicationContext,
                              member: discord.Option(discord.Member, "Member to add to lobby", required=True),
                              lobby_choice: discord.Option(str, "Lobby to add member to", required=False,
                                                           choices=["casual", "ranked"])):
        """Add a player to a lobby"""
        lobby = Lobby.get(lobby_choice) or Lobby.channel_to_lobby(ctx.channel)
        if not lobby:
            await disp.LOBBY_NOT_FOUND.send_priv(ctx, lobby_choice or ctx.channel.mention)
            return

        if not (p := await d_obj.registered_check(ctx, member)):
            return

        await ctx.defer(ephemeral=True)

        if p.lobby:
            await p.lobby.lobby_leave(p)
        joined = lobby.lobby_join(p)
        if joined:
            await disp.LOBBY_PLAYER_ADDED.send_priv(ctx, p.name, lobby.name)
        else:
            await disp.LOBBY_PLAYER_CANT_ADD.send_priv(ctx, p.name, lobby.name)

    @lobby_admin.command(name="removeplayer")
    async def lobby_removeplayer(self, ctx: discord.ApplicationContext,
                                 member: discord.Option(discord.Member, "Member to remove from Lobby, required=True"),
                                 lobby_choice: discord.Option(str, "Lobby to remove member from", required=False,
                                                              choices=["casual", "ranked"])):
        """Remove a player from a lobby"""
        lobby = Lobby.get(lobby_choice) or Lobby.channel_to_lobby(ctx.channel)
        if not lobby:
            await disp.LOBBY_NOT_FOUND.send_priv(ctx, lobby_choice or ctx.channel.mention)
            return

        if not (p := await d_obj.registered_check(ctx, member)):
            return

        await ctx.defer(ephemeral=True)

        if p.lobby != lobby:
            await disp.LOBBY_PLAYER_NOT_IN.send_priv(ctx, p.name, lobby.name)
            return

        await lobby.lobby_leave(p)
        await disp.LOBBY_PLAYER_REMOVED.send_priv(ctx, p.name, lobby.name)

    #########################################################
    # Accounts Admin Commands
    accounts_admin = discord.SlashCommandGroup(
        name="accounts",
        description="Admin Accounts Commands",
        **common_kwargs
    )

    @accounts_admin.command(name="assign")
    async def account_assign(self, ctx: discord.ApplicationContext,
                             member: discord.Option(discord.Member, "Recipients @mention", required=True),
                             acc_id: discord.Option(int, "A specific account ID to assign, 1-24", min_value=1,
                                                    max_value=24,
                                                    required=False),
                             validated: discord.Option(bool, "Force Validate the Account, defaults to False",
                                                       default=False)):
        """Assign an account to a user, with optional specific account ID"""
        await ctx.defer(ephemeral=True)
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
            return
        if p.account:
            await accounts.terminate(p.account, force_clean=True)
        if not acc_id:
            acc = accounts.pick_account(p)
        else:
            acc = accounts.all_accounts[acc_id]
            if acc.a_player:
                return await disp.ACCOUNT_IN_USE.send_priv(ctx, acc.id)
            accounts.set_account(p, acc)

        if not acc:
            return await disp.ACCOUNT_NO_ACCOUNT.send_priv(ctx)

        if await accounts.send_account(acc, p):
            await disp.ACCOUNT_SENT_2.send_priv(ctx, p.mention, acc.id)

        if validated:
            await accounts.validate_account(acc)

        # if DM's failed
        if not acc.message:
            await disp.ACCOUNT_DM_FAILED.send_priv(ctx, p.mention)

    @accounts_admin.command(name="validate")
    async def account_validate(self, ctx: discord.ApplicationContext,
                               member: discord.Option(discord.Member, "Player whose account to validate",
                                                      required=True)):
        """Validate a player's account manually"""
        await ctx.defer(ephemeral=True)
        if not (p := await d_obj.registered_check(ctx, member)):
            return
        elif not p.account:
            await disp.ACCOUNT_NOT_ASSIGNED.send_priv(ctx, member.mention)
        elif await accounts.validate_account(p.account):
            await disp.ACCOUNT_VALIDATE_SUCCESS.send_priv(ctx, p.account.id, p.mention)
            return
        else:
            await disp.ACCOUNT_VALIDATE_ALREADY.send_priv(ctx)

    @accounts_admin.command(name="terminate")
    async def account_terminate(self, ctx: discord.ApplicationContext,
                                member: discord.Option(discord.Member, "Player whose account to terminate",
                                                       required=True),
                                clean: discord.Option(bool, "Should the account be force cleaned?", default=False)):
        """Terminate a player's account"""
        await ctx.defer(ephemeral=True)
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
            return
        if acc := p.account:
            await accounts.terminate(acc, force_clean=clean)
            cleaned_str = "Cleaned Account" if acc.is_clean else f"Account was not cleaned, " \
                                                                 f"player is online on {acc.online_name}"
            await disp.ACCOUNT_TERMINATED.send_priv(ctx, acc.id, cleaned_str)
        else:
            await disp.ACCOUNT_NOT_ASSIGNED.send_priv(ctx, p.mention)

    @accounts_admin.command(name='info')
    async def account_info(self, ctx: discord.ApplicationContext):
        """Provide info on FSBot's connected Jaeger Accounts"""
        num_available = len(accounts._available_accounts)
        assigned = accounts._busy_accounts.values()
        num_used = len(assigned)
        online = [acc for acc in accounts.all_accounts.values() if acc.online_id]
        await disp.ACCOUNT_INFO.send_priv(ctx, num_available=num_available, num_used=num_used, assigned=assigned,
                                          online=online)

    @accounts_admin.command(name='watchtower')
    async def watchtower_toggle(self, ctx: discord.ApplicationContext,
                                action: discord.Option(str,
                                                       "Enable, Disable or check status of the Unassigned Online "
                                                       "Tracker",
                                                       choices=("Enable", "Disable", "Status"), required=True)
                                ):
        """Accounts Watchtower Control"""
        running = accounts.UNASSIGNED_ONLINE_WARN
        changed = False

        if action == "Enable" and not running:
            accounts.UNASSIGNED_ONLINE_WARN = True
            changed = True
        elif action == "Disable" and running:
            accounts.UNASSIGNED_ONLINE_WARN = False
            changed = True
        string = f"Accounts watchtower was {'running' if running else 'stopped'}."
        if changed:
            string += f" It is now {'started' if accounts.UNASSIGNED_ONLINE_WARN else 'stopped'}."
            await d_obj.d_log(string)
        await ctx.respond(string, ephemeral=True)

    @accounts_admin.command(name='reload')
    async def accounts_reload(self, ctx: discord.ApplicationContext):
        """Run the Accounts Initializer Manually"""
        await ctx.defer(ephemeral=True)
        info = await accounts.init(cfg.GAPI_SERVICE)
        await d_obj.d_log(info)
        await disp.ANY.send_priv(ctx, info)

    @commands.message_command(name="Assign Account", **common_kwargs)
    @commands.max_concurrency(number=1, wait=True)
    async def msg_assign_account(self, ctx: discord.ApplicationContext, message: discord.Message):
        """
            Assign an account via Message Interaction
        """
        await ctx.defer(ephemeral=True)

        if not d_obj.is_admin(ctx.user):
            return await disp.CANT_USE.send_priv(ctx)

        p = Player.get(message.author.id)
        if not p:  # if not a player
            await disp.NOT_PLAYER_2.send_priv(ctx, message.author.mention)
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
        if await accounts.send_account(acc, p):
            await disp.ACCOUNT_SENT_2.send_priv(ctx, p.mention, acc.id)
            await message.add_reaction("\u2705")

        # if DM's failed
        else:
            await disp.ACCOUNT_DM_FAILED.send_priv(ctx, p.mention)
            await message.add_reaction("\u274C")

    @msg_assign_account.error
    async def msg_assign_account_concurrency_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.respond('Someone else is using this command right now, try again soon!', ephemeral=True)

    ##########################################################

    player_admin = discord.SlashCommandGroup(
        name="player",
        description="Admin Player Commands",
        **common_kwargs
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

    @commands.user_command(name="Player Info", **common_kwargs)
    async def user_player_info(self, ctx: discord.ApplicationContext, user: discord.User):
        """
            Get Player Info via User Interaction
        """
        await ctx.defer(ephemeral=True)
        p = Player.get(user.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, user.mention)
            return

        await disp.REG_INFO.send_priv(ctx, player=p)

    @player_admin.command(name='rename')
    async def player_rename(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.Member, "@mention to get info on", required=True),
                            name: discord.Option(str, "New name for Player, must be alphanumeric", required=True)):
        """Rename a given player"""
        await ctx.defer(ephemeral=True)
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
            return
        if await p.rename(name):
            await disp.REGISTER_RENAME.send_priv(ctx, member.mention, name)
            return
        await disp.REGISTER_INVALID_NAME.send_priv(ctx, name)

    @player_admin.command(name='clean')
    async def player_clean(self, ctx: discord.ApplicationContext,
                           member: discord.Option(discord.Member, "@mention to clean", required=True)):
        """Remove a player from their active commitments: lobbies, matches, accounts."""
        await ctx.defer(ephemeral=True)
        p = Player.get(member.id)
        if not p:
            await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
            return

        await p.clean()

        await disp.ADMIN_PLAYER_CLEAN.send_priv(ctx, p.mention)

    @player_admin.command(name='setcharacter')
    async def player_set_character(self, ctx: discord.ApplicationContext,
                                   member: discord.Option(discord.Member,
                                                          "@mention to modify online status. Defaults to you",
                                                          required=False),
                                   character: discord.Option(str,
                                                             "Character to show as online. Defaults to logout.",
                                                             autocomplete=player_chars_autocomplete,
                                                             required=False)):
        """Set a player's online status to one of their characters, or offline."""
        member = member or ctx.user
        if not (p := await d_obj.registered_check(ctx, member)):
            return
        if not p.has_own_account and not p.account:
            return await disp.ADMIN_PLAYER_NO_ACCOUNT.send_priv(ctx, p.mention)

        # Auto-complete character name from players characters
        found_chars = [char for char in p.ig_names if char.lower().find(character.lower()) >= 0] if character else False
        character = found_chars[0] if found_chars else character

        # If character is valid, set it as online
        if character and (char_id := p.
                char_id_by_name(character)):
            await census.login(char_id, accounts.account_char_ids, Player.map_chars_to_players())
            await disp.ADMIN_PLAYER_LOGIN_SET.send_priv(ctx, p.mention, character)
        # If no character, set player as offline
        elif p.online_name and not character:
            await census.logout(p.char_id_by_name(p.online_name), accounts.account_char_ids,
                                Player.map_chars_to_players())
            await disp.ADMIN_PLAYER_LOGOUT_SET.send_priv(ctx, p.mention)
        # If character not found, send error
        elif character:
            await disp.ADMIN_PLAYER_CHAR_NOT_FOUND.send_priv(ctx, character, p.mention)
        # If player is already offline, send error
        else:
            await disp.ADMIN_PLAYER_LOGOUT_ALREADY.send_priv(ctx, p.mention)

    register_admin = discord.SlashCommandGroup(
        name="register",
        description="Admin Registration Commands",
        **common_kwargs
    )

    @register_admin.command(name="noaccount")
    async def register_no_acc(self, ctx: discord.ApplicationContext,
                              member: discord.Option(discord.Member, "@mention to modify", required=True)):
        """Force register a specific player as not having a personal Jaeger account."""
        await ctx.defer(ephemeral=True)
        if (p := Player.get(member.id)) is None:
            return await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)

        if await p.register(None):
            return await disp.AS.send_priv(ctx, member.mention, disp.REG_SUCCESFUL_NO_CHARS())
        return await disp.AS.send_priv(ctx, member.mention, disp.REG_ALREADY_NO_CHARS())

    @register_admin.command(name="personal")
    async def register_personal_acc(self, ctx: discord.ApplicationContext,
                                    member: discord.Option(discord.Member, "@mention to modify", required=True)):

        """Force register a specific player with their personal jaeger account."""
        if (p := Player.get(member.id)) is None:
            return await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)
        await ctx.send_modal(register.RegisterCharacterModal(player=p))

    ###############################################################

    timeout_admin = discord.SlashCommandGroup(
        name="timeout",
        description="Admin Timeout Commands",
        **common_kwargs
    )

    @timeout_admin.command(name='check')
    async def timeout_check(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.Member, "@mention to check timeout for", required=True)):
        """Check the timeout status of a player"""
        if (p := Player.get(member.id)) and p.is_timeout:
            timestamps = [tools.format_time_from_stamp(p.timeout_until, x) for x in ("R", "F")]
            return await disp.TIMEOUT_UNTIL.send_priv(ctx, p.mention, p.name, *timestamps)
        await disp.TIMEOUT_NOT.send_priv(ctx, p.mention, p.name)

    @timeout_admin.command(name='until')
    async def timeout_until(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.Member, "@mention to timeout", required=True),
                            reason: discord.Option(str, name="reason", description="Reason for timeout"),
                            date: discord.Option(str, name="date",
                                                 description="Format YYYY-MM-DD", required=True,
                                                 min_length=10, max_length=10),
                            time_str: discord.Option(str, name="time",
                                                     description="Format HH:MM", default="00:00",
                                                     min_length=5, max_length=5),
                            zone: discord.Option(str, name="timezone",
                                                 description="Defaults to UTC", default="UTC",
                                                 # TODO Use an autocomplete to find timezone choices
                                                 choices=tools.pytz_discord_options())
                            ):
        """Timeout a player until a specific date/time, useful for long timeouts.  Timezone defaults to UTC."""
        await ctx.defer(ephemeral=True)
        full_dt_str = ' '.join([date, time_str])
        try:
            timeout_dt = dt.strptime(full_dt_str, '%Y-%m-%d %H:%M')
            timeout_dt = timezone(zone).localize(timeout_dt)
            stamp = int(timeout_dt.timestamp())
        except ValueError:
            return await disp.TIMEOUT_WRONG_FORMAT.send_priv(ctx, full_dt_str)

        if p := Player.get(member.id):
            # Check if timeout is in the past
            relative, short_time = tools.format_time_from_stamp(stamp, "R"), tools.format_time_from_stamp(stamp, "f")
            if stamp < tools.timestamp_now():
                return await disp.TIMEOUT_PAST.send_priv(ctx, short_time)

            # Set timeout, clear player
            await d_obj.timeout_player(p=p, stamp=stamp, mod=ctx.user, reason=reason)
            return await disp.TIMEOUT_NEW.send_priv(ctx, p.mention, p.name, relative, short_time)
        await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)

    @timeout_admin.command(name='for')
    async def timeout_for(self, ctx: discord.ApplicationContext,
                          member: discord.Option(discord.Member, "@mention to timeout", required=True),
                          reason: discord.Option(str, name="reason", description="Reason for timeout"),
                          minutes: discord.Option(int, "Minutes to timeout", default=0, min_value=0),
                          hours: discord.Option(int, "Hours to timeout", default=0, min_value=0),
                          days: discord.Option(int, "Days to timeout", default=0, min_value=0),
                          weeks: discord.Option(int, "Weeks to timeout", default=0, min_value=0)
                          ):
        """Timeout a player for a set period of time"""
        await ctx.defer(ephemeral=True)

        if (delta := timedelta(minutes=minutes, hours=hours, days=days, weeks=weeks)) + dt.now() == dt.now():
            return await disp.TIMEOUT_NO_TIME.send_priv(ctx)

        timeout_dt = dt.now() + delta

        if p := Player.get(member.id):
            # Set timeout, clear player
            await d_obj.timeout_player(p=p, stamp=int(timeout_dt.timestamp()), mod=ctx.user, reason=reason)

            timestamps = [tools.format_time_from_stamp(p.timeout_until, x) for x in ("R", "f")]
            return await disp.TIMEOUT_NEW.send_priv(ctx, p.mention, p.name, *timestamps)
        await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)

    @timeout_admin.command(name='clear')
    async def timeout_clear(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.Member, "@mention to end timeout for", required=True)):
        """Clear a specific players timeout"""
        await ctx.defer(ephemeral=True)
        if p := Player.get(member.id):
            if not p.is_timeout:
                return await disp.TIMEOUT_NOT.send_priv(ctx, p.mention, p.name)

            # Set Timeout to 0 (clearing it)
            await d_obj.timeout_player(p=p, stamp=0, mod=ctx.user)
            return await disp.TIMEOUT_CLEAR.send_priv(ctx, p.mention, p.name)
        await disp.NOT_PLAYER_2.send_priv(ctx, member.mention)

    ##############################################################

    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        if loader.is_all_loaded():
            return

        #  Wait until the bot is ready before starting loops, ensure account_handler has finished init
        await accounts.INITIALISED
        self.account_sheet_reload.start()
        if cfg.TEST:  # Don't start census if in test mode.  Allows for easier faction assignment testing
            log.warning("TEST MODE: Census and WSS not started")
        else:
            self.census_rest.start()
            self.wss_restart.start()
            log.info("Census REST and WSS Started..")

    @tasks.loop(seconds=60)
    async def census_rest(self):
        """Backup census method for checking accounts online status"""
        for _ in range(3):
            if await census.online_status_rest(Player.map_chars_to_players()):
                if self.census_rest.minutes != 1:
                    log.info("Census REST successfully ran, changing interval to 1 minute")
                    self.census_rest.change_interval(minutes=1)
                return True
            await asyncio.sleep(3)  # Wait before retrying
        log.warning("Could not reach REST api during census REST after 3 tries, increasing interval to 10 minutes")
        self.census_rest.change_interval(minutes=10)  # Increase interval to 10 minutes after failure
        return False

    @tasks.loop(hours=6)
    async def wss_restart(self):
        """Restart the census_watchtower regularly in order to stop it from dying?"""
        if self.census_watchtower and not self.census_watchtower.done():
            try:
                await census.EVENT_CLIENT.close()
            except Exception as e:
                log.error(f"Failed to close WSS: {e}")
            self.census_watchtower.cancel()
        self.census_watchtower = self.bot.loop.create_task(census.online_status_updater(Player.map_chars_to_players))

    # @census_watchtower.after_loop
    # async def after_census_watchtower(self):
    #     if self.census_watchtower.failed():
    #         await d_obj.log(f"{d_obj.colin.mention} Census Watchtower has failed")
    #     if self.census_watchtower.is_being_cancelled():
    #         await census.EVENT_CLIENT.close()

    @tasks.loop(time=time(hour=11, minute=0, second=0))
    async def account_sheet_reload(self):
        log.info("Reinitialized Account Sheet and Account Characters")
        await accounts.init(cfg.GAPI_SERVICE)


def setup(client):
    client.add_cog(AdminCog(client))

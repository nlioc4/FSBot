"""Class to handle lobby and invites """

# External Imports
from __future__ import annotations
import asyncio
import discord
from datetime import datetime as dt, timedelta
from logging import getLogger
from typing import Coroutine

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
import modules.database as db
from classes.players import Player
from classes.match import BaseMatch
from display import AllStrings as disp, embeds, views
import modules.tools as tools

log = getLogger('fs_bot')

RECENT_LOG_LENGTH: int = 8
RECENT_LOG_TIMEOUT: int = 10800  # three hours
LONGER_LOG_LENGTH: int = 30


class DashboardView(views.FSBotView):
    def __init__(self, lobby):
        super().__init__(timeout=None)
        self.lobby: Lobby = lobby
        if self.lobby.disabled:
            self.disable_all_items()
            return
        if self.lobby.lobbied:
            self.add_item(self.ChallengeDropdown(self.lobby))
        else:
            self.leave_lobby_button.disabled = True
            self.reset_lobby_button.disabled = True
            self.custom_timeout_lobby_button.disabled = True

    def update(self):
        if self.lobby.disabled:
            self.disable_all_items()
            return self
        self.enable_all_items()
        if self.lobby.lobbied:

            self.add_item(self.ChallengeDropdown(self.lobby))
        else:
            self.leave_lobby_button.disabled = True
            self.reset_lobby_button.disabled = True
            self.custom_timeout_lobby_button.disabled = True
        return self

    class ChallengeDropdown(discord.ui.Select):
        def __init__(self, lobby):
            self.lobby: Lobby = lobby
            options = []
            for player in lobby.lobbied:
                option = discord.SelectOption(label=player.name, value=str(player.id))
                options.append(option)

            plural = self.lobby.max_match_players > 2

            super().__init__(placeholder=f"Pick{' a' if not plural else ''} Player{'(s)' if plural else ''}"
                                         f" in the lobby to challenge...",
                             options=options,
                             min_values=1,
                             max_values=min(self.lobby.max_match_players - 1, len(options)),
                             )

        async def callback(self, inter: discord.Interaction, owner=None):
            owner: Player = owner if owner else Player.get(inter.user.id)
            if not await d_obj.registered_check(inter, owner):
                return
            invited_players: list[Player] = [Player.get(int(value)) for value in self.values]
            if owner in invited_players:
                await disp.LOBBY_INVITED_SELF.send_temp(inter, owner.mention)
                return
            if owner.match and owner.match.owner != owner:
                await disp.LOBBY_NOT_OWNER.send_priv(inter)
                return
            ## TODO Add check that lobby type matches
            already_invited = self.lobby.already_invited(owner, invited_players)
            if already_invited:
                await disp.LOBBY_INVITED_ALREADY.send_priv(inter, ' '.join([p.mention for p in already_invited]))
                [invited_players.remove(p) for p in already_invited]
                inter = inter.followup
            no_dms = list()
            for invited in invited_players:
                if not await self.lobby.send_invite(owner, invited):
                    no_dms.append(invited)
            if no_dms:
                await disp.LOBBY_NO_DM.send_temp(inter.channel, ','.join([p.mention for p in no_dms]))
                self.lobby.lobby_log(
                    f'{",".join([p.name for p in no_dms])} could not be invited, as they are not accepting DM\'s')
            remaining = [p for p in invited_players if p not in no_dms]
            remaining_mentions = ",".join([p.mention for p in remaining])

            if remaining and owner.match:
                await disp.LOBBY_INVITED_MATCH.send_temp(inter, owner.mention, remaining_mentions, owner.match.id_str,
                                                         allowed_mentions=discord.AllowedMentions(users=[inter.user]))
                self.lobby.lobby_log(
                    f'{owner.name} invited {",".join([p.name for p in remaining])} to Match: {owner.match.id_str}')

            elif remaining:
                await disp.LOBBY_INVITED.send_temp(inter, owner.mention, remaining_mentions,
                                                   allowed_mentions=discord.AllowedMentions(users=[inter.user]))
                self.lobby.lobby_log(f'{owner.name} invited {",".join([p.name for p in remaining])} to a match')

            else:
                await disp.LOBBY_NO_DM_ALL.send_priv(inter, owner.mention)

            self.lobby.schedule_dashboard_update()

    @discord.ui.button(label="Join Lobby", style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.registered_check(inter, player):
            return
        elif player.match:
            await disp.LOBBY_ALREADY_MATCH.send_priv(inter, player.mention,
                                                     player.match.thread.mention)
        elif not player.lobby:
            self.enable_all_items()
            await disp.LOBBY_JOIN.send_temp(inter, player.mention)
            self.lobby.lobby_join(player)
            self.lobby.schedule_dashboard_update()

        else:
            await disp.LOBBY_ALREADY_IN.send_priv(inter, player.mention)

    @discord.ui.button(label="Reset Timeout", style=discord.ButtonStyle.blurple)
    async def reset_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.registered_check(inter, player):
            return
        elif player in self.lobby.lobbied:
            await self.lobby.lobby_timeout_set(player)
            await disp.LOBBY_TIMEOUT_RESET.send_priv(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_priv(inter, player.mention)

    @discord.ui.button(label="Custom Timeout", style=discord.ButtonStyle.blurple)
    async def custom_timeout_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        if not (p := Player.get(inter.user.id)) or p.lobby != self.lobby:
            await disp.LOBBY_NOT_IN.send_priv(inter, p.mention)
        elif await self.lobby.check_player_timeout_status(p):
            await disp.LOBBY_TIMEOUT_ONLINE.send_priv(inter)
        else:
            await disp.LOBBY_TIMEOUT_CUSTOM.send_priv(inter, tools.format_time_from_stamp(p.lobby_timeout_stamp, 't'),
                                                      view=views.CustomLobbyTimeoutView())

    @discord.ui.button(label="Extended History", style=discord.ButtonStyle.blurple)
    async def history_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        if len(self.lobby.logs) <= len(self.lobby.logs_recent):
            await disp.LOBBY_NO_HISTORY.send_priv(inter, inter.user.mention)
            return
        await disp.LOBBY_LONGER_HISTORY.send_priv(inter, inter.user.mention, logs=self.lobby.logs_longer)

    @discord.ui.button(label="Leave Lobby", style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.registered_check(inter, player):
            return
        elif await self.lobby.lobby_leave(player):
            await inter.response.defer()
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)


class Lobby:
    all_lobbies = {}
    UPDATE_DELAY = 10  # seconds to wait between automatic updates

    @classmethod
    async def create_lobby(cls, name, channel, match_type=BaseMatch, timeout_minutes=30):
        if name in Lobby.all_lobbies:
            raise tools.UnexpectedError("%s lobby already exists!")

        obj = cls(name, channel, match_type, timeout_minutes)
        await obj.update()

        return obj

    @classmethod
    def get(cls, lobby) -> Lobby | None:
        return cls.all_lobbies.get(lobby)

    @staticmethod
    def channel_to_lobby(channel: discord.TextChannel) -> Lobby | None:
        channel_dict = {lobby.channel: lobby for lobby in Lobby.all_lobbies.values()}
        try:
            return channel_dict[channel]
        except KeyError:
            return None

    def __init__(self, name, channel, match_type, timeout_minutes):
        # vars
        self.name = name
        self.channel: discord.TextChannel = channel
        self.__match_type = match_type
        self.timeout_minutes = timeout_minutes
        self.__disabled = False

        # update
        self.__update_lock = asyncio.Lock()
        self.__next_update_task: asyncio.Task | None = None
        self.__next_update: Coroutine | None = None

        #  Display
        self.dashboard_msg: discord.Message | None = None
        self.dashboard_embed: discord.Embed | None = None
        self.__embed_func = embeds.duel_dashboard
        self.__view: DashboardView | None = None
        self.__view_func = DashboardView

        #  Containers
        self.__lobbied_players: list[Player] = []  # List of players currently in lobby
        self.__invites: dict[Player, list[Player]] = {}  # list of invites by owner.id: list[invited players]
        # self.__warned_players: list[Player] = []  # list of players that have been warned of impending timeout
        self.__warned_players: dict[
            Player, discord.Message] = {}  # dict of (Player, warning_message) for players warned of impending timeout
        self.__matches: list[BaseMatch] = []  # list of matches created by this lobby
        self.__logs: list[(int, str)] = []  # lobby logs recorded as a list of tuples, (timestamp, message)

        Lobby.all_lobbies[self.name] = self

    def lobby_log(self, message):
        self.__logs.append((tools.timestamp_now(), message))
        log.info(f'[{self.name}]Lobby Log: {message}')

    @property
    def logs(self):
        return self.__logs

    @property
    def logs_recent(self):
        return [item for item in self.__logs if
                item[0] > tools.timestamp_now() - RECENT_LOG_TIMEOUT][-RECENT_LOG_LENGTH:]

    @property
    def logs_longer(self):
        return self.__logs[-LONGER_LOG_LENGTH:]

    @property
    def lobbied(self):
        return self.__lobbied_players

    @property
    def matches(self):
        return self.__matches

    @property
    def warned(self):
        return self.__warned_players

    @property
    def max_match_players(self) -> int:
        return self.__match_type.MAX_PLAYERS

    @property
    def mention(self):
        return self.channel.mention

    def dashboard_purge_check(self, message: discord.Message):
        """Checks if messages are either the dashboard message, or an admin message before purging them"""
        if message != self.dashboard_msg and not d_obj.is_admin(message.author):
            return True
        else:
            return False

    def _new_embed(self):
        """Create a new embed for the lobby"""
        return self.__embed_func(self)

    def view(self, new=False):
        """Either return the current view, or create a new view from the set view_function
        New param will force a new view, otherwise one will only be created if required"""
        if not new and self.__view:
            return self.__view.update()
        return self.__view_func(self)

    async def update_dashboard_message(self, action="send", force=False):
        """Either sends a new dashboard message, or edits the existing message if required."""
        new_embed = self._new_embed()
        if not tools.compare_embeds(new_embed, self.dashboard_embed):
            self.dashboard_embed = new_embed
            force = True

        match action:
            case "send":
                return await self.channel.send(content="",
                                               embed=self.dashboard_embed,
                                               view=self.view())
            case "edit" if force:
                return await self.dashboard_msg.edit(content="",
                                                     embed=self.dashboard_embed,
                                                     view=self.view())

    async def create_dashboard(self):
        """Purges the channel, and then creates dashboard Embed w/ view"""
        try:
            msg_ids = await db.async_db_call(db.get_field, 'restart_data', 0, 'dashboard_msg_ids')
            msg_id = msg_ids[self.name]
            self.dashboard_msg = await self.channel.fetch_message(msg_id)
            self.dashboard_msg = await self.update_dashboard_message(action='edit', force=True)
        except (KeyError, discord.NotFound):
            log.info('No previous embed found for %s, creating new message...', self.name)
            self.dashboard_msg = await self.create_dashboard()
        finally:
            await db.async_db_call(db.set_field, 'restart_data', 0,
                                   {f'dashboard_msg_ids.{self.name}': self.dashboard_msg.id})
            await self.channel.purge(check=self.dashboard_purge_check)

    async def update_dashboard(self):
        """Checks if dashboard exists and either creates one, or updates the current dashboard and purges messages
        older than 5 minutes """
        if not self.dashboard_msg:
            await self.create_dashboard()
            return

        await self.channel.purge(before=(dt.now() - timedelta(minutes=5)),
                                 check=self.dashboard_purge_check)

        # Edit dashboard message if required, if not editable, send new message
        try:
            await self.update_dashboard_message('edit')
        except discord.NotFound as e:
            await d_obj.d_log(f'Unable to edit {self.name} dashboard message, resending...', error=e)
            await self.create_dashboard()

    def schedule_dashboard_update(self):
        """Schedules a dashboard update"""
        task = d_obj.bot.loop.create_task(self.update_dashboard())

    async def check_player_timeout_status(self, player: Player) -> bool:
        """Checks if a player should have timeout_stamp updated based on Player discord Status.
        Updates players timestamp if necessary, returns whether timestamp was updated"""
        player_memb = d_obj.guild.get_member(player.id)
        if player_memb.status in [discord.Status.online, discord.Status.do_not_disturb, discord.Status.streaming]:
            await self.lobby_timeout_set(player)
            return True
        return False

    async def lobby_timeout_set(self, player, timestamp=None):
        """Set the timestamp a player will be timed out from the lobby at.  If timestamp is not provided,
        sets to lobby default
         Returns True if player was in lobby"""
        timeout_at = timestamp or tools.timestamp_now() + self.timeout_minutes * 60

        if player in self.__lobbied_players:
            player.set_lobby_timeout(timeout_at)
            if msg := self.__warned_players.pop(player, None):
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
                self.lobby_log(f"{player.name} reset their lobby timeout.")
                await self.update()
            return True
        return False

    async def update_timeouts(self):
        """Check all lobbied players for timeouts, send timeout messages"""
        for p in self.lobbied:
            # Update timeout stamps

            if await self.check_player_timeout_status(p):
                pass

            # Timeout if current time greater than timeout stamp
            elif p.lobby_timeout_stamp < tools.timestamp_now():
                await self.lobby_leave(p, reason="timeout")

            # Warn if current time less than 5 minutes (300 s) before timeout stamp
            elif p.lobby_timeout_stamp - 300 < tools.timestamp_now() and p not in self.__warned_players:
                self.lobby_log(f'{p.name} will soon be timed out of the lobby.')
                self.__warned_players[p] = await disp.LOBBY_TIMEOUT_SOON.send(self.channel, p.mention,
                                                                              tools.format_time_from_stamp(
                                                                                  p.lobby_timeout_stamp, 'R'))

    def update_matches(self):
        """Remove matches from match list if ended"""
        for match in self.__matches:
            if match.is_ended:
                self.__matches.remove(match)

    async def _send_lobby_pings(self, player):
        """Gets list of players that could potentially be pinged, checks online status pursuant to preferences.
        Pings passing players, and marks them as pinged."""
        #TODO This can be refactored to be more efficient, but it's not a priority.
        # Could use new Player.member to avoid the extra dict mapping

        # Collect set of all players requesting these skill levels, if they haven't already been pinged
        players_to_ping = Player.get_players_to_ping(player.skill_level)
        if not players_to_ping:
            return

        # Map discord member objects to player objects, ensure Member object exists.
        player_membs_dict = {d_obj.guild.get_member(to_ping.id): to_ping for to_ping in players_to_ping
                             if d_obj.guild.get_member(to_ping.id) is not None}
        # Actually check online Status if pref requires it
        to_remove = []
        for p_m in player_membs_dict:
            if player_membs_dict[p_m].lobby_ping_pref == 1 and p_m.status != discord.Status.online:
                to_remove.append(p_m)
        for p_m in to_remove:
            player_membs_dict.pop(p_m)

        # build list of ping coroutines to execute
        ping_coros = []
        for p_m in player_membs_dict:
            player_membs_dict[p_m].lobby_last_ping = tools.timestamp_now()  # mark players as pinged
            ping_coros.append(disp.LOBBY_PING.send(p_m, player.mention, self.mention,
                                                   player_membs_dict[p_m].lobby_ping_freq))
        # Actually send all pings
        sent_pings = await asyncio.gather(*ping_coros, return_exceptions=True)

        # Log Which Users were Pinged
        pinged = []
        for message in sent_pings:
            if isinstance(message, Exception):
                log.info(f"Error sending lobby ping: {message}")
                continue
            if isinstance(message, discord.Message):
                pinged.append(Player.get(message.channel.recipient.id).name)
        if pinged:
            log.info(f"{', '.join(pinged)} pinged.")

    async def update(self):
        """Updates Lobby, including timeouts, displays and attached matches."""

        try:
            async with self.__update_lock:

                self.update_matches()
                await self.update_timeouts()
                await self.update_dashboard()
        except asyncio.CancelledError:
            pass
        else:
            # schedule next update if update completes successfully
            d_obj.bot.loop.call_soon(self._schedule_update_task)

    async def _update_task(self):
        await asyncio.sleep(self.UPDATE_DELAY)
        await self.update()

    def _schedule_update_task(self):
        """Schedules new update task, removes previous task"""
        self._cancel_update()

        self.__next_update_task = d_obj.bot.loop.create_task(self._update_task(), name=f"Lobby [{self.name}] Updater")

    def _cancel_update(self):
        """Cancel the next upcoming update, if it hasn't completed"""
        if self.__next_update_task and not self.__next_update_task.done():
            self.__next_update_task.cancel()

    async def disable(self):
        """Disable the Lobby"""
        if self.__disabled:
            return False
        self.__disabled = True
        await asyncio.gather(*[self.lobby_leave(p) for p in self.lobbied])
        self.lobby_log("Lobby Disabled")
        self._schedule_update_task()
        return True

    async def enable(self):
        """Enable the lobby"""
        if not self.__disabled:
            return False
        self.__disabled = False
        self.lobby_log("Lobby Enabled")
        self._schedule_update_task()
        return True

    @property
    def disabled(self):
        return self.__disabled

    async def lobby_leave(self, player, match=None, *, reason=''):
        """Removes from lobby list, executes player lobby leave method, returns True if removed
        Reason param lets you pass a custom leave reason."""
        if player in self.__lobbied_players:
            player.on_lobby_leave()
            self.__lobbied_players.remove(player)
            if msg := self.__warned_players.pop(player, None):
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
            if match:
                self.lobby_log(f'{player.name} joined Match: {match.id_str}')
            elif reason:
                self.lobby_log(f'{player.name} left the lobby due to {reason}.')
                await disp.LOBBY_LEAVE_REASON.send_long(self.channel, player.mention, reason)
            else:
                self.lobby_log(f'{player.name} left the lobby.')
                await disp.LOBBY_LEAVE.send_temp(self.channel, player.mention)
            self.schedule_dashboard_update()
            return True
        else:
            return False

    def lobby_join(self, player, timeout_at=None):
        """Adds to lobby list, executes player lobby join method, returns True if added.
        param timeout_at, timestamp to timeout player at.  Defaults to 60 minutes from now if not provided
        """
        if player not in self.__lobbied_players or not player.lobby:
            timeout_at = timeout_at or tools.timestamp_now() + self.timeout_minutes * 60
            player.on_lobby_add(self, timeout_at)
            self.__lobbied_players.append(player)
            self.lobby_log(f'{player.name} joined the lobby.')

            # schedule update_pings call, so that lobby join doesn't have to wait for it to complete
            asyncio.create_task(self._send_lobby_pings(player))

            return True
        else:
            return False

    async def send_invite(self, owner, invited) -> BaseMatch | bool:
        """Send an invitation to a player, and invite them to a match if sent"""
        for _ in range(3):
            try:
                memb = d_obj.guild.get_member(invited.id)
                view = views.InviteView(self, owner, invited)
                name_str = f'{owner.mention}({owner.name})[{owner.skill_level.rank}]'
                invite_timeout = tools.format_time_from_stamp(tools.timestamp_now() + view.timeout, "R")
                await disp.DM_INVITED.send(memb, invited.mention, name_str, invite_timeout, view=view)
                return self.invite(owner, invited)
            except discord.Forbidden:
                return False

    def invite(self, owner: Player, invited: Player):
        """Invite Player to match, if match already existed returns match.  Returns False if player couldn't be DM'd"""
        if owner.match:
            if owner.match.owner == owner:
                owner.match.invite(invited)
                return owner.match
            else:
                raise tools.UnexpectedError("Non match owner attempted to invite player")

        else:
            try:
                self.__invites[owner.id].append(invited)
                return True
            except KeyError:
                self.__invites[owner.id] = [invited]
                return True

    async def accept_invite(self, owner, player):
        """Accepts invite from owner to player, if match doesn't exist then creates it and returns match.
        If owner has since joined a different match, returns false."""
        if owner.match and owner.match.owner == owner:
            match = owner.match
            if not await match.join_match(player):
                return False  # if match join failed (match full)
            await self.lobby_leave(player, match)
            return match
        elif owner.active:
            return False
        else:

            match = await self.__match_type.create(owner, player, lobby=self)
            self.__matches.append(match)

            if owner.id in self.__invites:
                self.__invites[owner.id].remove(player)
                for other_player in self.__invites[owner.id]:
                    match.invite(other_player)
                del self.__invites[owner.id]
            await asyncio.gather(self.lobby_leave(player, match),
                                 self.lobby_leave(owner, match))
            return match

    def decline_invite(self, owner, player):
        """Decline an invitation from owner to player"""
        if owner.match and owner.match.owner == owner:
            owner.match.decline_invite(player)
        if owner.id in self.__invites:
            self.__invites[owner.id].remove(player)
            if not self.__invites[owner.id]:
                del self.__invites[owner.id]

    def already_invited(self, owner, invited_players):
        """Check which players in a given list the owner has already invited to a match"""
        already_invited_list = []
        for match in self.__matches:
            if match.owner.id == owner.id:
                already_invited_list.extend(
                    [p for p in invited_players if p in match.invited])  # check matches for already invited players
        if owner.id in self.__invites:
            already_invited_list.extend(  # check invites for already invited players
                [p for p in invited_players if p in self.__invites[owner.id]])
        return already_invited_list

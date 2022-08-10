"""Class to handle lobby and invites """

# External Imports
import asyncio
import discord
from datetime import datetime as dt, timedelta
from logging import getLogger

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
RECENT_LOG_TIMEOUT: int = 3600  # one hour
LONGER_LOG_LENGTH: int = 30


class DashboardView(views.FSBotView):
    def __init__(self, lobby):
        super().__init__(timeout=None)
        self.lobby: Lobby = lobby
        if self.lobby.disabled:
            self.disable_all_items()

        if self.lobby.lobbied:
            self.add_item(self.ChallengeDropdown(self.lobby))
        else:
            self.leave_lobby_button.disabled = True
            self.reset_lobby_button.disabled = True

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
            if not await d_obj.is_registered(inter, owner):
                return
            invited_players: list[Player] = [Player.get(int(value)) for value in self.values]
            if owner in invited_players:
                await disp.LOBBY_INVITED_SELF.send_temp(inter, owner.mention)
                return
            if owner.match and owner.match.owner != owner:
                await disp.LOBBY_NOT_OWNER.send_priv(inter)
                return
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

            await self.lobby.update_dashboard()

    @discord.ui.button(label="Join Lobby", style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)

        if not await d_obj.is_registered(inter, player):
            return
        elif player.match:
            await disp.LOBBY_ALREADY_MATCH.send_priv(inter, player.mention, player.match.text_channel.mention)
        elif await self.lobby.lobby_join(player):
            self.enable_all_items()
            await self.lobby.update_dashboard()
            await disp.LOBBY_JOIN.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_ALREADY_IN.send_priv(inter, player.mention)

    @discord.ui.button(label="Reset Timeout", style=discord.ButtonStyle.blurple)
    async def reset_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, player):
            return
        elif player in self.lobby.lobbied:
            self.lobby.lobby_timeout_reset(player)
            await disp.LOBBY_TIMEOUT_RESET.send_priv(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_priv(inter, player.mention)

    @discord.ui.button(label="Extended History", style=discord.ButtonStyle.blurple)
    async def history_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        if len(self.lobby.logs) <= len(self.lobby.logs_recent):
            await disp.LOBBY_NO_HISTORY.send_temp(inter, inter.user.mention)
            return
        await disp.LOBBY_LONGER_HISTORY.send(inter, inter.user.mention, logs=self.lobby.logs_longer, delete_after=20)

    @discord.ui.button(label="Leave Lobby", style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, player):
            return
        elif self.lobby.lobby_leave(player):
            await self.lobby.update_dashboard()
            await disp.LOBBY_LEAVE.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)


class Lobby:
    all_lobbies = {}

    @classmethod
    async def create_lobby(cls, name, channel, match_type=BaseMatch, timeout_minutes=30):
        if name in Lobby.all_lobbies:
            raise tools.UnexpectedError("%s lobby already exists!")

        obj = cls(name, channel, match_type, timeout_minutes)
        obj.dashboard_embed = embeds.duel_dashboard(obj)
        await obj.update_dashboard()

        return obj

    @staticmethod
    def channel_to_lobby(channel: discord.TextChannel):
        channel_dict = {lobby.channel: lobby for lobby in Lobby.all_lobbies.values()}
        try:
            return channel_dict[channel]
        except KeyError:
            return False

    def __init__(self, name, channel, match_type, timeout_minutes):
        # vars
        self.name = name
        self.channel: discord.TextChannel = channel
        self.__match_type = match_type
        self.timeout_minutes = timeout_minutes
        self.__disabled = False

        #  Display
        self.dashboard_msg: discord.Message | None = None
        self.dashboard_embed: discord.Embed | None = None
        self.__embed_func = embeds.duel_dashboard
        self.__view: DashboardView | None = None
        self.__view_func = DashboardView

        #  Containers
        self.__lobbied_players: list[Player] = []  # List of players currently in lobby
        self.__invites: dict[Player, list[Player]] = {}  # list of invites by owner.id: list[invited players]
        self.__warned_players: list[Player] = []  # list of players that have been warned of impending timeout
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
        return [item for item in self.__logs if item[0] > tools.timestamp_now() - RECENT_LOG_TIMEOUT][
               -RECENT_LOG_LENGTH:]

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

    async def _dashboard_message(self, action="send", force=False):
        """Either sends a new dashboard message, or edits the existing message if required."""
        new_embed = self._new_embed()
        requires_edit = force or False
        if not tools.compare_embeds(new_embed, self.dashboard_embed):
            self.dashboard_embed = new_embed
            requires_edit = True

        match action:
            case "send":
                return await self.channel.send(content="",
                                               embed=self.dashboard_embed,
                                               view=self.view())
            case "edit" if requires_edit:
                return await self.dashboard_msg.edit(content="",
                                                     embed=self.dashboard_embed,
                                                     view=self.view())

    async def create_dashboard(self):
        """Purges the channel, and then creates dashboard Embed w/ view"""
        if not self.dashboard_msg:
            try:
                msg_id = await db.async_db_call(db.get_field, 'restart_data', 0, 'dashboard_msg_id')
            except KeyError:
                log.info('No previous embed found for %s, creating new message...', self.name)
                self.dashboard_msg = await self._dashboard_message()
            else:
                self.dashboard_msg = await self.channel.fetch_message(msg_id)
                self.dashboard_msg = await self._dashboard_message(action='edit', force=True)
            finally:
                await db.async_db_call(db.set_field, 'restart_data', 0, {'dashboard_msg_id': self.dashboard_msg.id})
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
            await self._dashboard_message('edit')
        except discord.NotFound as e:
            await d_obj.d_log(f'Unable to edit {self.name} dashboard message, resending...', error=e)
            await self._dashboard_message()

    def _player_timeout_at(self, player: Player) -> int:
        """Determine a player timeout based on Player discord Status.
        returns Timestamp to timeout player at """
        player_memb = d_obj.guild.get_member(player.id)
        #  Determine potential timeout
        if player_memb.status in [discord.Status.online, discord.Status.do_not_disturb, discord.Status.streaming]:
            return 0
        else:
            return tools.timestamp_now() + (self.timeout_minutes * 60)

    async def update_timeouts(self):
        """Check all lobbied players for timeouts, send timeout messages"""
        for p in self.lobbied:

            # Update timeout stamps

            # Timeout stamp not set, and player lobbied 4x normal timeout ensure that player is indeed online
            if p.lobby_timeout_stamp == 0:
                if p.lobbied_stamp + self.timeout_minutes * 60 * 4 < tools.timestamp_now():
                    self.player_timeout_update(p)
                return

            # Timeout if current time greater than timeout stamp
            elif p.lobby_timeout_stamp < tools.timestamp_now():
                try:
                    self.lobby_timeout(p)
                except KeyError as e:
                    log.error(f"Error on timeout for {p.name}, running lobby_leave...", exc_info=e)
                    self.lobby_leave(p)
                await disp.LOBBY_TIMEOUT.send(self.channel, p.mention, delete_after=30)

            # Warn if current time less than 5 minutes (300 s) before timeout stamp
            elif p.lobby_timeout_stamp - 300 < tools.timestamp_now() and p not in self.__warned_players:
                self.__warned_players.append(p)
                self.lobby_log(f'{p.name} will soon be timed out of the lobby')
                await disp.LOBBY_TIMEOUT_SOON.send(self.channel, p.mention, delete_after=30)

    def update_matches(self):
        """Remove matches from match list if ended"""
        for match in self.__matches:
            if match.is_ended:
                self.__matches.remove(match)

    async def _update_pings(self, player):
        #  Make list of levels in the lobby
        levels_in_lobby = [p.skill_level for p in self.__lobbied_players]

        # Collect set of all players requesting these skill levels, if they haven't already been pinged
        players_to_ping = Player.get_players_to_ping(levels_in_lobby)
        if not players_to_ping:
            return

        # Check ping preferences and online status
        player_membs_dict = {d_obj.guild.get_member(to_ping.id): to_ping for to_ping in players_to_ping}
        to_remove = []
        for p_m in player_membs_dict:
            if player_membs_dict[p_m].lobby:
                to_remove.append(p_m)
            elif player_membs_dict[p_m].lobby_ping_pref == 1 and p_m.status != discord.Status.online:
                to_remove.append(p_m)
        for p_m in to_remove:
            player_membs_dict.pop(p_m)
        # build list of ping coroutines to execute
        ping_coros = []
        for p_m in player_membs_dict:
            ping_coros.append(disp.LOBBY_PING.send(p_m, player.mention, self.mention,
                                                   player_membs_dict[p_m].lobby_ping_freq))
        await asyncio.gather(*ping_coros)

        # Mark Players as pinged
        for p in player_membs_dict.values():
            p.lobby_last_ping = tools.timestamp_now()

    async def update(self):
        """Runs all update methods"""
        self.update_matches()
        await self.update_timeouts()
        await self.update_dashboard()

    async def disable(self):
        """Disable the Lobby"""
        if self.__disabled:
            return False
        self.__disabled = True
        for p in self.lobbied:
            self.lobby_leave(p)
        self.lobby_log("Lobby Disabled")
        await self.update()
        return True

    async def enable(self):
        """Enable the lobby"""
        if not self.__disabled:
            return False
        self.__disabled = False
        self.lobby_log("Lobby Enabled")
        await self.update()
        return True

    @property
    def disabled(self):
        return self.__disabled

    def lobby_timeout(self, player):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in self.__lobbied_players:
            player.on_lobby_leave()
            self.__lobbied_players.remove(player)
            self.__warned_players.remove(player)
            self.lobby_log(f'{player.name} was removed from the lobby by timeout.')
            return True
        else:
            return False

    def lobby_timeout_reset(self, player):
        """Resets player lobbied timestamp, using Discord status to set timeout duration.
         Returns True if player was in lobby"""
        if player in self.__lobbied_players:
            player.set_lobby_timeout(self._player_timeout_at(player))
            if player in self.__warned_players:
                self.__warned_players.remove(player)
                self.lobby_log(f"{player.name} reset their lobby timeout.")
            return True
        return False

    def player_timeout_update(self, p):
        # If Player not in lobby, or new lobby stamp == old lobby stamp, do nothing
        if p not in self.__lobbied_players or p.lobby_timeout_stamp == self._player_timeout_at(p):
            return
        # If old lobby stamp not 0 and new lobby stamp not 0, keep old lobby stamp.
        # This covers cases where player is still offline during multiple resets.
        if p.lobby_timeout_stamp != 0 and self._player_timeout_at(p) != 0:
            return
        # If all the above fails, reset timeout.  Will set to 0 if online, will set to new timeout if newly offline.
        self.lobby_timeout_reset(p)



    def lobby_leave(self, player, match=None):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in self.__lobbied_players:
            player.on_lobby_leave()
            self.__lobbied_players.remove(player)
            if player in self.__warned_players:
                self.__warned_players.remove(player)
            if match:
                self.lobby_log(f'{player.name} joined Match: {match.id_str}')
            else:
                self.lobby_log(f'{player.name} left the lobby.')
            return True
        else:
            return False

    async def lobby_join(self, player):
        """Adds to lobby list, executes player lobby join method, returns True if added.
        param timeout_at, timestamp to timeout player at
        """
        if player not in self.__lobbied_players:

            player.on_lobby_add(self, self._player_timeout_at(player))
            self.__lobbied_players.append(player)
            self.lobby_log(f'{player.name} joined the lobby.')
            await self._update_pings(player)
            return True
        else:
            return False

    async def send_invite(self, owner, invited) -> BaseMatch | bool:
        """Send an invitation to a player, and invite them to a match if sent"""
        for _ in range(3):
            try:
                memb = d_obj.guild.get_member(invited.id)
                view = views.InviteView(self, owner, invited)
                msg = await disp.DM_INVITED.send(memb, invited.mention, owner.mention, view=view)
                view.msg = msg
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
            await match.join_match(player)
            await match.update_embed()
            self.lobby_leave(player, match)
            return match
        elif owner.active:
            return False
        else:

            match = await BaseMatch.create(owner, player)
            self.__matches.append(match)

            await disp.MATCH_JOIN.send_temp(match.text_channel, f'{owner.mention}{player.mention}')
            if owner.id in self.__invites:
                self.__invites[owner.id].remove(player)
                for other_player in self.__invites[owner.id]:
                    match.invite(other_player)
                    del self.__invites[owner.id]
            self.lobby_leave(player, match)
            self.lobby_leave(owner, match)
            return match

    def decline_invite(self, owner, player):
        if owner.match and owner.match.owner == owner:
            owner.match.decline_invite(player)
        if owner.id in self.__invites:
            self.__invites[owner.id].remove(player)
            if not self.__invites[owner.id]:
                del self.__invites[owner.id]

    def already_invited(self, owner, invited_players):
        already_invited_list = []
        for match in self.__matches:
            if match.owner.id == owner.id:
                already_invited_list.extend(
                    [p for p in invited_players if p in match.invited])  # check matches for already invited players
        if owner.id in self.__invites:
            already_invited_list.extend(  # check invites for already invited players
                [p for p in invited_players if p in self.__invites[owner.id]])
        return already_invited_list

"""Class to handle lobby and invites """

# External Imports
import discord
from discord.ext import commands, tasks
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

            super().__init__(placeholder="Pick Player(s) in the lobby to challenge...",
                             custom_id='dashboard-challenge',
                             options=options,
                             min_values=1,
                             max_values=len(options),
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
        elif self.lobby.lobby_join(player):
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
            await disp.LOBBY_TIMEOUT_RESET.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)

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
        self.__view: DashboardView | None = None
        self.embed_func = embeds.duel_dashboard
        self.view_func = DashboardView

        #  Containers
        self.__lobbied_players: list[Player] = []  # List of players currently in lobby
        self.__invites: dict[Player, list[Player]] = {}  # list of invites by owner.id: list[invited players]
        self.__warned_players: list[Player] = []  # list of players that have been warned of impending timeout
        self.__matches: list[BaseMatch] = []  # list of matches created by this lobby
        self.__logs: list[(int, str)] = []  # lobby logs recorded as a list of tuples, (timestamp, message)

        Lobby.all_lobbies[self.name] = self

    def lobby_log(self, message):
        self.__logs.append((tools.timestamp_now(), message))
        log.info(f'{self.name} Lobby Log: {message}')

    @property
    def logs(self):
        return self.__logs

    @property
    def logs_recent(self):
        return self.__logs[-RECENT_LOG_LENGTH:]

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

    def dashboard_purge_check(self, message: discord.Message):
        """Checks if messages are either the dashboard message, or an admin message before purging them"""
        if message != self.dashboard_msg and not d_obj.is_admin(message.author):
            return True
        else:
            return False

    def _new_embed(self):
        return self.embed_func(self)

    def view(self, new=False):
        if not new and self.__view:
            return self.__view.update()
        return self.view_func(self)

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
            log.error(f'Unable to edit {self.name} dashboard message, resending...', e)
            await d_obj.d_log(f'Unable to edit {self.name} dashboard message, resending...')
            await self._dashboard_message()

    async def update_timeouts(self):
        """Check all lobbied players for timeouts, send timeout messages"""
        for p in self.lobbied:
            stamp_dt = dt.fromtimestamp(p.lobbied_timestamp)
            if stamp_dt < (dt.now() - timedelta(minutes=self.timeout_minutes)):
                self.lobby_timeout(p)
                await disp.LOBBY_TIMEOUT.send(self.channel, p.mention, delete_after=30)
            elif stamp_dt < (
                    dt.now() - timedelta(minutes=self.timeout_minutes - 5)) and p not in self.__warned_players:
                self.__warned_players.append(p)
                self.lobby_log(f'{p.name} will soon be timed out of the lobby')
                await disp.LOBBY_TIMEOUT_SOON.send(self.channel, p.mention, delete_after=30)

    async def update(self):
        """Runs all update methods"""
        await self.update_timeouts()
        await self.update_dashboard()

    def disable(self):
        if self.__disabled:
            return False
        self.__disabled = True
        for p in self.lobbied:
            self.lobby_leave(p)
        self.lobby_log("Lobby Disabled")
        return True

    def enable(self):
        if not self.__disabled:
            return False
        self.__disabled = False
        self.lobby_log("Lobby Enabled")
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
        """Resets player lobbied timestamp, returns True if player was in lobby"""
        if player in self.__lobbied_players:
            player.reset_lobby_timestamp()
            if player in self.__warned_players:
                self.__warned_players.remove(player)
            return True
        return False

    def lobby_leave(self, player, match=None):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in self.__lobbied_players:
            player.on_lobby_leave()
            self.__lobbied_players.remove(player)
            if match:
                self.lobby_log(f'{player.name} joined Match: {match.id_str}')
            else:
                self.lobby_log(f'{player.name} left the lobby.')
            return True
        else:
            return False

    def lobby_join(self, player):
        """Adds to lobby list, executes player lobby join method, returns True if added"""
        if player not in self.__lobbied_players:
            player.on_lobby_add(self)
            self.__lobbied_players.append(player)
            self.lobby_log(f'{player.name} joined the lobby.')
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
                for player in self.__invites[owner.id]:
                    match.invite(player)
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

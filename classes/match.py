"""Holds main match classes"""

# External Imports
from __future__ import annotations
import discord
import asyncio
from logging import getLogger
from enum import Enum
from typing import Coroutine, NamedTuple, List, Literal

# Internal Imports
import modules.discord_obj as d_obj
import modules.config as cfg
import modules.stats_handler as stats_handler
from display import AllStrings as disp, embeds, views
import modules.tools as tools
from classes.players import Player, ActivePlayer
import modules.database as db
import modules.accounts_handler as accounts
from classes.player_stats import PlayerStats

log = getLogger('fs_bot')

MATCH_TIMEOUT_TIME = 900
MATCH_WARN_TIME = 600
_match_id_counter = 0


class Round(NamedTuple):
    """Represents a single round of a match"""
    round_number: int
    p1_id: int
    p2_id: int
    winner: int | Literal[1, 2]
    p1_faction: str = ""
    p2_faction: str = ""
    defaulted: bool = False

    @property
    def winner_id(self):
        return self.p1_id if self.winner == 1 else self.p2_id

    @property
    def winner_faction(self):
        return self.p1_faction if self.winner == 1 else self.p2_faction


class MatchState(Enum):
    INVITING = "Waiting for players to join the match..."
    PICKING_FACTIONS = "Waiting for factions to be determined..."
    LOGGING_IN = "Waiting for players to log in..."
    GETTING_READY = "Waiting for players to be ready..."
    PLAYING = "Currently playing..."
    SWITCHING_SIDES = "Waiting for players to switch factions..."
    SUBMITTING = "Waiting for players to submit scores..."
    ENDED = "Match ended..."


class EndCondition(Enum):
    COMPLETED = "The match was completed successfully..."
    APPEALED = "The match outcome was appealed by one of the participants..."
    TOO_MANY_CONFLICTS = "The players tried to submit too many conflicting results..."
    TIMEOUT = "The match was ended by timeout..."
    EXTERNAL = "The match was ended externally..."
    CANCELLED = "The match was cancelled..."
    FORFEIT = "The match was forfeit by one player leaving early..."
    ERROR = "The match was ended due to an internal error..."


class BaseMatch:
    _active_matches = dict()
    _recent_matches = dict()
    UPDATE_DELAY = 15  # number of seconds to delay updates by
    MAX_PLAYERS = 10
    TYPE = "Casual"

    class MatchInfoView(views.FSBotView):
        """View to handle match controls"""

        def __init__(self, match):
            super().__init__(timeout=None)
            self.match = match
            if not self.match.should_warn:
                self.reset_timeout_button.style = discord.ButtonStyle.grey
                self.reset_timeout_button.disabled = True

        def update(self):
            # Update timeout reset button
            if self.match.should_warn:
                self.reset_timeout_button.style = discord.ButtonStyle.green
                self.reset_timeout_button.disabled = False
            else:
                self.reset_timeout_button.style = discord.ButtonStyle.grey
                self.reset_timeout_button.disabled = True

            # Update voice lock indicator
            if self.match.public_voice:
                self.voice_button.label = "Voice: Public"
                self.voice_button.style = discord.ButtonStyle.green
            else:
                self.voice_button.label = "Voice: Private"
                self.voice_button.style = discord.ButtonStyle.red

            if self.match.is_ended:
                self.disable_all_items()

            return self

        async def in_match_check(self, inter, p: Player | ActivePlayer) -> bool:
            if isinstance(p, Player):
                p = p.active
            if p in self.match.players:
                return True
            await disp.MATCH_NOT_IN.send_priv(inter, self.match.id_str)
            return False

        async def leave_button_callback(self, button: discord.Button, inter: discord.Interaction):
            """Callback for leave button"""
            p = Player.get(inter.user.id)
            if not await d_obj.registered_check(inter, p) or not await self.in_match_check(inter, p):
                return
            await inter.response.defer(ephemeral=True)

            if self.match.is_ended:  # do nothing if match already ended
                return

            await self.match.leave_match(p.active)

        @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
        async def leave_button(self, button: discord.Button, inter: discord.Interaction):
            await self.leave_button_callback(button, inter)

        @discord.ui.button(label="Reset Timeout", style=discord.ButtonStyle.green)
        async def reset_timeout_button(self, button: discord.Button, inter: discord.Interaction):
            """Resets the match from timeout, if there are more than two players"""
            await inter.response.defer(ephemeral=True)

            # Refuse timeout reset if less than 2 players
            if len(self.match.players) < 2:
                await disp.MATCH_TIMEOUT_NO_RESET.send_priv(inter.response, inter.user.mention)

            else:
                await self.match.reset_timeout()
                await disp.MATCH_TIMEOUT_RESET.send_priv(inter.response, inter.user.mention)

        @discord.ui.button(label="Request Account", style=discord.ButtonStyle.blurple)
        async def account_button(self, button: discord.Button, inter: discord.Interaction):
            """Requests an account for the player"""
            await inter.response.defer()
            p: Player = Player.get(inter.user.id)
            if not await d_obj.registered_check(inter, p) or not await self.in_match_check(inter, p):
                return
            elif p.has_own_account:
                await disp.ACCOUNT_HAS_OWN.send_priv(inter)
                return
            elif p.account and p.account.is_terminated:
                await accounts.clean_account(acc=p.account)
            elif p.account and p.account.message:
                await disp.ACCOUNT_ALREADY.send_priv(inter, f"<#{p.account.message.channel.id}>")
                return
            elif p.account and not p.account.message:
                await d_obj.d_log(f"Account {p.account.id} has no message to {p.mention}.  Cleaning...")
                await accounts.terminate(p.account, force_clean=True)
                return
            acc = accounts.pick_account(p)
            if acc:  # if account found
                msg = await accounts.send_account(acc)
                if msg:  # if allowed to dm user
                    await disp.ACCOUNT_SENT.send_priv(inter, f"<#{msg.channel.id}>")
                else:  # if couldn't dm
                    await disp.ACCOUNT_NO_DMS.send_priv(inter)

            else:  # if no account found
                await disp.ACCOUNT_NO_ACCOUNT.send_priv(inter)

        @discord.ui.button(label="Voice: Private", style=discord.ButtonStyle.red)
        async def voice_button(self, button: discord.Button, inter: discord.Interaction):
            """Toggles whether the match voice channel is public or private.  Only usable by the match Owner"""
            p = Player.get(inter.user.id)
            if p != self.match.owner and not d_obj.is_admin(inter.user):
                await disp.MATCH_NOT_OWNER.send_priv(inter)
                return
            await inter.response.defer(ephemeral=True)
            await self.match.toggle_voice_lock()

    def __init__(self, owner: Player, player: Player, lobby):
        # Vars
        global _match_id_counter
        _match_id_counter += 1
        self.__id = _match_id_counter
        self.owner = owner
        self.__lobby = lobby
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__end_condition = None
        self.timeout_stamp = None
        self.timeout_warned = False
        self.was_timeout = False
        self.__status = MatchState.LOGGING_IN
        self.__public_voice = False
        self._update_lock = asyncio.Lock()
        self._next_update_task: asyncio.Task | None = None  # store asyncio.Handle for next update call
        self._next_update: Coroutine | None = None

        # Display
        self.thread: discord.Thread | None = None
        self.voice_channel: discord.VoiceChannel | None = None
        self.info_message: discord.Message | None = None
        self.__timeout_message: discord.Message | None = None
        self.embed_cache: discord.Embed | None = None
        self._embed_func = embeds.match_info
        self.__view: BaseMatch.MatchInfoView | None = None
        self._view_class = self.MatchInfoView

        self._admin_log_embed_func = embeds.match_log
        self.admin_log_embed_cache: discord.Embed | None = None
        self._admin_log_message: discord.Message | None = None

        #  Containers
        self.__players: list[ActivePlayer] = [owner.on_playing(self),
                                              player.on_playing(self)]  # List of ActivePlayer, add owners active_player
        self.__previous_players: list[Player] = list()  # list of Player objects, who have left the match
        self.__invited = list()
        self.match_log = list()  # logs recorded as list of tuples, (timestamp, message, Public)

        self.__account_check_tasks = [asyncio.create_task(
            self._check_accounts_delay(*self.__players))]  # Task for account checking
        BaseMatch._active_matches[self.id] = self

    @classmethod
    def active_matches_list(cls) -> list['BaseMatch']:
        return list(BaseMatch._active_matches.values())

    @classmethod
    def active_matches_dict(cls):
        return BaseMatch._active_matches

    @classmethod
    def active_match_thread_ids(cls):
        return {match.thread.id: match for match in BaseMatch._active_matches.values()}

    @classmethod
    def get(cls, match_id: int) -> BaseMatch | RankedMatch:
        return cls._active_matches.get(match_id)

    @classmethod
    def get_by_thread(cls, thread: discord.Thread | int) -> BaseMatch | RankedMatch:
        if isinstance(thread, discord.Thread):
            thread = thread.id
        return cls.active_match_thread_ids().get(thread)

    @classmethod
    async def end_all_matches(cls):
        end_coros = [match.end_match(end_condition=EndCondition.EXTERNAL) for match in
                     cls.active_matches_dict().values()]
        await asyncio.gather(*end_coros)

    @classmethod
    async def create(cls, owner: Player, invited: Player, *, base_class=None, lobby=None) -> RankedMatch | BaseMatch:
        # init _match_id_counter if first match created
        global _match_id_counter
        if not _match_id_counter:
            last_match = await db.async_db_call(db.get_last_element, 'matches')
            if last_match:
                _match_id_counter = last_match['_id']

        # Create Match Object, init channels + first update
        base_class = base_class or cls
        obj = base_class(owner, invited, lobby)
        obj.log(f'{owner.name} created the match with {invited.name}')

        await obj._make_channels()  # Make thread ahd voice channel
        await obj.send_embed()  # Send initial embed

        obj.update_soon()  # Perform initial update

        # Show match creation message
        await disp.MATCH_CREATE.send(obj.thread, f'{owner.mention}{invited.mention}', obj.id_str)

        # If a player already has an account, update their account timeout
        for p in obj.players:
            if p.account:
                accounts.account_timeout_delay(p.player, p.account, accounts.MAX_TIME)

        return obj

    def set_id(self, match_id):
        self.__id = match_id

    async def _make_channels(self):
        try:
            # Create private thread
            self.thread: discord.Thread = await self.__lobby.channel.create_thread(
                name=f'{self.TYPE}┊{self.id_str}┊'
            )
            # Stop players from manually adding users to the thread
            await self.thread.edit(invitable=False)

            # Add players to thread
            add_corous = [self.thread.add_user(p.player.member) for p in self.__players]
            await asyncio.gather(*add_corous)

            # Create voice channel, with extended overwrites to set channel to private
            self.voice_channel = await d_obj.categories['user'].create_voice_channel(
                name=f'{self.TYPE}┊{self.id_str}┊Voice',
                overwrites=self._get_overwrites()
            )

        except (discord.HTTPException, discord.Forbidden) as e:
            await d_obj.d_log(source=self.owner.name,
                              message=f"Error Creating Match Channel for Match {self.id_str}",
                              error=e)
            await self.end_match(EndCondition.ERROR)

    async def toggle_voice_lock(self):
        """Toggles whether the matches voice channel is public or private.
          Returns whether channel is currently public"""

        if self.__public_voice:
            await self.set_voice_private()
        else:
            await self.set_voice_public()
        return self.__public_voice

    async def _clear_voice(self, all_users=False):
        #  gather disconnect coroutines if users not in match, and not admins
        to_disconnect = [memb.move_to(d_obj.channels['general_voice']) for memb in self.voice_channel.members
                         if all_users or memb.id not in [p.id for p in self.players] or not d_obj.is_admin(memb)]
        if to_disconnect:
            await asyncio.gather(*to_disconnect)

    async def set_voice_private(self):
        """Set the matches voice channel to private, only allowing members of the match to join.
           Disconnect any users that aren't members of the match / admins"""
        await self.voice_channel.set_permissions(d_obj.roles['view_channels'],
                                                 connect=False, view_channel=False)
        await self._clear_voice()
        self.__public_voice = False
        self.log("Voice Channel has been set to private!")
        await self.update()

    async def set_voice_public(self):
        """Set the matches' voice channel to public, allowing any user to join"""
        await self.voice_channel.set_permissions(d_obj.roles['view_channels'],
                                                 connect=True, view_channel=True)
        self.__public_voice = True
        self.log("Voice Channel has been set to public!")
        await self.update()

    def _get_overwrites(self):
        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False,
                                                                  send_messages=False),
            d_obj.roles['timeout']: discord.PermissionOverwrite(view_channel=False, connect=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True, connect=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True, connect=True),
            d_obj.roles['bot']: discord.PermissionOverwrite(view_channel=True, connect=True),
        }
        overwrites.update({d_obj.guild.get_member(p.id): discord.PermissionOverwrite(view_channel=True, connect=True)
                           for p in self.__players})
        return overwrites

    async def join_match(self, player: Player):
        if len(self.__players) >= self.MAX_PLAYERS:
            return False
        #  Joins player to match and updates permissions
        if player in self.__invited:
            self.__invited.remove(player)
        self.__players.append(player.on_playing(self))
        await self._channel_update(player, True)
        await disp.MATCH_JOIN.send(self.thread, player.mention)
        self.log(f'{player.name} joined the match')
        if player.account:
            accounts.account_timeout_delay(player, player.account, accounts.MAX_TIME)
        self.__account_check_tasks.append(asyncio.create_task(self._check_accounts_delay(player)))
        self.update_soon()
        return True

    async def leave_match(self, player: ActivePlayer):
        """Removes a player from a match.  Can end a match if conditions are met"""
        if not self.is_ended:
            # Conditions if player leaves while match is active

            #  If less than 2 Players, end match
            if len(self.__players) <= 2:
                await self.end_match(EndCondition.FORFEIT, leaving_player=player)
                return

            if player.player == self.owner:
                if len(self.players) >= 3 and not await self.change_owner():
                    # if 3 or more players and new owner possible, assign new owner rather than ending the match
                    await self.end_match(EndCondition.FORFEIT, leaving_player=player)
                    return

        if player in self.__players:
            self.__players.remove(player)
        self.__previous_players.append(player.on_quit())
        self.log(f'{player.name} left the match')

        #  If Player was assigned an account, start delayed termination
        if player.account:
            accounts.account_timeout_delay(player=player.player, acc=player.account, delay=300)

        #  After-leave active Match conditions
        if not self.is_ended:
            await asyncio.gather(
                self.update(),
                self._channel_update(player, None),
                self._clear_voice(),
                disp.MATCH_LEAVE.send(self.thread, player.mention, allowed_mentions=False),
            )

    async def change_owner(self, player: None | ActivePlayer = None):
        """Set a new owner if player provided, otherwise pick a new owner from players.
        Return new owner, or None if no new owner found."""

        player = player or next((p for p in self.__players if p.player != self.owner), None)

        if not player:
            return False

        self.owner = player.player
        await disp.MATCH_NEW_OWNER.send(self.thread, player.mention)
        await self.update()
        return player

    async def end_match(self, end_condition: EndCondition, details=None, leaving_player=None, force=False):
        """Ends the match, with a given end condition, and extra details if wanted.  Force will force the coroutine
        to run, even if the match is already considered ended.  Leaving_player is used in forfeits, to denote which
        player is leaving early.  Main process is covered by the update Asyncio.lock()"""
        if self.is_ended and not force:
            return
        async with self._update_lock:
            # Update vars, cancel next scheduled update
            self.end_stamp = tools.timestamp_now()
            self.status = MatchState.ENDED
            self.end_condition = end_condition
            self.log('Match Ended')
            self._cancel_update()
            self.__lobby.remove_match(self)

            # Cancel Account checks if not complete
            for task in self.__account_check_tasks:
                if not task.done():
                    task.cancel()

            # Display match ended to users
            await asyncio.gather(
                disp.MATCH_END.send(self.thread, self.id_str),
                self.update_embed(),
                self.update_match_log()
            )

            # Update DB with current players, then remove players
            await db.async_db_call(db.set_element, 'matches', self.id, self.get_end_data())
            with self.thread.typing():
                leave_coroutines = [self.leave_match(player) for player in self.__players]
                await asyncio.gather(*leave_coroutines)
                await asyncio.sleep(5)

            # Store match object, trim _recent_matches if it is too large
            BaseMatch._recent_matches[self.id] = BaseMatch._active_matches.pop(self.id)
            if len(BaseMatch._recent_matches) > 50:
                keys = list(BaseMatch._recent_matches.keys())
                for i in range(20):
                    del BaseMatch._recent_matches[keys[i]]

            #  Move Users to general voice, delete voice channel, lock thread if not already deleted
            await self._clear_voice(all_users=True)
            try:
                await asyncio.gather(
                    self.voice_channel.delete(reason='Match Ended'),
                    self.thread.edit(archived=True, locked=True, reason='Match Ended'),
                    return_exceptions=True
                )
            except discord.NotFound:
                pass

    def get_end_data(self):
        data = {'_id': self.id, 'type': self.TYPE, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'end_condition': self.__end_condition.name,
                'owner': self.owner.id,
                'channel_id': 0 if not self.thread else f'{self.thread.parent_id}/{self.thread.id}',
                'current_players': [p.id for p in self.__players],
                'previous_players': [p.id for p in self.__previous_players],
                'match_log': self.match_log}
        return data

    async def _channel_update(self, player, action: bool | None):
        """Updates a players access to the Matches channels / threads"""
        await asyncio.gather(
            self.thread.add_user(player.member) if action else self.thread.remove_user(player.member),
            self.voice_channel.set_permissions(player.member, view_channel=action, connect=action)
        )

    def _new_embed(self):
        return self._embed_func(self)

    def view(self, new=False):
        """Retrieve the current view, or create a new one if needed.
        :param new: Force a new view to be created
        """
        if not new and self.__view:
            return self.__view.update()
        self.__view = self._view_class(self)
        return self.__view

    async def send_embed(self):
        """Send a new embed to the match thread"""
        if not self.embed_cache:
            self.embed_cache = self._new_embed()
        if not self.thread:  # can't find the thread, pass and wait for next update
            return
        self.info_message = await disp.NONE.send(self.thread, embed=self.embed_cache, view=self.view())
        await self.info_message.pin()

    async def _check_accounts_delay(self, *players_to_check):
        """Check for players that have no personal account, and are yet to send a request for a temp account"""
        await asyncio.sleep(300)  # run check after 5 minutes
        no_acc = []
        for p in players_to_check:
            if not p.has_own_account and not p.account and p.match == self:
                no_acc.append(p)
        if no_acc:
            await disp.MATCH_NO_ACCOUNT.send(self.thread, ''.join([p.mention for p in no_acc]),
                                             d_obj.channels['register'].mention)

    async def update_embed(self):
        """Update the match embed if required.  If no embed found, send a new one."""
        if self.info_message:
            if not tools.compare_embeds(self.embed_cache, new_embed := self._new_embed()):
                self.embed_cache = new_embed

                try:
                    await disp.NONE.edit(self.info_message, embed=self.embed_cache, view=self.view())
                except discord.errors.NotFound as e:
                    log.error("Couldn't find self.info_message for Match %s", self.id_str, exc_info=e)
                    await self.send_embed()
        else:
            await self.send_embed()

    async def send_admin_log(self):
        """Send a new Admin Log for this match"""
        if not self.admin_log_embed_cache:
            self.admin_log_embed_cache = self._admin_log_embed_func(self)
        self._admin_log_message = await disp.NONE.send(d_obj.channels['match_history'],
                                                       embed=self.admin_log_embed_cache)

    async def update_match_log(self):
        """Update the Admin Match Log if required.  If no embed found, send a new one."""
        if self._admin_log_message:
            if not tools.compare_embeds(self.admin_log_embed_cache, new_embed := self._admin_log_embed_func(self)):
                self.admin_log_embed_cache = new_embed

                try:
                    await disp.NONE.edit(self._admin_log_message, embed=self.admin_log_embed_cache)

                except discord.errors.NotFound as e:
                    log.error("Couldn't find self._admin_log_message for Match %s", self.id_str, exc_info=e)
                    await self.send_admin_log()
        else:
            await self.send_admin_log()

    def update_status(self):
        """Simple status update, check for number of online/logged in players"""
        if len(self.players) < 2:
            self.status = MatchState.INVITING
        elif len(self.online_players) < 2:
            self.status = MatchState.LOGGING_IN
        elif self.online_players:
            self.status = MatchState.PLAYING

    async def reset_timeout(self):
        """Resets the matches current timeout if one is set, deletes old timeout warning"""
        if self.__timeout_message:
            try:
                await self.__timeout_message.delete()
            except discord.errors.NotFound:
                log.error("No timeout warning message found for match %s", self.id_str)
        if self.timeout_stamp:  # only reset if timeout_stamp is set
            self.timeout_stamp = None
            if self.timeout_warned:  # only log if warned
                self.timeout_warned = False
                self.log("Match Timeout Reset")
            await self.update()

    async def update_timeout(self):
        # check timeout, reset if at least 2 players and online_players
        if self.online_players and len(self.players) >= 2:
            asyncio.create_task(self.reset_timeout())  # Reset timeout, create task as this coro uses update lock
        else:
            if not self.timeout_stamp:  # set timeout stamp
                self.timeout_stamp = tools.timestamp_now()
                self.timeout_warned = False
            elif self.should_timeout and not self.was_timeout:  # Timeout Match
                self.was_timeout = True
                self.log("Match timed out for inactivity...")
                await disp.MATCH_TIMEOUT.send(self.thread, self.all_mentions)
                # Use create_task, so that on_update doesn't wait for on_timeout
                asyncio.create_task(self.end_match(end_condition=EndCondition.TIMEOUT))
                raise asyncio.CancelledError
            elif self.should_warn and not self.timeout_warned:  # Warn of timeout
                self.timeout_warned = True
                self.log("Unless the timeout is reset, the match will timeout soon...")
                self.__timeout_message = await disp.MATCH_TIMEOUT_WARN.send(
                    self.thread, self.all_mentions,
                    tools.format_time_from_stamp(self.timeout_at, 'R'))

    async def update(self):
        """Update the match object:  updates timeout, match status, and the embed if required"""
        # ensure exclusive access to update
        try:
            async with self._update_lock:
                if self.is_ended:  # Quit update if match is ended
                    return

                # Check if the match should be warned / timed out
                await self.update_timeout()

                # Updated Match Status
                self.update_status()

                # Reflect match embed with updated match attributes, also updates match view
                # Also updates admin log embed
                await asyncio.gather(self.update_embed(), self.update_match_log())
        except asyncio.CancelledError:
            pass
        else:
            # schedule next update
            d_obj.bot.loop.call_later(0.1, self._schedule_update_task)

    def update_soon(self):
        """Schedule an update for the match immediately, without waiting for the coroutine to finish"""
        d_obj.bot.loop.create_task(self.update(), name=f'Match [{self.id_str}] Updater')

    async def _update_task(self):
        """Task wrapper around update call to add delay"""
        await asyncio.sleep(self.UPDATE_DELAY)
        await self.update()

    def _schedule_update_task(self):
        """Schedule next update of the match, cancel currently scheduled update."""
        # Cancel next update if it exists
        self._cancel_update()

        # Schedule next update
        self._next_update_task = d_obj.bot.loop.create_task(self._update_task(), name=f'Match [{self.id_str}] Updater')

    def _cancel_update(self):
        """Cancel the next upcoming update"""
        if self._next_update_task and not self._next_update_task.done():
            self._next_update_task.cancel()

    def log(self, message, public=True):
        self.match_log.append((tools.timestamp_now(), message, public))
        log.info(f'Match ID [{self.id}]: {message}')

    def char_login(self, user):
        self.log(f"{user.name} logged in as {user.online_name}")
        self.update_soon()

    def char_logout(self, user, char_name):
        self.log(f"{user.name} logged out from {char_name}")
        self.update_soon()

    @property
    def recent_logs(self):
        return self.match_log[-15:]

    def get_log_fields(self, max_fields=5, show_all=False):
        """Return a list of EmbedFields, split by maximum embed string length
        if necessary (maximum string length of 1000).

        :param max_fields: The maximum number of fields to return, defaults to 5.
        Returns fields closest to current time.
        :param show_all: If True, all entries will be shown, otherwise only public entries will be shown.
        """
        fields = []
        current_field = discord.EmbedField(name='\u200b', value='', inline=False)
        for entry in self.match_log:
            # Check if Entry should be public
            if not entry[2] and not show_all:
                continue

            # Set up next string
            next_string = f'[{tools.format_time_from_stamp(entry[0], "T")}] {entry[1]}\n'
            # Check if next string is too long to be added to current field
            if len(current_field.value) + len(next_string) > 1000:
                fields.append(current_field)
                current_field = discord.EmbedField(name='\u200b', value='', inline=False)
            current_field.value += next_string

        # Check if current field is empty, if not add to list
        if current_field.value:
            fields.append(current_field)

        # Trim fields if necessary
        if len(fields) > max_fields:
            fields = fields[-max_fields:]

        # Set first field in returns title to 'Match Log', if fields exist
        if fields:
            fields[0].name = 'Match Log'
        return fields

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, value):
        if not value >= _match_id_counter:
            raise ValueError('Match ID\'s must be equal to / higher than the Match Id Counter, %s', _match_id_counter)
        self.__id = value

    @property
    def id_str(self):
        return str(self.__id).zfill(4)

    @property
    def players(self):
        return self.__players

    @property
    def prev_players(self):
        return self.__previous_players

    @property
    def all_players(self) -> list[ActivePlayer]:
        return [*self.__players, *self.__previous_players]

    @property
    def invited(self):
        return self.__invited

    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, value):
        if value not in MatchState:
            raise ValueError(f'Status must be a value of MatchState, not {value}')
        self.__status = value

    @property
    def is_ended(self):
        return self.status == MatchState.ENDED

    @property
    def end_condition(self):
        return self.__end_condition

    @end_condition.setter
    def end_condition(self, value):
        if value not in EndCondition:
            raise ValueError(f'End Condition must be a value of EndCondition, not {value}')
        self.__end_condition = value

    @property
    def has_standard_end(self):
        return self.__end_condition in (EndCondition.COMPLETED, EndCondition.FORFEIT)

    @property
    def online_players(self):
        return [p for p in self.__players if p.online_name]

    @property
    def all_mentions(self):
        return ''.join([p.mention for p in self.__players])

    @property
    def public_voice(self):
        return self.__public_voice

    @property
    def timeout_at(self):
        if not self.timeout_stamp:
            return False
        return self.timeout_stamp + MATCH_TIMEOUT_TIME

    @property
    def should_warn(self):
        if not self.timeout_stamp:
            return False
        return True if self.timeout_stamp + MATCH_WARN_TIME <= tools.timestamp_now() else False

    @property
    def should_timeout(self):
        if not self.timeout_stamp:
            return False
        return True if self.timeout_stamp + MATCH_TIMEOUT_TIME <= tools.timestamp_now() else False

    def invite(self, player: Player):
        if player not in self.__invited:
            self.__invited.append(player)

    def decline_invite(self, player: Player):
        if player in self.__invited:
            self.__invited.remove(player)


class RankedMatch(BaseMatch):
    """
    picking factions -> logging in
    (player1 faction, player2 faction)
    logging in -> playing
    (player1 logged in player2 logged in)
    playing
    (player1 logged in, player2 logged in, scores not submitted)
        -> log in (log out by accident)
        -> submitting (round ends)
    submitting
    (only one score submitted)
        -> log in (need to switch sides)
        -> match ends (winner declared)
        -> playing
        -> conflicting scores
            -> appeal
            -> submitting
    """
    MATCH_LENGTH = 9  # Number of Rounds in a Match
    FACTION_SWAP_ENABLED = False  # Whether players must swap factions between rounds
    MAX_PLAYERS = 2  # Number of Players in a Match
    WRONG_SCORE_LIMIT = 3  # Number of times a player can submit a wrong score before the match is cancelled
    TYPE = 'Ranked'

    class RankedMatchView(BaseMatch.MatchInfoView):
        """Match View for Ranked Matches"""

        def __init__(self, match: 'RankedMatch'):
            super().__init__(match)
            self.match = match
            self.last_round = self.match.current_round
            self.round_button = discord.ui.Button(label=f'Round: {self.match.current_round}', row=1, disabled=True)
            self.player1_button = discord.ui.Button(label=self.match.player1.name_and_char_display, row=1,
                                                    disabled=True)
            self.vs_button = discord.ui.Button(label="VS", row=1, disabled=True)
            self.player2_button = discord.ui.Button(label=self.match.player2.name_and_char_display, row=1,
                                                    disabled=True)
            for button in [self.round_button, self.player1_button, self.vs_button, self.player2_button]:
                self.add_item(button)

            self.round_won_button = discord.ui.Button(label="Round Won", row=2, disabled=True,
                                                      style=discord.ButtonStyle.green)
            self.round_won_button.callback = lambda ctx: self.match.submit_score_callback(won=True, ctx=ctx)
            self.add_item(self.round_won_button)

            self.round_lost_button = discord.ui.Button(label="Round Lost", row=2, disabled=True,
                                                       style=discord.ButtonStyle.red)
            self.round_lost_button.callback = lambda ctx: self.match.submit_score_callback(won=False, ctx=ctx)
            self.add_item(self.round_lost_button)

        def update(self):
            """Update the match view.  Return itself to allow updating in the same line as sending"""
            # Update Round Display Buttons if round has changed
            if self.last_round != self.match.current_round:

                # Update Round Buttons
                self.round_button.label = f'Round: {self.match.current_round}'

                self.player1_button.label = self.match.player1.name_and_char_display
                self.player1_button.emoji = self.match.player1.assigned_faction_emoji
                if self.match.player1.assigned_faction_abv == "NC":
                    self.player1_button.style = discord.ButtonStyle.blurple
                else:
                    self.player1_button.style = discord.ButtonStyle.red

                self.player2_button.label = self.match.player2.name_and_char_display
                self.player2_button.emoji = self.match.player2.assigned_faction_emoji
                if self.match.player2.assigned_faction_abv == "NC":
                    self.player2_button.style = discord.ButtonStyle.blurple
                else:
                    self.player2_button.style = discord.ButtonStyle.red

            # Update Round Won/Lost Buttons
            if self.match.round_in_progress:
                self.round_won_button.disabled = False
                self.round_lost_button.disabled = False
            else:
                self.round_won_button.disabled = True
                self.round_lost_button.disabled = True

            return super().update()

        async def leave_button_callback(self, button: discord.Button, inter: discord.Interaction):
            """Ranked Match Specific Leave button callback"""
            p = Player.get(inter.user.id)
            if not await d_obj.registered_check(inter, p) or not await self.in_match_check(inter, p):
                return
            await inter.response.defer(ephemeral=True)

            if self.match.is_ended:
                # if Match has ended when button clicked.
                return

            if self.match.rounds_complete == 0:
                # If Match has not had a round completed yet
                await disp.MATCH_LEAVE.send(self.match.thread, p.mention)
                await self.match.end_match(end_condition=EndCondition.CANCELLED, leaving_player=p)

            else:
                confirm = views.ConfirmView(timeout=30)

                await disp.RM_FORFEIT_CONFIRM.send_priv(inter, ping=p,
                                                        view=confirm)
                if await confirm.confirmed:
                    self.match.log(f"Match is ending due to {p.name} leaving early!")
                    await self.match.leave_match(p.active)
                    await self.match.end_match(EndCondition.FORFEIT, leaving_player=p)

        @discord.ui.button(label="Appeal", style=discord.ButtonStyle.red)
        async def appeal_button(self, button: discord.Button, inter: discord.Interaction):
            if self.match.status != MatchState.SUBMITTING:
                return await disp.INVALID_INTERACTION.send_priv(inter)
            p = Player.get(inter.user.id)
            if not await d_obj.registered_check(inter, p) or not await self.in_match_check(inter, p):
                return
            await disp.RM_APPEALED.send_priv(inter, self.match.id_str)
            await self.match.end_match(EndCondition.APPEALED)

    class RankedRoundView(views.FSBotView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__(timeout=None)
            self.match = match

        @discord.ui.button(label="Round Won", style=discord.ButtonStyle.green)
        async def round_won_button(self, button: discord.Button, inter: discord.Interaction):
            await self.match.submit_score_callback(won=True, ctx=inter)

        @discord.ui.button(label="Round Lost", style=discord.ButtonStyle.red)
        async def round_lost_button(self, button: discord.Button, inter: discord.Interaction):
            await self.match.submit_score_callback(won=False, ctx=inter)

    def __init__(self, owner: Player, invited: Player, lobby):
        super().__init__(owner, invited, lobby)

        # Set Initial Status
        self.status = MatchState.PICKING_FACTIONS

        # Player Objects
        self.player1 = self.players[0]
        self.player2 = self.players[1]
        self._player1_stats: PlayerStats | None = None
        self._player2_stats: PlayerStats | None = None
        self.first_pick = None  # ActivePlayer obj of first pick
        self.first_picked_faction = ""  # string abbreviation for faction first picked

        # Match Variables
        self.__round_history: List[Round] = []
        self.__match_outcome: int = 0

        # Round Variables
        self.__round_wrong_scores_counter = 0

        self.__p1_submitted_score = None
        self.__p2_submitted_score = None

        # Display Objects
        self._round_message: discord.Message | None = None
        self._embed_func = embeds.ranked_match_info
        self._view_class = self.RankedMatchView

    @classmethod
    async def create(cls, owner: Player, invited: Player, *, base_class=None, lobby=None) -> RankedMatch:
        obj = await super().create(owner, invited, base_class=cls, lobby=lobby)  # RankedMatch create

        # Retrieve Stats PlayerStats
        obj._player1_stats = await PlayerStats.fetch_from_db(p_id=owner.id, p_name=owner.name)
        obj._player2_stats = await PlayerStats.fetch_from_db(p_id=invited.id, p_name=invited.name)
        obj.first_pick = obj._first_faction_pick()

        # Start Faction Picker
        await disp.RM_FACTION_PICK.send(obj.thread, obj.first_pick.mention, view=obj.FactionPickView(obj))

        return obj

    @classmethod
    async def create_from_data(cls, data: dict):
        """Create a RankedMatch in progress from data in the Database"""
        owner = Player.get(data['owner'])
        invited = Player.get(data['player2_id'])
        obj = await super().create(owner, invited, base_class=cls)
        # TODO will need to be edited for reopening threads

        # Set Variables
        obj.set_id(data['_id'])
        obj.start_stamp = data['start_stamp']
        obj.match_log = data['match_log']

        # Retrieve Current Stats Objects
        obj._player1_stats = await PlayerStats.fetch_from_db(p_id=owner.id, p_name=owner.name)
        obj._player2_stats = await PlayerStats.fetch_from_db(p_id=invited.id, p_name=invited.name)

        # Fill out round objects
        obj.add_rounds_from_data(*data['round_history'])

        # Set player Factions
        obj.first_pick = Player.get(data['first_pick']).active
        obj.first_picked_faction = data['first_picked_faction']

        obj.first_pick.assigned_faction_id = obj.first_picked_faction
        second_pick = obj.player1 if obj.first_pick is obj.player2 else obj.player2
        second_pick.assigned_faction_id = 2 if obj.first_pick == 3 else 3

        if obj.rounds_complete >= obj.wins_required - 1 and obj.FACTION_SWAP_ENABLED:
            await obj._switch_factions()

        return obj

    # def get_round_view(self):
    #     return self.RankedRoundView(self)

    def get_player(self, user: discord.Member | discord.User):
        """Utility method to get the Player object from a Discord user for a match.
        Returns False if player is not in the match"""
        p_id = user.id
        if p_id == self.player1.id:
            return self.player1
        elif p_id == self.player2.id:
            return self.player2
        else:
            return False

    async def player_check(self, inter: discord.Interaction):
        """Utility method to check if a player is in the match.
        Sends a message to the player and returns False if they are not in the match"""
        if not (p := self.get_player(inter.user)):
            await disp.MATCH_NOT_IN.send_priv(inter, self.id_str)
            return False
        return p

    def get_end_data(self):

        return {
            **super().get_end_data(),
            'player1_id': self.player1.id,
            'player2_id': self.player2.id,
            'first_pick': self.first_pick.id,
            'first_picked_faction': self.first_picked_faction,
            'match_outcome': self.__match_outcome,
            'round_history': [r._asdict() for r in self.__round_history]
        }

    # Faction Picks
    class FactionPickView(views.FSBotView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__()
            self.match = match
            self.tr_pick_button.emoji = cfg.emojis.get("TR")
            self.nc_pick_button.emoji = cfg.emojis.get("NC")

        async def picked_fac(self, faction_id, inter):
            """Executes all logic for faction pick buttons, as well as handling response."""
            if not (p := await self.match.player_check(inter)):
                return False

            if not p == self.match.first_pick:
                await disp.RM_FACTION_NOT_PICK.send_priv(inter)
                return False

            # Set the unpicked faction, build vars
            faction_str = cfg.factions[faction_id]
            other_faction_id = 2 if faction_id == 3 else 3
            other_faction_str = cfg.factions[other_faction_id]

            # Set Player Factions in Player Objects
            if p == self.match.player1:
                other_p = self.match.player2
            else:
                other_p = self.match.player1
            self.match.first_picked_faction = faction_id
            p.assigned_faction_id = faction_id  # Set Chosen faction var for each player
            other_p.assigned_faction_id = other_faction_id

            self.match.log(f"{p.name} picked {faction_str}, {other_p.name} has been assigned {other_faction_str}!")
            asyncio.create_task(self.match.update())
            return await disp.RM_FACTION_PICKED.send(inter,
                                                     p.mention,
                                                     faction_str + cfg.emojis[faction_str],
                                                     other_p.mention,
                                                     other_faction_str + cfg.emojis[other_faction_str])

        @discord.ui.button(label="NC", style=discord.ButtonStyle.blurple)
        async def nc_pick_button(self, button: discord.Button, inter: discord.Interaction):
            if await self.picked_fac(2, inter):
                self.tr_pick_button.style = discord.ButtonStyle.grey
                self.disable_all_items()
                self.stop()
                await disp.NONE.edit(self.message, view=self)

        @discord.ui.button(label="TR", style=discord.ButtonStyle.red)
        async def tr_pick_button(self, button: discord.Button, inter: discord.Interaction):
            if await self.picked_fac(3, inter):
                self.nc_pick_button.style = discord.ButtonStyle.grey
                self.disable_all_items()
                self.stop()
                await disp.NONE.edit(self.message, view=self)

    def _first_faction_pick(self):
        """Determine which player picks faction first.  Player with lower elo, or if elo is identical Owner."""
        if self._player1_stats.elo <= self._player2_stats.elo:
            return self.player1
        elif self._player1_stats.elo > self._player2_stats.elo:
            return self.player2
        else:
            raise tools.UnexpectedError("No first pick chosen!")

    @property
    def factions_picked(self):
        """Check whether factions have been picked for the match"""
        return self.player1.assigned_faction_id and self.player2.assigned_faction_id

    async def _switch_factions(self):
        """Sends message to switch factions, switches match variables"""
        self.player1.assigned_faction_id, self.player2.assigned_faction_id = \
            self.player2.assigned_faction_id, self.player1.assigned_faction_id
        await disp.RM_FACTION_SWITCH.send(self.thread, ping=self.players)
        self.log(disp.RM_FACTION_SWITCH())

    # Character Detection

    @property
    def ready_to_play(self):
        """Checks both players online on correct factions"""
        return self.player1.on_assigned_faction and self.player2.on_assigned_faction

    @property
    def _both_online(self):
        return self.player1.online_id and self.player1.online_id

    @property
    def _one_online(self):
        if self._both_online:
            return False
        if self.player1.online_id or self.player2.online_id:
            return True
        return False

    # Utility

    @property
    def player1_stats(self) -> PlayerStats:
        return self._player1_stats

    @property
    def player2_stats(self) -> PlayerStats:
        return self._player2_stats

    def get_opponent(self, player):
        """Pass a player object to get the opposite player object"""
        if player is self.player1:
            return self.player2
        elif player is self.player2:
            return self.player1
        else:
            raise tools.UnexpectedError("Player not in match!")

    # Score Analysis

    def _check_one_score_submitted(self) -> bool:
        return self.__p1_submitted_score or self.__p2_submitted_score

    def _check_scores_submitted(self) -> bool:
        return self.__p1_submitted_score and self.__p2_submitted_score

    def get_player_submitted_score(self, player):
        if player is self.player1:
            return self.__p1_submitted_score
        elif player is self.player2:
            return self.__p2_submitted_score
        else:
            raise tools.UnexpectedError("Player not in match!")

    def get_submitted_score_emoji(self, player):
        """Return an emoji representation of a players score submission"""
        if (score := self.get_player_submitted_score(player)) == 1:
            return "✉️✅✉️"
        elif score == -1:
            return "✉️❌✉️"
        else:
            return ""

    def _check_scores_equal(self) -> bool:
        if not self._check_scores_submitted():
            raise tools.UnexpectedError("Scores not submitted on equal check!")
        if self.__p1_submitted_score == -self.__p2_submitted_score:
            return True
        return False

    # Round Control + Info

    @property
    def rounds_complete(self) -> int:
        return len(self.__round_history)

    @property
    def current_round(self) -> int:
        """Return the current round number if a round is in progress, otherwise return the next round number."""
        if self.status not in (MatchState.LOGGING_IN, MatchState.PLAYING, MatchState.SUBMITTING):
            return len(self.__round_history)
        return len(self.__round_history) + 1

    @property
    def round_in_progress(self) -> bool:
        """Return whether a round is in progress"""
        return self.status in (MatchState.PLAYING, MatchState.SUBMITTING)

    @property
    def round_history(self) -> List[Round]:
        return self.__round_history

    def add_rounds_from_data(self, *rounds: dict):
        """Add rounds objects to the round history, by converting variables passed to Round."""
        for r in rounds:
            self.__round_history.append(Round(**r))

    def _decide_round_winner(self):
        """Set self.__round_winner variable and return it"""
        if self.__p1_submitted_score == -self.__p2_submitted_score == 1:
            self.__round_winner = self.player1
        elif self.__p1_submitted_score == -self.__p2_submitted_score == -1:
            self.__round_winner = self.player2
        else:
            raise tools.UnexpectedError("Error determining round winner!")
        return self.__round_winner

    # Score Info

    def get_player1_wins(self):
        """Return the number of round wins player 1 has"""
        return sum(1 for r in self.__round_history if r.winner == 1)

    def get_player2_wins(self):
        """Return the number of round wins player 2 has"""
        return sum(1 for r in self.__round_history if r.winner == 2)

    @property
    def player1_result(self) -> float:
        """Return a float representing the result for player 1, based on rounds won out of rounds complete"""
        return self.get_player1_wins() / self.rounds_complete

    @property
    def player2_result(self) -> float:
        """Return a float representing the result for player 2, based on rounds won out of rounds complete"""
        return self.get_player2_wins() / self.rounds_complete

    def get_score_string(self) -> str:
        """Return a formatted string displaying the score of the match, along with round history
        Returns empty string if there is no history"""

        name_line = f"{self.player1.name} - {self.player2.name}\n"
        score_line = f"{self.get_player1_wins()} - {self.get_player2_wins()}".center(len(name_line)) + "\n"

        if len(self.__round_history) == 0:
            return name_line + score_line

        round_lines = ''
        for r in self.__round_history:
            round_lines += f"[{r.round_number}]"
            if r.defaulted:
                round_lines += f"Defaulted: {self.player1.name if r.winner == 2 else self.player2.name} was Given Win\n"
            else:
                p1_bold = "**" if r.winner == 1 else ""
                p2_bold = "**" if r.winner == 2 else ""
                round_lines += f"{cfg.emojis[r.p1_faction]}{p1_bold}{self.player1.name}{p1_bold} - " \
                               f"{cfg.emojis[r.p2_faction]}{p2_bold}{self.player2.name}{p2_bold}\n"

        return name_line + score_line + round_lines

    def get_short_score_string(self) -> str:
        """Returns a score string with only current scores for each player."""
        return f"{self.get_player1_wins()}:{self.get_player2_wins()}"

    def get_round_string(self) -> str:
        """Returns a string to display info on the current round: check if players are on the correct characters,
        who has submitted, and the rounds score"""
        online, offline = "🟢", "🔴"
        player1_online = online if self.player1.on_assigned_faction else offline
        player2_online = online if self.player2.on_assigned_faction else offline

        player1_submitted = self.get_submitted_score_emoji(self.player1)
        player2_submitted = self.get_submitted_score_emoji(self.player2)

        round_string = \
            f"{self.player1.name}[{self.get_player1_wins()}]: {player1_online}" \
            f"{self.player1.assigned_char_display}{player1_submitted}\n" \
            "**vs**\n" \
            f"{self.player2.name}[{self.get_player2_wins()}]: {player2_online}" \
            f"{self.player2.assigned_char_display}{player2_submitted}\n"
        return round_string

    @property
    def wins_required(self):
        """Returns the number of wins required to win the match"""
        return self.MATCH_LENGTH // 2 + 1

    def _submit_score(self, player, score):
        """Submits scores for given player. Returns the opponents submitted score"""
        if player == self.player1:
            self.__p1_submitted_score = score
            return self.__p2_submitted_score
        if player == self.player2:
            self.__p2_submitted_score = score
            return self.__p1_submitted_score

    async def submit_score_callback(self, won: bool,
                                    ctx: discord.Interaction):
        """Callback for when a player submits their score, for use in round won/lost buttons.
        """
        await ctx.response.defer(ephemeral=True)
        if not (p := await self.player_check(ctx)):
            return False
        if not self.round_in_progress:  # Check correct state
            await disp.INVALID_INTERACTION.send_priv(ctx)
            return False

        if won:
            other_score = self._submit_score(p, 1)
        else:
            other_score = self._submit_score(p, -1)

        self.update_soon()
        return other_score

    def set_round_winner(self, winner: ActivePlayer):
        """For manually setting the winner of a round, for use in admin commands
        Returns False if the match is not currently in progress and a winner can't be set"""
        if not self.round_in_progress:
            return False

        if winner == self.player1:
            self.__p1_submitted_score = 1
            self.__p2_submitted_score = -1
        elif winner == self.player2:
            self.__p1_submitted_score = -1
            self.__p2_submitted_score = 1
        else:
            raise tools.UnexpectedError(f"Invalid player passed to set_round_winner: {winner}")

        self.log(disp.RM_ROUND_WINNER_SET(winner.name))
        return True

    async def score_mismatch(self):
        """Display a score mismatch to the players, reset submitted scores, ask for new submission"""
        self.__p1_submitted_score = None
        self.__p2_submitted_score = None
        self.__round_wrong_scores_counter += 1

        await disp.RM_SCORES_WRONG.send_long(self._round_message, ping=self.players)
        self.log(disp.RM_SCORES_WRONG())

    async def update(self):
        """Custom overwrite of original BaseMatch.update() method, for additional functionality in RankedMatch.
        Must handle checking round status, match status, pick status etc.  Must schedule next update"""
        # ensure exclusive access to update
        try:
            async with self._update_lock:
                if self.is_ended:  # Quit update if match is ended
                    return

                # Check if the match should be warned / timed out
                await self.update_timeout()
                # Update Status and run transition specific logic
                match self.status:
                    case MatchState.PICKING_FACTIONS if self.factions_picked and self.ready_to_play:
                        self.status = MatchState.PLAYING
                        await self._start_round()

                    case MatchState.PICKING_FACTIONS if self.factions_picked:
                        self.status = MatchState.LOGGING_IN

                    case MatchState.LOGGING_IN if self.ready_to_play:
                        # Initial round start, both players logged in
                        self.status = MatchState.PLAYING
                        await self._start_round()

                    case MatchState.PLAYING if self._check_one_score_submitted():
                        # Transition to submitting once at least one player has submitted score
                        self.status = MatchState.SUBMITTING

                    case MatchState.SUBMITTING:
                        if self.__round_winner:
                            # State shouldn't be reached
                            self.status = MatchState.PLAYING
                            await self._start_round()
                        elif self._check_scores_submitted() and self._check_scores_equal():
                            # if both scores submitted and equal

                            if self.current_round == (self.MATCH_LENGTH // 2) and self.FACTION_SWAP_ENABLED:
                                # if half-time and swaps enabled
                                if await self._end_round():  # check if match should end before starting next round
                                    return  # This is future proofing, should never be called at halftime
                                self.status = MatchState.SWITCHING_SIDES
                                await self._switch_factions()

                            elif self.rounds_complete <= self.MATCH_LENGTH:
                                # all other normal round progression
                                if await self._end_round():  # check if match should end before starting next round
                                    return
                                self.status = MatchState.PLAYING
                                await self._start_round()

                        elif self.__round_wrong_scores_counter >= self.WRONG_SCORE_LIMIT:
                            # If too many wrong scores submitted
                            asyncio.create_task(self.end_match(end_condition=EndCondition.TOO_MANY_CONFLICTS))

                        elif self._check_scores_submitted():
                            await self.score_mismatch()

                    case MatchState.SWITCHING_SIDES if self.ready_to_play:
                        self.status = MatchState.PLAYING
                        await self._start_round()

                # Update Display Objects
                await asyncio.gather(
                    self.update_embed(),
                    self.update_match_log(),
                    self.update_round_msg()
                )

        except asyncio.CancelledError:
            pass
        else:
            # schedule next update
            d_obj.bot.loop.call_later(0.1, self._schedule_update_task)

    # Admin Functions
    async def force_score_submit(self, winner: ActivePlayer):
        """Submits scores for both players, setting the winner to the given player"""
        if winner == self.player1:
            self.__p1_submitted_score, self.__p2_submitted_score = 1, -1
        elif winner == self.player2:
            self.__p1_submitted_score, self.__p2_submitted_score = -1, 1
        else:
            raise ValueError("Invalid player given to decide_round")

    # Round Control Functions

    async def update_round_msg(self):
        """Update the round message, or send a new one if it doesn't exist (if it was deleted after round end)"""
        if self.round_in_progress:
            # Check there is a round in progress before sending / updating message
            if self._round_message:
                await disp.RM_ROUND_MESSAGE.edit(self._round_message, match=self, view=self.RankedRoundView(self))
            else:
                self._round_message = await disp.RM_ROUND_MESSAGE.send(self.thread,
                                                                       match=self, view=self.RankedRoundView(self))

    def _delete_round_msg(self):
        """Delete the round message"""
        if self._round_message:
            try:
                asyncio.create_task(self._round_message.delete())
            except discord.NotFound:
                pass
            self._round_message = None

    async def _start_round(self):
        """Starts a new round, resets round variables"""

        #  Reset score variables
        self.__round_wrong_scores_counter = 0
        self.__round_winner = None
        self.__p1_submitted_score, self.__p2_submitted_score = None, None

        self.log(
            f"Round [{self.current_round}/{self.MATCH_LENGTH}] "
            f"Started: {self.player1.assigned_faction_char} vs {self.player2.assigned_faction_char}")

        # No need to send new round message, as it's sent as part of the update loop

    async def _end_round(self):
        """Ends current round, returns True if Match should also end"""
        self._decide_round_winner()

        # Delete old round message
        self._delete_round_msg()

        match_round = Round(
            round_number=self.current_round,
            winner=1 if self.__round_winner is self.player1 else 2,
            p1_id=self.player1.id,
            p2_id=self.player2.id,
            p1_faction=self.player1.assigned_faction_abv,
            p2_faction=self.player2.assigned_faction_abv
        )

        # add round to round list
        self.__round_history.append(match_round)

        # Publish Round winner
        await disp.RM_ROUND_WINNER.send(self.thread, self.__round_winner.mention,
                                        self.current_round - 1, self.get_short_score_string(), allowed_mentions=False)
        self.log(disp.RM_ROUND_WINNER(self.__round_winner.name, self.current_round - 1, self.get_short_score_string()))

        # Check end conditions: Match length reached, or one player reaches win threshold
        if self.rounds_complete >= self.MATCH_LENGTH or \
                True in [wins >= self.wins_required for wins in (self.get_player1_wins(), self.get_player2_wins())]:
            asyncio.create_task(self.end_match(end_condition=EndCondition.COMPLETED))
            return True
        return False

    async def end_match(self, end_condition: EndCondition, details=None, leaving_player=None, force=False):
        """Overwrite of original end_match function to add RankedMatch specific features"""

        # Base end_match features
        if self.is_ended:
            return
        self._cancel_update()  # Cancel Updates if Incoming
        self.status = MatchState.ENDED  # Update Status
        self.end_condition = end_condition  # Set End Condition

        # Delete round message if it exists
        self._delete_round_msg()

        # EndCondition Conditionals

        match end_condition:

            case EndCondition.FORFEIT:
                # Determine which player left
                if leaving_player is self.player2:
                    # Top up player1 wins with forfeits
                    for i in range(self.wins_required - self.get_player1_wins()):
                        self.__round_history.append(
                            Round(
                                round_number=self.current_round,
                                winner=1,
                                p1_id=self.player1.id,
                                p2_id=self.player2.id,
                                defaulted=True
                            ))
                    self.log(f"Match was forfeit by {self.player2.name}")

                elif leaving_player is self.player1:
                    # Top up player2 wins with forfeits
                    for i in range(self.wins_required - self.get_player2_wins()):
                        self.__round_history.append(
                            Round(
                                round_number=self.current_round,
                                winner=2,
                                p1_id=self.player1.id,
                                p2_id=self.player2.id,
                                defaulted=True
                            ))
                    self.log(f"Match was forfeit by {self.player1.name}")

            case EndCondition.TOO_MANY_CONFLICTS:
                self.log("Match was ended due to excessive score conflicts!")
                await disp.RM_ENDED_TOO_MANY_CONFLICTS.send(self.thread, ping=self.players)

            case EndCondition.CANCELLED:
                self.log(f"Match was cancelled! " + (f"{leaving_player.name} left before a round was completed!"
                                                     if leaving_player else ""))

            case EndCondition.COMPLETED:
                pass
                # Normal End condition

        if self.has_standard_end:
            # Check correct completion before determining winner and altering Elo

            # Determine Match winner
            p1_wins, p2_wins = self.get_player1_wins(), self.get_player2_wins()
            self.__match_outcome = p1_wins - p2_wins

            # Publish Match Winner
            if self.__match_outcome > 0:
                # Player 1 Wins
                if p1_wins < self.wins_required:
                    log.error(f"Match ID: {self.id} was ended with a winner but not enough wins!")
                await disp.RM_WINNER.send(self.thread, self.player1.name, p1_wins, p2_wins)
                self.log(disp.RM_WINNER(self.player1.name, p1_wins, p2_wins))
            elif self.__match_outcome < 0:
                # Player 2 Wins
                if p2_wins < self.wins_required:
                    log.error(f"Match ID: {self.id} was ended with a winner but not enough wins!")
                await disp.RM_WINNER.send(self.thread, self.player2.name, p2_wins, p1_wins)
                self.log(disp.RM_WINNER(self.player2.name, p2_wins, p1_wins))
            else:
                # Match was a draw
                await disp.RM_DRAW.send(self.thread)
                self.log(disp.RM_DRAW())

            # Determine Elo Changes
            await stats_handler.update_elo(self)

            # Send players Elo Changes
            await asyncio.gather(
                disp.ELO_DM_UPDATE.send(self.player1, match=self, player=self.player1),
                disp.ELO_DM_UPDATE.send(self.player2, match=self, player=self.player2)
            )

        else:
            # Nonstandard Ending, warn of no elo saving
            await disp.RM_ENDED_NO_ELO.send(self.thread, ping=self.players)

        # run original end_match, force=true to ignore is_ended attribute set earlier
        await super().end_match(end_condition=end_condition, force=True)

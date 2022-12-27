"""Holds main match classes"""

# External Imports
import discord
import asyncio
from logging import getLogger
from enum import Enum
from typing import Coroutine, Union, NamedTuple, List

import display.views
# Internal Imports
import modules.discord_obj as d_obj
import modules.config as cfg
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
    p1_faction: str
    p2_faction: str
    winner: str


class MatchState(Enum):
    INVITING = "Waiting for players to join the match..."
    PICKING_FACTIONS = "Waiting for players to pick factions..."
    LOGGING_IN = "Waiting for players to log in..."
    GETTING_READY = "Waiting for players to be ready..."
    PLAYING = "Currently playing..."
    SWITCHING_SIDES = "Waiting for players to switch factions..."
    SUBMITTING = "Submitting scores..."
    ENDED = "Match ended..."


class EndCondition(Enum):
    COMPLETED = "The match was completed successfully..."
    APPEALED = "The match outcome was appealed by one of the participants..."
    TOO_MANY_CONFLICTS = "The players tried to submit too many conflicting result..."
    TIMEOUT = "The match was ended by timeout..."
    EXTERNAL = "The match was ended externally..."


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
            self._update()
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

        def _update(self):
            """For Inheritance"""
            pass

        async def in_match_check(self, inter, p: Player) -> bool:
            if p.active in self.match.players:
                return True
            await disp.MATCH_NOT_IN.send_priv(inter, self.match.id_str)
            return False

        @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
        async def leave_button(self, button: discord.Button, inter: discord.Interaction):
            p: Player = Player.get(inter.user.id)
            if not await d_obj.is_registered(inter, p) or not await self.in_match_check(inter, p):
                return

            await disp.MATCH_LEAVE.send_priv(inter, p.mention)
            await self.match.leave_match(p.active)

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
            if not await d_obj.is_registered(inter, p) or not await self.in_match_check(inter, p):
                return
            elif p.has_own_account:
                await disp.ACCOUNT_HAS_OWN.send_priv(inter)
                return
            elif p.account:
                await disp.ACCOUNT_ALREADY.send_priv(inter)
                return
            else:
                acc = accounts.pick_account(p)
                if acc:  # if account found
                    msg = await accounts.send_account(acc)
                    if msg:  # if allowed to dm user
                        await disp.ACCOUNT_SENT.send_priv(inter, msg.channel.jump_url)
                    else:  # if couldn't dm
                        await disp.ACCOUNT_NO_DMS.send_priv(inter)
                        acc.clean()

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

            if await self.match.toggle_voice_lock():
                await disp.MATCH_VOICE_PUB.send_priv(inter.response, self.match.voice_channel.mention)
            else:
                await disp.MATCH_VOICE_PRIV.send_priv(inter.response, self.match.voice_channel.mention)

    def __init__(self, owner: Player, player: Player):
        # Vars
        global _match_id_counter
        _match_id_counter += 1
        self.__id = _match_id_counter
        self.owner = owner
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__end_condition = None
        self.timeout_stamp = None
        self.timeout_warned = False
        self.was_timeout = False
        self.was_conflict = False
        self.status = MatchState.LOGGING_IN
        self.__public_voice = False
        self.__update_lock = asyncio.Lock()
        self.__next_update_task: asyncio.Task | None = None  # store asyncio.Handle for next update call
        self.__next_update: Coroutine = None

        # Display
        self.text_channel: discord.TextChannel | None = None
        self.voice_channel: discord.VoiceChannel | None = None
        self.info_message: discord.Message | None = None
        self.__timeout_message: discord.Message | None = None
        self.embed_cache: discord.Embed | None = None
        self.__embed_func = embeds.match_info
        self.__view: BaseMatch.MatchInfoView | None = None
        self.__view_class = self.MatchInfoView

        #  Containers
        self.__players: list[ActivePlayer] = [owner.on_playing(self),
                                              player.on_playing(self)]  # active player list, add owners active_player
        self.__previous_players: list[Player] = list()  # list of Player objects, who have left the match
        self.__invited = list()
        self.match_log = list()  # logs recorded as list of tuples, (timestamp, message, Public)

        BaseMatch._active_matches[self.id] = self

    @classmethod
    def active_matches_list(cls) -> list['BaseMatch']:
        return list(BaseMatch._active_matches.values())

    @classmethod
    def active_matches_dict(cls):
        return BaseMatch._active_matches

    @classmethod
    def active_match_channel_ids(cls):
        return {match.text_channel.id: match for match in BaseMatch._active_matches.values()}

    @classmethod
    async def end_all_matches(cls):
        end_coros = [match.end_match() for match in cls.active_matches_dict().values()]
        await asyncio.gather(*end_coros)

    @classmethod
    async def create(cls, owner: Player, invited: Player, base_class=None) -> Union['BaseMatch', 'RankedMatch']:
        # init _match_id_counter if first match created
        global _match_id_counter
        if not _match_id_counter:
            last_match = await db.async_db_call(db.get_last_element, 'matches')
            if last_match:
                _match_id_counter = last_match['_id']

        # Create Match Object, init channels + first update
        base_class = base_class or cls
        obj = base_class(owner, invited)
        obj.log(f'{owner.name} created the match with {invited.name}')

        await obj._make_channels()

        await obj.update()
        asyncio.create_task(obj._check_accounts_delay(*obj.players))

        return obj

    async def _make_channels(self):
        overwrites = self._get_overwrites()
        try:
            # Create text channel, with provided overwrites
            self.text_channel = await d_obj.categories['user'].create_text_channel(
                name=f'{self.TYPE}┊{self.id_str}┊',
                overwrites=overwrites,
                topic=f'Match channel for {self.TYPE.lower()} Match [{self.id_str}], created by {self.owner.name}'
            )
            # Create voice channel, with extended overwrites to set channel to private
            self.voice_channel = await d_obj.categories['user'].create_voice_channel(
                name=f'{self.TYPE}┊{self.id_str}┊Voice',
                # Same overwrites, except disallow sending messages in text-in-voice
                overwrites=overwrites
            )
        except (discord.HTTPException, discord.Forbidden) as e:
            await d_obj.d_log(source=self.owner.name,
                              message=f"Error Creating Match Channel for Match {self.id_str}",
                              error=e)
            await self.end_match()

    async def toggle_voice_lock(self):
        """Toggles whether the matches voice channel is public or private.
          Returns whether channel is currently public"""

        if self.__public_voice:
            await self.set_voice_private()
        else:
            await self.set_voice_public()
        return self.__public_voice

    async def _clear_voice(self):
        #  gather disconnect coroutines if users not in match, and not admins
        to_disconnect = [memb.move_to(None) for memb in self.voice_channel.members
                         if memb.id not in [p.id for p in self.players] and not d_obj.is_admin(memb)]

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
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            d_obj.roles['timeout']: discord.PermissionOverwrite(view_channel=False, connect=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True, connect=True),
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
        await disp.MATCH_JOIN.send(self.text_channel, player.mention)
        self.log(f'{player.name} joined the match')
        asyncio.create_task(self._check_accounts_delay(player))
        await self.update()
        return True

    async def leave_match(self, player: ActivePlayer):
        #  If player is owner, and match isn't ended, end match
        if player.player == self.owner and not self.is_ended:
            if len(self.players) >= 3 and await self.change_owner():
                # if 3 or more players and new owner possible, assign new owner rather than ending the match
                pass
            else:
                await self.end_match()
                return

        self.__players.remove(player)
        self.__previous_players.append(player.on_quit())
        self.log(f'{player.name} left the match')
        #  If match still exists
        if not self.is_ended:
            await self.update()
            await self._channel_update(player, None)
            await self._clear_voice()
            await disp.MATCH_LEAVE.send(self.text_channel, player.mention)

        #  If Player was assigned an account, terminate
        if player.account:
            await accounts.terminate(player=player.player)

        if not self.__players and not self.is_ended:  # if no players left, and match not already ended.
            await self.end_match()  # Should only be called if match didn't end when owner left??

    async def change_owner(self, player: None | ActivePlayer = None):
        """Set a new owner if player provided, otherwise pick a new owner from players.
        Return new owner, or None if no new owner found."""

        player = player or next((p for p in self.__players if p.player != self.owner), None)

        if not player:
            return False

        self.owner = player.player
        await disp.MATCH_NEW_OWNER.send(self.text_channel, player.mention)
        await self.update()
        return player

    async def end_match(self, end_result: EndCondition, details=None):
        if self.is_ended:
            return
        async with self.__update_lock:
            # Update vars, cancel next scheduled update
            self.end_stamp = tools.timestamp_now()
            self.status = MatchState.ENDED
            self.__end_condition = end_result
            self.log('Match Ended')
            self._cancel_update()

            # Display match ended to users
            await disp.MATCH_END.send(self.text_channel, self.id_str)
            await self.update_embed()

            # Update DB with current players, then remove players
            await db.async_db_call(db.set_element, 'matches', self.id, self.get_end_data())
            with self.text_channel.typing():
                leave_coroutines = [self.leave_match(player) for player in self.__players]
                await asyncio.gather(*leave_coroutines)
                await asyncio.sleep(5)

            # Store match object, trim _recent_matches if it is too large
            BaseMatch._recent_matches[self.id] = BaseMatch._active_matches.pop(self.id)
            if len(BaseMatch._recent_matches) > 50:
                keys = list(BaseMatch._recent_matches.keys())
                for i in range(20):
                    del BaseMatch._recent_matches[keys[i]]

            #  Delete channels if not already deleted
            try:
                await asyncio.gather(
                    self.text_channel.delete(reason='Match Ended'),
                    self.voice_channel.delete(reason='Match Ended')
                )
            except discord.NotFound:
                pass

    def get_end_data(self):
        data = {'_id': self.id, 'type': self.TYPE, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'end_condition': self.__end_condition.name,
                'owner': self.owner.id, 'channel_id': 0 if not self.text_channel else self.text_channel.id,
                'current_players': [p.id for p in self.__players],
                'previous_players': [p.id for p in self.__previous_players],
                'match_log': self.match_log}
        return data

    async def _channel_update(self, player, action: bool | None):
        """Updates a players access to the Matches channels"""
        player_member = d_obj.guild.get_member(player.id)
        await asyncio.gather(
            self.text_channel.set_permissions(player_member, view_channel=action),
            self.voice_channel.set_permissions(player_member, view_channel=action, connect=action)
        )

    def _new_embed(self):
        return self.__embed_func(self)

    def view(self, new=False):
        if not new and self.__view:
            return self.__view.update()
        self.__view = self.__view_class(self)
        return self.__view

    async def send_embed(self):
        if not self.embed_cache:
            self.embed_cache = self._new_embed()
        self.info_message = await disp.MATCH_INFO.send(self.text_channel, embed=self.embed_cache, view=self.view())
        await self.info_message.pin()

    async def _check_accounts_delay(self, *players_to_check):
        """Check for players that have no personal account, and are yet to send a request for a temp account"""
        await asyncio.sleep(300)  # run check after 5 minutes
        no_acc = []
        for p in players_to_check:
            if not p.has_own_account and not p.account:
                no_acc.append(p)
        if no_acc:
            await disp.MATCH_NO_ACCOUNT.send(self.text_channel, ''.join([p.mention for p in no_acc]),
                                             d_obj.channels['register'].mention)

    async def update_embed(self):
        if self.info_message:
            if not tools.compare_embeds(self.embed_cache, new_embed := self._new_embed()):
                self.embed_cache = new_embed

                try:
                    await disp.MATCH_INFO.edit(self.info_message, embed=self.embed_cache, view=self.view())
                except discord.errors.NotFound as e:
                    log.error("Couldn't find self.info_message for Match %s", self.id_str, exc_info=e)
                    await self.send_embed()
        else:
            await self.send_embed()

    def update_status(self):
        if len(self.players) < 2:
            self.status = MatchState.INVITING
        elif len(self.online_players) < 2:
            self.status = MatchState.LOGGING_IN
        elif self.online_players:
            self.status = MatchState.PLAYING

    async def reset_timeout(self):
        """Resets the matches current timeout, deletes old timeout warning"""
        if self.__timeout_message:
            try:
                await self.__timeout_message.delete()
            except discord.errors.NotFound:
                log.error("No timeout warning message found for match %s", self.id_str)
        self.timeout_stamp = None
        self.log("Match Timeout Reset")
        await self.update()

    async def update_timeout(self):
        # check timeout, reset if at least 2 players and online_players
        if self.online_players and len(self.players) >= 2:
            self.timeout_stamp = None
        else:
            if not self.timeout_stamp:  # set timeout stamp
                self.timeout_stamp = tools.timestamp_now()
                self.timeout_warned = False
            elif self.should_timeout and not self.was_timeout:  # Timeout Match
                self.was_timeout = True
                self.log("Match timed out for inactivity...")
                await disp.MATCH_TIMEOUT.send(self.text_channel, self.all_mentions)
                # Use create_task, so that on_update doesn't wait for on_timeout
                asyncio.create_task(self.end_match(end_result=EndCondition.TIMEOUT))
                raise asyncio.CancelledError
            elif self.should_warn and not self.timeout_warned:  # Warn of timeout
                self.timeout_warned = True
                self.log("Unless the timeout is reset, the match will timeout soon...")
                self.__timeout_message = await disp.MATCH_TIMEOUT_WARN.send(
                    self.text_channel, self.all_mentions,
                    tools.format_time_from_stamp(self.timeout_at, 'R'))

    async def update(self, status_update=False):
        """Update the match object:  updates timeout, match status, and the embed if required"""
        # ensure exclusive access to update
        try:
            async with self.__update_lock:
                if self.is_ended:  # Quit update if match is ended
                    return

                # Check if the match should be warned / timed out
                await self.update_timeout()

                # Updated Match Status.  May be disabled for use in subclasses
                if status_update:
                    self.update_status()

                # Reflect match embed with updated match attributes, also updates match view
                await self.update_embed()
        except asyncio.CancelledError:
            pass
        else:
            # schedule next update
            d_obj.bot.loop.call_later(0.1, self._schedule_update_task)

    async def _update_task(self):
        """Task wrapper around update call"""
        await asyncio.sleep(self.UPDATE_DELAY)
        await self.update()

    def _schedule_update_task(self):
        """Schedule next update of the match, cancel currently scheduled update."""
        # Cancel next update if it exists
        self._cancel_update()

        # Schedule next update
        self.__next_update_task = d_obj.bot.loop.create_task(self._update_task(), name=f'Match [{self.id_str}] Updater')

    def _cancel_update(self):
        """Cancel the next upcoming update"""
        if self.__next_update_task:
            self.__next_update_task.cancel()

    def log(self, message, public=True):
        self.match_log.append((tools.timestamp_now(), message, public))
        log.info(f'Match ID [{self.id}]: {message}')

    async def char_login(self, user):
        self.log(f"{user.name} logged in as {user.online_name}")
        await self.update()

    async def char_logout(self, user, char_name):
        self.log(f"{user.name} logged out from {char_name}")
        await self.update()

    @property
    def recent_logs(self):
        return self.match_log[-15:]

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

    @staticmethod
    def max_players():
        return BaseMatch.max_players

    @property
    def players(self):
        return self.__players

    @property
    def prev_players(self):
        return self.__previous_players

    @property
    def invited(self):
        return self.__invited

    @property
    def is_ended(self):
        return self.status == MatchState.ENDED

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
    (player1 faction, blayer2 faction)
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
    MATCH_LENGTH = 8
    MAX_PLAYERS = 2
    WRONG_SCORE_LIMIT = 3
    TYPE = 'Ranked'

    class RankedMatchView(BaseMatch.MatchInfoView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__(match)
            self.match = match

    class RankedRoundView(display.views.FSBotView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__(timeout=None)
            self.match = match

        @discord.ui.button(label="Round Won", style=discord.ButtonStyle.green)
        async def round_won_button(self, button: discord.Button, inter: discord.Interaction):
            await self.match.update()
            if self.match.status != MatchState.PLAYING:
                return await disp.INVALID_INTERACTION.send_priv(inter)

            p = Player.get(inter.user.id)
            self.match.submit_score(p, 1)

            await disp.RM_SCORE_SUBMITTED.send_priv(inter, "Round Won")

        @discord.ui.button(label="Round Lost", style=discord.ButtonStyle.green)
        async def round_lost_button(self, button: discord.Button, inter: discord.Interaction):
            await self.match.update()
            if self.match.status != MatchState.PLAYING:
                return await disp.INVALID_INTERACTION.send_priv(inter)

            p = Player.get(inter.user.id)
            self.match.submit_score(p, -1)

            await disp.RM_SCORE_SUBMITTED.send_priv(inter, "Round Lost")

        @discord.ui.button(label="Appeal", style=discord.ButtonStyle.green, row=1)
        async def appeal_button(self, button: discord.Button, inter: discord.Interaction):
            await self.match.update()
            if self.match.status != MatchState.SUBMITTING:
                return await disp.INVALID_INTERACTION.send_priv(inter)
            p = Player.get(inter.user.id)
            await disp.RM_MATCH_APPEALED.send_priv(inter, self.match.id_str)
            await self.match.end_match(EndCondition.APPEALED)

    def __init__(self, owner: Player, invited: Player):
        super().__init__(owner, invited)

        # Player Objects
        self.player1 = owner.on_playing(self)
        self.player2 = invited.on_playing(self)
        self.__player1_stats: PlayerStats | None = None
        self.__player2_stats: PlayerStats | None = None
        self.first_pick = self._first_faction_pick()

        # Match Variables
        self.__round_history: List[Round] = []
        # Round Variables
        self.__round_wrong_scores_counter = 0

        self.__p1_submitted_score = None
        self.__p2_submitted_score = None

        # Display Objects
        self.__round_view_class = None  # Replace with round_view
        self.__round_view: discord.ui.View | None = None
        self.__round_message: discord.Message | None = None

        self.__view_class = self.RankedMatchView

    @classmethod
    async def create(cls, owner: Player, invited: Player, base_class=None) -> 'RankedMatch':
        obj = await super().create(owner, invited, base_class=cls)  # RankedMatch create

        # Retrieve Stats PlayerStats
        obj.__player1_stats = await PlayerStats.get_from_db(p_id=owner.id, p_name=owner.name)
        obj.__player2_stats = await PlayerStats.get_from_db(p_id=invited.id, p_name=invited.name)

        # Set Initial Status
        obj.status = MatchState.PICKING_FACTIONS

        # Start Faction Picker
        # Todo Start Ranked loop here instead, move faction picker to ranked loop
        await disp.RM_FACTION_PICK.send(obj.text_channel, obj.first_pick.mention)

        return obj

    def get_player(self, inter: discord.Interaction):
        """Utility method to get the Player object from a Discord Interaction for a match.
        Returns False if player is not in the match"""
        p_id = inter.user.id
        if p_id == self.player1.id:
            return self.player1
        elif p_id == self.player2.id:
            return self.player2
        else:
            return False

    def get_end_data(self):

        return {
            **super().get_end_data(),
            'player1_id': self.player1.id,
            'player2_id': self.player2.id,
            'match_outcome': self.__match_outcome,
            'round_history': [r._asdict() for r in self.__round_history]
        }

    # Faction Picks
    class FactionPickView(views.FSBotView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__()
            self.match = match

        async def picked_fac(self, faction_id, inter):
            """Executes all logic for faction pick buttons, as well as handling response."""
            if not (p := self.match.get_player(inter)):
                await disp.MATCH_NOT_IN.send_priv(inter, self.match.id_str)
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
            p.assigned_faction = faction_id  # Set Chosen faction var for each player
            other_p.assigned_faction_id = other_faction_id

            self.match.log(f"{p.name} picked {faction_str}, {other_p.name} has been assigned {other_faction_str}!")
            return await disp.RM_FACTION_PICKED.send(inter,
                                                     p.mention,
                                                     faction_str + cfg.emojis[faction_str],
                                                     other_p.mention,
                                                     other_faction_str + cfg.emojis[other_faction_str])

        @discord.ui.button(label="NC", style=discord.ButtonStyle.blurple, emoji=cfg.emojis['NC'])
        async def nc_pick_button(self, button: discord.Button, inter: discord.Interaction):
            if await self.picked_fac(2, inter):  # Only disable button if successful faction pick
                self.tr_pick_button.style = discord.ButtonStyle.grey
                self.disable_all_items()
                await disp.NONE.edit(self.msg, view=self)

        @discord.ui.button(label="TR", style=discord.ButtonStyle.red, emoji=cfg.emojis['TR'])
        async def tr_pick_button(self, button: discord.Button, inter: discord.Interaction):
            if await self.picked_fac(3, inter):  # Only disable button if successful faction pick
                self.nc_pick_button.style = discord.ButtonStyle.grey
                self.disable_all_items()
                await disp.NONE.edit(self.msg, view=self)

    def _first_faction_pick(self):
        """Determine which ptayer picks faction first.  Player with lower elo, or if elo is identical Owner."""
        if self.__player1_stats.elo >= self.__player2_stats.elo:
            return self.player1
        elif self.__player1_stats.elo < self.__player2_stats.elo:
            return self.player2
        else:
            raise tools.UnexpectedError("No first pick chosen!")

    def _factions_picked(self):
        """Check whether factions have been picked for the match"""
        return self.player1.assigned_faction_id and self.player2.assigned_faction_id

    # Round Scores Section

    @property
    def _ready_to_play(self):
        # Checks both players online on correct factions
        return self.player1.current_faction == self.player1.assigned_faction_abv \
            and self.player2.current_faction == self.player2.assigned_faction_abv

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

    def _check_one_score_submitted(self):
        if self._check_one_score_submitted(): return False
        return self.__p1_submitted_score or self.__p2_submitted_score

    def _check_scores_submitted(self):
        return self.__p1_submitted_score and self.__p2_submitted_score

    def _check_scores_equal(self):
        if not self._check_scores_submitted():
            return False
        if self.__p1_submitted_score == -self.__p2_submitted_score:
            return True
        return False

    @property
    def rounds_complete(self):
        return len(self.__round_history)

    @property
    def current_round(self):
        if self.status in (MatchState.PLAYING, MatchState.SUBMITTING):
            return len(self.__round_history) + 1
        return None

    def _decide_round_winner(self):
        if self.__p1_submitted_score == -self.__p2_submitted_score == 1:
            return self.player1
        elif self.__p1_submitted_score == -self.__p2_submitted_score == -1:
            return self.player2
        else:
            raise tools.UnexpectedError("Error determining round winner!")

    def submit_score(self, player, score):
        """submits scores for given player"""
        if player == self.player1:
            self.__p1_submitted_score = score
        if player == self.player2:
            self.__p2_submitted_score = score

    async def update(self, status_update=False):
        """Custom overwrite of original BaseMatch.update method, for additional functionality in RankedMatch.
        Must handle checking round status, match status, pick status etc.  Must schedule next update"""

        # ensure exclusive access to update
        try:
            async with self.__update_lock:
                if self.is_ended:  # Quit update if match is ended
                    return

                # Check if the match should be warned / timed out
                await self.update_timeout()

                # Update Status and run transition specific logic
                match self.status:
                    case MatchState.LOGGING_IN if self._ready_to_play:
                        # Initial Status Update, both players logged in
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
                        elif self._check_scores_equal():
                            # if both scores submitted and equal
                            if self.rounds_complete == (self.MATCH_LENGTH // 2):
                                # if half-time
                                await self._end_round()
                                self.status = MatchState.SWITCHING_SIDES
                                self.player1.assigned_faction_id, self.player2.assigned_faction_id = \
                                    self.player2.assigned_faction_id, self.player1.assigned_faction_id
                                # TODO send notice to switch sides
                                # Round progression here
                            elif self.rounds_complete == self.MATCH_LENGTH:
                                # if round has reached match length and should end
                                # Shouldn't be reached
                                await self.end_match(end_result=EndCondition.COMPLETED)
                                # Match ending here
                            elif self.rounds_complete < self.MATCH_LENGTH:

                                # all other normal round progression
                                await self._end_round()
                                self.status = MatchState.PLAYING
                                await self._start_round()
                        elif self._check_scores_submitted():
                            ## this case is handled in the view ()
                            log.warning("if scores are submitted but don't match, this code should never run")
                            pass

                        elif self.__round_wrong_scores_counter >= self.WRONG_SCORE_LIMIT:
                            # If too many wrong scores submitted
                            self.log("Match was ended due to excessive score conflicts!")
                            return await self.end_match(end_result=EndCondition.TOO_MANY_CONFLICTS)

                    case MatchState.SWITCHING_SIDES if self._ready_to_play:
                        self.status = MatchState.PLAYING
                        await self._start_match()

                # Reflect match embed with updated match attributes, also updates match view
                await self.update_embed()
        except asyncio.CancelledError:
            pass
        else:
            # schedule next update
            d_obj.bot.loop.call_later(0.1, self._schedule_update_task)

    async def _start_round(self):
        #  Reset score variables
        self.__round_wrong_scores_counter = 0
        self.__round_winner = None
        self.__p1_submitted_score, self.__p2_submitted_score = None, None

        self.log(
            f"Round [{self.current_round}] Started: {self.player1.assigned_faction_display} vs {self.player2.assigned_faction_abv}")

        # Send new round message
        self.__round_message = await disp.RM_ROUND_MESSAGE.send(self.text_channel, self.rounds_complete,
                                                                self.player1.assigned_faction_display,
                                                                self.player2.assigned_faction_display,
                                                                view=self.__round_view)

    async def _end_round(self):
        winner = self._decide_round_winner()

        # Delete old round message
        try:
            await self.__round_message.delete()
        except discord.NotFound:
            pass

        # Publish Round winner
        await disp.RM_ROUND_WINNER.send(self.text_channel, winner.mention, self.rounds_complete)
        self.log(disp.RM_ROUND_WINNER(winner.name, self.rounds_complete))

        round = Round(self.player1.assigned_faction_abv, self.player2.assigned_faction_abv,
                      "player1" if winner is self.player1 else "player2")

        # add round to round list
        self.__round_history.append(round)
        if self.rounds_complete >= self.MATCH_LENGTH:
            asyncio.create_task(self.end_match(end_result=EndCondition.COMPLETED))


    async def end_match(self, end_result: EndCondition, details=None):
        p1_wins = len(sum(r for r in self.__round_history if r.winner == "player1"))
        p2_wins = len(sum(r for r in self.__round_history if r.winner == "player2"))

        self.__end_result
        if p1_wins == p2_wins:
            self.__match_outcome = "tie"
        elif p1_wins > p2_wins:
            self.__match_outcome = "player1Wins"
        else:
            self.__match_outcome = "player2Wins"

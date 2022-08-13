"""Holds main match classes"""
# External Imports
import discord
import asyncio
from logging import getLogger
from enum import Enum

# Internal Imports
import modules.discord_obj as d_obj
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


class MatchState(Enum):
    INVITING = "Waiting for players to join the match..."
    LOGGING_IN = "Waiting for players to log in..."
    GETTING_READY = "Waiting for players to be ready..."
    PLAYING = "Currently playing..."
    SUBMITTING = "Submitting scores..."
    ENDED = "Match ended..."


class BaseMatch:
    _active_matches = dict()
    _recent_matches = dict()
    MAX_PLAYERS = 10
    TYPE = "Casual"

    def __init__(self, owner: Player, player: Player):
        # Vars
        global _match_id_counter
        _match_id_counter += 1
        self.__id = _match_id_counter
        self.owner = owner
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.timeout_stamp = None
        self.timeout_warned = False
        self.was_timeout = False
        self.status = MatchState.LOGGING_IN
        self.public_voice = False
        self.__ended = False
        self.__update_locked = True

        # Display
        self.text_channel: discord.TextChannel | None = None
        self.voice_channel: discord.VoiceChannel | None = None
        self.info_message: discord.Message | None = None
        self.embed_cache: discord.Embed | None = None
        self.__embed_func = embeds.match_info
        self.__view: views.MatchInfoView | None = None
        self.view_func = views.MatchInfoView

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
    async def create(cls, owner: Player, invited: Player):
        global _match_id_counter  # init _match_id_counter if first match created
        if not _match_id_counter:
            last_match = await db.async_db_call(db.get_last_element, 'matches')
            if last_match:
                _match_id_counter = last_match['_id']
        obj = cls(owner, invited)
        obj.log(f'{owner.name} created the match with {invited.name}')

        await obj._make_channel()

        await obj.send_embed()
        obj.setup()
        obj.__update_locked = False
        return obj

    async def _make_channel(self):
        overwrites = self._get_overwrites()
        try:
            self.text_channel = await d_obj.categories['user'].create_text_channel(
                name=f'{self.TYPE}┊{self.id_str}┊',
                overwrites=overwrites,
                topic=f'Match channel for {self.TYPE.lower()} Match [{self.id_str}], created by {self.owner.name}'
            )
            overwrites[d_obj.guild.default_role].update(send_messages=False, connect=False)
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

    def _get_overwrites(self):
        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            d_obj.roles['timeout']: discord.PermissionOverwrite(view_channel=False, connect=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True, connect=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True, connect=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True, connect=True),
            d_obj.roles['bot']: discord.PermissionOverwrite(view_channel=True, connect=True),
        }
        overwrites.update({d_obj.guild.get_member(p.id): discord.PermissionOverwrite(view_channel=True, connect=True)
                           for p in self.__players})
        return overwrites

    def setup(self):
        """For Inheritance, called post match_create"""

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
        await self.update()
        return True

    async def leave_match(self, player: ActivePlayer):
        self.__players.remove(player)
        self.__previous_players.append(player.on_quit())
        self.log(f'{player.name} left the match')
        #  If match still exists
        if not self.is_ended:
            await self.update()
            await self._channel_update(player, None)
            await disp.MATCH_LEAVE.send(self.text_channel, player.mention)

        #  Object cleanup
        if player.account:
            await accounts.terminate(player=player.player)
            player.player.set_account(None)
        if player.player == self.owner and not self.is_ended:
            await self.end_match()
            return
        if not self.__players and not self.is_ended:  # if no players left, and match not already ended.
            await self.end_match()  # Should only be called if match didn't end when owner left

    async def end_match(self):
        if self.is_ended:
            return
        self.__update_locked = True
        self.end_stamp = tools.timestamp_now()
        self.status = MatchState.ENDED
        self.log('Match Ended')
        await disp.MATCH_END.send(self.text_channel, self.id)
        await self.update_embed()
        self.__ended = True
        await db.async_db_call(db.set_element, 'matches', self.id, self.get_data())
        with self.text_channel.typing():
            await asyncio.sleep(5)
            for player in self.__players:
                await self.leave_match(player)
        BaseMatch._recent_matches[self.id] = BaseMatch._active_matches.pop(self.id)
        if len(BaseMatch._recent_matches) > 50:  # Trim _recent_matches if it reaches over 50
            keys = list(BaseMatch._recent_matches.keys())
            for i in range(20):
                del BaseMatch._recent_matches[keys[i]]
        #  Delete text_channel if it is not already deleted
        try:
            await asyncio.gather(
                self.text_channel.delete(reason='Match Ended'),
                self.voice_channel.delete(reason='Match Ended')
            )
        except discord.NotFound:
            pass

    def get_data(self):
        data = {'_id': self.id, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'owner': self.owner.id, 'channel_id': 0 if not self.text_channel else self.text_channel.id,
                'current_players': [p.id for p in self.__players],
                'previous_players': [p.id for p in self.__previous_players],
                'match_log': self.match_log}
        return data

    async def _channel_update(self, player, action: bool | None):
        player_member = d_obj.guild.get_member(player.id)
        await asyncio.gather(
            self.text_channel.set_permissions(player_member, view_channel=action),
            self.voice_channel.set_permissions(player_member, view_channel=action)
        )

    def _new_embed(self):
        return self.__embed_func(self)

    def view(self, new=False):
        if not new and self.__view:
            return self.__view.update()
        self.__view = self.view_func(self)
        return self.__view

    async def send_embed(self):
        if not self.embed_cache:
            self.embed_cache = self._new_embed()
        self.info_message = await disp.MATCH_INFO.send(self.text_channel, embed=self.embed_cache, view=self.view())
        await self.info_message.pin()

    async def update_embed(self):
        if self.info_message:
            self.embed_cache = self.embed_cache if tools.compare_embeds(self.embed_cache,
                                                                        self._new_embed()) else self._new_embed()
            try:
                await disp.MATCH_INFO.edit(self.info_message, embed=self.embed_cache, view=self.view())
            except discord.NotFound as e:
                log.error("Couldn't find self.info_message for Match %s", self.id_str, exc_info=e)
        else:
            await self.send_embed()

    def update_status(self):
        if len(self.players) < 2:
            self.status = MatchState.INVITING
        elif len(self.online_players) < 2:
            self.status = MatchState.LOGGING_IN
        elif self.online_players:
            self.status = MatchState.PLAYING

    async def _on_timeout(self):
        """for inheritance purposes"""
        await self.end_match()

    async def update_timeout(self):
        # check timeout, reset if least 2 players and online_players
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
                await self._on_timeout()
            elif self.should_warn and not self.timeout_warned:  # Warn of timeout
                self.timeout_warned = True
                self.log("Unless the timeout is reset, the match will timeout soon...")
                await disp.MATCH_TIMEOUT_WARN.send(self.text_channel, self.all_mentions,
                                                   tools.format_time_from_stamp(self.timeout_at, 'R'),
                                                   delete_after=30)

    async def update(self, check_timeout=True, user=None, char_name=None):
        """Update the match object.  Check_timeout is used to specify whether the timeout should be checked, default True.
        Login can be used to log a login action, pass a player.
        Otherwise, updates timeout, match status, and the embed if required"""

        # Do nothing if match is ended or update_locked
        if self.is_ended or self.__update_locked:
            return

        # Lock the match, so it can't be updated by any other methods if an update is in progress
        self.__update_locked = True

        if check_timeout:
            await self.update_timeout()

        self.update_status()
        await self.update_embed()

        # Unlock the match
        self.__update_locked = False

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
        return self.__ended

    @property
    def online_players(self):
        return [p for p in self.__players if p.online_name]

    @property
    def all_mentions(self):
        return ''.join([p.mention for p in self.__players])

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
    MATCH_LENGTH = 7
    MAX_PLAYERS = 2
    TYPE = 'Ranked'

    class RankedMatchView(views.MatchInfoView):

        def __init__(self, match: 'RankedMatch'):
            super().__init__(match)
            self.match = match

        @discord.ui.button(label="Round Won", style=discord.ButtonStyle.green, row=1)
        async def round_won_button(self, button: discord.Button, inter: discord.Interaction):
            p = Player.get(inter.user.id)
            self.match.submit_score(p, 1)

            if self.match._check_scores_submitted:
                if self.match._check_scores_equal():
                    button.disabled = True

            pass

        @discord.ui.button(label="Round Lost", style=discord.ButtonStyle.green, row=1)
        async def round_lost_button(self, button: discord.Button, inter: discord.Interaction):
            pass

        @discord.ui.button(label="Dispute", style=discord.ButtonStyle.red)
        async def dispute_round_button(self, button: discord.Button, inter: discord.Interaction):
            pass

    def __init__(self, owner: Player, invited: Player):
        super().__init__(owner, invited)
        self.__round_counter = 0
        self.__round_wrong_scores_counter = 0
        self.__round_winner = None
        self.__player1 = owner.on_playing(self)
        self.__player2 = invited.on_playing(self)
        self.__player1_stats = PlayerStats.get_from_db(p_id=owner.id, p_name=owner.name)
        self.__player2_stats = PlayerStats.get_from_db(p_id=invited.id, p_name=invited.name)
        self.__p1_submitted_score = None
        self.__p2_submitted_score = None
        super().view_func = self.RankedMatchView

    def setup(self):
        pass

    def _check_scores_submitted(self):
        if self.__p1_submitted_score and self.__p2_submitted_score:
            return True

    def _check_scores_equal(self):
        if not self._check_scores_submitted():
            raise tools.UnexpectedError("Both scores haven't been submitted yet!")
        if self.__p1_submitted_score == -self.__p2_submitted_score:
            return True
        return False

    def _check_round_winner(self):
        if self.__p1_submitted_score == -self.__p2_submitted_score == 1:
            self.__round_winner = self.__player1
            return self.__round_winner
        elif self.__p1_submitted_score == -self.__p2_submitted_score == -1:
            self.__round_winner = self.__player2
            return self.__round_winner
        else:
            raise tools.UnexpectedError("Error determining round winner!")

    def submit_score(self, player, score):
        """submits scores, returns player"""
        if player == self.__player1:
            self.__p1_submitted_score = score
        if player == self.__player2:
            self.__p2_submitted_score = score

    async def _progress_round(self):

        self._check_round_winner()
        self.__round_counter += 1
        if self.__round_counter >= self.MATCH_LENGTH:
            await self.end_match()  ## todo, subclass end_match or add more functionality to successful match end
            return

        #  Reset score variables
        self.__round_wrong_scores_counter = 0
        self.__round_winner = None
        self.__p1_submitted_score = None
        self.__p2_submitted_score = None

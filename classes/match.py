"""Holds main match classes"""
# External Imports
import discord
import asyncio
from logging import getLogger
from enum import Enum

# Internal Imports
import modules.discord_obj as d_obj
import modules.tools as tools
from classes.players import Player, ActivePlayer
import modules.database as db

log = getLogger('fs_bot')
match_id_counter = 0


class MatchState(Enum):
    INVITING = "Waiting for an invite to be accepted..."
    GETTING_READY = "Waiting for players to log in..."
    PLAYING = "Currently playing..."
    ENDED = "Match ended..."


class BaseMatch:
    _active_matches = dict()
    _recent_matches = dict()

    def __init__(self, owner: Player, invited: list[Player]):
        self.__id = None
        self.owner = owner
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__invited = invited
        self.__players: list[ActivePlayer] = [owner.on_playing(self)]  # player list, add owners active_player
        self.__previous_players = list[Player]
        self.match_log = list()  # logs recorded as list of tuples, (timestamp, message)
        self.status = MatchState.INVITING
        self.voice_channel: discord.VoiceChannel | None = None
        BaseMatch._active_matches[self.id] = self

    @classmethod
    async def create(cls, owner: Player, invited: list[Player]):
        obj = cls(owner, invited)
        # last_match = None  # await db.async_db_call(db.get_last_element, 'matches')
        # print('past db call')
        # obj.set_id(1 if not last_match else last_match['match_id'] + 1)
        invited_overwrites = {d_obj.guild.get_member(p.id): discord.PermissionOverwrite(view_channel=True)
                              for p in invited}

        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True),
            d_obj.guild.get_member(owner.id): discord.PermissionOverwrite(view_channel=True)
        }
        overwrites.update(invited_overwrites)

        obj.voice_channel = await d_obj.categories['user'].create_voice_channel(
            name=f'Match: {obj.id}',
            overwrites=overwrites)

        obj.log(f'Owner:{owner.name}{owner.id}')
        obj.log(f'Invited: {[player.name for player in invited]}')
        return obj

    def accept_invite(self, player: Player):
        self.__invited.remove(player)
        self.__players.append(player.on_playing(self))
        if self.status == MatchState.INVITING:
            self.status = MatchState.GETTING_READY
        self.log(f'{player.name} accepted invite')

    async def decline_invite(self, player: Player):
        self.__invited.remove(player)
        await self.channel_update()
        self.log(f'{player.name} declined invite')

    def invite(self, player: Player):
        if player not in self.__invited or player.active not in self.__players:
            self.__invited.append(player)
            self.log(f'Invited: {player.name}')
            return True
        else:
            return False

    def is_invited(self, player: Player):
        return player in self.__invited

    async def leave_match(self, player: ActivePlayer):
        self.__previous_players.append(player.player)
        self.__players.remove(player)
        player_member = d_obj.guild.get_member(player.id)
        await self.voice_channel.set_permissions(player_member, view_channel=False)
        player.player.on_quit()
        self.log(f'{player.name} left the match')

    async def end_match(self):
        self.end_stamp = tools.timestamp_now()
        # add match end message
        with self.voice_channel.typing():
            await asyncio.sleep(10)
        await self.voice_channel.delete(reason='Match Ended')
        self.log('Match Ended')
        await db.async_db_call(db.set_element, 'matches', self.get_data())
        for player in self.__players:
            await self.leave_match(player)

        del BaseMatch._active_matches[self.id]
        BaseMatch._recent_matches[self.id] = self

    def get_data(self):
        player_ids = [player.id for player in self.__players]
        data = {'match_id': self.id, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'owner': self.owner.id, 'players': player_ids, 'match_log': self.match_log}
        return data

    async def channel_update(self):
        if not self.__players:
            await self.end_match()
        players_members = [d_obj.guild.get_member(player.id) for player in self.__players + self.__invited]
        for player_member in players_members:
            await self.voice_channel.set_permissions(player_member, view_channel=True)

    def log(self, message):
        self.match_log.append((tools.timestamp_now(), message))
        log.info(f'Match ID [{self.id}]:{message}')

    @property
    def id(self):
        return self.__id

    @property
    def invited(self):
        return self.__invited

    @property
    def players(self):
        return self.__players

    @property
    def prev_players(self):
        return self.__previous_players

    # @id.setter
    # def set_id(self, a_id: int):
    #     self.__id = a_id

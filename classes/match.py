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
import modules.accounts_handler_simple as accounts

log = getLogger('fs_bot')
_match_id_counter = 0


class MatchState(Enum):
    INVITING = "Waiting for an invite to be accepted..."
    GETTING_READY = "Waiting for players to log in..."
    PLAYING = "Currently playing..."
    ENDED = "Match ended..."


class BaseMatch:
    _active_matches = dict()
    _recent_matches = dict()

    def __init__(self, owner: Player, player: Player):
        global _match_id_counter
        _match_id_counter += 1
        self.__id = _match_id_counter
        self.owner = owner
        self.__invited = list()
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__players: list[ActivePlayer] = [owner.on_playing(self), player.on_playing(self)]   # player list, add owners active_player
        self.__previous_players: list[Player] = list()
        self.match_log = list()  # logs recorded as list of tuples, (timestamp, message)
        self.status = MatchState.INVITING
        self.text_channel: discord.TextChannel | None = None
        self.info_message: discord.Message | None = None
        BaseMatch._active_matches[self.id] = self

    @classmethod
    async def create(cls, owner: Player, invited: Player):
        obj = cls(owner, invited)
        # last_match = None  # await db.async_db_call(db.get_last_element, 'matches')
        # print('past db call')
        # obj.set_id(1 if not last_match else last_match['match_id'] + 1)

        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True),
            d_obj.guild.get_member(owner.id): discord.PermissionOverwrite(view_channel=True),
            d_obj.guild.get_member(invited.id): discord.PermissionOverwrite(view_channel=True)
        }

        obj.text_channel = await d_obj.categories['user'].create_text_channel(
            name=f'Match︰{obj.id}',
            overwrites=overwrites)

        obj.log(f'Owner:{owner.name}{owner.id}')
        return obj

    async def join_match(self, player: Player):
        #  Joins player to match and updates permissions
        self.__invited.remove(player)
        self.__players.append(player.on_playing(self))
        await self.channel_update(player, True)
        self.log(f'{player.name} joined the match')

    async def leave_match(self, player: ActivePlayer):
        self.__previous_players.append(player.player)
        self.__players.remove(player)
        await self.channel_update(player, False)
        player.player.on_quit()
        self.log(f'{player.name} left the match')
        if not self.__players and not self.end_stamp:  # if no players left, and match not already ended
            await self.end_match()
        if player.account:
            await accounts.terminate_account(player=player.player)
            player.player.set_account(None)

    async def end_match(self):
        self.end_stamp = tools.timestamp_now()
        # add match end message
        with self.text_channel.typing():
            await asyncio.sleep(10)
        for player in self.__players:
            await self.leave_match(player)
        await self.text_channel.delete(reason='Match Ended')
        self.log('Match Ended')
        await db.async_db_call(db.set_element, 'matches', self.id, self.get_data())
        del BaseMatch._active_matches[self.id]
        BaseMatch._recent_matches[self.id] = self

    def get_data(self):
        player_ids = [player.id for player in self.__players]
        data = {'match_id': self.id, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'owner': self.owner.id, 'players': player_ids, 'match_log': self.match_log}
        return data

    async def channel_update(self, player, action: bool):
        player_member = d_obj.guild.get_member(player.id)
        await self.text_channel.set_permissions(player_member, view_channel=action)

    def log(self, message):
        self.match_log.append((tools.timestamp_now(), message))
        log.info(f'Match ID [{self.id}]:{message}')

    @property
    def id(self):
        return self.__id

    @property
    def players(self):
        return self.__players

    @property
    def prev_players(self):
        return self.__previous_players

    @property
    def invited(self):
        return self.__invited

    def invite(self, player: Player):
        if player not in self.__invited:
            self.__invited.append(player)

    def decline_invite(self, player: Player):
        if player in self.__invited:
            self.__invited.remove(player)


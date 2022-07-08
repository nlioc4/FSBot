"""Holds main match classes"""
# External Imports
import discord
import asyncio
from logging import getLogger

# Internal Imports
import modules.discord_obj as d_obj
import modules.config as cfg
import Lib.tools as tools
from classes.players import Player, ActivePlayer
from display import ContextWrapper, AllStrings as disp
import modules.database as db

log = getLogger('fs_bot')

class BaseMatch:
    _active_matches = dict()
    _recent_matches = dict()

    def __init__(self, owner: Player, invited: list[Player]):
        self.id = None
        self.owner = owner
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__invited = invited
        self.__players = list[ActivePlayer] = [owner.on_playing(self)]  # player list, add owners active_player
        self.__previous_players = list[Player]
        self.match_log = list()  # logs recorded as list of strings, timestamp;source;message
        self.voice_channel: discord.VoiceChannel | None = None
        self.text_channel: discord.TextChannel | None = None
        BaseMatch._active_matches[self.id] = self

    @classmethod
    async def create(cls, owner: Player, invited: list[Player]):
        obj = cls(owner, invited)
        last_match = await db.async_db_call(db.get_last_element, 'matches')
        obj.id = last_match['match_id'] + 1
        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True),
            d_obj.guild.get_member(owner.id): discord.PermissionOverwrite(view_channel=True)
        }
        obj.voice_channel = await d_obj.channels['dashboard'].category.create_voice_channel(
            name=f'Match: {obj.id} Voice',
            overwrites=overwrites)

        obj.text_channel = await d_obj.channels['dashboard'].category.create_text_channel(
            name=f'Match: {obj.id} Text',
            overwrites=overwrites)
        obj.log('self', f'Match:{obj.id} created by Owner:{owner.name}{owner.id}')
        obj.log('self', f'Invited: {[player.name for player in invited]}')
        return obj

    async def accept_invite(self, player: Player):
        self.__invited.remove(player)
        self.__players.append(player.on_playing(self))
        await self.channel_update()

    def decline_invite(self, player: Player):
        self.__invited.remove(player)

    async def leave_match(self, player: ActivePlayer):
        self.__previous_players.append(player.player)
        self.__players.remove(player)
        player_member = d_obj.guild.get_member(player.id)
        await self.voice_channel.set_permissions(player_member, view_channel=False)
        await self.text_channel.set_permissions(player_member, view_channel=False)
        player.player.on_quit()

    async def end_match(self):
        ctx = ContextWrapper(None, self.text_channel.id, None, self.text_channel)
        self.end_stamp = tools.timestamp_now()
        await disp.MATCH_END.send(ctx, self.id)
        await asyncio.sleep(10)
        await self.voice_channel.delete(reason='Match Ended')
        await self.text_channel.delete(reason='Match Ended')
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
        players_members = [d_obj.guild.get_member(player.id) for player in self.__players]
        for player_member in players_members:
            await self.voice_channel.set_permissions(player_member, view_channel=True)
            await self.voice_channel.set_permissions(player_member, view_channel=True)

    def log(self, source, message):
        string = f'{tools.timestamp_now()}|{source}|{message}'
        self.match_log.append(string)
        log.info(f'{source}|{message}')


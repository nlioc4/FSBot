"""Holds main match classes"""
# External Imports
import discord
import asyncio

# Internal Imports
import modules.discord_obj as d_obj
import modules.config as cfg
import Lib.tools as tools
from players import Player, ActivePlayer
from display import ContextWrapper, AllStrings as disp
import modules.database as db


class BaseMatch:
    def __init__(self, owner: Player, invited: list[Player]):
        self.id = await db.async_db_call(db.get_last_element, 'matches')['match_id'] + 1
        self.owner = owner
        self.start_stamp = tools.timestamp_now()
        self.end_stamp = None
        self.__invited = invited
        self.__players = list[ActivePlayer] = [owner.on_playing(self)]  # player list, add owners active_player
        self.__previous_players = list[Player]
        self.match_logs = dict[int: str] # logs recorded by timestamp: log_message

        overwrites = {
            d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True),
            d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True),
            d_obj.guild.get_member(self.owner.id): discord.PermissionOverwrite(view_channel=True)

        }
        self.voice_channel = await d_obj.channels['dashboard'].category.create_voice_channel(name=f'Match: {self.id} Voice',
                                                                                            overwrites=default_overwrites)
        self.text_channel = await d_obj.channels['dashboard'].category.create_text_channel(name=f'Match: {self.id} Text',
                                                                                            overwrites=default_overwrites)  # Temp until text in voice is completed

    def accept_invite(self, player: Player):
        self.__invited.remove(player)
        self.__players.append(player.on_playing(self))
        self.channel_update()

    def decline_invite(self, player: Player):
        self.__invited.remove(player)

    def leave_match(self, player: ActivePlayer):
        self.__previous_players.append(player.player)
        self.__players.remove(player)
        player_member = d_obj.guild.get_member(player.id)
        await self.voice_channel.set_permissions(player_member, view_channel=False)
        await self.text_channel.set_permissions(player_member, view_channel=False)
        player.on_quit()

    def end_match(self):
        ctx = ContextWrapper(None, self.text_channel.id, None, self.text_channel)
        self.end_stamp = tools.timestamp_now()
        await disp.MATCH_END.send(ctx, self.id)
        await asyncio.sleep(10)
        await self.voice_channel.delete(reason='Match Ended')
        await self.text_channel.delete(reason='Match Ended')
        db.async_db_call(db.set_element, 'matches', self.get_data())
        for players in self.__players:
            self.leave_match(player)


    def get_data(self):
        player_ids = [player.id for player in self__players]
        data = {'match_id': self.id, 'start_stamp': self.start_stamp, 'end_stamp': self.end_stamp,
                'owner': self.owner.id, 'players': player_ids, 'match_log': self.match_logs}

    async def channel_update(self):
        if not self.__players:
            self.end_match()
        players_members = [d_obj.guild.get_member(player.id) for player in self.__players]
        for player_member in players_members:
            await self.voice_channel.set_permissions(player_member, view_channel=True)
            await self.voice_channel.set_permissions(player_member, view_channel=True)





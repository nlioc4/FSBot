"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord
from logging import getLogger
import asyncio

from discord.ext import commands, tasks

# Internal Imports
import display
from display import AllStrings as disp, views
import modules.config as cfg
import modules.tools as tools
from classes.match import BaseMatch, MatchState
from classes import Player
from modules import discord_obj as d_obj
from modules.spam_detector import is_spam
import modules.accounts_handler as accounts


log = getLogger('fs_bot')

class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot):
        self.bot = bot
        self.matches_init.start()
        # self.matches_loop.start()

    @tasks.loop(count=1)
    async def matches_init(self):
        # clear old match channels if any exist
        channels_to_delete = []
        text_channels = d_obj.categories['user'].text_channels
        voice_channels = d_obj.categories['user'].voice_channels
        for channel in text_channels:
            if channel.name.startswith('casual'):
                channels_to_delete.append(channel.delete())
        for channel in voice_channels:
            if channel.name.startswith('Casual'):
                channels_to_delete.append(channel.delete())
        await asyncio.gather(*channels_to_delete)

    @commands.Cog.listener('on_message')
    async def matches_message_listener(self, message: discord.Message):

        if message.author == self.bot.user:
            return

        match_channel_dict = BaseMatch.active_match_channel_ids()
        if message.channel.id not in match_channel_dict:
            return

        if p := Player.get(message.author.id):
            match_channel_dict[message.channel.id].log(
                f'{p.name}: {message.clean_content}', public=False
            )


def setup(client):
    client.add_cog(MatchesCog(client))

"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord

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


class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot):
        self.bot = bot
        self.matches_init.start()
        self.matches_loop.start()

    @tasks.loop(count=1)
    async def matches_init(self):
        # clear old match channels if any exist
        channels = d_obj.categories['user'].text_channels
        for channel in channels:
            if channel.name.startswith('casual'):
                await channel.delete()

    @tasks.loop(seconds=30)
    async def matches_loop(self):
        # update match info embeds
        for match in BaseMatch.active_matches_list():
            # only iterate on matches that have started > 5 seconds ago, and are not stopped
            if match.start_stamp > tools.timestamp_now() - 5 or match.end_stamp:
                continue
            await match.update_match()

    @commands.Cog.listener('on_message')
    async def matches_message_listener(self, message: discord.Message):

        if message.author == self.bot.user:
            return

        match_channel_dict = BaseMatch.active_match_channel_ids()
        if message.channel.id not in match_channel_dict:
            return

        match_channel_dict[message.channel.id].log(
            f'{message.author.name}: {message.content}', public=False
        )
        await match_channel_dict[message.channel.id].update_match()


def setup(client):
    client.add_cog(MatchesCog(client))

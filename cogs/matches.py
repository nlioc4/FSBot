"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord

from discord.ext import commands, tasks

# Internal Imports
import display
from display import AllStrings as disp, views
import modules.config as cfg
from classes.match import BaseMatch
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
            if channel.name.startswith('match-id'):
                await channel.delete()

    @tasks.loop(seconds=10)
    async def matches_loop(self):
        # update match info embeds
        for match in BaseMatch.active_matches_list():
            await match.update_match()










def setup(client):
    client.add_cog(MatchesCog(client))







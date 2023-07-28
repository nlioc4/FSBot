"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord
from logging import getLogger
import asyncio

from discord.ext import commands, tasks

# Internal Imports
import modules.config as cfg
from classes.match import BaseMatch
from classes import Player
from modules import discord_obj as d_obj

log = getLogger('fs_bot')


class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.matches_init.start()

    @tasks.loop(count=1)
    async def matches_init(self):
        await d_obj.loaded.wait()

        # clear old match channels/threads if any exist
        coroutines = []

        # delete old match voice channels
        voice_channels = d_obj.categories['user'].voice_channels
        for channel in voice_channels:
            if (channel.name.startswith('Casual') or channel.name.startswith('Ranked')) \
                    and channel not in d_obj.channels.values():
                coroutines.append(channel.delete())

        # Archive old match Threads
        # Epic list comprehension
        threads = [thread for thread in
                   [*d_obj.channels['casual_lobby'].threads, *d_obj.channels['ranked_lobby'].threads] if
                   not thread.archived]
        for thread in threads:
            coroutines.append(thread.archive(locked=True))

        await asyncio.gather(*coroutines)

    @commands.Cog.listener('on_message')
    async def matches_message_listener(self, message: discord.Message):

        if message.author == self.bot.user:
            return

        if not (match := BaseMatch.active_match_thread_ids().get(message.channel.id)):
            return

        image = ''
        if message.attachments:
            for img in message.attachments:
                image += f"[Image]({img.url})"

        if p := Player.get(message.author.id):
            match.log(
                f'{p.name}: {message.clean_content}{image}', public=False
            )


def setup(client):
    client.add_cog(MatchesCog(client))

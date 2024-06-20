"""
Quick Spam detector meant to stop the recent influx of discord spam links
"""

# External Imports
import discord
from discord.ext import commands
from logging import getLogger
import re

# Internal Imports
import modules.discord_obj as d_obj
from display import AllStrings as disp

log = getLogger('fs_bot')


class SpamCheckCog(commands.Cog, name="SpamCheckCog"):
    def __init__(self):
        self.enabled = True

    @commands.Cog.listener('on_message')
    async def spam_check(self, message: discord.Message):
        if not self.enabled:
            return

        if message.author == d_obj.bot.user:
            return

        if d_obj.is_admin(message.author):
            return

        if message.guild is None:
            return

        if message.author not in message.guild.members:
            return

        if message.channel.type == discord.ChannelType.news:
            return

        # If message contains a link to discord, and an @everyone / @ here mention, delete it and kick the user.
        if re.search(r"https?://discord.gg/.*", message.content):

            if re.search(r"@everyone|@here", message.content):
                await message.delete()
                await disp.SPAM_LINK_KICKED.send(message.author)
                await message.author.ban(reason="Spam Link detected.", delete_message_seconds=60)
                await message.author.unban(reason="Soft bank for message deletion.")
                await d_obj.d_log(disp.SPAM_LINK_KICK(message.author.name, message.author.mention))
            else:
                await d_obj.d_log(
                    f'User {message.author.name} posted a discord link [here]({message.jump_url}).',
                    d_obj.colin.mention)


def setup(bot): 
    bot.add_cog(SpamCheckCog())

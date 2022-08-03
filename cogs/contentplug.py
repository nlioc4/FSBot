"""
Simple filter setup to create threads in #contentplug, and enforce the content only rule

"""


# External Imports
from discord.ext import commands
import discord
from logging import getLogger

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj

TEST_LIST = ['.com', '.ru', '.net', '.org', '.info', '.biz', '.io', '.co', "https://", "http://", "www.", ".ca"]
log = getLogger("fs_bot")

class ContentPlug(commands.Cog, name="ContentPlug"):
    def __init__(self, bot):
        self.bot = bot
        self.enabled = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.enabled:
            return
        matches = [item for item in TEST_LIST if (item in message.content)]

        if message.author == self.bot.user:
            return
        elif not message.channel.id == cfg.channels['content-plug']:
            return
        elif d_obj.roles['app_admin'] in message.author.roles:
            return
        elif matches or message.attachments:
            await message.create_thread(name=f"{message.author.display_name}'s content thread")
        elif not matches:
            log.info(f'{message.author.name} had a message deleted in content plug.')
            await message.delete()
            await message.channel.send(f'Oops {message.author.mention}, messages in this channel '
                                       f'must contain either an attachment or a link!', delete_after=10)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not self.enabled:
            return
        matches = [item for item in TEST_LIST if (item in after.content)]

        if after.author == self.bot.user:
            return
        elif not after.channel.id == cfg.channels['content-plug']:
            return
        elif d_obj.roles['app_admin'] in after.author.roles:
            return
        elif matches or before.attachments or after.attachments:
            return
        elif not matches:
            log.info(f'{after.author.name} had a message deleted in content plug.')
            await after.delete()
            await after.channel.send(f'Oops {after.author.mention}, messages in this channel '
                                     f'must contain either an attachment or a link!', delete_after=10)


def setup(client):
    client.add_cog(ContentPlug(client))
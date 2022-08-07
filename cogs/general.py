import discord
from discord.ext import commands
from logging import getLogger

import asyncio

# Internal Imports
from modules import trello
from display import AllStrings as disp
import modules.config as cfg

log = getLogger('fs_bot')


class GeneralCog(commands.Cog, name="GeneralCog"):

    def __init__(self, client):
        self.bot: discord.Bot = client

    @commands.slash_command(name="suggestion")
    async def suggestion(self, ctx: discord.ApplicationContext,
                         title: discord.Option(str, "Input your suggestion's title here", required=True),
                         description: discord.Option(str, "Describe your suggestion here", required=True)):
        """Send a suggestion for FSBot to the administration team!"""

        await trello.create_card(title, description)
        await disp.SUGGESTION_ACCEPTED.send_priv(ctx, ctx.user.mention)


def setup(client):
    client.add_cog(GeneralCog(client))
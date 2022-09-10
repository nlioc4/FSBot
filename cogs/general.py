import discord
from discord.ext import commands
from logging import getLogger

import asyncio

# Internal Imports
from modules import trello
from modules import discord_obj as d_obj
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

        await trello.create_card(title, f"Suggested by [{ctx.user.name}] : " + description)
        await disp.SUGGESTION_ACCEPTED.send_priv(ctx, ctx.user.mention)

    @commands.slash_command(name="freeme", guild_ids=[cfg.general['guild_id']])
    async def free_me(self, ctx: discord.ApplicationContext):
        await ctx.defer(epehemeral=True)
        if not (p := d_obj.is_player(ctx.user)):
            return await disp.NOT_PLAYER.send_priv(ctx)
        await d_obj.role_update(member=ctx.user, player=p, reason=f"{ctx.user.name} requested freedom and was granted it.")
        await disp.TIMEOUT_RELEASED.send_priv(ctx)


def setup(client):
    client.add_cog(GeneralCog(client))

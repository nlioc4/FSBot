import discord
from discord.ext import commands, tasks
from logging import getLogger

import asyncio

# Internal Imports
from modules import trello
from modules import discord_obj as d_obj, tools, bot_status
from display import AllStrings as disp, views


import modules.config as cfg

log = getLogger('fs_bot')


class GeneralCog(commands.Cog, name="GeneralCog"):

    def __init__(self, client):
        self.bot: discord.Bot = client
        self.bot.add_view(views.RemoveTimeoutView())
        self.activity_update.start()

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
            return await disp.NOT_PLAYER.send_priv(ctx, ctx.user.mention, d_obj.channels['register'])
        if p.timeout_until != 0 and not p.is_timeout:
            await d_obj.timeout_player(p=p, stamp=0)
            await disp.TIMEOUT_RELEASED.send_priv(ctx)
        elif p.is_timeout:
            await disp.TIMEOUT_STILL.send_priv(ctx, tools.format_time_from_stamp(p.timeout_until, 'R'))
        else:
            await disp.TIMEOUT_FREE.send_priv(ctx)

    @tasks.loop(seconds=5)
    async def activity_update(self):
        await bot_status.update_status()


def setup(client):
    client.add_cog(GeneralCog(client))

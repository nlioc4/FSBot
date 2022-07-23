"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord
from classes import Player
from discord.ext import commands, tasks

# Internal Imports
import display
from display import AllStrings as disp
import modules.config as cfg
from classes.players import Player
from classes.match import BaseMatch
from modules import discord_obj as d_obj
from modules.spam_detector import is_spam


class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(seconds=10)
    async def matches_loop(self):
        # update match info embeds
        for match in BaseMatch._active_matches.values():
            disp.MATCH_INFO.edit(match.info_message, match=match)



def setup(client):
    client.add_cog(MatchesCog(client))


class MatchInfoView(discord.ui.View):
    """View to handle match controls"""
    def __init__(self, match: BaseMatch):
        super().__init__()
        self.match = match


    @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
    async def leave_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return

        await disp.MATCH_LEAVE.send_temp(inter, p.mention)
        await asyncio.wait(3)
        if p == match.owner:
            await match.end_match()
        else:
            await self.match.leave_match(p.active)


    @discord.ui.Button(label="Request Account", style=discord.ButtonStyle.blurple)
    async def account_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        if p.has_own_account:
            await disp.ACCOUNT_HAS_OWN.send_temp(inter, p.mention)
            return
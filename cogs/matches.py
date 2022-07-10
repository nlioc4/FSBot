"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord
from discord.ext import commands

# Internal Imports
import display
import modules.config as cfg
from classes.players import Player
from classes.match import BaseMatch
from .display import AllStrings as disp


class InviteView(discord.ui.View):
    """Cog to handle accepting or declining match invites"""

    def __init__(self, match):
        super().__init__()
        self.match: BaseMatch = match

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        if not self.match.is_invited(p):
            await disp.INVITE_WRONG_USER.send_priv(inter)
            return
        self.match.accept_invite(p)

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        if not self.match.is_invited(p):
            await disp.INVITE_WRONG_USER.send_priv(inter)
            return
        await self.match.decline_invite(p)


class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot):
        self.bot = bot




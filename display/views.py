"""Views to be used in the bot"""


# External Imports
import discord


# Interal Imports
import modules.discord_obj as d_obj
import modules.lobby as lobby
from modules.spam_detector import is_spam
from classes import Player
from display import AllStrings as disp



class InviteView(discord.ui.View):
    """View to handle accepting or declining match invites"""

    def __init__(self, owner):
        super().__init__(timeout=300)
        self.owner: Player = owner

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return

        await lobby.accept_invite(self.owner, p)
        await inter.message.delete()
        await disp.MATCH_ACCEPT.send_priv(inter)

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        lobby.decline_invite(self.owner, p)
        await inter.message.delete()
        await disp.MATCH_DECLINE.send_priv(inter)



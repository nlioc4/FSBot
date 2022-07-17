"""Views to be used in the bot"""


# External Imports
import discord


# Interal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from modules.spam_detector import is_spam
from classes import Player
from display import AllStrings as disp, embeds, views



class InviteView(discord.ui.View):
    """View to handle accepting or declining match invites"""

    def __init__(self, owner):
        super().__init__()
        self.owner: Player = owner ##TODO broken

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return

        await disp.MATCH_ACCEPT.send_temp(inter, p.mention)
        if len(self.match.invited) == 0:
            await inter.message.delete()
        else:
            await disp.MATCH_INVITED.edit(inter.message, ' '.join([invited.mention for invited in self.match.invited]),
                                          self.match.owner.mention, view=InviteView(self.match))

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        if not self.match.is_invited(p):
            await disp.INVITE_WRONG_USER.send_priv(inter)
            return
        await self.match.decline_invite(p)
        await disp.MATCH_DECLINE.send_temp(inter, p.mention)
        if len(self.match.invited) == 0:
            await inter.message.delete()
        else:
            await disp.MATCH_INVITED.edit(inter.message, ' '.join([invited.mention for invited in self.match.invited]),
                                          self.match.owner.mention, view=InviteView(self.match))
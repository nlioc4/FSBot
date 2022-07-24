"""Views to be used in the bot"""


# External Imports
import discord
import asyncio

# Interal Imports
import modules.discord_obj as d_obj
import modules.lobby as lobby
from modules.spam_detector import is_spam
from classes import Player
from display import AllStrings as disp
import modules.accounts_handler_simple as accounts


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


class MatchInfoView(discord.ui.View):
    """View to handle match controls"""
    def __init__(self, match):
        super().__init__()
        self.match = match

    @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
    async def leave_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return

        await disp.MATCH_LEAVE.send_temp(inter, p.mention)
        await asyncio.sleep(1)
        if p == self.match.owner:
            await self.match.end_match()
        else:
            await self.match.leave_match(p.active)

    @discord.ui.button(label="Request Account", style=discord.ButtonStyle.blurple)
    async def account_button(self, button: discord.Button, inter: discord.Interaction):
        """Requests an account for the player"""
        p: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, p):
            return
        elif p.has_own_account:
            await disp.ACCOUNT_HAS_OWN.send_priv(inter)
            return
        elif p.account:
            await disp.ACCOUNT_ALREADY.send_priv(inter)
            return
        else:
            acc = accounts.pick_account(p)
            msg = None
            if acc:  # if account found
                msg = await accounts.send_account(acc)
                if msg:  # if could dm user
                    await disp.ACCOUNT_SENT.send_priv(inter)
                else:
                    await disp.ACCOUNT_NO_DMS.send_priv(inter)
                    acc.clean()

            else:  # if no account found
                await disp.ACCOUNT_NO_ACCOUNT.send_priv(inter)


"""Views to be used in the bot"""

# External Imports
import discord
import asyncio
import sys
import traceback

# Interal Imports
import modules.discord_obj as d_obj
import modules.lobby as lobby
from modules.spam_detector import is_spam
import modules.tools as tools
from classes import Player
from display import AllStrings as disp
import modules.accounts_handler as accounts
from modules.loader import is_all_locked


class FSBotView(discord.ui.View):
    """Base View for the bot, includes error handling and locked check"""

    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_all_locked():
            memb = d_obj.guild.get_member(interaction.user.id)
            if d_obj.is_admin(memb):
                return True
            else:
                await disp.ALL_LOCKED.send_priv(interaction)
                return False
        if await is_spam(interaction, view=True):
            return False
        return True

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:

        try:
            await disp.GENERAL_ERROR.send_priv(interaction, error, d_obj.colin.mention)
        except discord.errors.InteractionResponded:
            pass
        finally:
            await d_obj.d_log(error, interaction.user)
        print(f"Ignoring exception in view {self} for item {item}:", file=sys.stderr)
        traceback.print_exception(error.__class__, error, error.__traceback__, file=sys.stderr)


class InviteView(FSBotView):
    """View to handle accepting or declining match invites"""

    def __init__(self, owner, player):
        super().__init__(timeout=300)
        self.owner: Player = owner
        self.player = player
        self.msg = None

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return

        self.disable_all_items()
        self.stop()

        match = await lobby.accept_invite(self.owner, p)
        await inter.response.edit_message(view=self)
        await disp.MATCH_ACCEPT.send(inter.message, match.text_channel.mention)

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return
        lobby.decline_invite(self.owner, p)
        self.disable_all_items()
        self.stop()

        await inter.response.edit_message(view=self)
        await disp.MATCH_DECLINE.send(inter.message)

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.msg.edit(view=self)
        await disp.DM_INVITE_EXPIRED.send(self.msg)
        lobby.decline_invite(self.owner, self.player)


class MatchInfoView(FSBotView):
    """View to handle match controls"""

    def __init__(self, match):
        super().__init__(timeout=None)
        self.match = match
        if not self.match.should_warn:
            self.reset_timeout_button.style = discord.ButtonStyle.grey
            self.reset_timeout_button.disabled = True

    @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
    async def leave_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return

        await disp.MATCH_LEAVE.send_priv(inter, p.mention)
        if p == self.match.owner:
            await self.match.end_match()
        else:
            await asyncio.sleep(0.5)
            await self.match.leave_match(p.active)

    @discord.ui.button(label="Reset Timeout", style=discord.ButtonStyle.green)
    async def reset_timeout_button(self, button: discord.Button, inter: discord.Interaction):
        """Resets the match from timeout"""
        self.match.timeout_at = tools.timestamp_now()
        await disp.MATCH_TIMEOUT_RESET.send_temp(self.match.text_channel, inter.user.mention)
        await self.match.update_embed()

    @discord.ui.button(label="Request Account", style=discord.ButtonStyle.blurple)
    async def account_button(self, button: discord.Button, inter: discord.Interaction):
        """Requests an account for the player"""
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return
        elif p.has_own_account:
            await disp.ACCOUNT_HAS_OWN.send_priv(inter)
            return
        elif p.account:
            await disp.ACCOUNT_ALREADY.send_priv(inter)
            return
        else:
            acc = accounts.pick_account(p)
            if acc:  # if account found
                msg = await accounts.send_account(acc)
                if msg:  # if could dm user
                    await disp.ACCOUNT_SENT.send_priv(inter)
                else:  # if couldn't dm
                    await disp.ACCOUNT_NO_DMS.send_priv(inter)
                    acc.clean()

            else:  # if no account found
                await disp.ACCOUNT_NO_ACCOUNT.send_priv(inter)

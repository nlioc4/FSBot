"""Views to be used in the bot"""

# External Imports
import discord
import asyncio
import sys
import traceback
from logging import getLogger

# Interal Imports
import modules.discord_obj as d_obj
from modules.spam_detector import is_spam
import modules.tools as tools
from classes import Player
from display import AllStrings as disp
import modules.accounts_handler as accounts
from modules.loader import is_all_locked

log = getLogger('fs_bot')


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
            await disp.LOG_GENERAL_ERROR.send_priv(interaction, error)
        except discord.errors.InteractionResponded or discord.errors.NotFound:
            pass
        finally:
            await d_obj.d_log(source=interaction.user.name, message="Error on component interaction", error=error)
            # log.error("Error on component interaction", exc_info=error)
        # traceback.print_exception(error.__class__, error, error.__traceback__, file=sys.stderr)


class InviteView(FSBotView):
    """View to handle accepting or declining match invites"""

    def __init__(self, lobby, owner, player):
        super().__init__(timeout=300)
        self.lobby = lobby
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

        match = await self.lobby.accept_invite(self.owner, p)

        if match:
            await disp.MATCH_ACCEPT.send(inter.message, match.text_channel.mention)
            await inter.response.edit_message(view=self)
            return
        await disp.DM_INVITE_INVALID.edit(inter.message, view=self)

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return
        self.lobby.decline_invite(self.owner, p)
        self.disable_all_items()
        self.stop()

        owner_mem = d_obj.guild.get_member(self.owner.id)
        await disp.MATCH_DECLINE_INFO.send(owner_mem, p.mention)

        await inter.response.edit_message(view=self)
        await disp.MATCH_DECLINE.send(inter.message)

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.msg.edit(view=self)
        await disp.DM_INVITE_EXPIRED.send(self.msg)
        owner_mem = d_obj.guild.get_member(self.owner.id)
        await disp.DM_INVITE_EXPIRED_INFO.send(owner_mem, self.player.mention)
        self.lobby.decline_invite(self.owner, self.player)


class MatchInfoView(FSBotView):
    """View to handle match controls"""

    def __init__(self, match):
        super().__init__(timeout=None)
        self.match = match
        if not self.match.should_warn:
            self.reset_timeout_button.style = discord.ButtonStyle.grey
            self.reset_timeout_button.disabled = True

    def update(self):
        self._update()
        if not self.match.should_warn:
            if self.match.should_warn:
                self.reset_timeout_button.style = discord.ButtonStyle.green
                self.reset_timeout_button.disabled = False
            else:
                self.reset_timeout_button.style = discord.ButtonStyle.grey
                self.reset_timeout_button.disabled = True
            return True

    def _update(self):
        """For Inheritance"""
        pass

    async def in_match_check(self, inter, p: Player) -> bool:
        if p.active in self.match.players:
            return True
        await disp.MATCH_NOT_IN.send_priv(inter, self.match.id_str)
        return False

    @discord.ui.button(label="Leave Match", style=discord.ButtonStyle.red)
    async def leave_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p) and not self.in_match_check(inter, p):
            return

        await disp.MATCH_LEAVE.send_priv(inter, p.mention)
        await self.match.leave_match(p.active)

    @discord.ui.button(label="Reset Timeout", style=discord.ButtonStyle.green)
    async def reset_timeout_button(self, button: discord.Button, inter: discord.Interaction):
        """Resets the match from timeout"""
        self.match.timeout_stamp = None
        await disp.MATCH_TIMEOUT_RESET.send_temp(self.match.text_channel, inter.user.mention)
        self.match.log("Match Timeout Reset")
        await self.match.update_embed()

    @discord.ui.button(label="Request Account", style=discord.ButtonStyle.blurple)
    async def account_button(self, button: discord.Button, inter: discord.Interaction):
        """Requests an account for the player"""
        await inter.response.defer()
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p) and not self.in_match_check(inter, p):
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
                if msg:  # if allowed to dm user
                    await disp.ACCOUNT_SENT.send_priv(inter)
                else:  # if couldn't dm
                    await disp.ACCOUNT_NO_DMS.send_priv(inter)
                    acc.clean()

            else:  # if no account found
                await disp.ACCOUNT_NO_ACCOUNT.send_priv(inter)

"""Views to be used in the bot"""

# External Imports
import discord
import asyncio
import sys
import traceback
from logging import getLogger

# Interal Imports
import modules.discord_obj as d_obj
from modules.spam_detector import is_spam, unlock
import modules.tools as tools
from classes import Player
from display import AllStrings as disp
import modules.accounts_handler as accounts
from modules.loader import is_all_locked

log = getLogger('fs_bot')


class FSBotView(discord.ui.View):
    """Base View for the bot, includes error handling and locked check"""

    def __init__(self, timeout=None):
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.msg = None

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

        if await d_obj.is_timeout_check(interaction):
            return False

        return True

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:

        try:
            await disp.LOG_GENERAL_ERROR.send_priv(interaction, error)
        except (discord.errors.InteractionResponded, discord.errors.NotFound):
            pass
        finally:
            await d_obj.d_log(source=interaction.user.name, message="Error on component interaction", error=error)
            # log.error("Error on component interaction", exc_info=error)
        # traceback.print_exception(error.__class__, error, error.__traceback__, file=sys.stderr)

    async def _scheduled_task(self, item: discord.ui.Item, interaction: discord.Interaction):
        """Subclassed scheduled task to unlock users from spam filter after callbacks finish"""
        await super()._scheduled_task(item, interaction)
        unlock(interaction.user.id)

    async def disable_and_stop(self):
        self.disable_all_items()
        self.stop()
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass


class InviteView(FSBotView):
    """View to handle accepting or declining match invites"""

    def __init__(self, lobby, owner, player):
        super().__init__(timeout=300)
        self.lobby = lobby
        self.owner: Player = owner
        self.player = player

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return

        self.stop()
        await disp.LOADING.edit(inter, view=False)
        match = await self.lobby.accept_invite(self.owner, p)

        if match:
            await disp.INVITE_ACCEPT.edit(inter.message, self.owner.mention, match.text_channel.mention)
        else:
            await disp.DM_INVITE_INVALID.edit(inter.message)

    @discord.ui.button(label="Decline Invite", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.Button, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return
        self.lobby.decline_invite(self.owner, p)
        self.stop()

        owner_mem = d_obj.guild.get_member(self.owner.id)
        await disp.INVITE_DECLINE_INFO.send(owner_mem, p.mention)

        await disp.INVITE_DECLINE.edit(inter, self.owner.mention, view=False)

    decline_reasons = {
        "Skill Preference": "Skill level does not match preference",
        "Faction Preference": "Faction choice does not match preference",
        "Forgot Queue": "User forgot they were in queue!",
        "Custom": "Enter a custom decline reason"
    }

    @discord.ui.select(placeholder="Give a reason for declining an invite",
                       min_values=1, max_values=1,
                       options=[discord.SelectOption(label=k, value=k, description=v) for k, v in
                                decline_reasons.items()])
    async def decline_select(self, select: discord.ui.Select, inter: discord.Interaction):
        p: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, p):
            return
        self.lobby.decline_invite(self.owner, p)
        self.stop()

        owner_mem = d_obj.guild.get_member(self.owner.id)
        reason = select.values[0]
        await disp.INVITE_DECLINE.edit(self.message, self.owner.mention, view=False)

        if reason != "Custom":
            await disp.INVITE_DECLINE_INFO_REASON.send(owner_mem, p.mention, self.decline_reasons[reason])
            await disp.INVITE_DECLINE_REASON.send(inter, reason)
        else:
            await inter.response.send_modal(self.DeclineInviteModal(self))

    class DeclineInviteModal(discord.ui.Modal):
        def __init__(self, invite_view) -> None:
            super().__init__(
                discord.ui.InputText(
                    label="Input Custom Decline Reason",
                    placeholder="Your decline reason here...",
                    style=discord.InputTextStyle.short,
                    min_length=1,
                    max_length=200
                ),
                title="Custom Invite Decline Reason")
            self.invite_view = invite_view

        async def callback(self, inter: discord.Interaction):
            reason = self.children[0].value
            await inter.response.defer()
            owner_mem = d_obj.guild.get_member(self.invite_view.owner.id)
            await disp.INVITE_DECLINE_INFO_REASON.send(owner_mem, self.invite_view.player.mention, reason)
            await disp.INVITE_DECLINE_REASON.send(inter, reason)

    async def on_timeout(self) -> None:
        # Show player invite as expired
        self.disable_all_items()
        await disp.DM_INVITE_EXPIRED.edit(self.message, self.owner.mention, view=False)

        # Show owner invite expired
        owner_mem = d_obj.guild.get_member(self.owner.id)
        await disp.DM_INVITE_EXPIRED_INFO.send(owner_mem, self.player.mention)

        # Decline Invite
        self.lobby.decline_invite(self.owner, self.player)


class RegisterPingsView(FSBotView):
    def __init__(self):
        super().__init__()

    @staticmethod
    async def send_prefs(inter, p):
        pref_str = ''
        if p.lobby_ping_pref == 0:
            await disp.PREF_PINGS_NEVER.edit(inter)
            return
        if p.lobby_ping_pref == 1:
            pref_str = 'Only if Online'
        if p.lobby_ping_pref == 2:
            pref_str = 'Always'
        await disp.PREF_PINGS_UPDATE.edit(inter, pref_str, p.lobby_ping_freq)

    @discord.ui.button(label="Never Ping", style=discord.ButtonStyle.red)
    async def pings_never_button(self, button: discord.ui.Button, inter: discord.Interaction):
        p = Player.get(inter.user.id)
        p.lobby_ping_pref = 0
        await p.db_update('lobby_ping_pref')
        await self.send_prefs(inter, p)

    @discord.ui.button(label="Ping if Online", style=discord.ButtonStyle.green)
    async def pings_online_button(self, button: discord.ui.Button, inter: discord.Interaction):
        p = Player.get(inter.user.id)
        p.lobby_ping_pref = 1
        await p.db_update('lobby_ping_pref')
        await self.send_prefs(inter, p)

    @discord.ui.button(label="Always Ping", style=discord.ButtonStyle.blurple)
    async def pings_always_button(self, button: discord.ui.Button, inter: discord.Interaction):
        p = Player.get(inter.user.id)
        p.lobby_ping_pref = 2
        await p.db_update('lobby_ping_pref')
        await self.send_prefs(inter, p)

    options = [
        discord.SelectOption(label="Always", value='0', description="Always get pinged when the lobby is joined"),
        discord.SelectOption(label="5 Minutes", value='5'),
        discord.SelectOption(label="10 Minutes", value='10'),
        discord.SelectOption(label="15 Minutes", value='15'),
        discord.SelectOption(label="30 Minutes", value='30'),
        discord.SelectOption(label="1 Hour", value='60'),
        discord.SelectOption(label="2 Hours", value='120'),
        discord.SelectOption(label="4 Hours", value='240')

    ]

    @discord.ui.select(placeholder="Input minimum ping frequency...", min_values=1, max_values=1, options=options)
    async def ping_freq_select(self, select: discord.ui.Select, inter: discord.Interaction):
        p = Player.get(inter.user.id)
        p.lobby_ping_freq = int(select.values[0])
        await p.db_update('lobby_ping_freq')
        await self.send_prefs(inter, p)


class RemoveTimeoutView(FSBotView):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Free Me!", custom_id="free_me", style=discord.ButtonStyle.green)
    async def free_me_button(self, button: discord.ui.Button, inter: discord.Interaction):
        await inter.response.defer()

        if not (p := d_obj.is_player(inter.user)):
            raise tools.UnexpectedError("Non player clicked 'free me' button")

        if p.is_timeout:
            return await disp.TIMEOUT_STILL.send_priv(inter, tools.format_time_from_stamp(p.timeout_until, "R"))

        await d_obj.timeout_player(p=p, stamp=0)


class ConfirmView(FSBotView):
    def __init__(self, timeout=60, response="Action", coroutine=None):
        super().__init__(timeout=timeout)
        self.response = response
        self.coroutine = coroutine
        self.confirmed = asyncio.Future()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, button: discord.ui.Button, inter: discord.Interaction):
        self.confirmed.set_result(True)
        self.stop()
        self.disable_all_items()
        self.cancel_button.style = discord.ButtonStyle.grey
        await disp.CONFIRMED.send_priv(inter, self.response)
        try:
            self.message.edit(view=self)
        except discord.NotFound:
            pass
        if self.coroutine:
            await self.coroutine

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, button: discord.ui.Button, inter: discord.Interaction):
        self.confirmed.set_result(False)
        self.stop()
        self.disable_all_items()
        self.confirm_button.style = discord.ButtonStyle.grey
        await disp.CANCELLED.send_priv(inter, self.response)
        try:
            self.message.edit(view=self)
        except discord.NotFound:
            pass

    async def on_timeout(self) -> None:
        self.confirmed.set_result(False)
        self.stop()
        self.disable_all_items()
        self.confirm_button.style = discord.ButtonStyle.grey
        try:
            self.message.delete(delay=10)
        except discord.NotFound:
            pass





"""
Cog built to handle interaction with the duel lobby.

"""
# External Imports
import discord
from discord.ext import commands, tasks
from datetime import datetime as dt, timedelta
from logging import getLogger

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from modules.spam_detector import is_spam
from classes.players import Player
from classes.match import BaseMatch
from display import AllStrings as disp, embeds, views
import modules.lobby as lobby

import modules.tools as tools

log = getLogger('fs_bot')


class ChallengeDropdown(discord.ui.Select):
    def __init__(self):
        options = []
        for player in lobby.lobbied():
            option = discord.SelectOption(label=player.name, value=str(player.id))
            options.append(option)

        super().__init__(placeholder="Pick Player(s) in the lobby to challenge...",
                         custom_id='dashboard-challenge',
                         options=options,
                         min_values=1,
                         max_values=len(options),
                         )

    async def callback(self, inter: discord.Interaction):
        owner: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, owner):
            return
        invited_players: list[Player] = [Player.get(int(value)) for value in self.values]
        if owner in invited_players:
            await disp.LOBBY_INVITED_SELF.send_temp(inter, owner.mention)
            return
        already_invited = lobby.already_invited(owner, invited_players)
        if already_invited:
            await disp.LOBBY_INVITED_ALREADY.send_priv(inter, ' '.join([p.mention for p in already_invited]))
            [invited_players.remove(p) for p in already_invited]
            inter = inter.followup
        no_dms = list()
        match = None
        for invited in invited_players:
            for _ in range(3):
                try:
                    memb = d_obj.guild.get_member(invited.id)
                    view = views.InviteView(owner, invited)
                    msg = await disp.DM_INVITED.send(memb, invited.mention, owner.mention, view=view)
                    view.msg = msg
                    match = lobby.invite(owner, invited)
                    break
                except discord.Forbidden:
                    if invited not in no_dms:
                        no_dms.append(invited)
        if no_dms:
            await disp.LOBBY_NO_DM.send_temp(inter.channel, ','.join([p.mention for p in no_dms]))
            lobby.lobby_log(
                f'{",".join([p.name for p in no_dms])} could not be invited, as they are not accepting DM\'s')
        remaining = [p for p in invited_players if p not in no_dms]
        remaining_mentions = ",".join([p.mention for p in remaining])
        if remaining and match:
            await disp.LOBBY_INVITED_MATCH.send_temp(inter, owner.mention, remaining_mentions, match.id,
                                                     allowed_mentions=discord.AllowedMentions(users=[inter.user]))
            lobby.lobby_log(f'{owner.name} invited {",".join([p.name for p in remaining])} to Match: {match.id}')
        elif remaining and not match:
            await disp.LOBBY_INVITED.send_temp(inter, owner.mention, remaining_mentions,
                                               allowed_mentions=discord.AllowedMentions(users=[inter.user]))
            lobby.lobby_log(f'{owner.name} invited {",".join([p.name for p in remaining])} to a match')
        else:
            await disp.LOBBY_NO_DM_ALL.send_priv(inter, owner.mention)
        await _cog.update_dashboard()


class DashboardView(views.FSBotView):
    def __init__(self):
        super().__init__(timeout=None)
        if lobby.lobbied():
            self.add_item(ChallengeDropdown())
        if not lobby.lobbied():
            self.leave_lobby_button.disabled = True
            self.reset_lobby_button.disabled = True

    @discord.ui.button(label="Join Lobby", custom_id='dashboard-join', style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, player):
            return
        elif player.match:
            await disp.LOBBY_ALREADY_MATCH.send_priv(inter, player.mention, player.match.text_channel.mention)
        elif lobby.lobby_join(player):
            await _cog.update_dashboard()
            await disp.LOBBY_JOIN.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_ALREADY_IN.send_priv(inter, player.mention)

    @discord.ui.button(label="Reset Timeout", custom_id='dashboard-reset', style=discord.ButtonStyle.blurple)
    async def reset_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, player):
            return
        elif player in lobby.lobbied():
            lobby.lobby_timeout_reset(player)
            await disp.LOBBY_TIMEOUT_RESET.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)

    @discord.ui.button(label="Extended History", custom_id='dashboard-history', style=discord.ButtonStyle.blurple)
    async def history_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        if len(lobby.logs) <= len(lobby.logs_recent()):
            await disp.LOBBY_NO_HISTORY.send_temp(inter, inter.user.mention)
            return
        await disp.LOBBY_LONGER_HISTORY.send(inter, inter.user.mention, logs=lobby.logs_longer(), delete_after=20)

    @discord.ui.button(label="Leave Lobby", custom_id='dashboard-leave', style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not await d_obj.is_registered(inter, player):
            return
        elif lobby.lobby_leave(player):
            await _cog.update_dashboard()
            await disp.LOBBY_LEAVE.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)


class DuelLobbyCog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                         default_permission=True)):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel: discord.TextChannel = d_obj.channels['dashboard']
        # Dynamics
        self.dashboard_msg: discord.Message | None = None
        self.dashboard_embed = None

        self.dashboard_loop.start()

    def cog_check(self, ctx):
        player = Player.get(ctx.user.id)
        return True if player else False

    def dashboard_purge_check(self, message: discord.Message):
        """Checks if messages are either the dashboard message, or an admin message before purging them"""
        if message != self.dashboard_msg and not d_obj.is_admin(message.author):
            return True
        else:
            return False

    async def create_dashboard(self):
        """Purges the channel, and then creates dashboard Embed w/ view"""
        await self.dashboard_channel.purge(check=self.dashboard_purge_check)
        self.dashboard_embed = embeds.duel_dashboard(lobby.lobbied(),lobby.logs_recent())
        self.dashboard_msg = await self.dashboard_channel.send(content="",
                                                               embed=self.dashboard_embed,
                                                               view=DashboardView())

    async def update_dashboard(self):
        """Checks if dashboard exists and either creates one, or updates the current dashboard and purges messages
        older than 5 minutes """
        if not self.dashboard_msg:
            await self.create_dashboard()
            return

        await d_obj.channels['dashboard'].purge(before=(dt.now() - timedelta(minutes=5)),
                                                check=self.dashboard_purge_check)

        #  Post new embed only if embed has changed
        new_embed = embeds.duel_dashboard(lobby.lobbied(), lobby.logs_recent())
        if not tools.compare_embeds(new_embed, self.dashboard_embed):
            self.dashboard_embed = new_embed
            await self.dashboard_msg.edit(embed=new_embed,
                                          view=DashboardView())

    @tasks.loop(seconds=10)
    async def dashboard_loop(self):
        """Loop to check lobby timeouts, also updates dashboard in-case preference changes are made"""
        for p in lobby.lobbied():
            stamp_dt = dt.fromtimestamp(p.lobbied_timestamp)
            if stamp_dt < (dt.now() - timedelta(minutes=lobby.timeout_minutes)):
                lobby.lobby_timeout(p)
                await disp.LOBBY_TIMEOUT.send(self.dashboard_channel, p.mention, delete_after=30)
            elif stamp_dt < (
                    dt.now() - timedelta(minutes=lobby.timeout_minutes - 5)) and p not in lobby.warned_players:
                lobby.warned_players.append(p)
                lobby.lobby_log(f'{p.name} will soon be timed out of the lobby')
                await disp.LOBBY_TIMEOUT_SOON.send(self.dashboard_channel, p.mention, delete_after=30)

        await self.update_dashboard()


_cog: DuelLobbyCog = None


def setup(client: discord.Bot):
    client.add_cog(DuelLobbyCog(client))
    global _cog
    _cog = client.cogs.get('DuelLobbyCog')

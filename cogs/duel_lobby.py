"""
Cog built to handle interaction with the duel lobby.

"""
# External Imports
import discord
from discord.ext import commands, tasks
from datetime import datetime as dt, timedelta
from logging import getLogger
import asyncio

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from modules.spam_detector import is_spam
from classes.players import Player, SkillLevel
from classes.match import BaseMatch
from display import AllStrings as disp
import display.embeds as embeds

import Lib.tools as tools

log = getLogger('fs_bot')

_bot: discord.Bot = None

_lobbied_players: list[Player] = []


class ChallengeDropdown(discord.ui.Select):
    def __init__(self):
        options = []
        for player in _lobbied_players:
            option = discord.SelectOption(label=player.name, value=str(player.id))
            options.append(option)
        if _lobbied_players:
            disabled = False
        else:
            disabled = True

        super().__init__(placeholder="Pick Player(s) in the lobby to challenge...",
                         custom_id='dashboard-challenge',
                         options=options,
                         disabled=disabled,
                         min_values=1,
                         max_values=len(options),
                         )

    async def callback(self, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, player):
            return
        invited_players: list(Player) = [Player.get(int(value)) for value in self.values]
        if player in invited_players:
            await disp.LOBBY_INVITED_SELF.send_temp(inter, player.mention)
            return
        if player and not player.match:
            if player in _lobbied_players:
                _cog.lobby_leave(player)
            match = await BaseMatch.create(player, invited_players)
            await _cog.update_dashboard()
            await disp.MATCH_CREATE.send_temp(inter, match.id, ' '.join([p.mention for p in invited_players]))


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        if _lobbied_players:
            self.add_item(ChallengeDropdown())

    @discord.ui.button(label="Join Lobby", custom_id='dashboard-join', style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, player):
            return
        elif _cog.lobby_join(player):
            await _cog.update_dashboard()
            await disp.LOBBY_JOIN.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_ALREADY_IN.send_temp(inter, player.mention)

    @discord.ui.button(label="Reset Timeout", custom_id='dashboard-reset', style=discord.ButtonStyle.blurple)
    async def reset_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, player):
            return
        elif player in _lobbied_players:
            player.reset_lobby_timestamp()
            await disp.LOBBY_TIMEOUT_RESET.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)

    @discord.ui.button(label="Leave Lobby", custom_id='dashboard-leave', style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if await is_spam(inter, inter.user) or not await d_obj.is_registered(inter, player):
            return
        elif _cog.lobby_leave(player):
            await _cog.update_dashboard()
            await disp.LOBBY_LEAVE.send_temp(inter, player.mention)
        else:
            await disp.LOBBY_NOT_IN.send_temp(inter, player.mention)


class DuelLobbyCog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                         default_permission=True)):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel = d_obj.channels['dashboard']
        # Dynamics
        self.dashboard_msg = None
        self.matches: list[BaseMatch] = []
        self.lobby_logs: list[(int, str)] = []
        self._warned_players: list[Player] = []
        self.timeout_minutes = 30
        self.dashboard_loop.start()

    def cog_check(self, ctx):
        player = Player.get(ctx.user.id)
        return True if player else False

    @property
    def logs_recent(self):
        return self.lobby_logs[-5:]

    def log(self, message):
        self.lobby_logs.append((tools.timestamp_now(), message))

    def lobby_timeout(self, player):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in _lobbied_players:
            player.on_lobby_leave()
            _lobbied_players.remove(player)
            self._warned_players.remove(player)
            self.log(f'{player.name} was removed from the lobby by timeout.')
            return True
        else:
            return False

    def lobby_leave(self, player):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in _lobbied_players:
            player.on_lobby_leave()
            _lobbied_players.remove(player)
            self.log(f'{player.name} left the lobby.')
            return True
        else:
            return False

    def lobby_join(self, player):
        """Adds to lobby list, executes player lobby join method, returns True if added"""
        if player not in _lobbied_players:
            player.on_lobby_add()
            _lobbied_players.append(player)
            self.log(f'{player.name} joined the lobby.')
            return True
        else:
            return False

    def dashboard_purge_check(self, message: discord.Message):
        if message != self.dashboard_msg and d_obj.is_not_admin(message.author):
            return True
        else:
            return False

    async def create_dashboard(self):
        await self.dashboard_channel.purge(check=self.dashboard_purge_check)
        self.dashboard_msg = await self.dashboard_channel.send(content="",
                                                               embed=embeds.duel_dashboard(_lobbied_players,
                                                                                           self.logs_recent),
                                                               view=DashboardView())

    async def update_dashboard(self):
        if not self.dashboard_msg:
            await self.create_dashboard()
            return
        await d_obj.channels['dashboard'].purge(before=(dt.now() - timedelta(minutes=5)),
                                                check=self.dashboard_purge_check)
        await self.dashboard_msg.edit(embed=embeds.duel_dashboard(_lobbied_players, self.logs_recent),
                                      view=DashboardView())

    async def create_match(self, creator, players: list[Player]):
        match = BaseMatch.create(creator, players)
        await asyncio.sleep(2)
        self.matches.append(match)
        self.log(f'Match: {match.id} created by {match.owner.name}')
        return match

    @tasks.loop(seconds=5)
    async def dashboard_loop(self):
        for p in _lobbied_players:
            stamp_dt = dt.fromtimestamp(p.lobbied_timestamp)
            if stamp_dt < (dt.now() - timedelta(minutes=self.timeout_minutes)):
                self.lobby_timeout(p)
                await disp.LOBBY_TIMEOUT.send(self.dashboard_channel, p.mention, delete_after=30)
            elif stamp_dt < (dt.now() - timedelta(minutes=self.timeout_minutes - 5)) and p not in self._warned_players:
                self._warned_players.append(p)
                await disp.LOBBY_TIMEOUT_SOON.send(self.dashboard_channel, p.mention, delete_after=10)

        await self.update_dashboard()


_cog: DuelLobbyCog = None


def setup(client: discord.Bot):
    client.add_cog(DuelLobbyCog(client))
    global _bot
    _bot = client
    global _cog
    _cog = client.cogs.get('DuelLobbyCog')

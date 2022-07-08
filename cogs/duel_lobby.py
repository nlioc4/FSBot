"""
Cog built to handle interaction with the duel lobby.

"""
# External Imports
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from classes.players import Player, SkillLevel
from classes.match import BaseMatch
from display import AllStrings as disp, ContextWrapper, InteractionContext, FollowupContext
import display.embeds as embeds

import Lib.tools as tools

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


        super().__init__(placeholder="Pick a Player in the lobby to challenge...",
                     custom_id='dashboard-challenge',
                     options=options,
                     disabled=disabled,
                     min_values=1,
                     max_values=len(options),
                     )

    async def callback(self, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not d_obj.is_registered(inter, player):
            return
        invited_players: Player = Player.get([int(value) for value in self.values])
        if player in invited_players:
            disp.LOBBY_INVITED_SELF.send(inter, player.mention)
            return
        if player and not player.match:
            if player in _lobbied_players:
                _cog.leave_lobby(player)
            invited_mentions_string = ' '.join([player.mention for player in invited_players])
            match = await _cog.create_match(player, challenged_players)
            await _cog.update_dashboard()
            await disp.MATCH_CREATE.send(match.text_channel, match.id, invited_mentions_string)
            await disp.LOBBY_INVITED.send(d_obj.channels['dashboard'], invited_mentions_string, player.mention)


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        if _lobbied_players:
            self.add_item(ChallengeDropdown())

    @discord.ui.button(label="Join Lobby", custom_id='dashboard-join', style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not d_obj.is_registered(inter, player):
            return
        if _cog.join_lobby(player):
            await _cog.update_dashboard()
            await disp.LOBBY_JOIN.send(inter, player.mention, delete_after=5)
        else:
            await inter.response.send_message(content=disp.LOBBY_ALREADY_IN(player.mention), ephemeral=True, delete_after=5)

    @discord.ui.button(label="Leave Lobby", custom_id='dashboard-leave', style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, inter: discord.Interaction):
        player: Player = Player.get(inter.user.id)
        if not d_obj.is_registered(inter, player):
            return
        if _cog.leave_lobby(player):
            await _cog.update_dashboard()
            await inter.response.send_message(content=disp.LOBBY_LEAVE(player.mention), ephemeral=True, delete_after=5)
        else:
            await inter.response.send_message(content=disp.LOBBY_NOT_IN(player.mention), ephemeral=True, delete_after=5)


class DuelLobbyCog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                         default_permission=True)):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel = d_obj.channels['dashboard']
        self.dashboard_channel_ctx = ContextWrapper(None, self.dashboard_channel.id, None, self.dashboard_channel)
        # Dynamics
        self.dashboard_msg = None
        self.matches: list[BaseMatch] = []
        self.lobby_logs: list[(int, str)] = []
        self.dashboard_loop.start()

    def cog_check(self, ctx):
        player = Player.get(ctx.user.id)
        return True if player else False

    @property
    def logs_last_five(self):
        return self.lobby_logs[-5:]

    def log(self, message):
        self.lobby_logs.append((tools.timestamp_now(), message))

    def leave_lobby(self, player):
        """Removes from lobby list, executes player lobby leave method, returns True if removed"""
        if player in _lobbied_players:
            player.on_lobby_leave()
            _lobbied_players.remove(player)
            self.log(f'{player.name} left the lobby.')
            return True
        else:
            return False

    def join_lobby(self, player):
        """Adds to lobby list, executes player lobby join method, returns True if added"""
        if player not in _lobbied_players:
            player.on_lobby_add()
            _lobbied_players.append(player)
            self.log(f'{player.name} joined the lobby.')
            return True
        else:
            return False

    def is_not_dashboard(self, message: discord.Message):
        if message != self.dashboard_msg:
            return True
        else:
            return False

    async def create_dashboard(self):
        await self.dashboard_channel.purge()
        self.dashboard_msg = await self.dashboard_channel.send(content="",
                                                               embed=embeds.duel_dashboard(_lobbied_players, self.logs_last_five),
                                                               view=DashboardView())

    async def update_dashboard(self):
        if not self.dashboard_msg:
            await self.create_dashboard()
            return
        await d_obj.channels['dashboard'].purge(before=(datetime.now() - timedelta(minutes=5)), check=self.is_not_dashboard)
        await self.dashboard_msg.edit(embed=embeds.duel_dashboard(_lobbied_players, self.logs_last_five), view=DashboardView())


    async def create_match(self, creator, players: list[Player]):
        match = BaseMatch(creator, players)
        self.matches.append(match)
        self.log(f'Match: {match.id} created by {match.owner.name}')
        return match

    @tasks.loop(seconds=60)
    async def dashboard_loop(self):
        await self.update_dashboard()


_cog: DuelLobbyCog = None

def setup(client: discord.Bot):
    client.add_cog(DuelLobbyCog(client))
    global _bot
    _bot = client
    global _cog
    _cog = client.cogs.get('DuelLobbyCog')

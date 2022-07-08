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
        options = [discord.SelectOption(label='TestOption')]
        for player in _lobbied_players:
            option = discord.SelectOption(label=player.mention, value=str(player.id))
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

    async def callback(self, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(i_ctx.author.id)
        invited_players: Player = Player.get([int(value) for value in self.values])
        if player and not player.match:
            invited_mentions_string = ' '.join([player.mention for player in invited_players])
            match = await DuelLobbyCog.create_match(player, challenged_players)
            await disp.MATCH_CREATE.send(match.text_channel, match.id, invited_mentions_string)
            await disp.LOBBY_INVITED.send(d_obj.channels['dashboard'], invited_mentions_string, player.mention)


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChallengeDropdown())

    @discord.ui.button(label="Join Lobby", custom_id='dashboard-join', style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(interaction.user.id) # TODO fix
        player.on_lobby_add()
        _lobbied_players.append(player)
        await _bot.cogs.get('DuelLobbyCog').update_dashboard()
        await disp.LOBBY_JOIN.send(i_ctx, player.mention)

    @discord.ui.button(label="Leave Lobby", custom_id='dashboard-leave', style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(i_ctx.author.id)
        player.on_lobby_leave()
        _lobbied_players.remove(player)
        await _bot.cogs.get('DuelLobbyCog').update_dashboard()
        await disp.LOBBY_LEAVE.send(i_ctx, player.mention)


class DuelLobbyCog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                         default_permission=True)):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel = d_obj.channels['dashboard']
        self.dashboard_channel_ctx = ContextWrapper(None, self.dashboard_channel.id, None, self.dashboard_channel)
        # Dynamics
        self.lobbied_players = _lobbied_players
        self.dashboard_msg = None
        self.dashboard_loop.start()

    def is_not_dashboard(self, message: discord.Message):
        if message != self.dashboard_msg:
            return True
        else:
            return False

    async def create_dashboard(self):
        await self.dashboard_channel.purge()
        self.dashboard_msg = await self.dashboard_channel.send(content="",
                                                               embed=embeds.duel_dashboard(None, self.lobbied_players),
                                                               view=DashboardView())


    async def update_dashboard(self):
        if not self.dashboard_msg:
            await self.create_dashboard()
            return
        await d_obj.channels['dashboard'].purge(before=(datetime.now() - timedelta(minutes=5)), check=self.is_not_dashboard)
        await self.dashboard_msg.edit(embed=embeds.duel_dashboard(None, self.lobbied_players), view=DashboardView())


    async def create_match(self, creator, players: list[Player]):
        match = BaseMatch(creator, players)
        return match

    @tasks.loop(seconds=60)
    async def dashboard_loop(self):
        await self.update_dashboard()


def setup(client: discord.Bot):
    global _bot
    _bot = client
    client.add_cog(DuelLobbyCog(client))

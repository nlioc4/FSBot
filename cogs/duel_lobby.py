"""
Cog built to handle interaction with the duel lobby.

"""
# External Imports
import discord
from discord.ext import commands, tasks

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from classes.players import Player, SkillLevel
from display import AllStrings as disp, ContextWrapper, InteractionContext, FollowupContext
import Lib.tools as tools


_lobbied_players = list[Player]


class ChallengeDropdown(discord.ui.Select):
    options = []
    for player in _lobbied_players:
        discord.SelectOption(label=player.mention, value=player.id)

    if _lobbied_players:
        disabled = False
    else:
        disabled = True

    super().__init__(placeholder="Pick a Player in the lobby to challenge...",
                     custom_id='dashboard-challenge',
                     options=options,
                     disabled=disabled,
                     min_values=1,
                     max_values=25,
                     )

    async def callback(self, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(i_ctx.author.id)
        challenged_players: Player = Player.get(self.values)

        await DuelLobbyCog.create_match(player, challenged_players)
        await disp.send(i_ctx, )


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Lobby", custom_id='dashboard-join', style=discord.ButtonStyle.green)
    async def join_lobby_button(self, button: discord.Button, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(i_ctx.author.id)
        player.on_lobby_add()
        DuelLobbyCog.lobbied_players.append(player)
        #  add update dashboard call

    @discord.ui.button(label="Leave Lobby", custom_id='dashboard-leave', style=discord.ButtonStyle.red)
    async def leave_lobby_button(self, button: discord.Button, interaction: discord.Interaction):
        i_ctx = InteractionContext(interaction)
        player: Player = Player.get(i_ctx.author.id)
        player.on_lobby_leave()
        DuelLobbyCog.lobbied_players.remove(player)
        # add update dashboard call







class DuelLobbyCog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                         default_permission=True)):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel = d_obj.channels['dashboard']
        self.dashboard_channel_ctx = ContextWrapper(None, self.dashboard_channel.id, None, self.dashboard_channel)
        # Dynamics
        self.lobbied_players: _lobbied_players
        self.dashboard_msg = None

        self.dashboard_channel.purge(bulk=True)


    async def create_dashboard(self):
        await self.dashboard_channel_ctx.send(view=DashboardView())

    async def update_dashboard(self):
        if not self.dashboard_msg:
            await self.create_dashboard()
        dboard_ctx = ContextWrapper(self.dashboard_msg)


    async def create_match(self, creator, players: list[Player]):
        init_player =

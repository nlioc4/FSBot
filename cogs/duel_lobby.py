"""
Cog built to handle interaction with the duel lobby.

"""
# External Imports
import asyncio
import discord
from discord import Status
from discord.ext import commands, tasks
from logging import getLogger

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
from classes.lobby import Lobby
from classes.match import RankedMatch
from classes.players import Player
from display import AllStrings as disp
from modules import tools

log = getLogger('fs_bot')


class DuelLobbyCog(commands.Cog, name="DuelLobbyCog"):
    def __init__(self, bot):
        #  Statics
        self.bot = bot
        self.dashboard_channel: discord.TextChannel = d_obj.channels['dashboard']
        # Dynamics
        self.dashboard_msg: discord.Message | None = None
        self.dashboard_embed = None

        self.guild_ids = [cfg.general["guild_id"]]

        asyncio.create_task(self.lobby_startup())

    def cog_check(self, ctx):
        player = Player.get(ctx.user.id)
        return True if player else False

    async def lobby_startup(self):
        """Startup Task that creates lobby objects.  Waits until bot is ready to proceed"""
        await d_obj.loaded.wait()
        if Lobby.all_lobbies.get("casual"):
            return
        casual_lobby = await Lobby.create_lobby("casual", d_obj.channels['dashboard'], timeout_minutes=30)

        ranked_lobby = await Lobby.create_lobby("ranked", d_obj.guild.get_channel(1061989011092144138),
                                                timeout_minutes=30, match_type=RankedMatch)

    # @commands.Cog.listener('on_presence_update')
    # async def lobby_timeout_updater(self, before, after):
    #     # This is redundant with the lobby loop
    #     #  Return if not player
    #     p = Player.get(p_id=after.id)
    #     if not p:
    #         return
    #     #  Return if status hasn't changed, or p not in lobby
    #     if before.status == after.status or not p.lobby:
    #         return
    #     p.lobby.lobby_timeout_reset(p)

    @commands.user_command(name="Invite To Match")
    async def user_match_invite(self, ctx: discord.ApplicationContext, user: discord.Member):
        # if invited self, cancel
        if ctx.user == user:
            await disp.LOBBY_INVITED_SELF.send_priv(ctx, ctx.user.mention)
            return
        invited = Player.get(user.id)
        owner = Player.get(ctx.user.id)

        # if the selected user or the owner is not a Player
        if not invited or not owner:
            return await disp.NOT_PLAYER_2.send_priv(ctx, "This user")

        # lobby is the owners lobby -> current channel lobby -> invited players lobby, in that order
        lobby = owner.lobby or Lobby.channel_to_lobby(ctx.channel) or invited.lobby

        # return if no lobby found in any case above
        if not lobby:
            await disp.LOBBY_CANT_INVITE.send_priv(ctx)
            return

        # return if the invited players lobby is not the found lobby
        if invited.lobby is not lobby:
            await disp.LOBBY_NOT_IN_2.send_priv(ctx, invited.mention)
            return

        # return if trying to invite to a match the player doesn't own
        if owner.match and owner.match.owner != owner:
            await disp.LOBBY_NOT_OWNER.send_priv(ctx)
            return

        # If all guards passed, send invite
        sent = await lobby.send_invite(owner, invited)
        if sent and owner.match:  # if sent, and invited to an existing match
            await disp.LOBBY_INVITED_MATCH.send_priv(ctx, owner.mention, invited.mention, owner.match.id_str)
            lobby.lobby_log(lobby.lobby_log(f'{owner.name} invited {invited.name} to Match: {owner.match.id_str}'))
            await lobby.update_dashboard()
        elif sent:  # if sent, and invited to a new match
            await disp.LOBBY_INVITED.send_priv(ctx, owner.mention, invited.mention)
            lobby.lobby_log(lobby.lobby_log(f'{owner.name} invited {invited.name} to a match.'))
            await lobby.update_dashboard()
        else:  # if couldn't send an invite to the player
            await disp.LOBBY_NO_DM.send_priv(ctx, invited.mention)


def setup(client: discord.Bot):
    client.add_cog(DuelLobbyCog(client))

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
import display as disp


class Cog(commands.Cog, name="DuelLobbyCog", command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                default_permission=True)):
    def __init__(self, bot):
        self.bot = bot
        self.dashboard_msg = None
        self.dashboard_channel = d_obj.channels['dashboard']

"""Cog designed to handle events for Matches, passing them on, holds views for matches, and matches themselves are tied to here"""

# External Imports
import discord
from discord.ext import commands

# Internal Imports
import display
import modules.config as cfg
from classes.players import Player
from classes.match import BaseMatch
from .display import AllStrings as disp



class MatchesCog(commands.Cog, name="MatchesCog",
                 command_attrs=dict(guild_ids=cfg.general['guild_id'], default_permission=True)):

    def __init__(self, bot):
        self.bot = bot




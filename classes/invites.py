"""This class is used to represent individual invites between players to a match
It inherits from FSBotView so that the invite class itself can be used as the view attached to the message."""


# External Imports
import discord


# Internal Imports
from display.views import FSBotView
from modules import discord_obj as d_obj, tools
from . import Player
from .match import BaseMatch, RankedMatch
from .lobby import Lobby
# TODO will need to adjust to avoid circular imports


class MatchInvite(FSBotView):
    """Class to represent an invitation to a match"""
    _all_invites = dict()  

    def __init__(self,
                 invited: Player,
                 inviting: Player,
                 match: BaseMatch | RankedMatch | None = None,
                 timeout: int = 300):

        self.invited = invited
        self.inviting = inviting
        self.match = match

        self.__invite_message: discord.Message | None = None

        super().__init__(timeout=timeout)

        # MatchInvite._all_invites[#TODO FIND AN ID] = self

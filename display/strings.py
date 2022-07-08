"""All Strings available to bot, helps with code simplification"""

# External Imports
import discord
from enum import Enum

# Internal Imports
import modules.config as cfg


class AllStrings(Enum):

    NOT_REGISTERED = "You are not registered {}, please go to {} first!"
    NOT_PLAYER = "You are not a player {}, please go to {} first!"


    LOBBY_INVITED = "{} you have been invited to a match by {}! Accept or decline below!"
    LOBBY_INVITED_SELF = "{} you can't invite yourself to a match!"
    LOBBY_JOIN = "{} you have joined the lobby!"
    LOBBY_LEAVE = "{} you have left the lobby!"
    LOBBY_NOT_IN = "{} you are not in this lobby!"
    LOBBY_ALREADY_IN = "{} you are already in this lobby!"


    MATCH_CREATE = "Match created: ID: {}, Invited {}"
    MATCH_END = "Match ID: {} Ended, closing match channels..."


    def __init__(self, string, embed=None):
        self.__string = string
        self.__embed = embed


    def __call__(self, *args):
        return self.__string.format(*args)


    async def send(self, ctx, *args, **kwargs):
        string = self.__string.format(*args) if self.__string else None
        embed = kwargs.get('embed') if kwargs.get('embed') else self.__embed
        view = kwargs.get('view') if kwargs.get('view') else None
        delete_after = kwargs.get('delete_after') if kwargs.get('delete_after') else None
        ephemeral = kwargs.get('ephemeral') if kwargs.get('ephemeral') else False

        match type(ctx):
            case discord.abc.Messageable:
                await ctx.send(content=string, embed=embed, view=view, delete_after=delete_after)

            case discord.InteractionResponse:
                await ctx.send_message(content=string, embed=embed, view=view, ephemeral=ephemeral)

            case discord.Interaction:
                await ctx.response.send_message(content=string, embed=embed, view=view, ephemeral=ephemeral)





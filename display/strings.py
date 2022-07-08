"""All Strings available to bot, helps with code simplification"""

# External Imports
import discord
from enum import Enum

# Internal Imports
from .classes import ContextWrapper, FollowupContext, InteractionContext, Message
from .embeds import *
import modules.config as cfg


class AllStrings(Enum):

    LOBBY_NOT_PLAYER = Message("You are not registered {}, please go to {} first!")
    LOBBY_INVITED = Message("{} you have been invited to a match by {}! Accept or decline below!")
    LOBBY_JOIN = Message("{} you have joined the lobby!")
    LOBBY_LEAVE = Message("{} you have left the lobby!")


    MATCH_CREATE = Message("Match created: ID: {}, Invited {}")
    MATCH_END = Message("Match ID: {} Ended, closing match channels...")


    async def send(self, ctx, *args, **kwargs):
        """
        Send the message

        :param ctx: context.
        :param args: Additional strings to format the main string with.
        :param kwargs: Keywords arguments to pass to the embed function.
        :return: The message sent.
        """
        if not isinstance(ctx, ContextWrapper):
            ctx = ContextWrapper.wrap(ctx)
        kwargs = self.value.get_elements(ctx, string_args=args, ui_kwargs=kwargs)
        return await ctx.send(**kwargs)

    async def edit(self, msg, *args, **kwargs):
        """
        Edit the message

        :param msg: Message to edit.
        :param args: Additional strings to format the main string with.
        :param kwargs: Keywords arguments to pass to the embed function.
        :return: The message edited.
        """
        if not isinstance(msg, ContextWrapper):
            msg = ContextWrapper.wrap(msg)
        kwargs = self.value.get_elements(msg, string_args=args, ui_kwargs=kwargs)
        return await msg.edit(**kwargs)


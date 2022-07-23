"""All Strings available to bot, helps with code simplification"""

# External Imports
import discord
from enum import Enum
import inspect

# Internal Imports
import modules.config as cfg
from .embeds import *


class AllStrings(Enum):
    NOT_REGISTERED = "You are not registered {}, please go to {} first!"
    NOT_PLAYER = "You are not a player {}, please go to {} first!"
    STOP_SPAM = "{}: Please stop spamming!"

    DM_INVITED = "{} you have been invited to a match by {}! Accept or decline below!"
    DM_INVITE_INVALID = "This invite is invalid!"

    REG_SUCCESSFUL_CHARS = "Successfully registered with characters: {}, {}, {}"
    REG_SUCCESFUL_NO_CHARS = 'Successfully registered with no Jaeger Account'
    REG_ALREADY_CHARS = "Already registered with characters: {}, {}, {}"
    REG_ALREADY_NO_CHARS = "Already Registered with no Jaeger Account"
    REG_MISSING_FACTION = "Registration Failed: Missing a character for faction {}"
    REG_CHAR_REGISTERED = "Registration Failed: Character: {} already registered by {}"
    REG_CHAR_NOT_FOUND = "Registration Failed: Character: {} not found in the Census API"
    REG_NOT_JAEGER = "Registration Failed: Character: {} is not from Jaeger!"
    REG_WRONG_FORMAT = "Incorrect Character Entry Format!"

    LOBBY_INVITED_SELF = "{} you can't invite yourself to a match!"
    LOBBY_INVITED = "{} invited {} to a match"
    LOBBY_INVITED_MATCH = "{} invited {} to match: {}"
    LOBBY_JOIN = "{} you have joined the lobby!"
    LOBBY_LEAVE = "{} you have left the lobby!"
    LOBBY_NOT_IN = "{} you are not in this lobby!"
    LOBBY_NO_DM = "{} could not be invited as they are refusing DM's from the bot!"
    LOBBY_NO_DM_ALL = "{} no players could be invited"
    LOBBY_ALREADY_IN = "{} you are already in this lobby!"
    LOBBY_TIMEOUT = "{} you have been removed from the lobby by timeout!"
    LOBBY_TIMEOUT_SOON = "{} you will soon be timed out from the lobby, click above to reset."
    LOBBY_TIMEOUT_RESET = "{} you have reset your lobby timeout."
    LOBBY_DASHBOARD = ''
    LOBBY_LONGER_HISTORY = '{}', longer_lobby_logs
    LOBBY_NO_HISTORY = '{} there is no extended activity to display!'

    INVITE_WRONG_USER = "This invite isnt for you!"

    MATCH_CREATE = "{} Match created ID: {}"
    MATCH_INFO = "", match_info
    MATCH_INVITED = "{} You've been invited to a match by {}, accept or decline below", None
    MATCH_ACCEPT = "You have accepted the invite."
    MATCH_DECLINE = "You have decline the invite."
    MATCH_JOIN = "{} You have joined the match"
    MATCH_LEAVE = "{} You have left the match."
    MATCH_END = "Match ID: {} Ended, closing match channels..."

    SKILL_LEVEL_REQ_ONE = "Your requested skill level has been set to: {}"
    SKILL_LEVEL_REQ_MORE = "Your requested skill levels have been set to: {}"
    SKILL_LEVEL = "Your skill level has been set to: {}"


    ACCOUNT_HAS_OWN = "{} you have registered with your own Jaeger account, you can't request a temporary account."

    def __init__(self, string, embed=None):
        self.__string = string
        self.__embed = embed

    def __call__(self, *args):
        return self.__string.format(*args)

    async def _do_send(self, action, ctx, *args, **kwargs):
        string = self.__string.format(*args) if self.__string else None
        embed = None
        view = kwargs.get('view') if kwargs.get('view') else None
        delete_after = kwargs.get('delete_after') if kwargs.get('delete_after') else None
        ephemeral = kwargs.get('ephemeral') if kwargs.get('ephemeral') else False
        allowed_mentions = kwargs.get('allowed_mentions') if kwargs.get('allowed_mentions') else discord.AllowedMentions.all()
        if self.__embed:
            #  Checks if embed, then retrieves only the embed specific kwargs
            embed_sig = inspect.signature(self.__embed)
            embed_kwargs = {arg: kwargs.get(arg) for arg in embed_sig.parameters}
            embed = self.__embed(**embed_kwargs)

        match type(ctx):
            case discord.User| discord.Member | discord.TextChannel | discord.VoiceChannel | discord.Thread:
                return await getattr(ctx, action)(content=string, embed=embed, view=view, delete_after=delete_after,
                                                  allowed_mentions=allowed_mentions)

            case discord.InteractionResponse:
                return await getattr(ctx, action + '_message')(content=string, embed=embed, view=view,
                                                               ephemeral=ephemeral, delete_after=delete_after,
                                                               allowed_mentions=allowed_mentions)

            case discord.Webhook if ctx.type == discord.WebhookType.application and action == "send":
                if view:
                    return await getattr(ctx, 'send')(content=string, embed=embed, view=view,
                                                      ephemeral=ephemeral, delete_after=delete_after,
                                                      allowed_mentions=allowed_mentions)
                else:
                    return await getattr(ctx, 'send')(content=string, embed=embed,
                                                      ephemeral=ephemeral, delete_after=delete_after,
                                                      allowed_mentions=allowed_mentions)

            case discord.Webhook if ctx.type == discord.WebhookType.application and action == "edit":  # Probably doesn't work
                return await getattr(ctx.fetch_message(), 'edit_message')(content=string, embed=embed, view=view,
                                                                          ephemeral=ephemeral,
                                                                          delete_after=delete_after)

            case discord.Interaction:
                return await getattr(ctx.response, action + '_message')(content=string, embed=embed, view=view,
                                                                        ephemeral=ephemeral, delete_after=delete_after,
                                                                        allowed_mentions=allowed_mentions)

    async def send(self, ctx, *args, **kwargs):
        return await self._do_send('send', ctx, *args, **kwargs)

    async def edit(self, ctx, *args, **kwargs):
        return await self._do_send('edit', ctx, *args, **kwargs)

    async def send_temp(self, ctx, *args, **kwargs):
        """ .send but sets delete_after to 5 seconds"""
        kwargs['delete_after'] = 5
        await self.send(ctx, *args, **kwargs)

    async def send_priv(self, ctx, *args, **kwargs):
        """ .send but sets ephemeral to true"""
        kwargs['ephemeral'] = True
        await self.send(ctx, *args, **kwargs)

"""All Strings available to bot, helps with code simplification"""

# External Imports
import discord
from enum import Enum

# Internal Imports
import modules.config as cfg


class AllStrings(Enum):
    NOT_REGISTERED = "You are not registered {}, please go to {} first!"
    NOT_PLAYER = "You are not a player {}, please go to {} first!"
    STOP_SPAM = "{}: Please stop spamming!"

    REG_SUCCESSFUL_CHARS = "Successfully registered with characters: {}, {}, {}"
    REG_SUCCESFUL_NO_CHARS = 'Successfully registered with no Jaeger Account'
    REG_ALREADY_CHARS = "Already registered with characters: {}, {}, {}"
    REG_ALREADY_NO_CHARS = "Already Registered with no Jaeger Account"
    REG_MISSING_FACTION = "Registration Failed: Missing a character for faction {}"
    REG_CHAR_REGISTERED = "Registration Failed: Character: {} already registered by {}"
    REG_CHAR_NOT_FOUND = "Registration Failed: Character: {} not found in the Census API"
    REG_NOT_JAEGER = "Registration Failed: Character: {} is not from Jaeger!"
    REG_WRONG_FORMAT = "Incorrect Character Entry Format!"

    LOBBY_INVITED = "{} you have been invited to a match by {}! Accept or decline below!"
    LOBBY_INVITED_SELF = "{} you can't invite yourself to a match!"
    LOBBY_JOIN = "{} you have joined the lobby!"
    LOBBY_LEAVE = "{} you have left the lobby!"
    LOBBY_NOT_IN = "{} you are not in this lobby!"
    LOBBY_ALREADY_IN = "{} you are already in this lobby!",
    LOBBY_TIMEOUT = "{} you have been removed from the lobby by timeout!"
    LOBBY_TIMEOUT_SOON = "{} you will soon be timed out from the lobby, click above to reset"
    LOBBY_TIMEOUT_RESET = "{} you have reset your lobby timeout."
    LOBBY_DASHBOARD = ''

    INVITE_WRONG_USER = "This invite isnt for you!"

    MATCH_CREATE = "Match created [ID: {}, Invited: {}]"
    MATCH_INVITED = "{} You've been invited to a match by {}, accept or decline below", None, True
    MATCH_END = "Match ID: {} Ended, closing match channels..."

    SKILL_LEVEL_REQ_ONE = "Your requested skill level has been set to: {}"
    SKILL_LEVEL_REQ_MORE = "Your requested skill levels have been set to: {}"
    SKILL_LEVEL = "Your skill level has been set to: {}"

    def __init__(self, string, embed=None, view=None):
        self.__string = string
        self.__embed = embed
        self.__view = view

    def __call__(self, *args):
        return self.__string.format(*args)

    async def _do_send(self, action, ctx, *args, **kwargs):
        string = self.__string.format(*args) if self.__string else None
        embed = None
        view = self.__view if not self.__view else kwargs['view']
        delete_after = kwargs.get('delete_after') if kwargs.get('delete_after') else None
        ephemeral = kwargs.get('ephemeral') if kwargs.get('ephemeral') else False
        if self.__embed:
            embed = self.__embed(**embed_kwargs)
            embed_kwargs = kwargs.get('embed')

        match type(ctx):
            case discord.User | discord.TextChannel | discord.VoiceChannel | discord.Thread:
                return await getattr(ctx, action)(content=string, embed=embed, view=view, delete_after=delete_after)

            case discord.InteractionResponse:
                return await getattr(ctx, action + '_message')(content=string, embed=embed, view=view,
                                                               ephemeral=ephemeral, delete_after=delete_after)

            case discord.Webhook if ctx.type == discord.WebhookType.application and action == "send":
                if view:
                    return await getattr(ctx, 'send')(content=string, embed=embed, view=view,
                                                      ephemeral=ephemeral, delete_after=delete_after)
                else:
                    return await getattr(ctx, 'send')(content=string, embed=embed,
                                                      ephemeral=ephemeral, delete_after=delete_after)

            case discord.Webhook if ctx.type == discord.WebhookType.application and action == "edit":  # Probably doesn't work
                return await getattr(ctx.fetch_message(), 'edit_message')(content=string, embed=embed, view=view,
                                                                          ephemeral=ephemeral,
                                                                          delete_after=delete_after)

            case discord.Interaction:
                return await getattr(ctx.response, action + '_message')(content=string, embed=embed, view=view,
                                                                        ephemeral=ephemeral, delete_after=delete_after)

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

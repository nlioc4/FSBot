"""All Strings available to bot, helps with code simplification
Also handles sending/editing messages to Discord."""

# External Imports
import discord
from enum import Enum
import inspect
from logging import getLogger

# Internal Imports
import modules.config as cfg
from .embeds import *
from modules.tools import UnexpectedError

log = getLogger('fs_bot')


class AllStrings(Enum):
    MESSAGE_DELETED = "Message \"{}\" has been deleted by the moderation team. Reason: {}"
    MESSAGE_DELETE_SUCCESSFUL = "Deleted message from {} successfully."

    NOT_REGISTERED = "You are not registered {}, please go to {} first!"
    NOT_PLAYER = "You are not a player {}, please go to {} first!"
    NOT_PLAYER_2 = "{} is not a player"
    STOP_SPAM = "{}: Please stop spamming!"
    ALL_LOCKED = "FSBot is currently disabled, please try again later!"
    DISABLED_PLAYER = "You are not currently allowed to use FSBot!"

    CHECK_FAILURE = "You have failed a check to run this command!"
    UNASSIGNED_ONLINE = "{} Unassigned Login", account_online_check
    LOADER_TOGGLE = "FSBot {}ed"
    HELLO = "Hello there {}"
    MANUAL_CENSUS = "Manual Census Check {}"
    SUGGESTION_ACCEPTED = "{} your suggestion has been submitted to the administration team. Thanks!"

    LOG_ACCOUNT = "Account [{}] sent to player: ID: [{}], name: [{}]"
    LOG_ERROR = "{} has run into an error, {} {}."
    LOG_GENERAL = "Log: {}"
    LOG_GENERAL_ERROR = "An error has occurred, {}"

    DM_ONLY = "This command can only be used in DM's!   "
    DM_INVITED = "{} you have been invited to a match by {}! Accept or decline below!"
    DM_INVITE_EXPIRED = "This invite has expired!"
    DM_INVITE_EXPIRED_INFO = "Your invite to {} has expired!"
    DM_INVITE_INVALID = "This invite is invalid!"
    DM_ALREADY = "You already have a Modmail thread started! Simple send a message to the bot to respond!"
    DM_RECEIVED = "Opened modmail thread, the mod team will get back to you as soon as possible!\n" \
                  "Further messages will be sent to the same thread and marked with '📨'.\n" \
                  "To stop sending messages reply with ``=quit``"
    DM_RECEIVED_GUILD = "Check DM's for your new modmail thread!"
    DM_IN_THREAD = '{} : {}'
    DM_TO_USER = None, from_staff_dm_embed
    DM_TO_STAFF = "{} New Modmail", to_staff_dm_embed
    DM_THREAD_CLOSE = "This DM thread has been closed.  A new instance must be created" \
                      " for further messages to be conveyed."


    EVENTS_PICKUPS = "@everyone\n" \
                     "\n" \
                     "Air pickups are coming back on {}.\n" \
                     "If you are new to these, they are ESF only group fights on Jaeger with even numbers " \
                     "(usually around 12 vs 12). All skill levels are welcome, we try to make both teams balanced " \
                     "and will re-balance them after every round if needed.\n" \
                     "\n" \
                     "If you have any questions feel free to ask in {}.\n" \
                     "Any info related to pickups can be found in {}.\n" \
                     "\n" \
                     "If you want to join you can react to the event (top left below the server banner) and show up " \
                     "in the Pickups-General voice channel. If you can't make it in time for the first round you can " \
                     "also join between rounds when we re-balance teams. Reacting to the event isn't required but it " \
                     "gives us a rough idea of the amount of people showing up." \
                     "\n" \
                     "\n" \
                     "{}"
    EVENTS_PICKUPS_CREATED = "Your pickups event was created!"
    EVENTS_PICKUPS_CREATION_ERROR = "Error: Please check if you have used the correct date (YYYY-MM-DD --> " \
                                    "with hyphens) and time (HH:MM --> 24 hour clock) formats."

    REG_SUCCESSFUL_CHARS = "Successfully registered with characters: {}, {}, {}."
    REG_SUCCESFUL_NO_CHARS = 'Successfully registered with no Jaeger Account'
    REG_ALREADY_CHARS = "Already registered with characters: {}, {}, {}."
    REG_ALREADY_NO_CHARS = "Already Registered with no Jaeger Account."
    REG_MISSING_FACTION = "Registration Failed: Missing a character for faction {}."
    REG_CHAR_REGISTERED = "Registration Failed: Character: {} already registered by {}."
    REG_CHAR_NOT_FOUND = "Registration Failed: Character: {} not found in the Census API."
    REG_NOT_JAEGER = "Registration Failed: Character: {} is not from Jaeger!"
    REG_WRONG_FORMAT = "Incorrect Character Entry Format! Enter either 1 character for each faction separated by ',' " \
                       "or a space, or one character without a faction suffix and suffixes will be added for you."
    REG_INFO = "", register_info
    REG_LOBBY_PINGS = "Choose your lobby ping preferences below...\n" \
                      "You will only ever be pinged if the player joining the lobby matches your requested skill levels"

    PREF_PINGS_NEVER = "You have chosen to never receive a ping when someone joins the lobby!"
    PREF_PINGS_ONLINE = "You have chosen to only receive a ping when someone joins the lobby if you have " \
                        "your Discord status set to 🟢Online!"
    PREF_PINGS_ALWAYS = "You have chosen to always receive a ping when someone joins the lobby!"
    PREF_PINGS_FREQ = "You have chosen to only receive a ping at minimum every {} minutes!"

    LOBBY_INVITED_SELF = "{} you can't invite yourself to a match!"
    LOBBY_INVITED = "{} invited {} to a match."
    LOBBY_INVITED_MATCH = "{} invited {} to match: {}."
    LOBBY_INVITED_ALREADY = "You've already sent an invite to {}."
    LOBBY_CANT_INVITE = "You can't invite a player to a match when you're not in a lobby!"
    LOBBY_JOIN = "{} you have joined the lobby!"
    LOBBY_LEAVE = "{} you have left the lobby!"
    LOBBY_NOT_IN = "{} you are not in this lobby!"
    LOBBY_NOT_IN_2 = "{} is not in the lobby!"
    LOBBY_NOT_OWNER = "You can't invite players to a match you don't own!"
    LOBBY_NO_DM = "{} could not be invited as they are refusing DM's from the bot!"
    LOBBY_NO_DM_ALL = "{} no players could be invited."
    LOBBY_ALREADY_IN = "{} you are already in this lobby!"
    LOBBY_ALREADY_MATCH = '{} you are already in a match ({}), leave to join the lobby again.'
    LOBBY_TIMEOUT = "{} you have been removed from the lobby by timeout!"
    LOBBY_TIMEOUT_SOON = "{} you will soon be timed out from the lobby, click above to reset."
    LOBBY_TIMEOUT_RESET = "{} you have reset your lobby timeout."
    LOBBY_DASHBOARD = ''
    LOBBY_LONGER_HISTORY = '{}', longer_lobby_logs
    LOBBY_NO_HISTORY = '{} there is no extended activity to display!'
    LOBBY_PING = "A player who matches one of your requested skill levels has joined the {} lobby!\n" \
                 "You will not be pinged again for {} minutes if another matching player joins the lobby."

    LOBBY_INFO_CHANNEL = "Duel Lobby: {} waiting"

    INVITE_WRONG_USER = "This invite isn\'t for you!"

    MATCH_CREATE = "{} Match created ID: {}"
    MATCH_INFO = "", match_info
    MATCH_INVITED = "{} You've been invited to a match by {}, accept or decline below", None
    MATCH_ACCEPT = "You have accepted the invite, join {}."
    MATCH_DECLINE = "You have decline the invite."
    MATCH_DECLINE_INFO = "{} has declined your match invitation."
    MATCH_DECLINE_SKILLEVEL = "{} has declined your match invitation due to a skill level mismatch."
    MATCH_DECLINE_NOTIME = "{} has declined your match invitation due to a lack of time."


    MATCH_JOIN = "{} has joined the match"
    MATCH_JOIN_2 = "{} has joined match {}."
    MATCH_LEAVE = "{} has left the match."
    MATCH_LEAVE_2 = "{} has left match {}."
    MATCH_TIMEOUT_WARN = "{} No online players detected, match will timeout in {}! Login or reset above!"
    MATCH_TIMEOUT_RESET = "{} timeout reset!"
    MATCH_TIMEOUT = "{} Match is being closed due to inactivity"
    MATCH_END = "Match ID: {} Ended, closing match channel..."
    MATCH_NOT_FOUND = "Match for channel {} not found!"
    MATCH_NOT_IN = "You are not in match {}."
    MATCH_NOT_IN_2 = "Player {} is not in match {}."
    MATCH_ALREADY = "{} is already in match {}."

    RM_SCORES_EQUAL = "Submitted scores are equal!"
    RM_SCORES_WRONG = "Submitted scores don't match, both players should submit again!"
    RM_SCORES_WRONG_2 = "Couldn't resolve scores, ending match and reporting..."

    SKILL_LEVEL_REQ_ONE = "Your requested skill level has been set to: {}."
    SKILL_LEVEL_REQ_MORE = "Your requested skill levels have been set to: {}."
    SKILL_LEVEL = "Your skill level has been set to: {}."

    ACCOUNT_HAS_OWN = "You have registered with your own Jaeger account, you can't request a temporary account."
    ACCOUNT_ALREADY = "You have already been assigned an account!"
    ACCOUNT_ALREADY_2 = "{} already has been assigned an account, ID: {}"
    ACCOUNT_SENT = "You have been sent an account, check your DM's."
    ACCOUNT_SENT_2 = "{} has been sent account ID: {}."
    ACCOUNT_LOG_OUT = "Your session has been ended, please log out!"
    ACCOUNT_TOKEN_EXPIRED = "After 5 minutes this account token has expired, please request another" \
                            " if you still need an account."
    ACCOUNT_NO_DMS = "You must allow the bot to send you DM's in order to receive an account!"
    ACCOUNT_NO_ACCOUNT = "Sorry, there are no accounts available at the moment.  Please ping Colin!"
    ACCOUNT_EMBED = "", account
    ACCOUNT_IN_USE = "Account ID: {} is already in use, please pick another account!"
    ACCOUNT_INFO = "", accountcheck
    ACCOUNT_VALIDATE_ERROR = "There was an error logging this usage.  Please try again, and if the " \
                             "issue persists please ask for help!"

    def __init__(self, string, embed=None):
        self.__string = string
        self.__embed = embed

    def __call__(self, *args):
        return self.__string.format(*args)

    async def _do_send(self, action, ctx, *args, **kwargs):
        args_dict = {}
        if self.__string:
            args_dict['content'] = self.__string.format(*args)
        if self.__embed and not kwargs.get('embed'):
            #  Checks if embed, then retrieves only the embed specific kwargs
            embed_sig = inspect.signature(self.__embed)
            embed_kwargs = {arg: kwargs.get(arg) for arg in embed_sig.parameters}
            args_dict['embed'] = self.__embed(**embed_kwargs)
        if kwargs.get('embed'):
            args_dict['embeds'] = [kwargs.get('embed')]
        if kwargs.get('embeds'):
            args_dict['embeds'] = kwargs.get('embeds')
        if kwargs.get('view') is not None:
            args_dict['view'] = None if not kwargs.get('view') else kwargs.get('view')
        if kwargs.get('files'):
            files = kwargs.get('files')
            if type(files) is not list:
                files = list(files)
            args_dict['files'] = files
        if kwargs.get('delete_after'):
            args_dict['delete_after'] = kwargs.get('delete_after')
        if kwargs.get('ephemeral'):
            args_dict['ephemeral'] = kwargs.get('ephemeral')
        if kwargs.get('allowed_mentions') is not None:
            if not kwargs.get('allowed_mentions'):
                args_dict['allowed_mentions'] = discord.AllowedMentions.none()
            else:
                args_dict['allowed_mentions'] = kwargs.get('allowed_mentions')
        if kwargs.get('remove_embed'):
            args_dict['embed'] = None

        match type(ctx):
            case discord.User | discord.Member | discord.TextChannel | discord.VoiceChannel | discord.Thread:
                return await getattr(ctx, action)(**args_dict)

            case discord.Message:
                if action == "send":
                    return await getattr(ctx, "reply")(**args_dict)
                if action == "edit":
                    return await getattr(ctx, action)(**args_dict)

            case discord.InteractionResponse:
                return await getattr(ctx, action + '_message')(**args_dict)

            case discord.Webhook if ctx.type == discord.WebhookType.application:
                if action == "send":
                    return await getattr(ctx, 'send')(**args_dict)
                if action == "edit":  # Probably (definitely) doesn't work
                    return await getattr(await ctx.fetch_message(), 'edit_message')(**args_dict)

            case discord.Interaction:
                if ctx.response.is_done():
                    if action == 'send':
                        return await getattr(ctx.followup, 'send')(**args_dict)
                    if action == 'edit':
                        return await getattr(ctx.message, 'edit')(**args_dict)
                return await getattr(ctx.response, action + '_message')(**args_dict)

            case discord.ApplicationContext:
                if action == "send":
                    return await getattr(ctx, "respond")(**args_dict)
                if action == "edit":
                    return await getattr(ctx, action)(**args_dict)

            case _:
                raise UnexpectedError(f"Unrecognized Context, {type(ctx)}")

    async def send(self, ctx, *args, **kwargs):
        return await self._do_send('send', ctx, *args, **kwargs)

    async def edit(self, ctx, *args, **kwargs):
        return await self._do_send('edit', ctx, *args, **kwargs)

    async def send_temp(self, ctx, *args, **kwargs):
        """ .send but sets delete_after to 5 seconds"""
        kwargs['delete_after'] = 5
        return await self.send(ctx, *args, **kwargs)

    async def send_priv(self, ctx, *args, **kwargs):
        """ .send but sets ephemeral to true"""
        kwargs['ephemeral'] = True
        return await self.send(ctx, *args, **kwargs)

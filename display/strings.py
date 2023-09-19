"""All Strings available to bot, helps with code simplification
Also handles sending/editing messages to Discord."""

# External Imports
import discord
from enum import Enum
import inspect
from logging import getLogger
import classes

# Internal Imports
from .embeds import *
from modules.tools import UnexpectedError

log = getLogger('fs_bot')


class AllStrings(Enum):
    """All Strings is a list of all strings available to the bot.
    This allows you to easily repeat or create messages to users.
    String Enums can be called directly to return only the string, or one of the send/edit methods can be used along
    with a context in the first positional argument to interface directly with discord.

    The Following Context types are currently supported:
    - discord.Message, discord.WebhookMessage, discord.TextChannel, discord.Thread, discord.User, discord.Member
    - discord.Interaction, discord.InteractionResponse, discord.ApplicationContext
    - classes.Player, classes.ActivePlayer

    """

    NONE = None
    ANY = '{}'
    LOADING = "Loading..."
    UNEXPECTED_ERROR = "An unexpected error has occurred, please contact an admin!"
    NOT_REGISTERED = "You are not registered {}, please go to {} first!"
    NOT_REGISTERED_2 = "{} is not registered!"
    NOT_PLAYER = "You are not a player {}, please go to {} first!"
    NOT_PLAYER_2 = "{} is not a player!"
    CANT_USE = "You can't use this!"
    COMMAND_ONLY = "Only command use is allowed in this channel, no messages!"
    CONFIRMED = "Confirmed: {}"
    CANCELLED = "Cancelled: {}"
    STOP_SPAM = "{}: Please stop spamming!"
    ALL_LOCKED = "FSBot is currently disabled, please try again later!"
    DISABLED_PLAYER = "You are not currently allowed to use FSBot!  Check your DM's for more info!"
    AS = "As {}: {}"
    SERVER_JOIN = "Welcome {}!", fs_join_embed
    GUILD_ONLY = "This can only be used in the Flight School Discord!"
    CONTENT_ONLY = 'Oops {}, messages in this channel must contain either an attachment or a link!'

    LEADERBOARD_UPDATED = "Leaderboard in {} was updated!"

    ADMIN_MATCH_CREATE_ALREADY = "One of the players used is already in a match!"
    ADMIN_MATCH_CREATE_SAME = "Both players are the same! Please pass different players!"
    ADMIN_PLAYER_LOGIN_SET = "{}'s online character has been set to {}!"
    ADMIN_PLAYER_LOGOUT_SET = "{} has been set to offline!"
    ADMIN_PLAYER_LOGOUT_ALREADY = "{} is already offline!"
    ADMIN_PLAYER_CHAR_NOT_FOUND = "Character `{}` not found in relation to player {}!"
    ADMIN_PLAYER_NO_ACCOUNT = "{} is registered with no Jaeger account and " \
                              "has not been assigned an FSBot Jaeger Account!"
    ADMIN_PLAYER_CLEAN = "{} has been cleaned."

    CHECK_FAILURE = "You have failed a check to run this command!"
    INVALID_INTERACTION = "This interaction shouldn't have been allowed!"
    UNASSIGNED_ONLINE = "{} Unassigned Login", account_online_check
    LOADER_TOGGLE = "FSBot {}ed"
    HELLO = "Hello there {}"
    MANUAL_CENSUS = "Manual Census Check {}"
    CENSUS_LOOP_STATUS = "The Census loop is {}"
    CENSUS_LOOP_CHANGED = "The Census loop was {}, it has now been {}."
    SUGGESTION_ACCEPTED = "{} your suggestion has been submitted to the administration team. Thanks!"

    LOG_ACCOUNT = "Account [{}] sent to player: ID: [{}], mention: [{}], name: [{}]"
    LOG_EMBED = None, fsbot_error
    LOG_MESSAGE = "FSBot Log: {}"
    LOG_GENERAL_ERROR = "An error has occurred, {}"

    DM_ONLY = "This command can only be used in DM's!   "
    DM_INVITED = "{} you have been invited to a match by {}! Accept or decline below!\n" \
                 "This invite expires {}, expiry will remove you from the lobby!"
    DM_INVITE_EXPIRED = "This invite from {} has expired!"
    DM_INVITE_EXPIRED_LOBBY_REMOVE = "This invite from {} has expired, which has removed you from the lobby!"
    DM_INVITE_EXPIRED_INFO = "Your invite to {} has expired!"
    DM_INVITE_INVALID = "This invite is invalid!"
    DM_ALREADY = "You already have a Modmail thread started! Simple send a message to the bot to respond!"
    DM_RECEIVED = "Opened modmail thread, the mod team will get back to you as soon as possible!\n" \
                  "Further messages will be sent to the same thread and marked with '📨'.\n" \
                  "To stop sending messages reply with ``=quit``"
    DM_RECEIVED_GUILD = "Check DM's for your new modmail thread!"
    DM_IN_THREAD = '{}\n: ``{}``'
    DM_TO_USER = None, from_staff_dm_embed
    DM_TO_STAFF = "{} New Modmail", to_staff_dm_embed
    DM_THREAD_CLOSE = "This DM thread has been closed.  A new instance must be created" \
                      " for further messages to be conveyed."

    REG_SUCCESSFUL_CHARS = "Successfully registered with characters: `{}`."
    REG_SUCCESFUL_NO_CHARS = 'Successfully registered with no Jaeger Account'
    REG_ALREADY_CHARS = "Already registered with characters: `{}`."
    REG_ALREADY_NO_CHARS = "Already Registered with no Jaeger Account."
    REG_MISSING_FACTION = "Registration Failed: Missing a character for faction {}."
    REG_CHAR_REGISTERED = "Registration Failed: Character: `{}` already registered by {}."
    REG_CHAR_PROTECTED = "Registration Failed: Character: `{}` is protected and may not be registered!"
    REG_CHAR_NOT_FOUND = "Registration Failed: Character: `{}` not found in the Census API."
    REG_NOT_JAEGER = "Registration Failed: Character: `{}` is not from Jaeger!"
    REG_WRONG_FORMAT = "Incorrect Character Entry Format! Enter either 1 character for each faction separated by ',' " \
                       "or a space, or one character without a faction suffix and suffixes will be added for you."
    REG_NO_CENSUS = "DBG's Census API is currently unavailable, cannot register characters.  Please try again soon!" \
                    "  Contact Colin if the problem persists!"
    REG_INFO = "", player_info

    PREF_PINGS_CURRENT = "Your current ping Preferences are:\n{}\nYou will only ever be pinged if the player joining " \
                         "the lobby matches your requested skill levels\nChoose your lobby ping preferences below..."
    PREF_PINGS_NEVER = "You have chosen to never receive a ping when someone joins the lobby!"
    PREF_PINGS_UPDATE = "Your ping preferences are now:\nReceive a ping when a matching player joins the lobby:" \
                        " **{}**, with at least **{}** minutes between pings"

    LOBBY_INVITED_SELF = "{} you can't invite yourself to a match!"
    LOBBY_INVITED = "{} invited {} to a match."
    LOBBY_INVITED_MATCH = "{} invited {} to match: {}."
    LOBBY_INVITED_ALREADY = "You've already sent an invite to {}."
    LOBBY_CANT_INVITE = "You or the player you are trying to invite are not in a lobby!"
    LOBBY_JOIN = "{} you have joined the lobby!"
    LOBBY_LEAVE = "{} you have left the lobby!"
    LOBBY_LEAVE_REASON = "{} you have left the lobby due to {}!"
    LOBBY_NOT_IN = "{} you are not in this lobby!"
    LOBBY_NOT_IN_2 = "{} is not in same the lobby as you!"
    LOBBY_NOT_OWNER = "You can't invite players to a match you don't own!"
    LOBBY_NO_DM = "{} could not be invited as they are refusing DM's from the bot!"
    LOBBY_NO_DM_ALL = "{} no players could be invited."
    LOBBY_ALREADY_IN = "{} you are already in a lobby!"
    LOBBY_ALREADY_MATCH = '{} you are already in match [{}], leave to join this lobby!'
    LOBBY_TIMEOUT_SOON = "{} you will  be timed out from the lobby {}, click above to reset."
    LOBBY_TIMEOUT_ONLINE = "While Online on Discord, you cannot be timed out from the lobby!"
    LOBBY_TIMEOUT_RESET = "{} you have reset your lobby timeout."
    LOBBY_TIMEOUT_SET = "You will be timed out at {} if not online."
    LOBBY_TIMEOUT_CUSTOM = "Set a custom timeout within the next 3 hours using the buttons below!\n" \
                           "You will be timed out at {} if not online."
    LOBBY_TIMEOUT_INVALID = "Set a custom timeout within the next 3 hours using the buttons below!\n" \
                            "You will be timed out at {} if not online." \
                            "\n**Timeout request for {} is invalid!**"

    LOBBY_DISABLED = "{} lobby has been disabled!"
    LOBBY_ENABLED = "{} lobby has been enabled!"
    LOBBY_NOT_FOUND = "{} lobby not found!"
    LOBBY_PLAYER_ADDED = "{} has been added to the {} lobby!"
    LOBBY_PLAYER_REMOVED = "{} has been removed from the {} lobby!"
    LOBBY_PLAYER_NOT_IN = "{} is not in the {} lobby!"
    LOBBY_PLAYER_CANT_ADD = "{} can't be added to the {} lobby!"

    LOBBY_DASHBOARD = ''
    LOBBY_LONGER_HISTORY = '{}', longer_lobby_logs
    LOBBY_NO_HISTORY = '{} there is no extended activity to display!'
    LOBBY_PING = "A player who matches one of your requested skill levels [{}] has joined the {} lobby!"

    INVITE_WRONG_USER = "This invite isn\'t for you!"

    MATCH_CREATE = "{} Match created ID: {}"
    MATCH_JOIN = "{} has joined the match"
    MATCH_JOIN_2 = "{} has joined match {}."
    MATCH_LEAVE = "{} has left the match."
    MATCH_LEAVE_2 = "{} has left match {}."
    MATCH_TIMEOUT_WARN = "{} No online players detected, match will timeout {}! Login or reset above!"
    MATCH_TIMEOUT_RESET = "{} timeout reset!"
    MATCH_TIMEOUT_NO_RESET = "{} timeout can't be reset without 2 or more players!"
    MATCH_TIMEOUT = "{} Match is being closed due to inactivity"
    MATCH_END = "Match ID: {} Ended, closing match thread..."
    MATCH_NOT_FOUND = "Match for not found for {}!"
    MATCH_NOT_RANKED = "This only works for ranked matches! {} is not a ranked match!"
    MATCH_NOT_OWNER = "Only the match owner can do this!"
    MATCH_NEW_OWNER = "The match owner is now {}!"
    MATCH_NOT_IN = "You are not in match {}."
    MATCH_NOT_IN_2 = "Player {} is not in a match."
    MATCH_NOT_IN_3 = "Player {} is not in match {}."
    MATCH_ALREADY = "{} is already in match {}."
    MATCH_VOICE_PUB = "{} is now public!"
    MATCH_VOICE_PRIV = "{} is now private!"
    MATCH_NO_ACCOUNT = "{} you are registered without a Jaeger Account and have yet to request one for this match!" \
                       "  If you have your own account please register it in {}," \
                       " otherwise request an account using the button above!"

    RM_FACTION_PICK = "{} pick which faction you will play below!"
    RM_FACTION_PICKED = "{} chose to play {}.\n {} has been assigned {}!\n" \
                        "Please log in to your assigned faction!"
    RM_FACTION_SWITCH = "Half time, please switch factions!" \
                        "  The match will resume when both players have logged back in."
    RM_FACTION_NOT_PICK = "It's not your turn to pick faction!"
    RM_LOG_IN = "Please log in to your assigned faction!"
    RM_SCORES_EQUAL = "Submitted scores are equal!"
    RM_SCORES_WRONG = "Submitted scores don't match, both players should submit again!\n  If possible, use " \
                      "retroactive video recording now to ensure match integrity."
    RM_SCORES_WRONG_2 = "Couldn't resolve scores, ending match and reporting..."
    RM_ROUND_MESSAGE = None, ranked_match_round
    RM_SCORE_SUBMITTED = "{} Score Submitted: {}"
    RM_ROUND_WINNER = "{} won round {}!  The score is now {}."
    RM_ROUND_WINNER_SET = "Round Winner set to {}!"
    RM_NO_CURRENT_ROUND = "There is no round currently in progress!"
    RM_APPEALED = "You have submitted an appeal for Match {}, it will be reviewed as soon as possible!"
    RM_FORFEIT_CONFIRM = "Leaving a match early will result in a loss being recorded, are you sure?"
    RM_WINNER = "{} has won the match with a score of {}:{}!"
    RM_DRAW = "The match was a draw!"
    RM_ENDED_NO_ELO = "The match was not completed properly, results will not be stored..."
    RM_ENDED_TOO_MANY_CONFLICTS = "The match is automatically being appealed due to too many score conflicts..."

    ELO_DM_UPDATE = None, elo_change
    ELO_SUMMARY = None, elo_summary

    INVITE_ACCEPT = "You have accepted the invite from {}, join {}."
    INVITE_DECLINE = "You have declined the invite from {}."
    INVITE_DECLINE_REASON = "Decline Reason:\n{}"
    INVITE_DECLINE_INFO = "{} has declined your match invitation."
    INVITE_DECLINE_INFO_REASON = "{} has declined your match invitation with reason:\n{}"

    REGISTER_NEW_PLAYER = "Welcome {}, you have accepted the rules." \
                          "  Set up your preferences in {} before dueling in {}!"
    REGISTER_RENAME = "{} has been renamed to {} successfully!"
    REGISTER_INVALID_NAME = "{} is not a valid alphanumeric name!"

    SKILL_LEVEL_REQ_ONE = "Your requested skill level has been set to: {}."
    SKILL_LEVEL_REQ_MORE = "Your requested skill levels have been set to: {}."
    SKILL_LEVEL = "Your skill level has been set to: {}."

    ACCOUNT_HAS_OWN = "You have registered with your own Jaeger account, you can't request a temporary account."
    ACCOUNT_ALREADY = "You have already been assigned an account! Check {} for more info..."
    ACCOUNT_ALREADY_2 = "{} already has been assigned an account, ID: {}"
    ACCOUNT_SENT = "You have been sent an account, check your DM's {}."
    ACCOUNT_SENT_2 = "{} has been sent account ID: {}."
    ACCOUNT_TERMINATED = "Account ID: {} has been terminated!  Account Status is: {}."
    ACCOUNT_NOT_ASSIGNED = "{} doesn't have an account assigned to them!"
    ACCOUNT_TERM_LOG = "Your FSBot Account session has ended, please log out of {}!"
    ACCOUNT_TERM = "Your FSBot Account session has ended!"
    ACCOUNT_LOGOUT_WARN = "This session has ended, please log out of {} now!"
    ACCOUNT_TOKEN_EXPIRED = "After 5 minutes this account token has expired, please request another" \
                            " if you still need an account."
    ACCOUNT_NO_DMS = "You must allow the bot to send you DM's in order to receive an account!"
    ACCOUNT_DM_FAILED = "Failed to send account to {}, DM's are likely closed!"
    ACCOUNT_NO_ACCOUNT = "Sorry, there are no accounts available at the moment.  Please ping Colin!"
    ACCOUNT_EMBED = None, account
    ACCOUNT_EMBED_FETCH = "Fetching account...", account
    ACCOUNT_IN_USE = "Account ID: {} is already in use, please pick another account!"
    ACCOUNT_INFO = "", accountcheck
    ACCOUNT_VALIDATE_ERROR = "There was an error logging this usage, the account cannot be validated." \
                             "  Please try again, and if the issue persists please ask for help!"
    ACCOUNT_VALIDATE_ALREADY = "This account has already been validated!"
    ACCOUNT_VALIDATE_SUCCESS = "Account ID: {} has been validated successfully for Player: {}!"
    ACCOUNT_VALIDATE_AUTO = "Account ID: {} is online and has been validated automatically for Player: {}!"

    TIMEOUT_UNTIL = "{}({}) is timed out, their timeout will expire {}, at {}."
    TIMEOUT_NOT = "{}({}) is not timed out."
    TIMEOUT_CLEAR = "{}({}) has had their timeout ended."
    TIMEOUT_WRONG_FORMAT = "Incorrect format ``{}``, formatting must follow ``YYYY-MM-DD`` for dates," \
                           "and ``HH:MM`` for times."
    TIMEOUT_NEW = "{}({}) has been timed out, their timeout will expire {}, at {}."
    TIMEOUT_NO_TIME = "Can't have all arguments == 0, that's not a timeout!"
    TIMEOUT_PAST = "{} is in the past, timeout module does not possess a time machine!"
    TIMEOUT_RELEASED = "You have been released from timeout! Please behave this time..."
    TIMEOUT_DM = "You have been timed out from FSBot until {} by {} for reason: {}."
    TIMEOUT_DM_REMOVED = "Your FSBot timeout has been removed by {}."
    TIMEOUT_DM_UPDATED = "{}\nThis timeout was last updated: {}."
    TIMEOUT_DM_UPDATE_R = "{}\nThis timeout was removed: {}."
    TIMEOUT_STILL = "You are still timed out, try again {}..."
    TIMEOUT_FREE = "You are not timed out from FSBot!"
    TIMEOUT_LOG = "{} has been timed out until {} by {} with reason: {}"

    USAGE_WRONG_FORMAT = "Incorrect format ``{}``, formatting must follow ``YYYY-MM-DD``. "
    USAGE_PSB = None, psb_account_usage

    # `stats` command strings
    STAT_RESPONSE = None, stat_response
    STATS_SELF_ONLY = "You must be an admin to check stats that are not your own!"
    STAT_NO_MATCHES = "{} has not participated in any matches :frowning:."
    STAT_TOTALS = "{} has participated in **{}** matches, over **{}** hours!"
    STAT_PARTNER_MATCH_COUNT = "<@{}> | {} matches"

    # Anomaly Strings
    ANOMALY_REGISTER = "You have registered for Aerial Anomaly alerts from {}!"
    ANOMALY_UNREGISTER = "You have unregistered for Aerial Anomaly alerts from {}!"
    ANOMALY_REGISTER_MSG = "Click the below buttons to register / deregister for Aerial Anomaly alerts for that server!"
    ANOMALY_REGISTER_CREATED = "Created Aerial Anomaly registration message in {}!"
    ANOMALY_EVENT = "{}", anomaly_event
    ANOMALY_MANUAL_LOOP = "Manually looping anomaly event updater!"
    ANOMALY_WSS_RESTART = "Restarting WSS for anomaly event updater!"
    ANOMALY_REMOVE_LEADERBOARD = "Removed {} from the anomaly leaderboard!"
    ANOMALY_REMOVE_LEADERBOARD_NOT_FOUND = "Could not find {} in the anomaly leaderboard!"

    # Voice Room Strings
    ROOM_NOT_IN = "You are not in a voice room!"
    ROOM_NOT_OWNER = "You are not the owner of this voice room!"
    ROOM_NOT_FOUND = "Voice room not found!"
    ROOM_NOT_MEMBER = "{} is not a member of this voice room!"
    ROOM_INVITED = "{} you have been invited to join {}'s voice room!"
    ROOM_INVITE = "You have invited {} to join {}!"
    ROOM_INVITED_ALREADY = "You have already invited {} to join {}!"
    ROOM_KICKED = "{} was removed from the voice room!"
    ROOM_KICK = "You have removed {} from the voice room {}!"
    ROOM_CREATED = "Voice room for {} has been created! Use {} to invite users, or {} to remove them!"

    def __init__(self, string, embed=None):
        self.__string = string
        self.__embed = embed

    def __call__(self, *args):
        return self.__string.format(*args)

    async def _do_send(self, action, ctx, *args, **kwargs):
        args_dict = {}
        if self.__string:
            args_dict['content'] = self.__string.format(*args)
        if kwargs.get('clear_content'):
            args_dict['content'] = None
        if ping := kwargs.get('ping'):
            if not args_dict.get('content'):  # Ensure Content is set to empty string if no content
                args_dict['content'] = ''
            try:
                if type(ping) in [list, tuple]:
                    args_dict['content'] = ''.join([pingable.mention for pingable in ping]) + args_dict['content']
                else:
                    args_dict['content'] = ping.mention + args_dict['content']
            except AttributeError as e:
                log.exception("_do-send received a non-mentionable object in ping argument", exc_info=e)
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
                files = [files]
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

        msg = None

        match type(ctx):
            case discord.User | discord.Member | discord.TextChannel | discord.VoiceChannel | discord.Thread:
                msg = await getattr(ctx, action)(**args_dict)

            case classes.Player | classes.ActivePlayer:
                # Test case to send directly to player objects
                import modules.discord_obj as d_obj
                ctx = await d_obj.bot.get_or_fetch_user(ctx.id)
                msg = await getattr(ctx, action)(**args_dict)

            case discord.Message | discord.WebhookMessage:
                if action == "send":
                    msg = await getattr(ctx, "reply")(**args_dict)
                elif action == "edit":
                    msg = await getattr(ctx, action)(**args_dict)

            case discord.InteractionResponse:
                if ctx.is_done():
                    ctx = ctx._parent
                    if action == 'send':
                        msg = await getattr(ctx.followup, 'send')(**args_dict)
                    elif action == 'edit':
                        msg = await getattr(ctx, 'edit_original_message')(**args_dict)
                else:
                    msg = await getattr(ctx, action + '_message')(**args_dict)

            case discord.Webhook if ctx.type == discord.WebhookType.application:
                if action == "send":
                    msg = await getattr(ctx, 'send')(**args_dict)
                elif action == "edit":  # Probably (definitely) doesn't work
                    msg = await getattr(await ctx.fetch_message(), 'edit_message')(**args_dict)

            case discord.Interaction:
                if ctx.response.is_done():
                    if action == 'send':
                        msg = await getattr(ctx.followup, 'send')(**args_dict)
                    elif action == 'edit':
                        msg = await getattr(ctx, 'edit_original_message')(**args_dict)
                else:
                    msg = await getattr(ctx.response, action + '_message')(**args_dict)

            case discord.ApplicationContext:
                if action == "send":
                    msg = await getattr(ctx, "respond")(**args_dict)
                elif action == "edit":
                    msg = await getattr(ctx, action)(**args_dict)

            case _:
                raise UnexpectedError(f"Unrecognized Context, {type(ctx)}")

        if msg and (view := args_dict.get('view')):
            if not view.message:
                view.message = msg
        return msg

    async def send(self, ctx, *args, **kwargs):
        return await self._do_send('send', ctx, *args, **kwargs)

    async def edit(self, ctx, *args, **kwargs):
        return await self._do_send('edit', ctx, *args, **kwargs)

    async def send_temp(self, ctx, *args, **kwargs):
        """ .send but sets delete_after to 5 seconds"""
        kwargs['delete_after'] = 5
        return await self.send(ctx, *args, **kwargs)

    async def send_long(self, ctx, *args, **kwargs):
        """ .send_temp but sets delete_after to 30 seconds"""
        kwargs['delete_after'] = 30
        return await self.send(ctx, *args, **kwargs)

    async def send_priv(self, ctx, *args, **kwargs):
        """ .send but sets ephemeral to true"""
        kwargs['ephemeral'] = True
        return await self.send(ctx, *args, **kwargs)

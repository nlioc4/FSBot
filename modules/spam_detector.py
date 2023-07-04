"""Simple method to detect spam.  Aggregates calls from a user ID,
 blocks if more than __msg_frequency within last __msg_distance seconds"""

# External Imports
import discord
from logging import getLogger
from datetime import timedelta

# Internal Imports
from display import AllStrings as disp
from modules.tools import timestamp_now
import modules.discord_obj as d_obj

log = getLogger('fs_bot')

__spam_list = dict()
__last_requests = dict()
_msg_frequency = 5
_msg_distance = 10


async def is_spam(ctx, view=False):
    private = False if type(ctx) == discord.Message else True
    user: discord.Member | discord.User = ctx.user if private else ctx.author
    a_id = user.id
    if a_id in __spam_list and __spam_list[a_id] > 0:
        if a_id in __last_requests and __last_requests[a_id] < timestamp_now() - _msg_distance:
            if not view:
                log.debug(f'Automatically Unlocked User ID:{a_id}, User Name: {user.name} from spam filter')
            unlock(a_id)
            return False
    __last_requests[a_id] = timestamp_now()
    if a_id not in __spam_list:
        __spam_list[a_id] = 1
        return False
    __spam_list[a_id] += 1
    if __spam_list[a_id] == 1:
        return False
    if __spam_list[a_id] > _msg_frequency:
        if private:
            await disp.STOP_SPAM.send_priv(ctx, user.mention)
        else:
            await disp.STOP_SPAM.send_temp(ctx, user.mention)
        log.debug(f'Locked User ID:{a_id}, User Name: {user.name} from spam filter')
        try:
            await user.timeout_for(timedelta(seconds=30), reason="Spamming FSBot")
            await d_obj.d_log(f"User {user.mention} was timed out for spamming")
        except discord.Forbidden:
            log.debug(f'Could not timeout {user.name} for spamming, missing permissions')
        return True
    return False


def unlock(a_id):
    __spam_list[a_id] = 0

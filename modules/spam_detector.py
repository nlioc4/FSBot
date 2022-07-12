"""Simple method to detect spam.  Aggregates calls from a user ID,
 blocks if more than __msg_frequency within last __msg_distance seconds"""

# External Imports
import discord
from logging import getLogger

# Internal Imports
from display import AllStrings as disp
from modules.tools import timestamp_now

log = getLogger('fs_bot')


__spam_list = dict()
__last_requests = dict()
_msg_frequency = 5
_msg_distance = 20


async def is_spam(ctx, user: discord.User | discord.Member):
    a_id = user.id
    if a_id in __spam_list and __spam_list[a_id] > 0:
        if a_id in __last_requests and __last_requests[a_id] < timestamp_now() - _msg_distance:
            log.info(f'Automatically Unlocked User ID:{a_id}, User Name: {user.name} from spam filter')
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
        await disp.STOP_SPAM.send_priv(ctx, user.mention)
        return True
    return False

def unlock(a_id):
    __spam_list[a_id] = 0


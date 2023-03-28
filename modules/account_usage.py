"""Module to aggregate account usage"""

# External Imports
from logging import getLogger

# Internal Imports
from modules import database as db
from modules import accounts_handler as accounts
from classes import Player

log = getLogger('fs_bot')


async def get_usages_period(user_id, start_stamp, end_stamp):
    usages = await db.async_db_call(db.find_elements,
                                           "account_usages",
                                           {"user_id": user_id, "start_time": {"$gte": start_stamp, "$lte": end_stamp}},
                                           projection={"_id": 0})
    return list(usages)

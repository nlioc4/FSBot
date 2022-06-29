"""
Census module for tracking Jaeger players.  Currently used to ensure FS block accounts aren't used outside current assignment.

"""

# External Imports
import auraxium
from auraxium import ps2
from logging import getLogger
import asyncio


# Internal Imports
import modules.config as cfg
import modules.accounts_handler_simple as accounts



log = getLogger('fs_bot')

def get_account_chars_list(account_dict: dict):
    """Builds a list of IGN's from the currently available Jaeger accounts"""
    chars_list = list()
    for acc in account_dict:
        name = account_dict[acc].in_game
        names = [f'{name}VS', f'{name}NC', f'{name}TR']
        chars_list.extend(names)
    return chars_list


async def get_chars_list_online_status(chars_list: list):
    "Gets online status from list of IGN's, returns as dictionary of account_id: online_char"
    names_string = ','.join(chars_list)
    async with auraxium.Client(service_id=cfg.general['api_key']) as client:
        # build query
        query = auraxium.census.Query('character', service_id=cfg.general['api_key'])
        query.add_term('name.first_lower', names_string.lower())
        join = query.create_join('characters_online_status')
        query.show('character_id', 'name.first')
        query.limit(100)
        try:
            data = await client.request(query)
        except auraxium.errors.ServiceUnavailableError:
            log.error('API unreachable during online check')
            return false

        # pull data from dict response
        online_names = list()
        for a_return in data['character_list']:
            if a_return['character_id_join_characters_online_status']['online_status'] != "0":
                online_names.append(a_return['name']['first'])
        # assemble dict return
        online_dict = dict()
        for name in online_names:
            a_id = int(name[-4:-2])
            online_dict[a_id] = [name, accounts._all_accounts[a_id].last_usage['id'],
                                 accounts._all_accounts[a_id].last_usage["time_string"]]
        # if no online accounts return False
        if len(online_dict.keys()) == 0:
            return False
    return online_dict


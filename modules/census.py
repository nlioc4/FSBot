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

WORLD_ID = 19

def get_account_chars_list(account_dict: dict):
    """Builds a list of IGN's from the currently available Jaeger accounts"""
    chars_list = list()
    for acc in account_dict:
        name = account_dict[acc].ig_name
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
            return False
        if data["returned"] == 0:
            log.error('API unreachable during online check')
            return False

        # pull data from dict response
        online_names = list()
        for a_return in data['character_list']:
            if a_return['character_id_join_characters_online_status']['online_status'] != "0":
                online_names.append(a_return['name']['first'])
        # assemble dict return
        online_dict = dict()
        for name in online_names:
            a_id = int(name[-4:-2])
            online_dict[a_id] = [name, accounts.all_accounts[a_id].unique_usages[-1]]
        # if no online accounts return False
        if len(online_dict.keys()) == 0:
            return False
    return online_dict


async def get_char_info(char_name) -> list[str, int, int, int]:
    """

    :param char_name: character name to be searched
    :return: [Character name, ID, faction and world].  Empty list if no character found
    """
    async with auraxium.Client(service_id=cfg.general['api_key']) as client:
        char = await client.get_by_name(auraxium.ps2.Character, char_name)
        if not char:
            return None
        char_world = await char.world()
        return [char.name.first, char.id, char.faction_id, char_world.id]


async def get_ids_facs_from_chars(chars_list) -> dict[str, tuple[int, int]] | bool:
    """

    :param chars_list, list of characters to return ids for
    :return: dict of str(char_name): int(id).  returns only chars that exist
    """
    names_string = ','.join(chars_list)
    async with auraxium.Client(service_id=cfg.general['api_key']) as client:
        # build query
        query = auraxium.census.Query('character', service_id=cfg.general['api_key'])
        query.add_term('name.first_lower', names_string.lower())
        query.show('character_id', 'name.first', 'faction_id')
        query.limit(100)
        try:
            data = await client.request(query)
        except auraxium.errors.ServiceUnavailableError:
            log.error('API unreachable during online check')
            return False

        char_dict = dict()
        for a_return in data['character_list']:
            char_name = a_return['name']['first']
            char_id = int(a_return['character_id'])
            char_fac_id = int(a_return['faction_id'])
            char_dict[char_name] = (char_id, char_fac_id)

        return char_dict


async def online_status_updater(all_active_players):
    """Responsible for updating active player and account objects with their currently
    online characters"""
    acc_char_ids = accounts.account_char_ids

    player_char_ids = {}
    for p in all_active_players.values():
        if not p.account:
            for char_id in p.player.ig_ids:
                player_char_ids[char_id] = p

    tracked_ids = acc_char_ids.keys() + player_char_ids.keys()

    client = auraxium.event.EventClient(service_id=cfg.general['api_key'])

    def char_id_check(event: auraxium.event.PlayerLogin | auraxium.event.PlayerLogout):
        return event.character_id in tracked_ids

    async def login_action(evt: auraxium.event.PlayerLogin):

        # Account Section
        if evt.character_id in acc_char_ids:
            accounts.account_char_ids[evt.character_id].online_id = evt.character_id

        # Player Section
        if evt.character_id in player_char_ids:
            player_char_ids[evt.character_id].online_id = evt.character_id

    async def logout_action(evt: auraxium.event.PlayerLogout):

        # Account Section
        if evt.character_id in acc_char_ids:
            acc = accounts.account_char_ids[evt.character_id]
            acc.online_id = None
            if acc.is_terminated():
                accounts.clean_account(acc)

        # Player Section
        if evt.character_id in player_char_ids:
            player_char_ids[evt.character_id].online_id = None

    login_trigger = auraxium.Trigger(auraxium.event.PlayerLogin, worlds=[WORLD_ID],
                                     conditions=[char_id_check], action=login_action)

    logout_trigger = auraxium.Trigger(auraxium.event.PlayerLogin, worlds=[WORLD_ID],
                                     conditions=[char_id_check], action=logout_action)

    client.add_trigger(login_trigger)
    client.add_trigger(logout_trigger)

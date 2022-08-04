"""
Census module for tracking Jaeger players.  Currently used to ensure FS block accounts aren't used outside current assignment.

"""

# External Imports
import auraxium
from logging import getLogger

# Internal Imports
import modules.config as cfg
import modules.accounts_handler as accounts

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
    """Gets online status from list of IGN's, returns as dictionary of account_id: online_char"""
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


async def get_char_info(char_name) -> list[str, int, int, int] | None:
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


async def _login(char_id, acc_char_ids, player_char_ids):
    # Account Section
    if char_id in acc_char_ids:
        acc = acc_char_ids[char_id]
        if acc.online_id == char_id:  # if already online
            return
        acc.online_id = char_id
        if acc.a_player and acc.a_player.match:
            await acc.a_player.match.update_match(login=acc.a_player)
        log.debug(f'Login detected: {char_id}: {acc.online_name}')

    # Player Section
    if char_id in player_char_ids:
        p = player_char_ids[char_id]
        if p.online_id == char_id:  # if already online
            return
        p.online_id = char_id
        if p.match:
            await p.match.update_match(login=p)
        log.debug(f'Login detected: {char_id}: {p.online_name}')


async def _logout(char_id, acc_char_ids, player_char_ids):
    # Account Section
    if char_id in acc_char_ids:
        acc = accounts.account_char_ids[char_id]
        if not acc.online_id:  # if already offline
            return
        log.debug(f'Logout detected: {char_id}: {acc.online_name}')
        acc.online_id = None
        if acc.a_player and acc.a_player.match:
            await acc.a_player.match.update_match()
        if acc.is_terminated:
            await accounts.clean_account(acc)

    # Player Section
    if char_id in player_char_ids:
        p = player_char_ids[char_id]
        if not p.online_id:  # if already offline
            return
        log.debug(f'Logout detected: {char_id}: {p.online_name}')
        p.online_id = None
        if p.match:
            await p.match.update_match()


async def online_status_updater(chars_players_map_func):
    """Responsible for updating active player and account objects with their currently
    online characters"""
    acc_char_ids = accounts.account_char_ids

    client = auraxium.event.EventClient(service_id=cfg.general['api_key'])

    async def login_action(evt: auraxium.event.PlayerLogin):
        player_char_ids = chars_players_map_func()
        await _login(evt.character_id, acc_char_ids, player_char_ids)

    async def logout_action(evt: auraxium.event.PlayerLogout):
        player_char_ids = chars_players_map_func()
        await _logout(evt.character_id, acc_char_ids, player_char_ids)

    # noinspection PyTypeChecker
    login_trigger = auraxium.Trigger(auraxium.event.PlayerLogin, worlds=[WORLD_ID], action=login_action)

    # noinspection PyTypeChecker
    logout_trigger = auraxium.Trigger(auraxium.event.PlayerLogout, worlds=[WORLD_ID], action=logout_action)

    client.add_trigger(login_trigger)
    client.add_trigger(logout_trigger)


async def online_status_rest(chars_players_map):
    acc_char_ids = accounts.account_char_ids

    tracked_ids = list(acc_char_ids.keys()) + list(chars_players_map.keys())
    ids_string = ','.join([str(x) for x in tracked_ids])
    async with auraxium.Client(service_id=cfg.general['api_key']) as client:
        # build query
        query = auraxium.census.Query('character', service_id=cfg.general['api_key'])
        query.add_term('character_id', ids_string)
        query.create_join('characters_online_status')
        query.show('character_id')
        query.limit(1000)
        try:
            data = await client.request(query)
        except auraxium.errors.ServiceUnavailableError:
            log.error('API unreachable during online status init')
            return False
        if data["returned"] == 0 or 'character_id_join_characters_online_status' not in data['character_list'][0]:
            log.error('API unreachable during online status init')
            return False

    # pull data from dict response
    online_ids = list()
    offline_ids = list()
    for a_return in data['character_list']:
        if a_return['character_id_join_characters_online_status']['online_status'] == "0":
            offline_ids.append(int(a_return['character_id']))
        else:
            online_ids.append(int(a_return['character_id']))

    log.debug(f"Online IDs: {online_ids}")
    log.debug(f"Offline IDs: {offline_ids}")

    for char_id in offline_ids:
        await _logout(char_id, acc_char_ids, chars_players_map)
    for char_id in online_ids:
        await _login(char_id, acc_char_ids, chars_players_map)

    return True

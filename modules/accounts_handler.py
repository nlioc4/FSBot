'''manages Account objects'''

# External Imports
from logging import getLogger
from gspread import service_account
from numpy import array

# Internal Imports
import classes
import modules.config as cfg


# Account Containers

_busy_accounts = dict()
_available_accounts = dict()

#Sheet Offsets
Y_OFFSET = 2
X_OFFSET = 1
Y_SKIP = 3

def init(service_account_path: str):
    # open/store google sheet
    gc = service_account(service_account_path)
    sh = gc.open_by_key(cfg.database["accounts_id"])
    raw_sheet = sh.worksheet(cfg.database["accounts_sheet_name"])
    sheet_imported = array(raw_sheet.get_all_values())

    # get number of accounts
    num_accounts = (len(sheet_imported[:, 1]) - 1) // 3


    # import accounts individually
    for i in (range(num_accounts)):
        # get account data
        a_in_game = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET + 2] # in-game char name, minus faction tag
        a_username = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET] # account username
        a_password = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET + 1] # account password
        raw_use = str(sheet_imported[i * Y_SKIP + Y_OFFSET + 1][X_OFFSET - 1])
        a_id = int(a_in_game[-2:]) # integer only account ID

        # update only
        if a_id in _available_accounts:
            _available_accounts[a_id].update(a_username, a_password)
        elif a_id in _busy_accounts:
            _busy_accounts[a_id].update(a_username, a_password)
        else:
            # account has yet to be initialised
            unique_usages_raw = sheet_imported[i * Y_SKIP + Y_OFFSET:i * Y_SKIP + Y_OFFSET + 3, 7:]
            a_unique_usages_id = list()
            a_unique_usages_date = list()
            for use in range(len(unique_usages_raw[2])):
                if unique_usages_raw[2][use] == "":
                    pass
                else:
                    a_unique_usages_id.append(int(unique_usages_raw[2][use]))
                    a_unique_usages_date.append(unique_usages_raw[0][use])
                # check if account is marked "used"
            if raw_use == "OPEN":
                _available_accounts[a_id] = classes.Account(a_id, a_username, a_password,
                                                            a_in_game, a_unique_usages_id)
            if raw_use == "USED":
                _busy_accounts[a_id] = classes.Account(a_id, a_username, a_password,
                                                       a_in_game, a_unique_usages_id)
                _busy_accounts[a_id].last_usage.update({"id": a_unique_usages_id[-1],
                                                        "timestamp": a_unique_usages_date[-1]})



def pick_account(a_player: classes.Player):
    """Pick the account that the player has used the most
    Avoid players using multiple accounts if possible
    """

    # if no accounts: quit
    if len(_available_accounts) == 0:
        return False

    # check if player has used accounts previously
    potential = list()
    for acc in _available_accounts:
        if a_player.id in _available_accounts[acc].unique_usages:
            potential.append(_available_accounts[acc])

    # pick account player has used most
    if potential:
        max_obj = potential[0]
        max_value = max_obj.unique_usages.count(a_player.id)
        for acc in potential:
            usages = acc.unique_usages.count(a_player.id)
            if usages > max_value:
                max_obj = acc
                max_value = usages
        set_account(a_player, max_obj)
        return True

    # if no usage, pick account with least usage
    first = list(_available_accounts.keys())[0]
    min_obj = _available_accounts[first]
    min_value = _available_accounts[first].nb_unique_usages
    for acc in _available_accounts:
        usages = _available_accounts[acc].nb_unique_usages
        if usages < min_value:
            min_obj = _available_accounts[acc]
            min_value = usages
    set_account(a_player, min_obj)
    return True


def set_account(a_player: classes.Player, acc: classes.Account):
    #  set it as current acc,

    # Put in busy dict
    del _available_accounts[acc.id]
    _busy_accounts[acc.id] = acc

    # adjust Player and Account objects
    print(f'Giving account [{acc.id}] to player: ID: [{a_player.id}], name: [{a_player.name}]')
    a_player.account = acc
    acc.a_player = a_player
    acc.unique_usages.append(a_player.id)
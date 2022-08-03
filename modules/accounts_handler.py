'''Manages Account objects'''

# External Imports
import asyncio
from logging import getLogger

import discord
from gspread import service_account
from numpy import array
from datetime import timedelta, datetime, timezone
import pytz

# Internal Imports
import classes
import modules.config as cfg
import modules.census as census
import modules.discord_obj as d_obj
import modules.database as db
from display import AllStrings as disp, views

eastern = pytz.timezone('US/Eastern')

# Account Containers

_busy_accounts = dict()
_available_accounts = dict()
all_accounts = None
account_char_ids = dict()  # maps to account objects, consider mapping directly to char_names

# Sheet Offsets
Y_OFFSET = 2
X_OFFSET = 1
Y_SKIP = 3
USAGE_OFFSET = 7

log = getLogger('fs_bot')


async def init(service_account_path: str):

    # open/store google sheet
    gc = service_account(service_account_path)
    sh = gc.open_by_key(cfg.database["accounts_id"])
    raw_sheet = sh.worksheet(cfg.database["accounts_sheet_name"])
    sheet_imported = array(raw_sheet.get_all_values())

    # TODO fix account # check
    # get number of accounts
    num_accounts = 24  # hacked for simplicity
    # num_accounts = (len(sheet_imported[:, 1]) - 1) // Y_SKIP

    # import accounts individually
    for i in (range(num_accounts)):
        # get account data
        a_in_game = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET + 2]  # in-game char name, minus faction tag
        a_username = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET]  # account username
        a_password = sheet_imported[i * Y_SKIP + Y_OFFSET][X_OFFSET + 1]  # account password
        a_id = int(a_in_game[-2:])  # integer only account ID

        # update only
        if a_id in _available_accounts:
            _available_accounts[a_id].update(a_username, a_password)

        elif a_id in _busy_accounts:
            _busy_accounts[a_id].update(a_username, a_password)


        else:
            # account has yet to be initialised
            unique_usages_raw = sheet_imported[i * Y_SKIP + Y_OFFSET:i * Y_SKIP + Y_OFFSET + 3, USAGE_OFFSET:]
            a_unique_usages_id = list()
            for use in range(len(unique_usages_raw[2])):
                if unique_usages_raw[2][use] == "":
                    pass
                else:
                    a_unique_usages_id.append(int(unique_usages_raw[2][use]))
                # check if account is marked "used"
            a_acc = classes.Account(a_id, a_username, a_password, a_in_game, a_unique_usages_id)
            _available_accounts[a_id] = a_acc

    # Create global all account dict
    global all_accounts
    all_accounts = _busy_accounts | _available_accounts

    # Make list of all char names,
    all_chars = []
    for acc_id in all_accounts:
        all_chars.extend(all_accounts[acc_id].ig_names)
    # get mapping of char_name: (char_id, char_faction) for existing chars
    char_id_map = await census.get_ids_facs_from_chars(all_chars)
    # List comprehension, for all acc_id, for all char_names per acc_id
    for acc_id, char_name in [(acc_id, char_name) for acc_id in all_accounts
                              for char_name in all_accounts[acc_id].ig_names]:
        if char_name in char_id_map:
            all_accounts[acc_id].ig_ids[char_id_map[char_name][1] - 1] = char_id_map[char_name][0]

    # Check for '0' ID's, add to queued delete list
    to_drop = []
    for acc_id, char_id in [(acc_id, char_id) for acc_id in all_accounts
                            for char_id in all_accounts[acc_id].ig_ids]:
        if char_id == 0 and acc_id not in to_drop:
            string = f'Account ID: {acc_id} has a missing character! Dropping account object...'
            print(string)
            await d_obj.channels['logs'].send(content=f"{d_obj.roles['app_admin'].mention} {string}")
            to_drop.append(acc_id)

        if char_id != 0:
            global account_char_ids
            account_char_ids[char_id] = all_accounts[acc_id]

    # execute delete list
    for acc_id in to_drop:
        del all_accounts[acc_id]

    log.info('Initialized Accounts: %s', len(all_accounts))


def pick_account(a_player: classes.Player) -> classes.Account | bool:
    """
    Pick the account that the player has used the most, or the least used account
    Avoid players using multiple accounts if possible
    Adapted from PogBot
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
            if usages == max_value and acc.nb_unique_usages < max_obj.nb_unique_usages:
                max_obj = acc
                max_value = usages
            elif usages > max_value:
                max_obj = acc
                max_value = usages
        set_account(a_player, max_obj)
        return max_obj

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
    return min_obj


def set_account(a_player: classes.Player, acc: classes.Account):
    """
    Set a players current account
    """
    # Put in busy dict
    del _available_accounts[acc.id]
    _busy_accounts[acc.id] = acc

    # adjust Player and Account objects
    acc.add_usage(a_player)
    a_player.set_account(acc)


class ValidateView(views.FSBotView):
    def __init__(self, acc):
        super().__init__(timeout=300)
        self.acc: classes.Account = acc
        self.end_session_button.disabled = True

    @discord.ui.button(label="Confirm Rules", style=discord.ButtonStyle.green)
    async def validate_button(self, button: discord.Button, inter: discord.Interaction):
        validate_account(acc=self.acc)
        button.disabled = True
        button.style = discord.ButtonStyle.grey
        self.end_session_button.disabled = False
        self.timeout = None
        log.info(f'Account [{self.acc.id}] sent to player: ID: [{inter.user.id}], name: [{inter.user.id}]')
        await disp.LOG_ACCOUNT.send(d_obj.channels['logs'], self.acc.id, inter.user.id, inter.user.mention,
                                    allowed_mentions=False)
        await disp.ACCOUNT_EMBED.edit(inter, acc=self.acc, view=self)

    @discord.ui.button(label="End Session", style=discord.ButtonStyle.red)
    async def end_session_button(self, button: discord.Button, inter: discord.Interaction):
        button.disabled = True
        self.stop()
        await terminate(acc=self.acc, inter=inter, view=self)

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await disp.ACCOUNT_TOKEN_EXPIRED.edit(self.acc.message, remove_embed=True, view=self)
        self.acc.a_player.set_account(None)
        self.acc.clean()


async def send_account(acc: classes.Account = None, player: classes.Player = None):
    """Sends account to player, provide either account or player"""
    if not acc and not player:
        raise ValueError("No args provided")
    if not acc:
        acc = player.account
    user = d_obj.bot.get_user(acc.a_player.id)
    for _ in range(3):
        try:
            acc.message = await disp.ACCOUNT_EMBED.send(user, acc=acc, view=ValidateView(acc))
            if acc.message:
                break
        except discord.Forbidden:
            continue
    return acc.message


def validate_account(acc: classes.Account = None, player: classes.Player = None):
    """Player accepted account, track usage and update object."""
    if not acc and not player:
        raise ValueError("No args provided")
    if not acc:
        acc = player.account
    if not player:
        player = acc.a_player

    # update account object
    acc.validate()

    # Update GSheet with Usage
    gc = service_account(cfg.GAPI_SERVICE)  # connection
    sh = gc.open_by_key(cfg.database["accounts_id"])  # sheet
    ws = sh.worksheet(cfg.database["accounts_sheet_name"])  # worksheet
    row = acc.id * Y_SKIP  # row of the account to be updated
    column = len(ws.row_values(row)) + 1  # updates via counting row values, instead of below counting nb_uniques
    # column = acc.nb_unique_usages + USAGE_OFFSET # column of the account to be updated
    cells_list = ws.range(row, column, row + 2, column)
    date = datetime.now().astimezone(eastern).date().strftime('%m/%d/%Y %H%M%S')
    cells_list[0].value = date
    cells_list[1].value = player.name
    cells_list[2].value = str(player.id)

    ws.update_cells(cells_list, 'USER_ENTERED')  # actually update the sheet
    ws.format(cells_list[0].address, {"numberFormat": {"type": "DATE", "pattern": "mmmm dd"}})


async def terminate(acc: classes.Account = None, player: classes.Player = None, inter=None,
                    view: discord.ui.View | int = 0):
    """Terminates account and sends message to log off, provide either account or player"""
    if not acc and not player:
        raise ValueError("No args provided")
    if not acc:
        acc = player.account
    if not player:
        player = acc.a_player

    acc.terminate()  # mark account as terminated

    # Send log-out message, adjust embed
    user = d_obj.bot.get_user(player.id)
    if acc.message:
        for _ in range(3):
            try:
                if await disp.ACCOUNT_LOG_OUT.send(user):
                    break
            except discord.Forbidden:
                continue

    if inter:
        await disp.ACCOUNT_EMBED.edit(inter, acc=acc, view=view)  # use interaction response to edit
    else:
        await disp.ACCOUNT_EMBED.edit(acc.message, acc=acc, view=view)  # use acc.message context to edit

    # Clean if already offline
    if not acc.online_id:
        await clean_account(acc)


async def clean_account(acc):
    # Update DB Usage
    acc.logout()
    await db.async_db_call(db.push_element, 'account_usages', acc.id, acc.last_usage)

    # Adjust player & account objects, return to available directory.
    acc.a_player.set_account(None)
    acc.clean()
    del _busy_accounts[acc.id]
    _available_accounts[acc.id] = acc


def has_account(a_player):
    for acc in _busy_accounts.values():
        if acc.a_player == a_player:
            return True
    else:
        return False


def accounts_info() -> tuple[int, int, list]:
    available = len(_available_accounts)
    used = len(_busy_accounts)
    usages = list()

    for acc in _busy_accounts:
        i = acc
        u = _busy_accounts[acc].a_player or classes.Player.get(_busy_accounts[acc].last_user_id)
        usages.append((i, u.mention))
    usages.sort()
    return available, used, usages

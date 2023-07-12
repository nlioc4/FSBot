'''Manages Account objects'''

# External Imports
import asyncio
from logging import getLogger

import discord
import gspread.exceptions
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
import modules.tools as tools
from display import AllStrings as disp, views, embeds

eastern = pytz.timezone('US/Eastern')

# Account Containers

_busy_accounts = dict()
_available_accounts = dict()
all_accounts = None
account_char_ids = dict()  # dict of account_char_id : account obj
INITIALISED: asyncio.Future = asyncio.Future()

UNASSIGNED_ONLINE_WARN = True
MAX_TIME = 10800  # Maximum time for account assignments (limit is ignored if user is in a match)

# Sheet Offsets
Y_OFFSET = 2
X_OFFSET = 1
Y_SKIP = 3
USAGE_OFFSET = 7

log = getLogger('fs_bot')


async def init(service_account_path: str, test=False):
    """Initializes the account handler.  Pulls account information from the Google sheet
    and creates/updates Account objects for each account.  Checks for missing characters.  Can be called after bot startup
    to refresh account information."""
    if test:  # Disable Unassigned Online Warnings if bot in test mode
        global UNASSIGNED_ONLINE_WARN
        UNASSIGNED_ONLINE_WARN = False

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

    # Report Failure and set up retry if census API fails
    if not char_id_map:
        await d_obj.d_log(message=f'Failed to retrieve character information from Census API.  '
                                  f'Retrying in 30 seconds...')
        await asyncio.sleep(30)
        char_id_map = await census.get_ids_facs_from_chars(all_chars)
        if not char_id_map:
            await d_obj.d_log(message=f'{d_obj.roles["app_admin"].mention}\n'
                                      f'Failed to retrieve character information from Census API.  '
                                      f'Characters have not been checked, please run account init when possible!.')
            return

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
            await d_obj.d_log(message=f'{d_obj.roles["app_admin"].mention}\n'
                                      f'Account ID: {acc_id} has a missing character! Dropping account object...')
            to_drop.append(acc_id)

        if char_id != 0:
            global account_char_ids
            account_char_ids[char_id] = all_accounts[acc_id]

    # execute delete list
    for acc_id in to_drop:
        del all_accounts[acc_id]

    await unassigned_online(None)  # Run check to ensure no accounts are online on startup.
    global INITIALISED
    if not INITIALISED or not INITIALISED.done():
        INITIALISED.set_result(True)
    info = f'Initialized Accounts: {len(all_accounts)}'
    await d_obj.d_log(info)
    return info


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
    def __init__(self, acc: classes.Account):
        super().__init__(timeout=300)
        self.acc = acc
        self.end_session_button.disabled = True
        self.update()

    def update(self):
        if self.acc.is_validated:
            self.validate_button.disabled = True
            self.validate_button.style = discord.ButtonStyle.grey
            self.end_session_button.disabled = False
            self.timeout = None
        if self.acc.is_terminated:
            self.disable_all_items()
            self.stop()
        return self

    @discord.ui.button(label="Confirm Rules", style=discord.ButtonStyle.green)
    async def validate_button(self, button: discord.Button, inter: discord.Interaction):
        try:
            await disp.ACCOUNT_EMBED_FETCH.edit(inter, acc=self.acc, view=self)
        except discord.NotFound:
            log.info("Interaction Not found on Validation Defer")
        try:
            await validate_account(acc=self.acc)
        except gspread.exceptions.APIError as e:
            await disp.ACCOUNT_VALIDATE_ERROR.send_priv(inter)

    @discord.ui.button(label="End Session", style=discord.ButtonStyle.red)
    async def end_session_button(self, button: discord.Button, inter: discord.Interaction):
        await inter.response.defer()
        button.disabled = True
        self.stop()
        await terminate(acc=self.acc, view=self)

    async def on_timeout(self) -> None:
        if not self.acc.is_validated:
            log.info(f"Validate View Timed out for Acc: {self.acc.id}, Player: {self.acc.a_player.name}")
            self.disable_all_items()
            await disp.ACCOUNT_TOKEN_EXPIRED.edit(self.acc.message, remove_embed=True, view=self)
            await clean_account(self.acc)


async def update_message(acc: classes.Account):
    """Updates the account message with the current account object"""
    if not acc.message:
        log.info(f"Account {acc.id} has no message!")
        return False

    # check if view has updated
    def view_changed():
        msg_view = discord.ui.View.from_message(acc.message)
        try:
            for new_child, old_child in zip(msg_view.children, acc.view.children, strict=True):
                if new_child == old_child:
                    continue
                else:
                    return True
        except ValueError:
            pass
        return False

    # Check if embed or view needs to be updated before wasting API calls
    if (acc.message.embeds and tools.compare_embeds(acc.message.embeds[0], embeds.account(acc))) or view_changed():
        await disp.ACCOUNT_EMBED.edit(acc.message, clear_content=True, acc=acc, view=acc.view.update())


async def send_account(acc: classes.Account = None, player: classes.Player = None):
    """Sends account to player, provide either account or player"""
    if not acc and not player:
        raise ValueError("No args provided")
    acc = acc or player.account or pick_account(player)
    if not acc:
        return False
    player = player or acc.a_player
    user = player.member
    account_timeout_delay(player=player, acc=acc, delay=MAX_TIME, update_msg=False)  # start timeout task
    for _ in range(3):
        try:
            acc.view = ValidateView(acc)
            acc.message = await disp.ACCOUNT_EMBED.send(user, acc=acc, view=acc.view)
            if acc.message:
                break
        except discord.Forbidden:
            continue
    if not acc.message:
        await d_obj.d_log(f"Error sending account to User: {player.mention}({player.name}), DM's are likely closed.")
        await clean_account(acc)
        return False
    else:
        return acc.message


async def validate_account(acc: classes.Account = None, player: classes.Player = None) -> bool:
    """Player accepted account, track usage and update object.  Returns True if validated, usage logged"""
    if not acc:
        acc = player.account
    if not player:
        player = acc.a_player
    if not acc and not player:
        raise ValueError("No args provided")

    # Check if already validated
    if acc.is_validated or acc.is_terminated:  # Accounts should never be terminated here, but just in case?
        await update_message(acc)
        return False

    # Update GSheet with Usage
    gc = service_account(cfg.GAPI_SERVICE)  # connection
    sh = gc.open_by_key(cfg.database["accounts_id"])  # sheet
    ws = sh.worksheet(cfg.database["accounts_sheet_name"])  # worksheet
    row = acc.id * Y_SKIP  # row of the account to be updated
    column = len(ws.row_values(row)) + 1  # updates via counting row values, instead of below counting nb_uniques
    # column = acc.nb_unique_usages + USAGE_OFFSET # column of the account to be updated

    try:
        cells_list = ws.range(row, column, row + 2, column)
        date = datetime.now().astimezone(eastern).date().strftime('%m/%d/%Y')
        cells_list[0].value = date
        cells_list[1].value = player.name
        cells_list[2].value = str(player.id)

        ws.update_cells(cells_list, 'USER_ENTERED')  # actually update the sheet
        ws.format(cells_list[0].address,
                  {"numberFormat": {"type": "DATE", "pattern": "mmmm dd"}, "horizontalAlignment": "CENTER"})
    except gspread.exceptions.APIError as e:
        resp = str(e)
        await disp.NONE.edit(acc.message, clear_content=True)
        if "exceeds grid limits" in resp:  # attempt to resize sheet before retrying
            ws.add_cols(15)
            return await validate_account(acc, player)
        await d_obj.d_log(f"Error logging usage to GSheet for Account: {acc.id},"
                          f" user: {acc.a_player.id}, ID: {acc.a_player.id}", error=e)
        raise e

    # Show Player Account Details
    acc.validate()
    await update_message(acc)
    if acc.a_player.match:
        acc.a_player.match.update_soon()  # update match if player is in a match

    # Log Account Validation
    log.info(f'Account [{acc.id}] sent to player: ID: [{player.id}], name: [{player.name}]')  # Log validation
    await disp.LOG_ACCOUNT.send(d_obj.channels['logs'], acc.id, player.id, player.mention,
                                player.name, allowed_mentions=False)

    return True


async def terminate(acc: classes.Account = None, player: classes.Player = None, view: discord.ui.View | bool = False,
                    force_clean=False):
    """Terminates account and sends message to log off, provide either account or player"""
    if not acc:
        acc = player.account
    if not player:
        player = acc.a_player
    if not acc and not player:
        raise ValueError("No args provided")
    if not acc:  # this would fire if the account was terminated by another process subsequently
        return await d_obj.d_log(message=f"Terminating {player.name}'s account failed, no account object.")

    if acc.terminate():  # if not already terminated:
        # End Account Timeout Countdown
        if acc.timeout_coro and not acc.timeout_coro.done():
            acc.timeout_coro.cancel()
            acc.timeout_coro = None

        # Send log-out message if logged in, adjust embed
        # choose which message to send depending on whether the account is currently online
        send_coro = disp.ACCOUNT_TERM_LOG.send(acc.message, acc.online_name) if acc.online_id \
            else disp.ACCOUNT_TERM.send(acc.message)
        for _ in range(3):
            try:
                if await send_coro:
                    break
            except discord.Forbidden:
                continue

        if acc.online_id:  # if online, send reminder to log out
            asyncio.create_task(logout_reminder(acc))

        # Log Account Termination
        d_obj.d_log_task(f'Account [{acc.id}] terminated for player: ID: [{player.id}], name: [{player.name}]')

    await update_message(acc)  # Update message to show account is terminated

    # Clean if already offline or forced
    if acc.is_terminated and (not acc.online_id or force_clean):
        await clean_account(acc)


async def terminate_all():
    """Terminates all currently assigned accounts, forcing clean whether online or not"""
    terminate_coroutines = [terminate(acc, force_clean=True) for acc in _busy_accounts.values()]
    await asyncio.gather(*terminate_coroutines)


async def clean_account(acc: classes.Account):
    if acc.is_clean:  # Check if account is already clean
        return
    if acc.is_validated:
        # Update DB Usage, only if account was actually used
        await db.async_db_call(db.add_element, 'account_usages', acc.last_usage)

    # Adjust player & account objects, return to available directory.
    acc.a_player.set_account(None)
    acc.clean()
    del _busy_accounts[acc.id]
    _available_accounts[acc.id] = acc

    # Log Account Clean
    d_obj.d_log_task(f'Account [{acc.id}] cleaned, returned to available accounts.')


async def unassigned_online(newest_login):
    """Send alert that an unassigned account has logged in"""
    if not UNASSIGNED_ONLINE_WARN:  # Disable if needed
        return

    online = [acc for acc in _available_accounts.values() if acc.online_id]

    if online:
        await disp.UNASSIGNED_ONLINE.send(d_obj.channels['logs'],
                                          d_obj.roles['app_admin'].mention,
                                          online=online,
                                          new=newest_login)


async def _account_timeout_delay(player: classes.Player, acc: classes.Account, delay: int, update_msg: bool):
    """Coroutine to terminate an account if specified delay is exceeded, unless player is in a match."""
    try:
        acc.set_timeout(delay)
        if update_msg:
            await update_message(acc)
        await asyncio.sleep(delay)  # Wait for specified delay
        if acc.timeout_at > tools.timestamp_now():  # Check if timeout was updated
            # if so, restart coroutine using remaining time as delay
            asyncio.get_event_loop().call_soon(account_timeout_delay, player, acc, acc.timeout_delta)

        if not player.match and acc.a_player == player:
            asyncio.create_task(terminate(acc, player))  # Terminate account if player is not in a match
            #  Use create_task to avoid cancelling this coroutine

        else:  # if Account is still being used validly, recreate timeout with new delay
            asyncio.get_event_loop().call_soon(account_timeout_delay, player, acc, delay)

    except asyncio.CancelledError:
        pass


def account_timeout_delay(player: classes.Player, acc: classes.Account, delay: int = 300, update_msg: bool = True):
    """Coroutine to terminate an account if specified delay is exceeded, unless player is in a match."""
    if acc.timeout_coro and not acc.timeout_coro.done():
        acc.timeout_coro.cancel()
    acc.timeout_coro = asyncio.create_task(_account_timeout_delay(player, acc, delay, update_msg))


async def logout_reminder(acc: classes.Account):
    """Looping coroutine to remind a player to logout of an account after it is terminated.
    Sends warning to log channel if players continue to stay on account."""
    try:

        await asyncio.sleep(300)

        if acc.online_id and acc.is_terminated:
            await disp.ACCOUNT_LOGOUT_WARN.send(acc.message, acc.online_name, ping=acc.a_player)

            acc.logout_reminders += 1
            if acc.logout_reminders % 3 == 0 or acc.logout_reminders == 1:
                await d_obj.d_log(f'User: {acc.a_player.mention} has not logged out of their Jaeger account'
                                  f' {acc.logout_reminders * 5} minutes after their session ended!')

            asyncio.create_task(logout_reminder(acc))
        elif acc.is_terminated:  # should be redundant as accounts are cleaned on logout in modules.census
            await clean_account(acc)
        else:
            pass
    except asyncio.CancelledError:
        pass
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        await d_obj.d_log(f'Unable to DM {acc.a_player.mention} to log out of their Jaeger account.\n'
                          f'Force cleaning account...')
        await clean_account(acc)


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

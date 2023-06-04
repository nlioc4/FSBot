'''
Player Classes, representing registered users, and related methods
'''
# Internal Imports
import modules.config as cfg
import modules.database as db
import modules.census as census
from classes.accounts import Account
import modules.tools as tools

# External Imports
from logging import getLogger
import re
from enum import Enum
from datetime import datetime

log = getLogger("fs_Bot")

WORLD_ID = 19  # Jaeger ID


class SkillLevel(tools.AutoNumber):
    # skill levels to be self proscribed
    HARMLESS = "Still learning how to handle an ESF, much less duel one"
    BEGINNER = "Making progress, knows up from down"
    NOVICE = "Has the basics down, but still working on tuning skills"
    COMPETENT = "Average ESF pilot, moves and shoots."
    PROFICIENT = "Capable of taking on most ESF pilots, but needs refinement"
    DANGEROUS = "Excellent aim or movement, but not both at the same time"
    EXPERT = "Capable of taking on all but the most skilled pilots"
    MASTER = "Top tier pilot, both aiming and movement mastered"
    TEACHER = "Players willing to spend time teaching new pilots to fly"

    def __init__(self, description=' '):
        self.description = description

    def __str__(self):
        return self.name[0] + self.name[1:].lower()

    @property
    def rank(self):
        return "T" if self._rank == 9 else self._rank  # hardcoding fix for 'TEACHER' rank

    @property
    def value(self):
        return self.description

    def sort(self):
        return self._rank


class CharInvalidWorld(Exception):
    """Attempted to register Character on wrong world"""

    def __init__(self, char):
        self.char = char
        super().__init__(f'{char} is from the wrong world')


class CharAlreadyRegistered(Exception):
    """Character is already registered to another player!"""

    def __init__(self, player, char):
        self.player = player
        self.char = char
        super().__init__(f'{char} already registered by {player.name}')


class CharBotAccount(Exception):
    """Attempted to register Character belonging to an FSBot Account"""

    def __init__(self, account, char):
        self.account = account
        self.char = char
        super().__init__(f'{char} is registered to FSBot Account {account.ig_name}')


class CharMissingFaction(Exception):
    """Registration failed to find a character for each required Faction"""

    def __init__(self, faction):
        self.faction = faction
        super().__init__(f'Missing character from faction: {faction}')


class CharNotFound(Exception):
    """One of the characters provided was not found during registration"""

    def __init__(self, char):
        self.char = char
        super().__init__(f'{char} not found in the Census API')


class Player:
    """Base Player Class, one for every registered user
    """

    _all_players = dict()
    _name_checking = [dict(), dict(), dict(), dict()]

    @classmethod
    def get(cls, p_id) -> 'Player':
        player: Player = cls._all_players.get(p_id)
        return player

    def remove(self):
        if self.__has_own_account:
            Player.name_check_remove(self)
        del Player._all_players[self.__id]

    @classmethod
    def name_check_add(cls, p):
        for i in range(4 if p.has_ns_character else 3):
            cls._name_checking[i][p.ig_ids[i]] = p

    @classmethod
    def name_check_remove(cls, p):
        for i in range(4 if p.has_ns_character else 3):
            try:
                del cls._name_checking[i][p.ig_ids[i]]
            except KeyError:
                log.warning(f"name_check_remove KeyError for player [id={p.id}], [key={p.ig_ids[i]}]")

    @classmethod
    def get_all_players(cls):
        return cls._all_players

    @classmethod
    def get_all_active_players(cls) -> list:
        return [p.active for p in cls.get_all_players().values() if p.active]

    @classmethod
    def get_players_to_ping(cls, level) -> set:
        could_ping = set()
        for p in list(cls.get_all_players().values()):

            #  Cases where a player should never be pinged:
            #  ping_pref == 0, category hidden, on timeout, or in lobby/match already.
            if p.lobby_ping_pref == 0 or p.hidden or p.is_timeout or p.lobby or p.match:
                continue

            # Check player hasn't been pinged within ping_freq
            if not p.lobby_last_ping or (p.lobby_last_ping and
                                         p.lobby_last_ping + p.lobby_ping_freq * 60 < tools.timestamp_now()):
                # if no req skill levels or a matching level in the lobby levels
                if not p.req_skill_levels or level in p.req_skill_levels:
                    could_ping.add(p)
        return could_ping

    @classmethod
    def map_chars_to_players(cls):
        dct = {}
        for i in cls._name_checking:
            dct.update(i)
        return dct

    def __init__(self, p_id, name):
        if not re.match(cfg.name_regex, name):
            name = "Non-Alphanumeric"
        self.__name = name
        self.__id = p_id
        self.__has_own_account = False
        self.__account = None
        self.__ig_names = ["N/A", "N/A", "N/A", "N/A"]
        self.__ig_ids = [0, 0, 0, 0]
        self.online_id = None
        self.__is_registered = False
        self.__hidden = False
        self.__timeout: dict = {'stamp': 0, "msg_id": 0, "reason": "", "mod_id": 0}  # this should be a named tuple
        self.__lobby_timeout_stamp = 0
        self.__lobbied_stamp = 0
        self.__active = None
        self.__match = None
        self.__lobby = None
        self.skill_level: SkillLevel = SkillLevel.HARMLESS
        self.pref_factions: list[str] = []
        self.req_skill_levels = None

        # Integers to represent ping preferences. {0: No Ping, 1: Ping if Online, 2: Ping Always}
        self.lobby_ping_pref = 0
        self.lobby_ping_freq = 30  # Minutes to wait in between pings
        self.lobby_last_ping = 0  # Timestamp of last time the player was pinged

        Player._all_players[p_id] = self  # adding to all players dictionary

    @classmethod
    def new_from_data(cls, data):  # make player object from database data
        obj = cls(data['_id'], data['name'])
        obj.__is_registered = data['is_registered']
        obj.skill_level = SkillLevel[data['skill_level']]

        if 'ig_ids' in data:
            obj.__has_own_account = True
            obj.__ig_names = data['ig_names'] if len(data['ig_names']) > 3 else data['ig_names'] + ["N/A"]
            obj.__ig_ids = data['ig_ids'] if len(data['ig_ids']) > 3 else data['ig_ids'] + [0]
            Player.name_check_add(obj)
        else:
            obj.__has_own_account = False
            obj.__ig_names = ["N/A", "N/A", "N/A", "N/A"]
            obj.__ig_ids = [0, 0, 0, 0]
        if 'timeout' in data:
            obj.__timeout = data['timeout']
        if 'hidden' in data:
            obj.__hidden = data['hidden']
        if 'pref_factions' in data:
            obj.pref_factions = data['pref_factions']
        if 'req_skill_levels' in data:
            obj.req_skill_levels = [SkillLevel[level] for level in data['req_skill_levels']]
        if 'lobby_ping_pref' in data:
            obj.lobby_ping_pref = data['lobby_ping_pref']
        if 'lobby_ping_freq' in data:
            obj.lobby_ping_freq = data['lobby_ping_freq']

    def get_data(self):  # get data for database push
        data = {'_id': self.id, 'name': self.__name,
                'is_registered': self.__is_registered,
                'skill_level': self.skill_level.name}
        if self.__has_own_account:
            data['ig_ids'] = self.__ig_ids
            data['ig_names'] = self.__ig_names
        if self.__timeout:
            data['timeout'] = self.__timeout
        if self.__hidden:
            data['hidden'] = self.__hidden
        if self.pref_factions:
            data['pref_factions'] = self.pref_factions
        if self.req_skill_levels:
            data['req_skill_levels'] = self.req_skill_levels
        if self.lobby_ping_pref:
            data['lobby_ping_pref'] = self.lobby_ping_pref
        if self.lobby_ping_freq:
            data['lobby_ping_freq'] = self.lobby_ping_freq

        return data

    async def db_update(self, arg):
        """Update a specific users database element.  Options are name, register, account, timeout,
         skill_level, req_skill_levels, pref_factions, pref_factions, hidden: """
        match arg:
            case 'name':
                await db.async_db_call(db.set_field, 'users', self.id, {'name', self.__name})
            case 'register':
                await db.async_db_call(db.set_field, 'users', self.id, {'is_registered': self.__is_registered})
            case 'account':
                doc = {'ig_ids': self.ig_ids, 'ig_names': self.ig_names}
                if self.has_own_account:
                    await db.async_db_call(db.set_field, 'users', self.id, doc)
                else:
                    await db.async_db_call(db.unset_field, 'users', self.id, doc)
            case 'timeout':
                await db.async_db_call(db.set_field, 'users', self.id, {'timeout': self.__timeout})
            case 'skill_level':
                await db.async_db_call(db.set_field, 'users', self.id, {'skill_level': self.skill_level.name})
            case 'req_skill_levels':
                await db.async_db_call(db.set_field, 'users', self.id,
                                       {'req_skill_levels': [level.name for level in self.req_skill_levels]})
            case 'pref_factions':
                await db.async_db_call(db.set_field, 'users', self.id, {'pref_factions': self.pref_factions})
            case 'hidden':
                await db.async_db_call(db.set_field, 'users', self.id, {'hidden': self.__hidden})
            case 'lobby_ping_pref':
                await db.async_db_call(db.set_field, 'users', self.id, {'lobby_ping_pref': self.lobby_ping_pref})
            case 'lobby_ping_freq':
                await db.async_db_call(db.set_field, 'users', self.id, {'lobby_ping_freq': self.lobby_ping_freq})
            case _:
                raise KeyError(f"No field {arg} found")

    @property
    def name(self):
        return self.__name

    def rename(self, name):
        if not re.match(cfg.name_regex, name):
            return False
        self.__name = name
        return True

    @property
    def id(self):
        return self.__id

    @property
    def mention(self):
        return f"<@{self.__id}>"

    @property
    def get_member(self):
        from modules import discord_obj
        return discord_obj.guild.get_member(self.id)

    async def get_user(self):
        from modules import discord_obj
        return await discord_obj.bot.get_or_fetch_user(self.id)

    async def get_stats(self):
        from . import PlayerStats
        return await PlayerStats.get_from_db(p_id=self.id, p_name=self.name)

    @property
    def ig_names(self):
        """Returns the players character names, or their assigned accounts characters names."""
        if self.account:
            return self.account.ig_names
        return self.__ig_names if self.has_ns_character else self.__ig_names[:-1]

    @property
    def ig_ids(self):
        """Returns the players character ids, or their assigned accounts characters ids."""
        if self.account:
            return self.account.ig_ids
        return self.__ig_ids if self.has_ns_character else self.__ig_ids[:-1]

    @property
    def is_registered(self) -> bool:
        return self.__is_registered

    @property
    def has_own_account(self) -> bool:
        return self.__has_own_account

    @property
    def has_ns_character(self) -> bool:
        """Return whether the user has a NS character registered, by ID != 0."""
        return self.__has_own_account and self.__ig_ids[3]

    @property
    def account(self) -> Account | None:
        return self.__account

    @property
    def is_timeout(self) -> bool:
        return self.__timeout['stamp'] > datetime.now().timestamp()

    @property
    def timeout_until(self):
        return self.__timeout['stamp']

    @property
    def timeout_msg_id(self):
        return self.__timeout['msg_id']

    @property
    def timeout_reason(self):
        return self.__timeout['reason']

    @property
    def timeout_mod_id(self):
        return self.__timeout['mod_id']

    async def set_timeout(self, timeout_until, timeout_msg_id=0, reason='', mod_id=0):
        """Should be rewritten to just always send values instead of conditionally updating values."""
        if timeout_until == 0:
            self.__timeout['stamp'] = timeout_until
            self.__timeout['msg_id'] = 0
            self.__timeout['reason'] = ''
            self.__timeout['mod_id'] = 0
        elif self.is_timeout:
            self.__timeout['stamp'] = timeout_until
            self.__timeout['mod_id'] = mod_id
            if reason:
                self.__timeout['reason'] = reason
        else:
            self.__timeout['stamp'] = timeout_until
            self.__timeout['msg_id'] = timeout_msg_id
            self.__timeout['reason'] = reason
            self.__timeout['mod_id'] = mod_id
        await self.db_update('timeout')

    @property
    def hidden(self):
        return self.__hidden

    @hidden.setter
    def hidden(self, value):
        self.__hidden = value

    @property
    def match(self):
        return self.__match

    @property
    def active(self):
        return self.__active

    @property
    def online_name(self):
        try:
            if self.online_id:
                return self.ig_names[self.ig_ids.index(self.online_id)]
            elif self.account and self.account.online_id:
                return self.account.online_name
            else:
                return False
        except ValueError:
            log.warning(f"Registration Changed during online_name call for {self.name}")
            return False

    def char_name_by_id(self, char_id) -> str | None:
        """Fetch a player or their accounts character name by id. Returns None if char not found"""
        if char_id in self.ig_ids:
            return self.ig_names[self.ig_ids.index(char_id)]
        return None

    def char_id_by_name(self, char_name) -> int | None:
        """Fetch a player or their accounts character id by name. Returns None if char not found"""
        if char_name in self.ig_names:
            return self.ig_ids[self.ig_names.index(char_name)]
        return None

    @property
    def current_ig_id(self):
        if self.online_id:
            return self.online_id
        elif self.account:
            return self.account.online_id
        else:
            return False

    @property
    def current_faction(self):
        if self.online_id:
            return cfg.factions[self.ig_ids.index(self.online_id) + 1]
        elif self.account and self.account.online_id:
            return cfg.factions[self.account.ig_ids.index(self.account.online_id) + 1]
        else:
            return False

    @property
    def lobby_timeout_stamp(self):
        return self.__lobby_timeout_stamp

    @property
    def lobbied_stamp(self):
        return self.__lobbied_stamp

    @property
    def lobby(self):
        return self.__lobby

    def on_lobby_add(self, lobby, timeout_at):
        self.__lobby_timeout_stamp = timeout_at
        self.__lobbied_stamp = tools.timestamp_now()
        self.__lobby = lobby

    def set_lobby_timeout(self, timeout_at):
        self.__lobby_timeout_stamp = timeout_at

    def on_lobby_leave(self):
        self.__lobby_timeout_stamp = 0
        self.__lobbied_stamp = 0
        self.__lobby = None

    def set_account(self, account: Account | None):
        self.__account = account

    def on_playing(self, match):
        self.__match = match
        self.__active = ActivePlayer(self)
        return self.__active

    def on_quit(self):
        self.__match = None
        self.__active = None
        return self

    async def clean(self):
        """Remove all player commitments """
        if self.account:
            from modules.accounts_handler import terminate
            await terminate(self.account)
        if self.match:
            await self.match.leave_match(self.active)
        if self.lobby:
            await self.lobby.lobby_leave(self)

    async def register(self, char_list: list | None) -> bool:
        """
        Register the player with char_list, if no char list register as no account.

        :param char_list: Single generic char, or factioned character list to be registered with.
        :return: Whether registration was updated
        """
        # No account
        if char_list is None:
            if self.__has_own_account:
                # Player had in game data, remove now
                Player.name_check_remove(self)

                self.__ig_names = ["N/A", "N/A", "N/A", "N/A"]
                self.__ig_ids = [0, 0, 0, 0]
                self.__has_own_account = False

                # update db
                await self.db_update('account')
                log.info(f"{self.name} changed registration to no account")
                return True
            elif not self.__is_registered:  # if player wasn't registered, register
                self.__is_registered = True
                log.info(f"{self.name} registered with no account")
                await self.db_update('register')
                return True
            else:
                return False

        else:
            if not await self._add_characters(char_list):
                return False
            else:

                if not self.__is_registered:
                    self.__is_registered = True
                    await self.db_update('register')
                    log.info(f"{self.name} registered with {self.__ig_names, self.ig_names}")
                    return True
                await self.db_update('account')
                log.info(f"{self.name} changed registration to {self.__ig_names, self.ig_names}")
                return True

    async def _add_characters(self, char_list: list) -> bool:
        """
        Checks a list of chars provided for faction and world, adds them to the player object.
        :param char_list: list of chars to check and add. Must either be 3/4 faction specific chars,
         or one generic char name.
        :return: True if characters updated, false if not
        """
        # if only one char name, add suffixes.
        if len(char_list) == 1:
            char_name = char_list[0]
            if char_name[-2:].lower() in ['vs', 'nc', 'tr', 'ns']:
                char_name = char_name[:-2]
            char_list = [char_name + 'VS', char_name + 'NC', char_name + 'TR', char_name + 'NS']

        updated = False
        new_names = ["N/A", "N/A", "N/A", "N/A"]
        new_ids = [0, 0, 0, 0]

        for char in char_list:
            char_info = await census.get_char_info(char)
            if not char_info:
                if "NS" == char[-2:]:  # skip CharNotFound if char is NS
                    continue
                raise CharNotFound(char)
            char_name, char_id, faction, world_id = [char_info[i] for i in range(4)]
            # check world
            if world_id != WORLD_ID:
                raise CharInvalidWorld(char)
            # check if char already registered
            if char_id in Player._name_checking[faction - 1]:
                p = Player._name_checking[faction - 1][char_id]
                if p != self:
                    raise CharAlreadyRegistered(p, char_name)
            # check if char ID matches FSBot account chars
            from modules.accounts_handler import account_char_ids
            if account := account_char_ids.get(char_id):
                raise CharBotAccount(account, char_name)

            # skip if a character was already found for this faction (NS named duplicates)
            if new_ids[faction - 1] != 0:
                continue

            # add id and name to list
            new_ids[faction - 1] = char_id
            new_names[faction - 1] = char_name

            # change updated if updated
            updated = updated or new_ids[faction - 1] != self.__ig_ids[faction - 1]

        # check one char per faction submitted. NS optional
        for i in range(4):
            if new_ids[i] == 0 and i != 3:
                raise CharMissingFaction(cfg.factions[i + 1])

        if updated:
            if self.has_own_account:
                Player.name_check_remove(self)
            self.__ig_names = new_names.copy()
            self.__ig_ids = new_ids.copy()
            Player.name_check_add(self)
            self.__has_own_account = True

        return updated


class ActivePlayer:
    """
    ActivePlayer class has added attributes and methods relevant to their current match.
    Called after a player starts a match
    """

    @classmethod
    async def get(cls, p_id):
        """Returns a Players ActivePlayer instance from ID.
        Returns none if player is not active or player doesn't exist"""
        p = Player.get(p_id)
        if p:
            return p.active
        return None

    def __init__(self, player: Player):
        self.__player = player
        self.assigned_faction_id = None
        # TODO None of the below are used, remove or refactor??
        self.round_wins = 0
        self.round_losses = 0
        self.match_win = None

    @property
    def player(self):
        return self.__player

    @property
    def match(self):
        return self.__player.match

    @property
    def has_own_account(self):
        return self.__player.has_own_account

    @property
    def account(self):
        return self.__player.account

    @property
    def id(self):
        return self.__player.id

    @property
    def name(self):
        return self.__player.name

    @property
    def mention(self):
        return self.__player.mention

    @property
    def get_member(self):
        return self.__player.get_member

    @property
    def ig_names(self):
        if self.player.has_own_account:
            return self.player.ig_names
        elif self.account:
            return self.account.ig_names
        else:
            return False

    @property
    def ig_ids(self):
        if self.player.has_own_account:
            return self.player.ig_ids
        elif self.account:
            return self.account.ig_ids
        else:
            return False

    @property
    def online_id(self):
        return self.player.online_id

    @property
    def online_name(self):
        return self.player.online_name

    @property
    def current_ig_id(self):
        return self.player.current_ig_id

    @property
    def current_faction(self):
        return self.player.current_faction

    @property
    def on_assigned_faction(self):
        return self.current_faction == self.assigned_faction_abv

    @property
    def assigned_faction_abv(self):
        if self.assigned_faction_id:
            return cfg.factions[self.assigned_faction_id]
        return "NO FACTION"

    @property
    def assigned_faction_char(self):
        if not self.has_own_account and not self.account:
            return "NO ACCOUNT"
        return self.ig_names[self.assigned_faction_id - 1]

    @property
    def assigned_char_display(self):
        """Gives a string with <FactionEmoji><AssignedCharacter>"""
        if not self.assigned_faction_id:
            return "NO FACTION"
        return f"{cfg.emojis[self.assigned_faction_abv]}{self.assigned_faction_char}"

    @property
    def assigned_faction_display(self):
        """Returns string of Player Name / Faction String / Faction Emoji / Assigned Character string"""
        if not self.assigned_faction_id:
            return f"{self.name} has no Faction Assigned!"
        return f"{self.name}({self.assigned_faction_abv}" + \
            f"{cfg.emojis[self.assigned_faction_abv]}{self.assigned_faction_char})"

    def on_quit(self):
        return self.player.on_quit()

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


class SkillLevel(Enum):
    # skill levels to be self perscribed
    BEGINNER = (0, "Still learning how to handle an ESF, much less duel one")
    NOVICE = (1, "Has the basics down, but still working on tuning skills")
    PROFICIENT = (2, "Capable of taking on all but the most skilled pilots")
    EXPERT = (3, "Peak skill, effortlessly lead targets while dodging")

    def __str__(self):
        first = self.name[0]
        rest = self.name[1:].lower()
        return first + rest

    @property
    def rank(self):
        return self.value[0]

    @property
    def description(self):
        return self.value[1]

    def sort(self):
        return self.value[0]


class CharInvalidWorld(Exception):
    def __init__(self, char):
        self.char = char
        super().__init__(f'{char} is from the wrong world')


class CharAlreadyRegistered(Exception):
    def __init__(self, player, char):
        self.player = player
        self.char = char
        super().__init__(f'{char} already registered by {player.name}')


class CharMissingFaction(Exception):
    def __init__(self, faction):
        self.faction = faction
        super().__init__(f'Missing character from faction: {faction}')


class CharNotFound(Exception):
    def __init__(self, char):
        self.char = char
        super().__init__(f'{char} not found in the Census API')


class Player:
    """Base Player Class, one for every registered user
    """

    _all_players = dict()
    _name_checking = [dict(), dict(), dict()]

    @classmethod
    def get(cls, p_id):
        player: Player = cls._all_players.get(p_id)
        return player

    def remove(self):
        if self.__has_own_account:
            Player.name_check_remove(self)
        del Player._all_players[self.__id]

    @classmethod
    def name_check_add(cls, p):
        for i in range(3):
            cls._name_checking[i][p.ig_ids[i]] = p

    @classmethod
    def name_check_remove(cls, p):
        for i in range(3):
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
        self.__ig_names = ["N/A", "N/A", "N/A"]
        self.__ig_ids = [0, 0, 0]
        self.online_id = None
        self.__is_registered = False
        self.__hidden = False
        self.__timeout = 0
        self.__lobbied_timestamp = 0
        self.__first_lobbied_timestamp = 0
        self.__active = None
        self.__match = None
        self.skill_level: SkillLevel = SkillLevel.BEGINNER
        self.pref_factions: list[str] = []
        self.req_skill_levels = None
        Player._all_players[p_id] = self  # adding to all players dictionary

    @classmethod
    def new_from_data(cls, data):  # make player object from database data
        obj = cls(data['_id'], data['name'])
        obj.__is_registered = data['is_registered']
        obj.skill_level = SkillLevel[data['skill_level']]

        if 'ig_ids' in data:
            obj.__has_own_account = True
            obj.__ig_names = data['ig_names']
            obj.__ig_ids = data['ig_ids']
            Player.name_check_add(obj)
        else:
            obj.__has_own_account = False
            obj.__ig_names = ["N/A", "N/A", "N/A"]
            obj.__ig_ids = [0, 0, 0]
        if 'timeout' in data:
            obj.__timeout = data['timeout']
        if 'hidden' in data:
            obj.__hidden = data['hidden']
        if 'pref_factions' in data:
            obj.pref_factions = data['pref_factions']
        if 'req_skill_levels' in data:
            obj.req_skill_levels = [SkillLevel[level] for level in data['req_skill_levels']]

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
        return data

    async def db_update(self, arg):
        '''Update a specific uers database element.  Options are name, register, account, timeout,
         skill_level, req_skill_levels, pref_factions, pref_factions, hidden: '''
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
                await db.async_db_call(db.set_field, 'users', self.id, {'req_skill_levels': [level.name for level in self.req_skill_levels]})
            case 'pref_factions':
                await db.async_db_call(db.set_field, 'users', self.id, {'pref_factions': self.pref_factions})
            case 'hidden':
                await db.async_db_call(db.set_field, 'users', self.id, {'hidden': self.__hidden})
            case _:
                raise KeyError(f"No field {arg} found")

    @property
    def name(self):
        return self.__name

    @property
    def id(self):
        return self.__id

    @property
    def mention(self):
        return f"<@{self.__id}>"

    @property
    def ig_names(self):
        return self.__ig_names

    @property
    def ig_ids(self):
        return self.__ig_ids

    @property
    def is_registered(self):
        return self.__is_registered

    @property
    def has_own_account(self):
        return self.__has_own_account

    @property
    def account(self):
        return self.__account

    @property
    def timeout(self):
        return self.__timeout

    @timeout.setter
    def timeout(self, time):
        self.__timeout = time

    @property
    def is_timeout(self):
        return self.__timeout > datetime.now().timestamp()

    def hidden(self):
        return self.__hidden

    @property
    def match(self):
        return self.__match

    @property
    def active(self):
        return self.__active

    @property
    def online_name(self):
        if self.online_id:
            return self.ig_names[self.ig_ids.index(self.online_id)]
        elif self.account and self.account.online_id:
            return self.account.ig_names[self.account.ig_ids.index(self.account.online_id)]
        else:
            return False

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
    def lobbied_timestamp(self):
        return self.__lobbied_timestamp

    @property
    def first_lobbied_timestamp(self):
        return self.__first_lobbied_timestamp

    @property
    def is_lobbied(self):
        return self.__lobbied_timestamp != 0

    def on_lobby_add(self):
        self.__lobbied_timestamp = tools.timestamp_now()
        self.__first_lobbied_timestamp = tools.timestamp_now()

    def reset_lobby_timestamp(self):
        self.__lobbied_timestamp = tools.timestamp_now()

    def on_lobby_leave(self):
        self.__lobbied_timestamp = 0
        self.__first_lobbied_timestamp = 0

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

                self.__ig_names = ["N/A", "N/A", "N/A"]
                self.__ig_ids = [0, 0, 0]
                self.__has_own_account = False

                # update db
                await self.db_update('account')
                return True
            elif not self.__is_registered:  # if player wasn't registered, register
                self.__is_registered = True
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
                    return True
                await self.db_update('account')
                return True

    async def _add_characters(self, char_list: list) -> bool:
        """
        Checks a list of chars provided for faction and world, adds them to the player object.
        :param char_list: list of chars to check and add. Must either be 3 factioned chars, or one generic char name.
        :return: True if characters updated, false if not
        """
        # if only one char name, add suffixes.
        if len(char_list) == 1:
            char_name = char_list[0]
            if char_name[-2].lower() in ['vs', 'nc', 'tr']:
                char_name = char_name[:-2]
            char_list = [char_name + 'VS', char_name + 'NC', char_name + 'TR']

        updated = False
        new_names = ["N/A", "N/A", "N/A"]
        new_ids = [0, 0, 0]

        for char in char_list:
            char_info = await census.get_char_info(char)
            if not char_info:
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

            # add id and name to list
            new_ids[faction - 1] = char_id
            new_names[faction - 1] = char_name

            # change updated if updated
            updated = updated or new_ids[faction - 1] != self.__ig_ids[faction - 1]

        # check one char per faction submitted
        for i in range(3):
            if new_ids[i] == 0:
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
    def __init__(self, player: Player):
        self.__player = player
        self.__match = player.match
        self.__account = player.account
        self.online_id = player.online_id
        self.round_wins = 0
        self.round_losses = 0
        self.match_win = None

    @property
    def player(self):
        return self.__player

    @property
    def match(self):
        return self.__match

    @property
    def account(self):
        return self.__account

    @property
    def id(self):
        return self.__player.id

    @property
    def name(self):
        return self.__player.name

    @property
    def mention(self):
        return self.player.mention

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
    def online_name(self):
        return self.player.online_name

    @property
    def current_ig_id(self):
        return self.player.current_ig_id


    @property
    def current_faction(self):
        return self.player.current_faction

    def on_quit(self):
        return self.player.on_quit()

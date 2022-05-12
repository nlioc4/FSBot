'''
Player Classes, representing registered users, and related methods
'''

import modules.config as cfg


from logging import getLogger
import re

log = getLogger("fs_Bot")

WORLD_ID = 19  # Jaeger ID






class Player:
    """Base Player Class, one for every registered user
    """

    _all_players = dict()


    def __init__(self, p_id, name):
        if not re.match(cfg.name_regex, name):
            name = "N/A"
        self.__name = name
        self.__id = p_id
        self.__ig_names = ["N/A", "N/A", "N/A"]
        self.__ig_ids = [0, 0, 0]
        self.__is_registered = False
        self.__has_own_account = False
        Player._all_players[p_id] = self  # adding to all players dictionary


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




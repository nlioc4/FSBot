"""Stats object to store player history, elo, and other stats"""

# External Imports
from logging import getLogger

# Internal Imports
import modules.database as db

log = getLogger('fs_bot')


class PlayerStats:

    @classmethod
    async def get_from_db(cls, p_id, p_name):
        data = await db.async_db_call(db.get_element, 'player_stats', p_id)
        return cls(p_id, p_name, data=data)

    def __init__(self, p_id, p_name, data=None):
        self.__id = p_id
        self.__name = p_name
        if data:
            self.__match_ids = data['matches']
            self.__elo_history = data['elo_history']
            self.__elo = data['elo']
            self.__match_wins = data['match_wins']
            self.__match_losses = data['match_losses']

        else:
            self.__match_ids = list()
            self.__elo_history = dict()  # Dict of elo changes, by match_id: eloDelta
            self.__elo = 1000
            self.__match_wins = 0
            self.__match_losses = 0

    def get_data(self):
        data = dict()
        data['_id'] = self.__id
        data['matches'] = self.__match_ids
        data['elo_history'] = self.__elo_history
        data['elo'] = self.__elo
        data['match_wins'] = self.__match_wins
        data['match_losses'] = self.__match_losses
        return data

    async def push_to_db(self):
        data = self.get_data()
        await db.async_db_call(db.set_element, 'player_stats', {self.__id: data})

    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        return self.__name

    @property
    def matches(self):
        return self.__match_ids

    @property
    def elo_history(self):
        return self.__elo_history

    @property
    def match_wins(self):
        return self.__match_wins

    @property
    def match_losses(self):
        return self.__match_losses

    @property
    def elo(self):
        return self.__elo

    def add_match(self, match_id, new_elo, match_won):
        self.__match_ids.append(match_id)
        elo_delta = new_elo - self.__elo
        self.__elo_history[match_id] = elo_delta
        if match_won:
            self.__match_wins += 1
        else:
            self.__match_losses += 1







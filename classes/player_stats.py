"""Stats object to store player history, elo, and other stats"""

# External Imports
from logging import getLogger

# Internal Imports
import modules.database as db
import modules.config as cfg

log = getLogger('fs_bot')


class PlayerStats:

    @classmethod
    async def get_from_db(cls, p_id, p_name):
        """Retrieve data for PlayerStats object from database.
        If no data exists, creates new PlayerStats object."""
        data = await db.async_db_call(db.get_element, cfg.database['collections']['user_stats'], p_id)
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
            self.__match_draws = data['match_draws']

        else:
            self.__match_ids: list[str] = list()  # list of Int match ID's
            self.__elo_history: dict[str, float] = dict()  # Dict of elo changes, by match_id: eloDelta
            self.__elo: float = 1000  # Players Elo
            self.__match_wins = 0  # Number of Matches Won
            self.__match_losses = 0  # Number of Matches lost
            self.__match_draws = 0  # Number of Matches Drawn

    def get_data(self):
        data = {
            '_id': self.__id,
            'matches': self.__match_ids,
            'elo_history': self.__elo_history,
            'elo': self.__elo,
            'match_wins': self.__match_wins,
            'match_losses': self.__match_losses,
            'match_draws': self.__match_draws
        }
        return data

    async def push_to_db(self):
        data = self.get_data()
        await db.async_db_call(db.set_element, cfg.database['collections']['user_stats'], self.__id, data)

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
    def match_draws(self):
        return self.__match_draws

    @property
    def elo(self):
        return self.__elo

    @property
    def int_elo(self):
        return int(self.__elo)

    def add_match(self, match_id, elo_delta, result):
        """Add a match to a player stats set.
        Result should be 1 if match won, 0.5 if match drawn, or 0 if match lost"""
        self.__match_ids.append(str(match_id))
        self.__elo_history[str(match_id)] = elo_delta
        self.__elo = self.__elo + elo_delta
        if result > 0.5:
            self.__match_wins += 1
        if result == 0.5:
            self.__match_draws += 1
        if result < 0.5:
            self.__match_losses += 1

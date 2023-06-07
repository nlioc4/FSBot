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

    def __init__(self, p_id, p_name, data: dict | None = None):
        self.__id = p_id
        self.__name = p_name
        if data:
            self.__match_ids = data.get('matches', list())
            self.__elo_history = data.get('elo_history', dict())
            self.__elo = data.get('elo', 1000)
            self.__match_wins = data.get('match_wins', 0)
            self.__match_losses = data.get('match_losses', 0)
            self.__match_draws = data.get('match_draws', 0)
            self.__nc_round_wins = data.get('nc_round_wins', 0)
            self.__tr_round_wins = data.get('tr_round_wins', 0)
            self.__nc_round_losses = data.get('nc_round_losses', 0)
            self.__tr_round_losses = data.get('tr_round_losses', 0)

        else:
            self.__match_ids: list[str] = list()  # list of Int match ID's
            self.__elo_history: dict[str, float] = dict()  # Dict of elo changes, by match_id: eloDelta
            self.__elo: float = 1000  # Players Elo
            self.__match_wins = 0  # Number of Matches Won
            self.__match_losses = 0  # Number of Matches lost
            self.__match_draws = 0  # Number of Matches Drawn
            self.__nc_round_wins = 0  # Number of Rounds Won as NC
            self.__tr_round_wins = 0  # Number of Rounds Won as TR
            self.__nc_round_losses = 0  # Number of Rounds Lost as NC
            self.__tr_round_losses = 0  # Number of Rounds Lost as TR

    def _get_data(self):
        data = {
            '_id': self.__id,
            'matches': self.__match_ids,
            'elo_history': self.__elo_history,
            'elo': self.__elo,
            'match_wins': self.__match_wins,
            'match_losses': self.__match_losses,
            'match_draws': self.__match_draws,
            'nc_round_wins': self.__nc_round_wins,
            'tr_round_wins': self.__tr_round_wins,
            'nc_round_losses': self.__nc_round_losses,
            'tr_round_losses': self.__tr_round_losses
        }
        return data

    async def push_to_db(self):
        data = self._get_data()
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
    def total_matches(self):
        return len(self.__match_ids)

    @property
    def nc_round_wins(self):
        return self.__nc_round_wins

    @property
    def tr_round_wins(self):
        return self.__tr_round_wins

    @property
    def total_round_wins(self):
        return self.__nc_round_wins + self.__tr_round_wins

    @property
    def nc_round_losses(self):
        return self.__nc_round_losses

    @property
    def tr_round_losses(self):
        return self.__tr_round_losses

    @property
    def total_round_losses(self):
        return self.__nc_round_losses + self.__tr_round_losses

    @property
    def total_nc_rounds(self):
        return self.__nc_round_wins + self.__nc_round_losses

    @property
    def total_tr_rounds(self):
        return self.__tr_round_wins + self.__tr_round_losses

    @property
    def elo(self):
        return self.__elo

    @property
    def int_elo(self):
        return int(self.__elo)

    @property
    def last_five_changes(self):
        """Helper to return list of last five match results w/ match ID.  Tuples of (match_id, elo_delta)"""
        last_five = dict()
        for match_id in self.__match_ids[-5:]:
            last_five[match_id] = self.__elo_history[match_id]
        return last_five.items()

    def add_match(self, match, elo_delta):
        """Add a match to a player stats set.
        Result should be >0.5 if match won, 0.5 if match drawn, or 0.5> if match lost"""
        from classes.match import RankedMatch
        match: RankedMatch

        if match.player1.id == self.__id:
            result = match.player1_result
        elif match.player2.id == self.__id:
            result = match.player2_result
        else:
            log.error(f'Player {self.__id} not in match {match.id}')
            return

        self.__match_ids.append(str(match.id))
        self.__elo_history[str(match.id)] = elo_delta
        self.__elo = self.__elo + elo_delta

        for match_round in match.round_history:
            if match_round.winner_faction == 'NC':
                if match_round.winner_id == self.__id:
                    self.__nc_round_wins += 1
                else:
                    self.__tr_round_losses += 1
            elif match_round.winner_faction == 'TR':
                if match_round.winner_id == self.__id:
                    self.__tr_round_wins += 1
                else:
                    self.__nc_round_losses += 1

        if result > 0.5:
            self.__match_wins += 1
        elif result == 0.5:
            self.__match_draws += 1
        elif result < 0.5:
            self.__match_losses += 1

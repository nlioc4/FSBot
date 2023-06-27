"""This file handles updating / displaying ELO ranks for players, in the form of a discord embed leaderboard.


    Elo Ranks Plan:
    4 Ranks:
        - Unranked: Less than 5 ranked matches played (but still at least 1), default threshold of 0 ELO

        Below Ranks require 5 ranked matches played minimum:
        - Bronze: Below 80th Percentile
        - Silver: 80th Percentile
        - Gold: 95th Percentile

    Leaderboard Updates: (8:00 AM UTC)
     - Update all player ranks
     - Recalculate elo thresholds for each rank, based on percentile


"""

# External Imports
from logging import getLogger
import discord
import numpy as np
import asyncio

# Internal Imports
import modules.database as db
import modules.config as cfg
import modules.tools as tools
from classes.player_stats import PlayerStats
import modules.discord_obj as d_obj
from classes import Player

log = getLogger('fs_bot')


class EloRank:
    """Class to hold data for a single elo rank
    name: Name of the rank
    elo_threshold: Minimum elo required to be in this rank
    matches_threshold: Minimum number of matches required to be in this rank
    percentile: Percentile threshold for this rank"""
    _all_ranks = dict()  # Dict of EloRank objects, by name

    def __init__(self, name: str, elo_threshold: int, matches_threshold: int, percentile_threshold: int):
        self.name = name
        self.elo_threshold = elo_threshold
        self.matches_threshold = matches_threshold
        self.percentile_threshold = percentile_threshold
        self._all_ranks[name] = self

    def __repr__(self):
        return f'{self.name}: Elo: {self.elo_threshold}, Matches: {self.matches_threshold}, ' \
               f'Percentile: {self.percentile_threshold}'

    @classmethod
    def get(cls, name: str):
        """Retrieve EloRank object from memory"""
        return cls._all_ranks.get(name)

    @classmethod
    def get_all(cls):
        """Retrieve all EloRank objects from memory"""
        return cls._all_ranks.values()

    @classmethod
    def get_by_int_repr(cls, int_repr: int):
        """Retrieve EloRank object from memory, by int_repr"""
        for rank in cls._all_ranks.values():
            if rank.int_repr == int_repr:
                return rank
        return None


# Create EloRank objects for each rank
EloRank("Gold", 1500, 5, 95)
EloRank("Silver", 1200, 5, 80)
EloRank("Bronze", 1000, 5, 40)
EloRank("Unranked", 0, 0, 0)


async def get_elo_rankings() -> list[PlayerStats]:
    """Retrieve all PlayerStats objects from database, sort by elo, return list"""
    await PlayerStats.get_all_from_db()
    return PlayerStats.get_all_sorted()


async def update_rank_thresholds():
    """Update the elo thresholds for each rank, based on the percentile threshold"""
    player_stats = await get_elo_rankings()  # Get all player stats

    # Create np array of all player elos, tied to player ID
    player_elos = np.array([(p_stats.elo, p_stats.id) for p_stats in player_stats])

    # Set the elo thresholds for each rank based on percentile
    for rank in EloRank.get_all():
        if rank.name == "Unranked":  # Don't change unranked threshold
            continue
        rank_percentile = rank.percentile_threshold
        rank.elo_threshold = np.percentile(player_elos[:, 0], rank_percentile)
        log.debug(f'{rank} threshold set to {rank.elo_threshold} based on {rank_percentile}th percentile')


async def update_player_ranks(player_stats=None):
    """Update the rank for each player_stats object in the list, based on their elo"""
    if player_stats is None:
        player_stats = []
    await update_rank_thresholds()  # Update the elo thresholds for each rank, based on the percentile threshold
    update_coroutines = []
    if not player_stats:
        player_stats = PlayerStats.get_all_sorted()
    for player_stat in player_stats:
        if 5 > player_stat.total_matches > 0:
            player_stat.update_rank(EloRank.get("Unranked").name)
        else:
            for rank in EloRank.get_all():
                if player_stat.elo >= rank.elo_threshold and \
                        player_stat.total_matches >= rank.matches_threshold:
                    player_stat.update_rank(rank.name)
                    break
        update_coroutines.append(player_stat.push_to_db())

    await asyncio.gather(*update_coroutines)


def create_rank_dict() -> dict:
    """
    Create a dictionary of lists of player_stats, sorted by rank
    """
    player_stats = PlayerStats.get_all_sorted()
    rank_array = np.array([(p_stats.rank, p_stats) for p_stats in player_stats])
    rank_dict = {}
    for rank in EloRank.get_all():
        rank_dict[rank.name] = rank_array[rank_array[:, 0] == rank.name, 1].tolist()

    return rank_dict

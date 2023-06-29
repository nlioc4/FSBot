"""Handles ELO calculation for the rest of the Bot"""

# External Imports
from logging import getLogger
import asyncio

# Internal Imports
from classes.player_stats import PlayerStats
from modules import config as cfg

K_FACTOR = 30
SCALE_FACTOR = 400


def _get_player_win_expectation(player_rating, opponent_rating):
    return (1 + 10 ** ((opponent_rating - player_rating) / SCALE_FACTOR))**-1


def _new_player_rating(player_rating, player_win_expect, results):
    return player_rating + _player_rating_delta(player_win_expect, results)


def _player_rating_delta(player_win_expect, results):
    return K_FACTOR * (results - player_win_expect)


async def update_elo(match) -> tuple[float, float]:
    """Update PlayerStats for a specific match, return Elo Deltas """
    from classes.match import RankedMatch
    match: RankedMatch

    player1_win_xpt = _get_player_win_expectation(match.player1_stats.elo, match.player2_stats.elo)
    player2_win_xpt = _get_player_win_expectation(match.player2_stats.elo, match.player1_stats.elo)

    player1_elo_delta = _player_rating_delta(player1_win_xpt, match.player1_result)
    player2_elo_delta = _player_rating_delta(player2_win_xpt, match.player2_result)

    if cfg.DISABLE_ELO_LOSS_ON_WIN:
        if match.player1_result > 0.5 and player1_elo_delta < 0:
            player1_elo_delta = 0
        if match.player2_result > 0.5 and player2_elo_delta < 0:
            player2_elo_delta = 0

    #  update player_stats
    match.player1_stats.add_match(match, player1_elo_delta)
    match.player2_stats.add_match(match, player2_elo_delta)
    await asyncio.gather(match.player1_stats.push_to_db(), match.player2_stats.push_to_db())

    return player1_elo_delta, player2_elo_delta



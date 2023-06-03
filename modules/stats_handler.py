"""Handles ELO calculation for the rest of the Bot"""

# External Imports
from logging import getLogger
import asyncio

# Internal Imports
from classes.player_stats import PlayerStats

K_FACTOR = 40
SCALE_FACTOR = 400


def _get_player_win_expectation(player_rating, opponent_rating):
    numerator = 1 + 10 ** ((opponent_rating - player_rating) / SCALE_FACTOR)
    return 1 / numerator


def _new_player_rating(player_rating, player_win_expect, results):
    return player_rating + _player_rating_delta(player_win_expect, results)


def _player_rating_delta(player_win_expect, results):
    return K_FACTOR * (results - player_win_expect)


async def update_elo(player1: PlayerStats, player2: PlayerStats, match_id, result, required_wins):
    """Update PlayerStats for a specific match, return Elo Deltas """
    player1_win_xpt = _get_player_win_expectation(player1.elo, player2.elo)
    player2_win_xpt = _get_player_win_expectation(player2.elo, player1.elo)


    if result == 0:
        player1_result = 0.5
        player2_result = 0.5
    else:
        player1_result = result / required_wins if result > 0 else (1 + result / required_wins)
        player2_result = -result / required_wins if result < 0 else (1 + -result / required_wins)

    player1_elo_delta = _player_rating_delta(player1_win_xpt, player1_result)
    player2_elo_delta = _player_rating_delta(player2_win_xpt, player2_result)

    #  update player_stats
    player1.add_match(match_id, player1_elo_delta, player1_result)
    player2.add_match(match_id, player2_elo_delta, player2_result)
    await asyncio.gather(player1.push_to_db(), player2.push_to_db())

    return player1_elo_delta, player2_elo_delta



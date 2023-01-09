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
    return player_rating + (K_FACTOR * (results - player_win_expect))

def _player_rating_delta(player_rating, player_win_expect, results):
    return K_FACTOR * (results - player_win_expect)




async def update_elo(player1: PlayerStats, player2: PlayerStats, match_id, result, match_length=8):
    """Update PlayerStats for a specific match, return updated PlayerStats """
    player1_win_xpt = _get_player_win_expectation(player1.elo, player2.elo)
    player2_win_xpt = _get_player_win_expectation(player2.elo, player1.elo)

    wins_req = match_length // 2 + 1

    if result == 0:
        player1_result = 0.5
        player2_result = 0.5
    else:
        player1_result = result/wins_req if result > 0 else (1 + result/wins_req)
        player2_result = -result/wins_req if result < 0 else (1 + -result/wins_req)

    player1_new_elo = _new_player_rating(player1.elo, player1_win_xpt, player1_result)
    player2_new_elo = _new_player_rating(player2.elo, player2_win_xpt, player2_result)



    #  update player_stats
    player1.add_match(match_id, player1_new_elo, player1_result)
    player2.add_match(match_id, player2_new_elo, player2_result)
    await asyncio.gather(player1.push_to_db(), player2.push_to_db())


    return player1, player2


"""Handles ELO calculation for the rest of the Bot"""

# External Imports
from logging import getLogger
import math

# Internal Imports
from classes.player_stats import PlayerStats
import modules.database as db

K_FACTOR = 40
SCALE_FACTOR = 400


def _get_player_win_expectation(player_rating, opponent_rating):
    numerator = 1 + 10 ** ((opponent_rating - player_rating) / SCALE_FACTOR)
    return 1 / numerator


def _new_player_rating(player_rating, player_win_expect, results):
    return player_rating + (K_FACTOR * (results - player_win_expect))


def _get_player_score(player, match_length):
    round_score_base = (match_length // 2) + 1
    player_net_wins = player.round_wins - player.round_losses
    player_score = 0.5 + (player_net_wins / round_score_base) / 2
    return player_score


async def update_elo(player1: 'classes.ActivePlayer', player2: 'classes.ActivePlayer', match_id, match_length=7):
    player1_stats = await PlayerStats.get_from_db(player1.id, player1.name)
    player2_stats = await PlayerStats.get_from_db(player2.id, player2.name)

    player1_win_xpt = _get_player_win_expectation(player1_stats.elo, player2_stats.elo)
    player2_win_xpt = _get_player_win_expectation(player2_stats.elo, player1_stats.elo)

    player1_score = _get_player_score(player1, match_length)
    player2_score = _get_player_score(player2, match_length)

    player1_new_elo = _new_player_rating(player1_stats.elo, player1_win_xpt, player1_score)
    player2_new_elo = _new_player_rating(player2_stats.elo, player2_win_xpt, player2_score)

    #  Determine Match Winner
    match_winner = None
    if player2_score > player1_score:
        player2.match_win = True
        player1.match_win = False
        match_winner = player2
    if player1_score > player2_score:
        player2.match_win = False
        player1.match_win = True
        match_winner = player1

    #  update player_stats
    player1_stats.add_match(match_id, player1_new_elo, player1.match_win)
    player2_stats.add_match(match_id, player2_new_elo, player2.match_win)
    await player1_stats.push_to_db()
    await player2_stats.push_to_db()

    return player1_stats, player2_stats, match_winner

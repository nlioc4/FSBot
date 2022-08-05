"""Modules to handle updating the bot's Activity status with various info"""

# External Imports
from logging import getLogger
import discord

import modules.tools as tools

_client: discord.Bot | None = None
matches = []
lobbies = []
current_activity = discord.Game(name="")
current_status = discord.Status.idle


#  TODO implement

def init(client):
    """Initialize the module by providing the discord bot client"""
    global _client
    _client = client


def _get_new_activity():
    lobby_str = '**Current Lobbbies:**\n'
    for lobby in lobbies:
        num_p = len(lobby.lobbied)
        lobby_str += f"{lobby.name}: {num_p} {'players' if num_p != 1 else 'player'}\n"

    match_str = '**Current Matches:**\n'
    for match in matches:
        num_p = len(match.players)
        match_str += f"[{match.id_str}]: {match.owner} {num_p} {'players' if num_p != 1 else 'player'}\n"

    global current_activity
    current_activity.name = lobby_str + match_str


def _get_new_status():
    global current_status
    if [match.players for match in matches] or [lobby.lobbied for lobby in lobbies]:
        current_status = discord.Status.online
    else:
        current_status = discord.Status.idle


async def update_status():
    _get_new_status()
    _get_new_activity()
    await _client.change_presence(activity=current_activity, status=current_status)


async def toggle_match(match):
    global matches
    if match not in matches:
        matches.append(match)
    else:
        matches.remove(match)
    await update_status()


async def toggle_lobby(lobby):
    global lobbies
    if lobby not in lobbies:
        lobbies.append(lobby)
    else:
        lobbies.remove(lobby)
    await update_status()


def check(obj):
    """check if an object is in either matches or lobbies"""
    return obj in matches or obj in lobbies

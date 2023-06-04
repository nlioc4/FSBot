"""Module to handle updating the Bot's Activity status with various info"""

# External Imports
import discord

# Internal Imports
import modules.discord_obj as d_obj
from classes.match import BaseMatch
from classes.lobby import Lobby

updated = True
current_activity = discord.Game(name="")
current_status = discord.Status.idle


def _get_new_activity():
    num_p = sum([len(lobby.lobbied) for lobby in Lobby.all_lobbies.values()])
    lobby_str = f"with {num_p} {'players' if num_p != 1 else 'player'} in lobby"

    global current_activity
    global updated
    if current_activity.name != lobby_str:  # only update if required
        updated = True
        current_activity.name = lobby_str


def _get_new_status():
    global current_status
    global updated
    if BaseMatch.active_matches_list() or sum([len(lobby.lobbied) for lobby in Lobby.all_lobbies.values()]):
        new_status = discord.Status.online
    else:
        new_status = discord.Status.idle

    if new_status != current_status:
        updated = True
        current_status = new_status


async def update_status():
    global updated
    _get_new_status()
    _get_new_activity()
    if updated:
        await d_obj.bot.change_presence(activity=current_activity, status=current_status)
        updated = False

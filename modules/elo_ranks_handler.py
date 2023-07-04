"""This file handles updating / displaying ELO ranks for players, in the form of a discord embed leaderboard.
It also handles updating the thresholds for each rank, based on the percentile threshold.
"""

# External Imports
from __future__ import annotations
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
        self.role: discord.Role | None = None
        self._all_ranks[name] = self

    def __repr__(self):
        return f'{self.name}: Elo: {self.elo_threshold}, Matches: {self.matches_threshold}, ' \
               f'Percentile: {self.percentile_threshold}'

    @classmethod
    def get(cls, name: str) -> EloRank:
        """Retrieve EloRank object from memory"""
        return cls._all_ranks.get(name)

    @classmethod
    def get_all(cls) -> [EloRank]:
        """Retrieve all EloRank objects from memory"""
        return cls._all_ranks.values()

    @property
    def mention(self):
        """Return mention for this rank, or name if no role exists"""
        if self.role:
            return self.role.mention
        return self.name



# Create EloRank objects for each rank
EloRank("Auraxium", 1500, 10, 99)
EloRank("Gold", 1500, 5, 90)
EloRank("Silver", 1200, 5, 60)
EloRank("Bronze", 1000, 5, 20)
EloRank("Unranked", 0, 1, 0)

# Define colors for each rank
ELO_RANK_COLORS = {
    "Auraxium": discord.Colour.from_rgb(84, 50, 168),
    "Gold": discord.Colour.from_rgb(238, 198, 79),
    "Silver": discord.Colour.from_rgb(170, 169, 173),
    "Bronze": discord.Colour.from_rgb(163, 102, 10)
}
# Define icons for each rank (DBG image set ID)
ELO_RANK_ICONS = {
    "Auraxium": 3068,
    "Gold": 3075,
    "Silver": 3079,
    "Bronze": 3072,
}
DBG_STATIC_URL = "https://census.daybreakgames.com/files/ps2/images/static/{}.png"


async def init_elo_ranks():
    """Create rank roles if they don't exist, set their icons.
    Also performs initial update of rank thresholds / player ranks, to ensure roles are created first"""
    for rank in EloRank.get_all():
        if rank.name == "Unranked":  # No role for unranked
            continue
        rank.role = await d_obj.get_or_create_role(f"{rank.name} Duel Rank",
                                                   colour=ELO_RANK_COLORS[rank.name],
                                                   mentionable=False,
                                                   hoist=True,
                                                   permissions=discord.Permissions.none())

        emoji = await d_obj.get_or_create_emoji(f"{rank.name}Medal",
                                                image=DBG_STATIC_URL.format(ELO_RANK_ICONS[rank.name]),
                                                roles=[rank.role])
        if not emoji:
            await d_obj.d_log(f"Couldn't create emoji for {rank.name} rank! Downloading image instead...")
            image = await tools.download_image(DBG_STATIC_URL.format(ELO_RANK_ICONS[rank.name]))
        else:
            image = await emoji.read()

        if not rank.role.icon:
            if image and "ROLE_ICONS" in d_obj.guild.features:  # Set icon if allowed and have image
                try:
                    await rank.role.edit(icon=image)
                except discord.Forbidden:
                    log.warning(f"Couldn't set icon for {rank.name} role!")
            else:
                log.info(f"Couldn't set icon for {rank.name} role! Missing image or feature unavailable.")

    await update_player_ranks()


async def update_player_rank_role(player_stat: PlayerStats):
    """Remove old rank role from player, add new rank role to player"""
    if not (p := Player.get(player_stat.id)) or not p.member:
        log.warning(f"Couldn't find player {p.id} or their Member Object in memory!")
        return

    new_rank = EloRank.get(player_stat.rank)

    for rank in EloRank.get_all():  # Remove all other rank roles from player
        if rank.role and rank.role in p.member.roles and rank is not new_rank:
            await p.member.remove_roles(rank.role)
    if new_rank.role and new_rank.role not in p.member.roles:  # Add new role if required
        await p.member.add_roles(new_rank.role)


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
        log.debug(f'{rank.name} threshold set to {rank.elo_threshold} based on {rank_percentile}th percentile')


async def update_player_ranks(player_stats=None):
    """Update the rank for each player_stats object in the list, based on their elo"""
    await update_rank_thresholds()  # Update the elo thresholds for each rank, based on the percentile threshold
    update_coroutines = []
    if not player_stats:
        player_stats = PlayerStats.get_all_sorted()
    for player_stat in player_stats:
        for rank in EloRank.get_all():
            if player_stat.elo >= rank.elo_threshold and player_stat.total_matches >= rank.matches_threshold:
                player_stat.update_rank(rank.name)
                # run every time, as change is checked in function
                update_coroutines.append(update_player_rank_role(player_stat))

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

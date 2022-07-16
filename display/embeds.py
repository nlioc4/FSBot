'''Contains Embeds and embed templates for use throughout the bot'''

# External Imports
from discord import Embed, Colour
import discord
import discord.utils

from datetime import timedelta, datetime as dt
import pytz

# Internal Imports
import modules.config as cfg
import modules.accounts_handler_simple as accounts
from modules.tools import format_time_from_stamp as format_stamp
from classes.players import Player, ActivePlayer, SkillLevel
from classes.match import BaseMatch, MatchState


# midnight tomorrow EST
eastern = pytz.timezone('US/Eastern')
midnight_eastern = (dt.now().astimezone(eastern) + timedelta(days=1)).replace(hour=0, minute=0, microsecond=0,
                                                                                    second=0)
formatted_time = discord.utils.format_dt(midnight_eastern, style="t")

_client: discord.Bot | None = None
_guild: discord.Guild | None = None


def init(client: discord.bot):
    # load discord guild
    global _client
    _client = client
    global _guild
    _guild = client.get_guild(cfg.general["guild_id"])


def bot_info() -> discord.Embed:
    """Bot Info Embed"""
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Bot Information",
        description="",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    embed.add_field(name='Loaded Accounts',
                    value=accounts.all_accounts)

    embed.add_field(name='Enabled Cogs',
                    value=_client.cogs.keys())

    return embed


def account(ctx, acc) -> discord.Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Account",
        description=f"\nYou've been assigned a Jaeger Account by {ctx.user.mention} \n"
                    f"This account is not to be used after: {formatted_time} \n",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    embed.add_field(name='Account Details',
                    value=f"DO NOT SAVE THESE DETAILS TO YOUR LAUNCHER\n"
                          f"Username: **{acc.username}**\n"
                          f"Password: **{acc.password}**\n",
                    inline=False
                    )
    embed.add_field(name="Follow all Jaeger and PREY's Flight School Rules while using this account",
                    value=
                    f"[Be careful not to interfere with other Jaeger users, "
                    f"check the calendar here]({cfg.JAEGER_CALENDAR_URL})",
                    inline=False
                    )
    return embed


def accountcheck(ctx, available, used, usages, online) -> discord.Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Accounts Info",
        description="",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    embed.add_field(name='Usage',
                    value=f"Available Accounts: **{available}**\n"
                          f"Used Accounts: **{used}**\n",
                    inline=False
                    )
    string = 'None'
    if usages:
        string = ''
        for usage in usages:
            string += f'[{usage[0]}] : {usage[1]}\n'

    embed.add_field(name='Currently Assigned Accounts',
                    value=string,
                    inline=False
                    )
    if online:
        string = '*Character Name : Last Player*\n'
        for acc in online:
            char_name = online[acc][0]
            last_player = _guild.get_member(online[acc][1])
            string = string + f'{char_name} : {last_player.mention}\n'
        embed.add_field(name='Currently Online Accounts',
                        value=string,
                        inline=False
                        )
    return embed


def account_online_check(online) -> discord.Embed:
    """Automatic Online Check Embed
    """
    embed = Embed(
        colour=Colour.red(),
        title="Unassigned Accounts Detected Online",
        description="",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    string = '*Character Name : Last Player *\n'
    for acc in online:
        char_name = online[acc][0]
        last_player = _guild.get_member(online[acc][1])
        string = string + f'{char_name} : {last_player.mention}\n'

    embed.add_field(name='Currently Online Accounts',
                    value=string,
                    inline=False
                    )
    return embed


def anomaly(world, zone, timestamp, state) -> discord.Embed:
    """Aerial Anomaly Notification Embed
    """
    colour = Colour.blurple()
    if state == "Ended":
        colour = Colour.red()

    embed = Embed(
        colour=colour,
        title="Aerial Anomaly Detected",
        description="",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    embed.set_thumbnail(url="https://i.imgur.com/Ch8QAZJ.png")

    embed.add_field(name=f'Server: {world}',
                    value=f'Continent: {zone}\nStarted: {format_stamp(timestamp, "r")}'
                          f'\nState: {state}',
                    inline=False)

    embed.add_field(name='Register',
                    value='Register in #roles',
                    inline=False)
    return embed


def duel_dashboard(lobbied_players: list[Player], logs: list[str]) -> discord.Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels.
    Base Embed, to be modified by calling method"""
    colour = Colour.blurple() if lobbied_players else Colour.greyple()

    embed = Embed(
        colour=colour,
        title="Flight School Bot Duel Dashboard",
        description="Your source for organized ESF duels",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    # Dashboard Description
    skill_level_shorthands = [f'**{level.rank}**: {str(level)}' for level in list(SkillLevel)]
    string = ''
    for i in skill_level_shorthands:
        string += f'[{i}] '
    embed.add_field(
        name='Skill Level Ranks',
        value=string,
        inline=False
    )

    # Player_list Header
    embed.add_field(
        name='----------------------Unranked Lobby----------------------',
        value='@Mention [Preferred Faction(s)][Skill Level][Wanted Level(s)][Time]\n',
        inline=False
    )
    if lobbied_players:
        players_string = ''
        for p in lobbied_players:
            preferred_facs = ''.join([cfg.emojis[fac] for fac in p.pref_factions]) if p.pref_factions else 'Any'
            req_skill_levels = ' '.join([str(level.rank) for level in p.req_skill_levels])\
                if p.req_skill_levels else 'Any'
            f_lobbied_stamp = format_stamp(p.first_lobbied_timestamp)
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}][{req_skill_levels}][{f_lobbied_stamp}]\n'
            players_string += string

        embed.add_field(name="----------------------------------------------------------------",
                        value=players_string,
                        inline=False)

    if logs:
        log_str = ''
        for log in logs:
            time_formatted = format_stamp(log[0], 'T')
            log_str += f'[{time_formatted}]{log[1]}\n'
        embed.add_field(name="Recent Activity",
                        value=log_str,
                        inline=False)
    return embed


def longer_lobby_logs(logs: list[str]) -> discord.Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels.
    Base Embed, to be modified by calling method"""

    embed = Embed(
        colour=Colour.blurple(),
        title="Flight School Bot Extended History",
        description="Your source for organized ESF duels",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    if logs:
        log_str = ''
        for log in logs:
            time_formatted = format_stamp(log[0], 'T')
            log_str += f'[{time_formatted}]{log[1]}\n'
        embed.add_field(name="Extended Recent Activity",
                        value=log_str,
                        inline=False)
    return embed


def match_info(match: BaseMatch) -> discord.Embed:
    """Match info for match channel, should go along with match control View"""
    colour = None
    match match.status:
        case MatchState.INVITING:
            colour = Colour.dark_blue()
        case MatchState.GETTING_READY:
            colour = Colour.blurple()
        case MatchState.Playing:
            colour = Colour.green()
        case MatchState.ENDED:
            colour = Colour.red()

    embed = Embed(
        colour=Colour.green(),
        title=f"Match Info for Match: {match.id}",
        description="",
        timestamp=dt.now()
    )

    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")

    match_info_str = (f"Owner: {match.owner.mention}\n"
                     f"Match status: {match.status}\n"
                     f"Match Start Time: {format_stamp(match.start_stamp)}\n"
                     )

    if match.end_stamp:
        base_info_str += f'Match End Time: {format_stamp(match.end_stamp)}'

    embed.add_field(name="Match Info",
                    value=match_info_str,
                    inline=False)

    if match.invited:
        embed.add_field(name="Invited Players",
                        value='\n'.join([p.mention for p in match.invited]),
                        inline=False
        )

    if match.invited:
        embed.add_field(name="Players",
                        value='\n'.join([p.mention for p in match.players]),
                        inline=False)


    return embed
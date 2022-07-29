'''Contains Embeds and embed templates for use throughout the bot'''

# External Imports
from discord import Embed, Colour
import discord
import discord.utils

from datetime import timedelta, datetime as dt
import pytz

# Internal Imports
import modules.config as cfg
import modules.accounts_handler as accounts
from modules.tools import format_time_from_stamp as format_stamp
from classes.players import Player, ActivePlayer, SkillLevel
from classes.match import BaseMatch, MatchState
import modules.discord_obj as d_obj


# midnight tomorrow EST
eastern = pytz.timezone('US/Eastern')
midnight_eastern = (dt.now().astimezone(eastern) + timedelta(days=1)).replace(hour=0, minute=0, microsecond=0,
                                                                                    second=0)
formatted_time = discord.utils.format_dt(midnight_eastern, style="t")


def fs_author(embed) -> discord.Embed:
    """

    :param embed: embed to modify
    :return:  discord.Embed, with author as FSBot
    """
    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")
    return embed


def account(acc) -> discord.Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Account",
        description="\nFollow all Jaeger and [PREY's Flight School Rules](https://www.google.com) while using this "
                    "account\n "
                    f"[Be careful not to interfere with other Jaeger users, "
                    f"check the calendar here]({cfg.JAEGER_CALENDAR_URL})\n"
                    f"Failure to follow these rules may result in removed access to the entire FSBot system"
    )

    if acc.is_terminated:
        embed.colour = Colour.red()
        embed.add_field(name='Account Session Ended',
                        value='This account token is no longer valid.',
                        inline=False)

    elif acc.is_validated:
        embed.colour = Colour.green()
        embed.add_field(name='Account Details',
                        value=f"DO NOT SAVE THESE DETAILS TO YOUR LAUNCHER\n"
                              f"Username: **{acc.username}**\n"
                              f"Password: **{acc.password}**\n",
                        inline=False
                        )
    else:
        embed.colour = Colour.greyple()
        embed.add_field(name='Account Unvalidated',
                        value='Click below to confirm you are not going to save this account\'s login details, '
                              '**you will not use this account after this session ends**, and that you understand all '
                              'other previously agreed to rules!',
                        inline=False)

    return fs_author(embed)


def accountcheck(available, used, usages, online) -> discord.Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Accounts Info",
        description="",
        timestamp=dt.now()
    )

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
            last_player = d_obj.guild.get_member(online[acc][1])
            string = string + f'{char_name} : {last_player.mention}\n'
        embed.add_field(name='Currently Online Accounts',
                        value=string,
                        inline=False
                        )
    return fs_author(embed)

def account_online_check(online) -> discord.Embed:
    """Automatic Online Check Embed
    """
    embed = Embed(
        colour=Colour.red(),
        title="Unassigned Accounts Detected Online",
        description="",
        timestamp=dt.now()
    )

    string = '*Character Name : Last Player *\n'
    for acc in online:
        char_name = acc.online_name
        last_player = d_obj.guild.get_member(acc.last_user_id)
        string = string + f'{char_name} : {last_player.mention}\n'

    embed.add_field(name='Currently Online Accounts',
                    value=string,
                    inline=False
                    )
    return fs_author(embed)


def duel_dashboard(lobbied_players: list[Player], logs: list[(int, str)]) -> discord.Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels."""
    colour = Colour.blurple() if lobbied_players else Colour.greyple()

    embed = Embed(
        colour=colour,
        title="Flight School Bot Duel Dashboard",
        description="Your source for organized ESF duels",
        timestamp=dt.now()
    )

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
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}][{req_skill_levels}][{f_lobbied_stamp}]\n '
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
    return fs_author(embed)


def longer_lobby_logs(logs: list[(int, str)]) -> discord.Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels."""

    embed = Embed(
        colour=Colour.blurple(),
        title="Flight School Bot Extended History",
        description="Your source for organized ESF duels",
        timestamp=dt.now()
    )

    if logs:
        log_str = ''
        for log in logs:
            time_formatted = format_stamp(log[0], 'T')
            log_str += f'[{time_formatted}]{log[1]}\n'
        embed.add_field(name="Extended Recent Activity",
                        value=log_str,
                        inline=False)
    return fs_author(embed)


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


    match_info_str = (f"Owner: {match.owner.mention}\n"
                     f"Match status: {match.status.value}\n"
                     f"Match Start Time: {format_stamp(match.start_stamp)}\n"
                     )

    if match.end_stamp:
        match_info_str += f'Match End Time: {format_stamp(match.end_stamp)}'

    embed.add_field(name="Match Info",
                    value=match_info_str,
                    inline=False)

    embed.add_field(
        name='----------------------------------------------------------',
        value='@Mention [Preferred Faction(s)][Skill Level]\n',
        inline=False
    )
    if match.invited:
        invited_string = ''
        for p in match.invited:
            preferred_facs = ''.join([cfg.emojis[fac] for fac in p.pref_factions]) if p.pref_factions else 'Any'
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}]\n'
            invited_string += string

        embed.add_field(name="Invited Players",
                        value=invited_string,
                        inline=False
        )

    if match.players:
        players_string = ''
        for p in match.players:
            p = p.player
            preferred_facs = ''.join([cfg.emojis[fac] for fac in p.pref_factions]) if p.pref_factions else 'Any'
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}]\n'

            players_string += string

        embed.add_field(name="Players",
                        value=players_string,
                        inline=False)

    if match.online_players:
        online_string = ''
        for p in match.online_players:
            fac_emoji = cfg.emojis[p.current_faction]
            string = f'{p.mention} as [{fac_emoji}{p.current_ig_name}]'
            online_string += string

        embed.add_field(name="Currently Online",
                        value=online_string,
                        inline=False)

    return fs_author(embed)


def to_staff_dm_embed(author: 'discord.User', msg: str) -> discord.Embed:
    author_disc = author.name + author.discriminator
    embed = Embed(
        colour=Colour.blurple(),
        title=f'DM Received from {author_disc}',
        description=f'{author.mention}: {msg}',
        timestamp=dt.now()
    )
    embed.set_author(name=author_disc, icon_url=author.display_avatar.url)

    embed.add_field(
        name="",
        value="Reply in thread to respond to the user.\n"
              "Preface messages with =me in order to identify yourself,\n"
              "rather than just appearing as 'FSBot Mod Team'\n"
              "ex. ``=me My message``"
              ""
    )
    return embed


def from_staff_dm_embed(msg: 'discord.Message') -> discord.Embed:
    ident = False
    message = msg.clean_content
    if message.startswith('=me '):
        i = message.index(' ')
        message = message[i+1:]
        ident = True

    embed = Embed(
        colour=Colour.blurple(),
        title=f'Mod Response',
        description=message
    )
    if ident:
        embed.set_author(name=msg.author.name, icon_url=msg.author.display_avatar.url)
        return embed
    else:
        return fs_author(embed)

'''Contains Embeds and embed templates for use throughout the bot'''

# External Imports
import discord
from discord import Embed, Colour

from datetime import timedelta, datetime as dt
import pytz

# Internal Imports
import modules.config as cfg
from modules.tools import format_time_from_stamp as format_stamp
from classes.players import SkillLevel, Player
import modules.discord_obj as d_obj


def fs_author(embed) -> Embed:
    """

    :param embed: embed to modify
    :return:  Embed, with author as FSBot
    """
    embed.set_author(name="FS Bot",
                     url="https://www.discord.gg/flightschool",
                     icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                              "/pfp.png")
    return embed


def account(acc) -> Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Account",
        description=f"\nFollow all Jaeger and PREY's Flight School <#{cfg.channels['rules']}> while using this "
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


def accountcheck(num_available, num_used, assigned, online) -> Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Colour.blue(),
        title="Flight School Jaeger Accounts Info",
        description="",
        timestamp=dt.now()
    )

    embed.add_field(name='Usage',
                    value=f"Available Accounts: **{num_available}**\n"
                          f"Used Accounts: **{num_used}**\n",
                    inline=False
                    )
    string = 'None'
    if assigned:
        string = '\u2705 : validated\n' \
                 '\u274C : terminated\n\n'
        for acc in assigned:
            pref = "\u2705" if acc.is_validated else ''
            pref = "\u274C" if acc.is_terminated else pref
            string += f'{pref}[{acc.id}] : {acc.a_player.name}\n'

    embed.add_field(name='Currently Assigned Accounts',
                    value=string,
                    inline=False
                    )
    if online:
        string = '*Character Name : Last Player*\n'
        for acc in online:
            last_player = d_obj.bot.get_user(acc.last_user_id)
            if not last_player:
                player_ment = f"User not found for ID {acc.last_user_id}"
            else:
                player_ment = last_player.mention
            string += f'{acc.online_name} : {player_ment}\n'
        embed.add_field(name='Currently Online Accounts',
                        value=string,
                        inline=False
                        )
    return fs_author(embed)


def account_online_check(online, new) -> Embed:
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
        last_player = d_obj.bot.get_user(acc.last_user_id)
        if not last_player:
            player_ment = f"User not found for ID {acc.last_user_id}"
        else:
            player_ment = f"{last_player.mention}({last_player.name})"
        bold = "**" if acc == new else ""
        string = string + f'{bold}{char_name}{bold} : {player_ment}\n'

    embed.add_field(name='Currently Online Accounts',
                    value=string,
                    inline=False
                    )
    return fs_author(embed)


def psb_account_usage(player, start_stamp, end_stamp, usages) -> Embed:
    """"PSB formatted account usage info for a given player"""

    embed = Embed(
        colour=Colour.blurple(),
        title="Flight School Jaeger Account Usage",
        description=f"Mention: {player.mention}\n"
                    f"Name: ``{player.name}``\n"
                    f"ID: ``{player.id}``"
    )
    format_start, format_end = format_stamp(start_stamp, 'd'), format_stamp(end_stamp, 'd')

    # storage
    usage_split_dict = {}
    usage_lines = []

    # create week separators
    week_start_stamps = []
    last_stamp = end_stamp
    while last_stamp > start_stamp:
        last_stamp = last_stamp - 604800  # seconds in a week
        week_start_stamps.append(last_stamp)

    # this is awful code
    for week in week_start_stamps:
        for usage in usages:
            if week + 604800 > usage['start_time'] >= week:
                if week_lst := usage_split_dict.get(week):
                    week_lst.append(usage)
                else:
                    usage_split_dict[week] = [usage]

    for week in usage_split_dict:
        num_usages = len(usage_split_dict[week])
        usage_lines.append(
            f"\u2705 {num_usages} usages from [{format_stamp(week, 'd')}--{format_stamp(week + 604800, 'd')}]\n"
        )

    if not usage_lines:
        embed.colour = Colour.red()
        embed.add_field(name="No Data",
                        value=f"This user has no registered use with FSBot Jaeger Accounts in the period\n"
                              f"{format_start}--{format_end}",
                        inline=False)
        return embed

    embed.add_field(
        name="Selected Period",
        value=f"{format_start}--{format_end}",
        inline=False
    )

    embed.add_field(
        name="Summary",
        value=f"Total Usage(s): ``{len(usages)}``\n"
              f"Total Point(s): ``{0.75 * len(usage_split_dict)}``",
        inline=False
    )

    embed.add_field(
        name="Usages",
        value=''.join(usage_lines),
        inline=False
    )
    return embed


def stat_response(player: Player, match_count: int, total_duel_sec: int, duel_partners: str) -> Embed:
    # Local import to avoid circular dependency
    from display import AllStrings

    embed = Embed(
        colour=Colour.blurple(),
        title=f"Match Statistics for {player.name}",
        description=AllStrings.STAT_TOTALS.value.format(player.mention, match_count, round(total_duel_sec / 60 / 60, 1))
    )

    if duel_partners:
        embed.add_field(
            name="Top Duel Partners",
            value=duel_partners
        )

    return embed


def player_info(player) -> Embed:
    embed = Embed(
        colour=Colour.greyple(),
        title=f"FSBot Registration Info for ``{player.name}``",
        description=f'Mention: {player.mention} ID: ``{player.id}``',
        timestamp=dt.now()
    )

    if player.has_own_account:
        embed.add_field(name="Registered Characters",
                        value='\n'.join([f'{player.ig_names[i]}{cfg.emojis[cfg.factions[i + 1]]}'
                                         for i in range(len(player.ig_names))]),
                        inline=False)
    elif player.is_registered:
        embed.add_field(name="Registered Characters",
                        value="Registered with No Jaeger Account",
                        inline=False)
    else:
        embed.add_field(name="Registered Characters",
                        value="Player is not registered",
                        inline=False)

    if player.account:
        embed.add_field(name="FSBot Jaeger Account",
                        value=f"Currently Assigned: ``{player.account.ig_name}``")

    if player.online_name:
        embed.add_field(name="Online Character",
                        value=f"{cfg.emojis[player.current_faction]}{player.online_name}")

    if player.lobby:
        embed.add_field(name="Player Lobby",
                        value=f"Current Lobby: {player.lobby.channel.mention}\n"
                              f"Lobby Timeout: {format_stamp(player.lobby_timeout_stamp)}")
    if player.match:
        embed.add_field(name="Player Match",
                        value=f"Current Match: [{player.match.id_str}]{player.match.thread.mention}\n")

    pref_fac_str = ''.join([cfg.emojis[fac] for fac in player.pref_factions]) if player.pref_factions else 'Any'
    pref_level_str = ' '.join(
        [f'**{level.rank}**:{str(level)}' for level in player.req_skill_levels]) if player.req_skill_levels else 'Any'
    preferences_string = f'Player Skill Level: **{player.skill_level.rank}**:{str(player.skill_level)}\n'
    preferences_string += f"Player Preferred Faction(s): {pref_fac_str}\n"
    preferences_string += f"Player Requested Skill Level(s): {pref_level_str}\n"

    embed.add_field(
        name="Player Preferences",
        value=preferences_string,
        inline=False
    )

    if player.lobby_ping_pref == 0:
        ping_pref = 'Never Ping.'
    else:
        ping_pref = f'**{"Always" if player.lobby_ping_pref == 2 else "Only if Online"}**, with at least ' \
                    f'**{player.lobby_ping_freq}** minutes between pings.'

    embed.add_field(
        name="Ping Preferences",
        value=f"Current ping Preferences are:\n{ping_pref}\n",
        inline=False
    )

    if player.is_timeout:
        relative, short = format_stamp(player.timeout_until, "R"), format_stamp(player.timeout_until, "f")
        embed.add_field(
            name="Player Timeout",
            value=f"Player is currently timed out, their timeout will expire {relative}, at {short}.\n"
                  f"Reason: {player.timeout_reason}\n"
                  f"Mod: {d_obj.bot.get_user(player.timeout_mod_id).mention}"
        )

    return fs_author(embed)


def duel_dashboard(lobby) -> Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels."""

    colour = Colour.blurple() if lobby.lobbied else Colour.greyple()

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
        if i == 4:
            string += '\n'
    embed.add_field(
        name='Skill Level Ranks',
        value=string,
        inline=False
    )

    # Player_list Header
    embed.add_field(
        name=f'{lobby.name.capitalize()} Lobby'.center(70, '-'),
        value='@Mention [Preferred Faction(s)][Skill Level][Wanted Level(s)][Time]\n',
        inline=False
    )

    players_string = 'No players currently in lobby...'
    if lobby.lobbied:
        players_string = ''
        for p in lobby.lobbied:
            timeout_warn = '⏳' if p in lobby.warned else ''
            preferred_facs = ''.join([cfg.emojis[fac] for fac in p.pref_factions]) if p.pref_factions else 'Any'
            req_skill_levels = ' '.join([str(level.rank) for level in p.req_skill_levels]) \
                if p.req_skill_levels else 'Any'
            f_lobbied_stamp = format_stamp(p.lobbied_stamp)
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}][{req_skill_levels}][{f_lobbied_stamp}]\n '
            players_string += timeout_warn + string

    embed.add_field(name="-" * 70,
                    value=players_string,
                    inline=False)

    if lobby.matches:
        matches_str = ''
        for match in lobby.matches:
            matches_str += f"Match: {match.id_str} [Owner: {match.owner.mention}, " \
                           f"Players: {', '.join([p.mention for p in match.players if p is not match.owner.active])}]\n"
        embed.add_field(
            name='Active Matches',
            value=matches_str,
            inline=False
        )

    log_str = '' if lobby.logs_recent else 'None in the last 3 hours...'
    for log in lobby.logs_recent:
        time_formatted = format_stamp(log[0], 'T')
        log_str += f'[{time_formatted}]{log[1]}\n'
    embed.add_field(name="Recent Activity",
                    value=log_str,
                    inline=False)
    return fs_author(embed)


def ranked_duel_dashboard(lobby) -> Embed:
    """Ranked Duel Dashboard, shows currently looking duelers and their rank"""
    colour = Colour.blurple() if lobby.lobbied else Colour.greyple()
    embed: Embed = Embed(
        colour=colour,
        title="Flight School Bot Ranked Duel Dashboard",
        description="Matches started in this lobby are ranked, and will affect your recorded ELO score!",
        timestamp=dt.now()
    )

    # Player List Header
    embed.add_field(
        name=f'{lobby.name.capitalize()} Lobby'.center(70, '-'),
        value='@Mention [ELO][Time]\n',
        inline=False
    )

    players_string = 'No players currently in lobby...'
    if lobby.lobbied:
        players_string = ''
        for p in lobby.lobbied:
            timeout_warn = '⏳' if p in lobby.warned else ''
            f_lobbied_stamp = format_stamp(p.lobbied_stamp)
            string = f'{p.mention}({p.name}) [{p.elo}][{f_lobbied_stamp}]\n '
            players_string += timeout_warn + string

    embed.add_field(name="-" * 70,
                    value=players_string,
                    inline=False)

    if lobby.matches:
        matches_str = ''
        for match in lobby.matches:
            matches_str += f"Match: {match.id_str} [Owner: {match.owner.mention}, " \
                           f"Players: {', '.join([p.mention for p in match.players if p is not match.owner.active])}]\n"
        embed.add_field(
            name='Active Matches',
            value=matches_str,
            inline=False
        )

    log_str = '' if lobby.logs_recent else 'None in the last 3 hours...'
    for log in lobby.logs_recent:
        time_formatted = format_stamp(log[0], 'T')
        log_str += f'[{time_formatted}]{log[1]}\n'
    embed.add_field(name="Recent Activity",
                    value=log_str,
                    inline=False)


def longer_lobby_logs(logs: list[(int, str)]) -> Embed:
    """Extended lobby history available on button press"""

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
            next_str = f'[{time_formatted}]{log[1]}\n'
            if len(log_str) + len(next_str) > 1024:
                embed.add_field(name="\u200b",
                                value=log_str,
                                inline=False)
                log_str = ''
            log_str = log_str + next_str
        if log_str:
            embed.add_field(name="\u200b",
                            value=log_str,
                            inline=False)
    return fs_author(embed)


def match_info(match) -> Embed:
    """Match info for match channel, should go along with match control View"""
    match match.status.name:
        case 'INVITING':
            colour = Colour.orange()
        case 'LOGGING_IN':
            colour = Colour.yellow()
        case 'PLAYING':
            colour = Colour.green()
        case 'ENDED':
            colour = Colour.red()
        case _:
            colour = Colour.dark_grey()

    embed = Embed(
        colour=colour,
        title=f"Match Info for Match: {match.id_str}",
        description="Match Owners can invite additional players by selecting them from the Lobby!",
        timestamp=dt.now()
    )

    match_info_str = (f"Owner: {match.owner.mention}\n"
                      f"Match Status: {match.status.value}\n"
                      f"Match Started: {format_stamp(match.start_stamp, 'R')} at {format_stamp(match.start_stamp)}\n"
                      )

    if match.end_stamp:
        match_info_str += f'Match End Time: {format_stamp(match.end_stamp)}\n'

    elif match.timeout_at:
        match_info_str += f"Match will timeout {format_stamp(match.timeout_at, 'R')}\n"
        match_info_str += f"Match timeout will be reset on login to Jaeger\n"

    if match.voice_channel:
        match_info_str += f'Match Voice Channel: {match.voice_channel.mention} ' \
                          f'{"🔓" if match.public_voice else "🔒"}\n'
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
            account_status = '☑️' if p.has_own_account else ''
            account_status = '✅' if p.account else account_status
            string = f'{account_status}{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}]\n'

            players_string += string

        embed.add_field(name="Players",
                        value=players_string,
                        inline=False)

    if match.online_players:
        online_string = ''
        for p in match.online_players:
            fac_emoji = cfg.emojis[p.current_faction]
            string = f'{p.mention} as [{fac_emoji}{p.online_name}]\n'
            online_string += string

        embed.add_field(name="Currently Online",
                        value=online_string,
                        inline=False)

    if match.recent_logs:
        log_string = ''
        title = "Match Logs"
        for log in match.recent_logs:
            if log[2]:
                next_string = f"[{format_stamp(log[0], 'T')}]{log[1]}\n"
                if len(log_string) + len(next_string) > 1000:
                    embed.add_field(name=title,
                                    value=log_string,
                                    inline=False)
                    log_string = ''
                    title = '\u200b'
                log_string = log_string + next_string

        if log_string:
            embed.add_field(name=title,
                            value=log_string,
                            inline=False)

    return fs_author(embed)


def ranked_match_info(match) -> Embed:
    """Match Info Embed, tailored to ranked matches."""
    from classes.match import MatchState
    from classes.match import RankedMatch
    match: RankedMatch

    match match.status:
        case MatchState.PICKING_FACTIONS:
            colour = Colour.blue()
        case MatchState.LOGGING_IN | MatchState.SWITCHING_SIDES:
            colour = Colour.yellow()
        case MatchState.SUBMITTING:
            colour = Colour.og_blurple()
        case MatchState.PLAYING:
            colour = Colour.green()
        case MatchState.ENDED:
            colour = Colour.red()
        case _:
            colour = Colour.dark_grey()

    embed = Embed(
        colour=colour,
        title=f"Match Info for Ranked Match: {match.id_str}",
        description="Good luck!",
        timestamp=dt.now()
    )

    match_info_str = (f"Player1: {match.player1.mention}\n"
                      f"Player2: {match.player2.mention}\n"
                      f"Match Status: {match.status.value}\n"
                      f"Match Started: {format_stamp(match.start_stamp, 'R')} at {format_stamp(match.start_stamp)}\n"
                      )

    if match.end_stamp:
        match_info_str += f'Match End Time: {format_stamp(match.end_stamp)}\n'

    elif match.timeout_at:
        match_info_str += f"Match will timeout {format_stamp(match.timeout_at, 'R')}\n"
        match_info_str += f"Match timeout will be reset on login to Jaeger\n"

    if match.voice_channel:
        match_info_str += f'Match Voice Channel: {match.voice_channel.mention} ' \
                          f'{"🔓" if match.public_voice else "🔒"}\n'
    embed.add_field(name="Match Info",
                    value=match_info_str,
                    inline=False)

    # Scores

    embed.add_field(name="Match Score",
                    value=match.get_score_string(),
                    inline=False)

    # Current Round
    online, offline = "🟢", "🔴"
    if match.factions_picked and not match.is_ended:  # check if match is in progress
        player1_online = online if match.player1.on_assigned_faction else offline
        player2_online = online if match.player2.on_assigned_faction else offline

        player1_submitted = "✉️" if match.check_player_score_submitted(match.player1) else ""
        player2_submitted = "✉️" if match.check_player_score_submitted(match.player2) else ""

        round_string = \
            f"{match.player1.name}: {player1_online}{match.player1.assigned_char_display}{player1_submitted}\n" \
            f"{match.player2.name}: {player2_online}{match.player2.assigned_char_display}{player2_submitted}\n"
        embed.add_field(name=f"Current Round: [{match.current_round}]",
                        value=round_string,
                        inline=False)

    if match.recent_logs:
        log_string = ''
        title = "Match Logs"
        for log in match.recent_logs:
            if log[2]:
                next_string = f"[{format_stamp(log[0], 'T')}]{log[1]}\n"
                if len(log_string) + len(next_string) > 1000:
                    embed.add_field(name=title,
                                    value=log_string,
                                    inline=False)
                    log_string = ''
                    title = '\u200b'
                log_string = log_string + next_string

        if log_string:
            embed.add_field(name=title,
                            value=log_string,
                            inline=False)

    return fs_author(embed)


def elo_change(match, player, new_elo: int, elo_delta: int) -> Embed:
    """Embed to show players their elo change after a match."""
    from classes.match import RankedMatch
    match: RankedMatch

    # Green if positive elo change, Red if negative
    colour = Colour.green() if elo_delta >= 0 else Colour.red()

    embed = Embed(
        colour=colour,
        title=f'Ranked Match [{match.id_str}] Elo Change',
        description=f'{player.mention} versus {match.get_opponent(player).mention} has ended.\n'
                    f'**Scoreline**\n{match.get_score_string()}\n'
                    f'{player.mention}\'s elo has changed by ``{elo_delta}`` points.\n'
                    f'{player.mention}\'s elo is now ``{new_elo}`` points.\n'
    )
    return fs_author(embed)


def elo_summary(player_stats):
    """Embed to show players their current ELO and history"""
    from classes.player_stats import PlayerStats
    player_stats: PlayerStats
    last_five = 'No Matches Recorded'
    if player_stats.last_five_changes:
        last_five = ''
        for match_id, change in player_stats.last_five_changes:
            last_five += f'[{match_id}]: ``{change}``\n'


    embed = Embed(
        colour=Colour.dark_gold(),
        title=f'Ranked Elo Summary for {player_stats.name}',
        description=
        f"Current Elo: {player_stats.elo}\n"
        f"Match Wins: {player_stats.match_wins}\n"
        f"Match Losses: {player_stats.match_losses}\n"
        f"Match Draws: {player_stats.match_draws}\n"
        f"Total Matches: {player_stats.total_matches}\n"
        f"Last Five Match Results: {last_five}\n"

    )
    return fs_author(embed)

def to_staff_dm_embed(author: 'discord.User', msg: str) -> Embed:
    author_disc = author.name + "#" + author.discriminator
    embed = Embed(
        colour=Colour.blurple(),
        title=f'DM Received from {author_disc}',
        description=f'{author.mention}: {msg}',
        timestamp=dt.now()
    )
    embed.set_author(name=author_disc, icon_url=author.display_avatar.url)

    embed.add_field(
        name="Usage",
        value="Send messages by replying in thread with the prefixes\n"
              "Prefix messages with ``! `` in order to identify yourself,\n"
              "or use ``~ `` to appear as 'Mod Response' '\n"
              "Sent messages will be marked with 📨\n"
              "ex. ``~ My message``\n"
              "    ``! My message``"

    )
    return embed


def from_staff_dm_embed(msg: 'discord.Message') -> Embed:
    ident = False
    message = msg.clean_content
    if message.startswith('! '):
        ident = True

    i = message.index(' ')
    message = message[i + 1:]

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


def fsbot_rules_embed() -> Embed:
    embed = Embed(
        colour=Colour.blurple(),
        title="Flight School Bot Rules",
        description="These rules are to be followed at all times while using the Flight School Bot!\n"
                    "Flight School Discord rules are still in effect...\n"
                    "If you ever need to speak to an admin, simply DM the bot,"
                    " starting with 'dm ', 'modmail ' or 'staff ' followed by your message."
    )

    embed.add_field(
        name="General Rules",
        value="\n"
              "1) Be kind! We're here to have fun, along with improving our skills, please be courteous to your fellow"
              " players during matches, and all of the time!\n"
              "2) Do not harass other players, whether this be through pings to duel or following them on Jaeger\n"
              f"3) Do not exploit the system, if you find a bug please let {d_obj.colin.mention} know!\n",
        inline=False
    )

    embed.add_field(
        name="Jaeger Account Info",
        value="\n"
              "Jaeger is a private server that uses the live game client, and can be used to duel in peace away "
              "from the general public on live servers. "
              "Access to Jaeger is mostly controlled by [PSB](https://discord.gg/enE4ZW6MuM), who have provided this "
              "discord with 24 **temporary use** accounts for players to use for one session and one session only.\n"
              "While on Jaeger you must insure you are not interfering with any schedule events,"
              " regardless of what account you are on.  [Click here](https://docs.google.com/spreadsheets/d/1eA4ybkAiz"
              "-nv_mPxu_laL504nwTDmc-9GnsojnTiSRE/edit?usp=sharing) to see the current Jaeger Calendar. \n"
              "While you can find out how to get your own account [here](https://docs.google.com/document/d/1fQy3tJS8Y7"
              "muivo9EHlWKwE6ZTdHhHTcP6-21cPVlcA/edit?usp=sharing), you can request a temporary account through"
              " the FSBot provided you adhere to the following rules.\n",
        inline=False
    )

    embed.add_field(
        name="FSBot Temporary Jaeger Account Rules",
        value="\n1) Accounts are to be used for **one** session only!  You will receive a discord DM telling you to "
              "log out when your session expires, you **MUST** log out at this point!\n\n"
              "2) Account sessions will automatically expire 3 hours after their start time or when the players match "
              "ends. If you still need an account at that time, simply request another after your session expires.\n\n"
              "3) Do not save the accounts login details into your launcher\n\n"
              "4) Do not delete characters and do not create characters\n\n"
              "5) Do not ASP (prestige) characters\n\n"
              "6) Do not interfere with other users of Jaeger\n\n"
              "7) Do not leave the Flight School outfits\n\n"
              "8) Do not leave a character with less than 350 Nanites.",
        inline=False
    )

    embed.add_field(
        name="Failure to follow any of the above rules may result in your removal from  FSBot.",
        value="Click the button below to signify your agreement to the above terms, and reveal the rest of the "
              "FSBot channels",
        inline=False
    )

    return fs_author(embed)


def fsbot_info_embed() -> Embed:
    embed = Embed(
        colour=Colour.blurple(),
        title="Info and Usage",
        description="\n The basic function of the bot is to provide a way for users to mark themselves as "
                    "'looking for duels', by joining a lobby.  Once in the lobby, players can be invited to a match "
                    "by anyone in or out of the lobby.  Match invites are accepted through an interaction in the users "
                    "private messages.  Once a match is joined, users are prompted to log in, and can request a "
                    "temporary Jaeger account if necessary."
    )
    embed.add_field(
        name="Registration",
        value="Before joining a match players must first register their Jaeger characters with the bot. "
              "If you do not have a personal Jaeger account, simply select 'Register: No Jaeger Account' to indicate "
              "to the bot that you require a temporary Jaeger account for matches.  If you have a personal Jaeger "
              "account select 'Register: Personal Jaeger Account', and enter either one generic character name to"
              " which faction suffixes will be added, or enter three specific character names, one for each faction, "
              "separated by commas.",
        inline=False
    )
    embed.add_field(
        name="Preferences",
        value="In order for users to find compatible duel partners more quickly, several preferences can be declared "
              "by the user.  These preferences will be displayed in the duel lobby next to your name. Self-assigned "
              "skill levels are available to help pick balanced partners.  Keep in mind that skill levels are "
              "self-assigned, and may not be entirely accurate.  Requested skill levels can also be chosen, "
              "for those who might wish to duel those in a specific skill range.  Users preferred faction indicates "
              "which faction they would like to play given the choice.",
        inline=False
    )

    embed.add_field(
        name="Notifications",
        value="You can opt-in to receive a notification if a player who matches your requested skill levels joins"
              " the lobby.  When you are pinged, and how frequently, can be adjusted below this message in the 'Lobby"
              " Pings' menu.  Setting your requested skill level to 'any' means you will receive a ping when a player of"
              " any skill level joins the lobby."
    )

    embed.add_field(
        name="Lobby",
        value=f"The duel lobby remains in <#{cfg.channels['casual_lobby']}> where a constantly updated embed shows the "
              "currently lobbied players, along with their preferences, and gives buttons and a dropdown to interact "
              "with the lobby.  The select menu can be used to invite any number of players to a match, though you "
              "obviously can not invite yourself. The select menu can also be used by a match owner to invite new "
              "users to an ongoing match.  Active matches and their owner are also displayed in the dashboard Embed.",
        inline=False
    )

    embed.add_field(
        name="Matches",
        value="Invites are sent out to user's DM's, and once an invite is accepted, a match is created.  When a new "
              "match is created, a private Discord channel is created along with it.  This channel is only visible to "
              "current players of the match, along with the mod team.\nIn the match channel, there is a familiar "
              "looking embed with info relating to this specific match.  If you require a temporary account, you can "
              "select the 'Request Account' button here, and one will be sent to you.\n"
              "Matches will timeout after 10 minutes if no players log in to Jaeger.  Once players log in to Jaeger, "
              "their online characters will be displayed in the match embed.  Players can leave or join the match while"
              " it is running, but if the owner leaves the match, the match will end.  Once the match ends, the channel"
              " will close and all temporary Jaeger account users will be asked to log out of their accounts.",
        inline=False
    )

    embed.add_field(
        name="Elo",
        value="A separate ranked lobby with 1v1 Elo Rated matches and a leaderboard is coming soon(tm)",
        inline=False
    )
    return fs_author(embed)


def fs_join_embed(mention) -> Embed:
    embed = Embed(
        colour=Colour.blurple(),
        title="Welcome to PREY's Flight School!",
        description=f"Hi {mention}, welcome to PREY's Flight School, the premier Discord server for the air game in"
                    f" [Planetside 2](https://www.planetside2.com/).  This server offers a number of resources for"
                    f" those just learning to fly, as well as experienced pilots.  Thanks for joining our community!"
    )
    # TODO fix hardcoded ID's, add to config or d_obj via search.
    embed.add_field(
        name="Guides and Resources",
        value=f"Guides for most different air vehicles can be found in <#751111752191574057>,"  # Guides channel
              f" which makes a great starting point for those new to the air game.  Channels in the 'Improvements and"
              f" advice' Section offer advice specific to certain vehicles, and should be kept on topic when possible."
              f"  Ask questions relating to each vehicle in their channel, or general Planetside 2 related questions "
              f" in <#751114546906792017>.",  # #ask-anything
        inline=False
    )

    embed.add_field(
        name="Hands on Teachers",
        value="<@&823128534759243796> represents a group of volunteers that try to make themselves available for more"
              " specific training.  If you have already gone through the Guides above and are still struggling with"
              " a concept or skill, feel free to ping this role to ask for specific help.  Keep in mind that these"
              " volunteers reside in a number of different timezones, and may not always be available to help.",
        inline=False
    )
    embed.add_field(
        name="Gameplay and Crew Requests",
        value="Feel free to use the voice channels in the 'Gameplay' category to play on live servers with other"
              " server members.  <#761753919906775061> can be used to find members to play specific vehicles with,"
              " by pinging the roles that can be granted in <#751115817692954717>.  When making these pings please"
              " remember to specify your Faction and Server, as there are players from all different servers here.",
        inline=False
    )

    embed.add_field(
        name="Flight School Bot and Duels",
        value=f"{d_obj.bot.user.mention} is a work in progress bot built to provide various utility functions to this"
              f" server, as well as facilitate matchmaking and account access for Duels on the private Jaeger server."
              f"  The bot can be accessed by **reading** and accepting the rules in {d_obj.channels['rules'].mention},"
              f" after which you will be granted access to additional channels where you can request duels with other"
              f" server members.  These duels are a great way to improve your aim and general skill in the air!",
        inline=False
    )

    embed.add_field(
        name="Moderation",
        value=f"Ensure you are following the rules in <#751221386093264936> at all times."
              f" If you have any other questions feel free to reach out to"
              f" to any {d_obj.roles['mod'].mention} or {d_obj.roles['admin'].mention}."
              f" For any moderation questions you may also message the entire staff team by using the /modmail command"
              f" or sending a message to {d_obj.bot.user.mention}, starting your message with ``dm ``, ``modmail ``,"
              f" or ``staff `` "
    )
    return fs_author(embed)

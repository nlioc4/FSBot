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
        description="\nFollow all Jaeger and [PREY's Flight School Rules]"
                    "(https://discord.com/channels/751110310508888194/751115817692954717) while using this "
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


def account_online_check(online) -> Embed:
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
            player_ment = last_player.mention
        string = string + f'{char_name} : {player_ment}\n'

    embed.add_field(name='Currently Online Accounts',
                    value=string,
                    inline=False
                    )
    return fs_author(embed)


def register_info(player) -> Embed:
    embed = Embed(
        colour=Colour.greyple(),
        title=f"FSBot Registration Info for {player.name}",
        description=f'Mention: {player.mention} ID: {player.id}',
        timestamp=dt.now()
    )

    if player.has_own_account:
        embed.add_field(name="Registered Characters",
                        value='\n'.join([f'{player.ig_names[i]}{cfg.emojis[cfg.factions[i + 1]]}' for i in range(3)]),
                        inline=False)
    elif player.is_registered:
        embed.add_field(name="Registered Characters",
                        value="Registered with No Jaeger Account",
                        inline=False)
    else:
        embed.add_field(name="Registered Characters",
                        value="Player is not registered",
                        inline=False)

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

    return fs_author(embed)


def duel_dashboard(lobbied_players: list['Player'], logs: list[(int, str)], matches: list) -> Embed:
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
            req_skill_levels = ' '.join([str(level.rank) for level in p.req_skill_levels]) \
                if p.req_skill_levels else 'Any'
            f_lobbied_stamp = format_stamp(p.first_lobbied_timestamp)
            string = f'{p.mention}({p.name}) [{preferred_facs}][{p.skill_level.rank}][{req_skill_levels}][{f_lobbied_stamp}]\n '
            players_string += string

        embed.add_field(name="----------------------------------------------------------------",
                        value=players_string,
                        inline=False)

    if matches:
        matches_str = ''
        for match in matches:
            matches_str += f"Match: {match.id_str} [Owner: {match.owner.mention}, " \
                           f"Players: {', '.join([p.mention for p in match.players])}]\n"
        embed.add_field(
            name='Active Matches',
            value=matches_str,
            inline=False
        )

    if logs:
        log_str = ''
        for log in logs:
            time_formatted = format_stamp(log[0], 'T')
            log_str += f'[{time_formatted}]{log[1]}\n'
        embed.add_field(name="Recent Activity",
                        value=log_str,
                        inline=False)
    return fs_author(embed)


def longer_lobby_logs(logs: list[(int, str)]) -> Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels."""

    embed = Embed(
        colour=Colour.blurple(),
        title="Flight School Bot Extended History",
        description="Your source for organized ESF duels",
        timestamp=dt.now()
    )

    if logs:
        log_str = ''
        for log in logs[::-1]:
            time_formatted = format_stamp(log[0], 'T')
            next_str = f'[{time_formatted}]{log[1]}\n'
            if len(log_str) + len(next_str) > 1024:
                embed.add_field(name="\u200b",
                                value=log_str,
                                inline=False)
                log_str = ''
            log_str = next_str + log_str
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
        case 'GETTING_READY':
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
        description="",
        timestamp=dt.now()
    )

    match_info_str = (f"Owner: {match.owner.mention}\n"
                      f"Match status: {match.status.value}\n"
                      f"Match Start Time: {format_stamp(match.start_stamp)}\n"
                      )

    if match.timeout_at:
        match_info_str += f"Match will timeout in {format_stamp(match.timeout_at, 'R')}"

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
            string = f'{p.mention} as [{fac_emoji}{p.online_name}]'
            online_string += string

        embed.add_field(name="Currently Online",
                        value=online_string,
                        inline=False)

    if match.recent_logs:
        log_string = ''
        for log in match.recent_logs:
            if log[2]:
                log_string += f"[{format_stamp(log[0], 'T')}]{log[1]}\n"
        embed.add_field(name="Match Logs",
                        value=log_string,
                        inline=False)

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

              ""
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
              "3) Do not exploit the system, if you find a bug please let @Colin know!\n",
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
              "-nv_mPxu_laL504nwTDmc-9GnsojnTiSRE/edit?usp=sharing) to see the current Jaeger Calendar \n"
              "While you can find out how to get your own account [here](https://docs.google.com/document/d/1fQy3tJS8Y7"
              "muivo9EHlWKwE6ZTdHhHTcP6-21cPVlcA/edit?usp=sharing), you can request a temporary account through"
              " the FSBot provided you adhere to the following rules.\n",
        inline=False
    )

    embed.add_field(
        name="Jaeger Account Rules",
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
              "for those who might wish to duel those outside their own skill range.  Users preferred faction can help"
              "match them up with an opponent using the specific ESF they want to practice against.",
        inline=False
    )

    embed.add_field(
        name="Lobby",
        value=f"The duel lobby remains in <#{cfg.channels['dashboard']}> where a constantly updated embed shows the "
              f"currently lobbied players, along with their preferences, and gives buttons and a dropdown to interact "
              f"with the lobby.  The select menu can be used to invite any number of players to a match, though you "
              f"obviously can not invite yourself. The select menu can also be used by a match owner to invite new "
              f"users to an ongoing match.  Active matches and their owner are also displayed in the dashboard Embed.",
        inline=False
    )

    embed.add_field(
        name="Matches",
        value="Invites are sent out to users DM's, and once an invite is accepted, a match is created.  When a new "
              "match is created, a private Discord channel is created along with it.  This channel is only visible to "
              "current players of the match, along with the mod team.  In the match channel, there is a familiar "
              "looking embed with info relating to this specific match.  If you require a temporary account, you can "
              "select the 'Request Account' button here, and one will be sent to you."
              " Matches will timeout after 10 minutes if no players log in to Jaeger.  Once players log in to Jaeger, "
              "their online characters will be displayed in the match embed.  Players can leave or join the match while"
              " it is running, but if the owner leaves the match, the match will end.  Once the match ends, the channel"
              " will close and all temporary Jaeger account users will be asked to log out of their accounts.",
        inline=False
    )

    embed.add_field(
        name="Elo",
        value="A ranked leaderboard, with 1v1 Elo Rated matches is coming soon(tm)",
        inline=False
    )
    return fs_author(embed)

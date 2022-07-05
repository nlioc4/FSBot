from discord import Embed, Color
import discord
import discord.utils
import modules.config as cfg
from datetime import timedelta, datetime
import pytz

# midnight tomorrow EST
eastern = pytz.timezone('US/Eastern')
midnight_eastern = (datetime.now().astimezone(eastern) + timedelta(days=1)).replace(hour=0, minute=0, microsecond=0,
                                                                                    second=0)
formatted_time = discord.utils.format_dt(midnight_eastern, style="t")

_guild = None


def init(client: discord.bot):
    # load discord guild
    global _guild
    _guild = client.get_guild(cfg.general["guild_id"])


def account(ctx, acc) -> discord.Embed:
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Color.blue(),
        title="Flight School Jaeger Account",
        description=f"\nYou've been assigned a Jaeger Account by {ctx.user.mention} \n"
                    f"This account is not to be used after: {formatted_time} \n"
    )
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
        colour=Color.blue(),
        title="Flight School Jaeger Accounts Info",
        description=""
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
        string = '*Character Name : Last Player : Last Assignment*\n'
        for acc in online:
            char_name, time_string = online[acc][0], online[acc][2]
            last_player = _guild.get_member(online[acc][1])
            string = string + f'{char_name} : {last_player.mention} : {time_string} \n'
        embed.add_field(name='Currently Online Accounts',
                        value=string,
                        inline=False
                        )
    return embed


def account_online_check(online) -> discord.Embed:
    """Automatic Online Check Embed
    """
    embed = Embed(
        colour=Color.red(),
        title="Unassigned Accounts Detected Online",
        description=""
    )

    string = '*Character Name : Last Player : Last Assignment*\n'
    for acc in online:
        char_name, time_string = online[acc][0], online[acc][2]
        last_player = _guild.get_member(online[acc][1])
        string = string + f'{char_name} : {last_player.mention} : {time_string} \n'

    embed.add_field(name='Currently Online Accounts',
                    value=string,
                    inline=False
                    )
    return embed


def anomaly(world, zone, timestamp, state) -> discord.Embed:
    """Aerial Anomaly Notification Embed
    """
    colour = Color.blurple()
    if state == "Ended":
        colour = Color.red()

    embed = Embed(
        colour=colour,
        title="Aerial Anomaly Detected",
        description=""
    )

    embed.set_thumbnail(url="https://i.imgur.com/Ch8QAZJ.png")

    embed.add_field(name=f'Server: {world}',
                    value=f'Continent: {zone}\nStarted: {discord.utils.format_dt(timestamp, style="R")}'
                          f'\nState: {state}',
                    inline=False)

    embed.add_field(name='Register',
                    value='Register in #roles',
                    inline=False)
    return embed


def duel_dashboard(active_players, ) -> discord.Embed:
    """Player visible duel dashboard, shows currently looking duelers, their requested skill Levels"""

    return embed
from discord import Embed, Color
import discord.utils
import modules.config as cfg
from datetime import timedelta, datetime
import pytz

# midnight EST
eastern = pytz.timezone('US/Eastern')
midnight_eastern = (datetime.now().astimezone(eastern) + timedelta(days=1)).replace(hour=0, minute=0, microsecond=0, second=0)
formatted_time = discord.utils.format_dt(midnight_eastern, style="t")


def account(ctx, acc):
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Color.blue(),
        title="Flight School Jaeger Account",
        description=f"\nYou've been assigned a Jaeger Account by {ctx.user.mention} \n"
                    f"This account is not to be used after: {formatted_time} \n"
    )
    embed.add_field(name='Account Details',
                    value=f"Username: **{acc.username}**\n"
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


def accountcheck(ctx, available, used, usages):
    """Jaeger Account Embed
    """
    embed = Embed(
        colour=Color.blue(),
        title="Flight School Jaeger Accounts Info",
        description=""
    )
    embed.add_field(name='Usaage',
                    value=f"Available Accounts: **{available}**\n"
                          f"Used Accounts: **{used}**\n",
                    inline=False
                    )
    string = "None"
    if usages:
        string = ""
        for usage in usages:
            string += f'[{usage[0]}] : {usage[1]}\n'

    embed.add_field(name='Currently Assigned Accounts',
                    value=string,
                    inline=False
                    )
    return embed

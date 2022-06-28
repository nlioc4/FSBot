"""
Cog built to watch Aerial Anomalies on most servers, pinging when events start
"""

# External Imports
import asyncio
from discord.ext import commands, tasks
import discord
from discord.commands import permissions
from logging import getLogger
from datetime import timedelta, datetime, time, timezone
import pytz
import auraxium

# Internal imports
import modules.config as cfg
import modules.census as census
import classes
import display

## 228(2),229(4),230(6),231(8),232(344)
WORLD_DICT = {1: "Connery", 10: "Miller", 13: "Cobalt", 17: "Emerald"}
ZONE_DICT = {2: "Indar", 4: "Hossin", 6: "Amerish", 8: "Esamir", 344: "Oshur"}
ANOMALY_IDS_STR = ['228', '229', '230', '231', '232']
STATE_DICT = {135: 'Started', 138: 'Ended'}


class AnomalyEvent:
    """Class to represent individual anomalies"""

    def __init__(self, event_id, timestamp, zone_id, world_id, instance_id, event_state_id):
        self.event_id = event_id
        self.timestamp = timestamp
        self.zone_id = zone_id
        self.world_id = world_id
        self.instance_id = instance_id
        self.state_id = event_state_id
        self.message = None

    def __repr__(self):
        return repr(f'{self.world_id}-{self.instance_id}')


class AnomalyChecker(commands.Cog, name="AnomalyChecker"):
    def __init__(self, bot):
        self.bot = bot
        self.notif_channel = None
        self.notif_role = None
        self.active_events = {}

    @commands.slash_command(name="anomalyinit", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomaly_init(self, ctx: discord.ApplicationContext,
                           channel: discord.Option(discord.TextChannel, "Notification Channel", required=True),
                           role: discord.Option(discord.Role, "Notification Role", required=True)):
        "Sets a Channel and Role for the Anomaly Notifier"
        self.notif_channel = channel
        self.notif_role = role
        self.anomaly_check.start()
        print("Initialized Anomaly Checker")
        await ctx.respond(f"Started Anomaly Check with role: {role.mention}, and channel: {channel.mention}",
                          ephemeral=True)

    @tasks.loop(minutes=1)
    async def anomaly_check(self):
        async with auraxium.Client(service_id=cfg.general['api_key']) as client:
            # build query
            query = auraxium.census.Query('world_event', service_id=cfg.general['api_key'])
            for i in WORLD_DICT.keys():
                query.add_term('world_id', i)
            query.limit(500)
            data = await client.request(query)
            new_events = {}
            # sort out anomalies from all world events, create AnomalyEvent instances
            for event in data['world_event_list']:
                if 'metagame_event_id' in event and event['metagame_event_id'] in ANOMALY_IDS_STR:
                    event_id = int(event['metagame_event_id'])
                    timestamp = datetime.fromtimestamp(int(event['timestamp']))
                    zone_id = int(event['zone_id'])
                    world_id = int(event['world_id'])
                    instance_id = int(event['instance_id'])
                    state_id = int(event['metagame_event_state'])
                    new_events[f'{world_id}-{instance_id}'] = (AnomalyEvent(event_id, timestamp, zone_id,
                                                           world_id, instance_id, state_id))

            # update master event list
            for event in new_events:
                if new_events[event].state_id == 135 and not event in self.active_events:
                    self.active_events[event] = new_events[event]
                elif new_events[event].state_id == 138 and event in self.active_events:
                    self.active_events[event].state_id = new_events[event].state_id

            # Send or Update Message and remove dict entry
            for event in list(self.active_events):
                current_event = self.active_events[event]
                if ((not current_event.message) and current_event.state_id == 135):
                    current_event.message = await self.notif_channel.send(content=f'{self.notif_role.mention}',
                                                                  embed=display.embeds.anomaly(
                                                                      world=WORLD_DICT[current_event.world_id],
                                                                      zone=ZONE_DICT[current_event.zone_id],
                                                                      timestamp=current_event.timestamp,
                                                                      state=STATE_DICT[current_event.state_id])
                                                                  )

                elif current_event.message and current_event.state_id == 138:
                    await current_event.message.edit(content='',
                                             embed=display.embeds.anomaly(
                                                 world=WORLD_DICT[current_event.world_id],
                                                 zone=ZONE_DICT[current_event.zone_id],
                                                 timestamp=current_event.timestamp,
                                                 state=STATE_DICT[current_event.state_id]
                                             ))
                    self.active_events.pop(event)

    @anomaly_check.before_loop
    async def before_anomaly_check(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(name="anomalystatus", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomlystatus(self, ctx: discord.ApplicationContext,
                           action: discord.Option(str, "Start, Stop or Status",
                                                  choices=("Start", "Stop", "Status"),
                                                  required=True)):
        """Provides Info on the status of the Anomaly Checker"""
        match action:
            case "Start":
                if self.anomaly_check.is_running():
                    await ctx.respond(
                        f"Anomaly Check is running with role:{self.notif_role} and channel: {self.notif_channel}",
                        ephemeral=True)
                else:
                    await ctx.respond(
                        f"Anomaly Check started with role:{self.notif_role} and channel: {self.notif_channel}",
                        ephemeral=True)
                    self.anomaly_check.start()
            case "Stop":
                if self.anomaly_check.is_running():
                    await ctx.respond(f"Anomaly Check stopped", ephemeral=True)
                    self.anomaly_check.cancel()
                else:
                    await ctx.respond("Anomaly Check already stopped", ephemeral=True)
            case "Status":
                await ctx.respond(f"Anomaly Check running: {self.anomaly_check.is_running()}", ephemeral=True)

    @commands.slash_command(name="anomalynotify", guild_ids=[cfg.general['guild_id']], default_permission=True)
    async def anomalynotify(self, ctx):
        """Enrolls or Unenrolls you from Aerial Anomaly Notifications"""
        if self.notif_role in ctx.user.roles:
            await ctx.user.remove_roles(self.notif_role)
            await ctx.respond("You have unenrolled from Aerial Anomaly notifications.", ephemeral=True)
        else:
            await ctx.user.add_roles(self.notif_role)
            await ctx.respond("You have enrolled in Aerial Anomaly notifications", ephemeral=True)


def setup(client):
    client.add_cog(AnomalyChecker(client))

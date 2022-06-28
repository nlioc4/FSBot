"""
Cog built to watch Aerial Anomalies on most servers, pinging when events start
"""

# External Imports
import asyncio
from discord.ext import commands, tasks
import discord
from logging import getLogger
from datetime import timedelta, datetime, time, timezone
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


class AnomalyRegisterButton(discord.ui.Button):
    def __init__(self, role: discord.Role, label: str()):
        """A button to assign a role / register for a servers notify"""
        super().__init__(
            label=label,
            style=discord.ButtonStyle.blurple,
            custom_id=str(role.id)
        )

    async def callback(self, interaction: discord.Interaction):
        """Function that runs when user clicks button, assigns/unassigns role"""
        user = interaction.user
        # user to be given role
        role = interaction.guild.get_role(int(self.custom_id))
        # role to be given
        server_name = role.name[:-10]
        # used in user notification

        # Add role, notify user
        if role not in user.roles:
            await user.add_roles(role)
            await interaction.response.send_message(
                f'You have registered for Anomaly Notifications from {server_name}.',
                ephemeral=True
            )
        else:
            await user.remove_roles(role)
            await interaction.response.send_message(
                f'You have deregistered for Anomaly Notifications from {server_name}',
                ephemeral=True
            )


class AnomalyChecker(commands.Cog, name="AnomalyChecker"):
    def __init__(self, bot):
        self.bot = bot
        self.notif_channel = None
        self.notif_roles = {}
        self.notif_register_msg = None
        self.active_events = {}
        self.anomaly_check.start()

    @commands.slash_command(name="anomalychannel", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomaly_channel(self, ctx: discord.ApplicationContext,
                              channel: discord.Option(discord.TextChannel, "Notification Channel", required=True),
                              ):
        "Sets a Channel for the Anomaly Notifier"
        self.notif_channel = channel
        await ctx.respond(f"Set Anomaly Notifier channel: {channel.mention}", ephemeral=True)

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
                ping = self.notif_roles[current_event.world_id].mention
                if ((not current_event.message) and current_event.state_id == 135):
                    current_event.message = await self.notif_channel.send(content=ping,
                                                                          embed=display.embeds.anomaly(
                                                                              world=WORLD_DICT[current_event.world_id],
                                                                              zone=ZONE_DICT[current_event.zone_id],
                                                                              timestamp=current_event.timestamp,
                                                                              state=STATE_DICT[current_event.state_id])
                                                                          )

                elif current_event.message and current_event.state_id == 138:
                    await current_event.message.edit(content=ping,
                                                     embed=display.embeds.anomaly(
                                                         world=WORLD_DICT[current_event.world_id],
                                                         zone=ZONE_DICT[current_event.zone_id],
                                                         timestamp=current_event.timestamp,
                                                         state=STATE_DICT[current_event.state_id]
                                                     ))
                    self.active_events.pop(event)

    @anomaly_check.before_loop
    async def before_anomaly_check(self):
        if not self.notif_roles:
            return
        await self.bot.wait_until_ready()




    @commands.slash_command(name="anomalystatus", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomlystatus(self, ctx: discord.ApplicationContext,
                           action: discord.Option(str, "Start, Stop or Status",
                                                  choices=("Start", "Stop", "Status"),
                                                  required=True)):
        """Provides Info on the status of the Anomaly Checker"""
        is_running = self.anomaly_checker.is_running()
        match action:
            case "Start" if is_running:
                    await ctx.respond(
                        f"Anomaly Check is running with channel: {self.notif_channel}", ephemeral=True)
            case "Start" if not is_running:
                    await ctx.respond(
                        f"Anomaly Check started with channel: {self.notif_channel}", ephemeral=True)
                    self.anomaly_check.start()
            case "Stop" if is_running:
                    await ctx.respond(f"Anomaly Check stopped", ephemeral=True)
                    self.anomaly_check.cancel()
            case "Stop" if not is_running:
                    await ctx.respond("Anomaly Check already stopped", ephemeral=True)
            case "Status":
                await ctx.respond(f"Anomaly Check running: {self.anomaly_check.is_running()}", ephemeral=True)

    @commands.slash_command(name="anomalyregistercreate", guild_ids=[cfg.general['guild_id']], default_permission=True)
    async def anomalyregistercreate(self, ctx: discord.ApplicationContext):
        """Creates anomaly notifcation registration message"""

        view = discord.ui.View(timeout=None)

        for world in self.notif_roles:
            role = self.notif_roles[world]
            label = WORLD_DICT[world]
            view.add_item(AnomalyRegisterButton(role, label))
        await ctx.respond("Click a button to register for notifications when an"
                          " Aerial Anomaly is detected on that server!", view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        """Called on bot restart, initializees, listents to and creates view as before or loads existing view."""
        guild = self.bot.get_guild(cfg.general['guild_id'])
        role_names = {i: f'{v} Anomalies' for i, v in WORLD_DICT.items()}
        for world_id in role_names:
            current_role = discord.utils.get(guild.roles, name=role_names[world_id])
            if current_role:
                self.notif_roles[world_id] = current_role
            else:
                self.notif_roles[world_id] = await guild.create_role(name=role_names[world_id])
        self.notif_channel = guild.get_channel(cfg.channels['anomaly-notification'])
        print("Initialized Anomaly Notifications")

        view = discord.ui.View(timeout=None)

        for world in self.notif_roles:
            role = self.notif_roles[world]
            label = WORLD_DICT[world]
            view.add_item(AnomalyRegisterButton(role, label))
        self.bot.add_view(view)


def setup(client):
    client.add_cog(AnomalyChecker(client))

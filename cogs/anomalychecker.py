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
import modules.discord_obj as d_obj

# 228(2),229(4),230(6),231(8),232(344)
WORLD_DICT = {1: "Connery", 10: "Miller", 13: "Cobalt", 17: "Emerald"}
ZONE_DICT = {2: "Indar", 4: "Hossin", 6: "Amerish", 8: "Esamir", 344: "Oshur"}
ANOMALY_IDS_STR = ['228', '229', '230', '231', '232']
ANOMALY_IDS = [228, 229, 230, 231, 232]
STATE_DICT_INT = {135: 'Started', 138: 'Ended'}
STATE_DICT_STR = {v: k for k, v in STATE_DICT_INT.items()}


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

    def __str__(self):
        return str(f'{self.world_id}-{self.instance_id}')


class AnomalyRegisterButton(discord.ui.Button):
    def __init__(self, role: discord.Role, label: str):
        """A button to assign a role / register for a servers notify"""
        super().__init__(
            label=label,
            style=discord.ButtonStyle.blurple,
            custom_id=str(role.id)  # use role ID as custom ID, so the bot knows which role to give
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
                ephemeral=True, delete_after=10
            )
        else:
            await user.remove_roles(role)
            await interaction.response.send_message(
                f'You have deregistered for Anomaly Notifications from {server_name}',
                ephemeral=True, delete_after=10
            )


class AnomalyChecker(commands.Cog, name="AnomalyChecker"):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.notif_channel = None  # Channel to post notifications to, pulled from config on_ready
        self.notif_roles = {}  # Roles to notify, pulled from server or created on_ready
        self.active_events: dict[str, AnomalyEvent] = {}
        self.websocket_ended = False
        self.event_client: auraxium.event.EventClient = None
        self.anomaly_check.start()

    @commands.slash_command(name="anomalychannel", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomaly_channel(self, ctx: discord.ApplicationContext,
                              channel: discord.Option(discord.TextChannel, "Notification Channel", required=True),
                              ):

        """Sets a Channel for the Anomaly Notifier"""
        self.notif_channel = channel
        await ctx.respond(f"Set Anomaly Notifier channel: {channel.mention}", ephemeral=True)

    @tasks.loop(count=1)
    async def anomaly_check(self):
        client = auraxium.event.EventClient(service_id=cfg.general['api_key'], no_ssl_certs=True)
        self.event_client = client

        # Anomaly Only Check
        def anomaly_check(event: auraxium.event.MetagameEvent):
            return event.metagame_event_id in ANOMALY_IDS

        async def anomaly_event(evt: auraxium.event.MetagameEvent):
            # create AnomalyEvent class
            anom = AnomalyEvent(evt.metagame_event_id, evt.timestamp, evt.zone_id,
                                evt.world_id, evt.instance_id, evt.metagame_event_state)

            # set ping according to world
            ping = self.notif_roles[anom.world_id].mention

            # if new anomaly send new message, add to dict
            if anom.state_id == STATE_DICT_STR['Started']:
                anom.message = await self.notif_channel.send(content=ping,
                                                             embed=display.embeds.anomaly(
                                                                 world=WORLD_DICT[anom.world_id],
                                                                 zone=ZONE_DICT[anom.zone_id],
                                                                 timestamp=anom.timestamp,
                                                                 state=STATE_DICT_INT[anom.state_id])
                                                             )
                self.active_events[anom.__str__()] = anom

            # if previously tracked anomaly, edit message and remove from dict
            elif str(anom) in self.active_events:
                old_anom = self.active_events[str(anom)]
                old_anom.state_id = anom.state_id
                anom.message = await old_anom.message.edit(content=ping,
                                                           embed=display.embeds.anomaly(
                                                               world=WORLD_DICT[old_anom.world_id],
                                                               zone=ZONE_DICT[old_anom.zone_id],
                                                               timestamp=old_anom.timestamp,
                                                               state=STATE_DICT_INT[old_anom.state_id])
                                                           )
                del self.active_events[str(old_anom)]

        # create trigger for anomaly event and add it to the client
        anomaly_trigger = auraxium.Trigger(auraxium.event.MetagameEvent,
                                           worlds=WORLD_DICT.keys(),
                                           conditions=[anomaly_check],
                                           action=anomaly_event)
        client.add_trigger(anomaly_trigger)

        if self.websocket_ended:
            await client.close()
            await d_obj.channels['logs'].send(content='Anomaly Checker web-socket has been closed')

    @anomaly_check.before_loop
    async def before_anomaly_check(self):
        # check roles have been loaded and bot is ready
        await self.bot.wait_until_ready()

    @anomaly_check.after_loop
    async def after_anomaly_check(self):
        for anom in self.active_events.values():
            await anom.message.delete()

    @commands.slash_command(name="anomalystatus", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomlystatus(self, ctx: discord.ApplicationContext,
                           action: discord.Option(str, "Start, Stop or Status",
                                                  choices=("Start", "Stop", "Status"),
                                                  required=True)):
        """Provides Info on the status of the Anomaly Checker"""
        is_running = bool(self.event_client.triggers)
        match action:
            case "Start" if is_running:
                await ctx.respond(f"Anomaly Check is running with channel: {self.notif_channel}", ephemeral=True)
            case "Start" if not is_running:
                await ctx.respond(f"Anomaly Check started with channel: {self.notif_channel}", ephemeral=True)
                self.websocket_ended = False
                self.anomaly_check.start()
            case "Stop" if is_running:
                await ctx.respond(f"Anomaly Check stopped", ephemeral=True)
                self.websocket_ended = True
                await asyncio.sleep(1)
                self.anomaly_check.cancel()
            case "Stop" if not is_running:
                await ctx.respond("Anomaly Check already stopped", ephemeral=True)
            case "Status":
                await ctx.respond(f"Anomaly Check running: {is_running}"
                                  f"Last Trigger: {self.event_client.triggers[0].last_run}", ephemeral=True)

    @commands.slash_command(name="anomalyregistercreate", guild_ids=[cfg.general['guild_id']], default_permission=False)
    async def anomalyregistercreate(self, ctx: discord.ApplicationContext,
                                    channel: discord.Option(discord.TextChannel, "Register Channel", required=True)):
        """Creates anomaly notification registration message"""

        view = discord.ui.View(timeout=None)

        for world in self.notif_roles:
            role = self.notif_roles[world]
            label = WORLD_DICT[world]
            view.add_item(AnomalyRegisterButton(role, label))
        await channel.send("Click a button to register for notifications when an"
                           " Aerial Anomaly is detected on that server!", view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        """Called on bot restart, initializes, listens to and creates view as before or loads existing view."""
        guild = self.bot.get_guild(cfg.general['guild_id'])
        # dynamically retrieve or create roles for each world
        role_names = {i: f'{v} Anomalies' for i, v in WORLD_DICT.items()}
        for world_id in role_names:
            current_role = discord.utils.get(guild.roles, name=role_names[world_id])
            if current_role:
                self.notif_roles[world_id] = current_role
            else:
                self.notif_roles[world_id] = await guild.create_role(name=role_names[world_id])
        # set notification channel
        self.notif_channel = guild.get_channel(cfg.channels['anomaly-notification'])
        print("Initialized Anomaly Notifications")

        # Load view on restart, create button for each world
        view = discord.ui.View(timeout=None)

        for world in self.notif_roles:
            role = self.notif_roles[world]
            label = WORLD_DICT[world]
            view.add_item(AnomalyRegisterButton(role, label))
        self.bot.add_view(view)


def setup(client):
    client.add_cog(AnomalyChecker(client))

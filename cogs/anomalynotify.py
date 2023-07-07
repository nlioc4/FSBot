"""Cog to track Aerial Anomalies in game, and notify users when they are beginning on their selected servers."""
import datetime
# External Imports
from logging import getLogger
import discord
from discord.ext import commands, tasks
import asyncio
import auraxium
from auraxium import EventClient, Trigger
import aiohttp

# Internal Imports
from modules import discord_obj as d_obj, tools, database as db, config as cfg, tools
from display import AllStrings as disp, views, embeds

log = getLogger('fs_bot')

# 228(2),229(4),230(6),231(8),232(344)
WORLD_DICT = {1: "Connery", 10: "Miller", 13: "Cobalt", 17: "Emerald", 40: "Soltech"}
ZONE_DICT = {2: "Indar", 4: "Hossin", 6: "Amerish", 8: "Esamir", 344: "Oshur"}
AIRCRAFT_ID_DICT = {"Scythe": 7, "Reaver": 8, "Mosquito": 9, "Liberator": 10,
                    "Galaxy": 11, "Valkyrie": 14, "Dervish": 2136}
ANOMALY_IDS_STR = ['228', '229', '230', '231', '232']
ANOMALY_IDS = [228, 229, 230, 231, 232]
STATE_DICT_INT = {135: 'Started', 138: 'Ended'}
STATE_DICT_STR = {v: k for k, v in STATE_DICT_INT.items()}


class AnomalyEvent:
    """Class to represent individual anomalies"""

    @classmethod
    def from_dict(cls, data):
        """Create an AnomalyEvent from a dictionary"""
        return cls(
            int(data['metagame_event_id']),
            int(data['timestamp']),
            int(data['zone_id']),
            int(data['world_id']),
            int(data['instance_id']),
            int(data['metagame_event_state'])
        ).update_from_dict(data)

    @classmethod
    def from_evt(cls, evt: auraxium.event.MetagameEvent):
        """Create an AnomalyEvent from a MetagameEvent"""
        return cls(
            evt.metagame_event_id,
            evt.timestamp.replace(tzinfo=datetime.UTC).timestamp(),
            evt.zone_id,
            evt.world_id,
            evt.instance_id,
            evt.metagame_event_state
        ).update_from_evt(evt)

    def __init__(self, event_id, timestamp, zone_id, world_id, instance_id, event_state_id):
        self.event_id = event_id
        self.timestamp = timestamp
        self.end_stamp = 0
        self.zone_id = zone_id
        self.world_id = world_id
        self.instance_id = instance_id
        self.state_id = event_state_id
        self.nc_progress = 0.
        self.tr_progress = 0.
        self.vs_progress = 0.
        self.population = {}  # Population {faction_str: count}
        self.vehicle_data = {}  # Vehicle Data {faction_str: {vehicle_name: count}}
        self.kills_data = {}  # Per character aircraft kills {char_id: kills}
        self.top_ten_data = {}  # Top ten players {char_id: Kills}
        self.top_ten = {}  # Top ten players {FactionEmoji-CharName: Kills}

        self.message = None
        self.ping_str = ''  # String to ping role with
        self.unique_id = str(self)
        self.last_update_stamp = tools.timestamp_now()

    def __repr__(self):
        return repr(f'{self.world_id}-{self.instance_id}')

    def __str__(self):
        return str(f'{self.world_id}-{self.instance_id}')

    def to_dict(self):
        return {
            'unique_id': self.unique_id,
            'metagame_event_id': self.event_id,
            'timestamp': self.timestamp,
            'end_stamp': self.end_stamp,
            'zone_id': self.zone_id,
            'world_id': self.world_id,
            'instance_id': self.instance_id,
            'metagame_event_state': self.state_id,
            'faction_nc': self.nc_progress,
            'faction_tr': self.tr_progress,
            'faction_vs': self.vs_progress,
            'kill_data': {str(char_id): count for char_id, count in self.kills_data.items()},
            'message_id': self.message.id if self.message else 0

        }

    def update_from_evt(self, evt: auraxium.event.MetagameEvent):
        """Update the anomaly with new data
        Generally just updates the progress of each faction and state
        """

        self.nc_progress = evt.faction_nc
        self.tr_progress = evt.faction_tr
        self.vs_progress = evt.faction_vs
        self.state_id = evt.metagame_event_state
        if not self.is_active:
            self.end_stamp = evt.timestamp.replace(tzinfo=datetime.UTC).timestamp()

        self.last_update_stamp = tools.timestamp_now()
        log.info(f'Updated {self} by evt')
        return self

    def update_from_dict(self, data: dict):
        """Update the anomaly with new data
        Generally just updates the progress of each faction and state
        """

        self.nc_progress = int(data['faction_nc'])
        self.tr_progress = int(data['faction_tr'])
        self.vs_progress = int(data['faction_vs'])
        self.state_id = int(data['metagame_event_state'])
        if not self.is_active:
            self.end_stamp = int(data['timestamp'])

        self.last_update_stamp = tools.timestamp_now()

        if data.get('kill_data'):
            self.kills_data = {int(char_id): int(count) for char_id, count in data['kill_data'].items()}

        log.info(f'Updated {self} by dict')
        return self

    def update_vehicles(self, data: dict):
        """Update the anomaly with new vehicle data from graphql"""
        for vehicle in data:
            for faction in data[vehicle]:
                if faction not in self.vehicle_data:
                    self.vehicle_data[faction] = {vehicle: data[vehicle][faction]}
                else:
                    self.vehicle_data[faction][vehicle] = data[vehicle][faction]

        return self

    def update_population(self, data: dict):
        """Update the anomaly with faction specific population data from graphql"""
        for faction in data:
            self.population[faction] = data[faction]

    def add_kill(self, char_id):
        """Track a characters Kill in an Anomaly"""
        if char_id not in self.kills_data:
            self.kills_data[char_id] = 1
        else:
            self.kills_data[char_id] += 1

    def get_fac_total_vehicles(self, faction: str):
        """Returns the total number of vehicles for a faction"""
        if faction not in self.vehicle_data:
            return 0
        return sum(self.vehicle_data[faction].values())

    @property
    def is_active(self):
        """Returns True if anomaly is active"""
        return self.state_id != STATE_DICT_STR['Ended']

    @property
    def state_name(self):
        """Returns the name of the state"""
        return STATE_DICT_INT[self.state_id]

    @property
    def world_name(self):
        """Returns the name of the world"""
        return WORLD_DICT[self.world_id]

    @property
    def zone_name(self):
        """Returns the name of the zone"""
        return ZONE_DICT[self.zone_id]


class AnomalyRegisterButton(discord.ui.Button):
    def __init__(self, role: discord.Role, world_name: str):
        """A button to assign a role / register for a servers notify"""
        super().__init__(
            label=world_name,
            style=discord.ButtonStyle.blurple,
            custom_id=f"{world_name}-{role.id}"  # world_name-role_id to store both in one string
        )

    async def callback(self, interaction: discord.Interaction):
        """Function that runs when user clicks button, assigns or removes role"""
        user = interaction.user
        # user to be given role

        # split world name and role id from custom id
        world_name, role_id = self.custom_id.split('-')

        # retrieve role
        role = d_obj.guild.get_role(int(role_id))

        # Add role, notify user
        if role not in user.roles:
            await disp.ANOMALY_REGISTER.send_priv(interaction, world_name, delete_after=5)
            await user.add_roles(role)
        else:
            await user.remove_roles(role)
            await disp.ANOMALY_UNREGISTER.send_priv(interaction, world_name, delete_after=5)


class AnomalyCog(commands.Cog, name="AnomalyCog"):

    def __init__(self, client):
        self.bot: discord.Bot = client
        self.events: dict[str, AnomalyEvent] = {}
        self.notify_roles: dict[int, discord.Role] = {}
        self.char_id_to_name: dict[int, str] = {}
        self.notify_channel: discord.TextChannel | None = None
        self.view: views.FSBotView | None = None
        self.event_client = EventClient(loop=self.bot.loop, service_id=cfg.general['api_key'])
        self.anomaly_initialize.start()

    @property
    def all_events_list(self):
        return list(self.events.values())

    @tasks.loop(count=1)
    async def anomaly_initialize(self):
        """Called on bot restart, initializes, listens to and creates view as before or loads existing view.
        Pulls existing events from DB.
        """

        # Retrieve or create role for each world
        roles = asyncio.gather(*[d_obj.get_or_create_role(f'{WORLD_DICT[world_id]} Anomaly Notify', mentionable=False)
                                 for world_id in WORLD_DICT])
        self.notify_roles.update({world_id: role for world_id, role in zip(WORLD_DICT, await roles)})

        # set notify channel
        self.notify_channel = d_obj.channels['anomaly_notify']

        # Retrieve existing events from DB as list of
        try:
            old_events = await db.async_db_call(db.get_field, 'restart_data', 0, 'anomaly_events')
        except KeyError:
            old_events = []
        for event in old_events:
            anom = self.events[event['unique_id']] = AnomalyEvent.from_dict(event)
            try:
                anom.message = await self.notify_channel.fetch_message(event['message_id'])
            except discord.NotFound:
                log.info(f'Could not find message for anomaly {anom.unique_id}.  Waiting for REST to update...')

        log.info(f'Loaded anomaly events from DB: {len(self.events)}')

        # Create view
        self.view = views.FSBotView()
        for world_id, role in self.notify_roles.items():
            self.view.add_item(AnomalyRegisterButton(role, WORLD_DICT[world_id]))

        # Add view to bot
        self.bot.add_view(self.view)

        # Start listening to anomaly events
        self.event_client.add_trigger(Trigger(event=auraxium.event.MetagameEvent,
                                              worlds=WORLD_DICT.keys(),
                                              conditions=[lambda evt: evt.metagame_event_id in ANOMALY_IDS and
                                                                      evt.world_id in WORLD_DICT.keys()],
                                              action=self.anomaly_event_handler))

        # Start tracking VehicleDestroy events
        self.event_client.add_trigger(Trigger(event=auraxium.event.VehicleDestroy, worlds=WORLD_DICT.keys(),
                                              conditions=[lambda evt: evt.world_id in WORLD_DICT.keys()],
                                              action=self.vehicle_desteroy_event_handler))

        # Start event update loop
        self.anomaly_update_loop.start()

    @anomaly_initialize.before_loop
    async def before_anomaly_initialize(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def anomaly_check(event: auraxium.event.MetagameEvent):
        return event.metagame_event_id in ANOMALY_IDS

    async def _update_event_embed(self, anom: AnomalyEvent):
        """Updates the message with new data or send a new message if not found"""
        ping_str = f"Time to shoot some planes {self.notify_roles[anom.world_id].mention}!"
        log.debug(f'Updating anomaly {anom.unique_id} message')
        if anom.message:
            anom.message = await disp.ANOMALY_EVENT.edit(anom.message, ping_str, anomaly=anom)
        else:
            anom.message = await disp.ANOMALY_EVENT.send(d_obj.channels['anomaly_notify'],
                                                         '' if not anom.is_active else ping_str, anomaly=anom)
        return anom.message

    def update_event_embed(self, anom: AnomalyEvent):
        """Uses task to update message"""
        asyncio.create_task(self._update_event_embed(anom))

    async def update_all_from_rest(self):
        """
        Update all events from the REST API, useful for updating faction progress
        """
        removed = []
        async with aiohttp.ClientSession() as session:

            query = auraxium.census.Query(collection='world_event', service_id=cfg.general['api_key']).limit(1000)
            query.add_term(field='type', value='METAGAME')
            async with session.get(query.url()) as resp:
                data = await resp.json()
            try:
                data: list[dict[str, str]] = [event for event in data['world_event_list']  # type: ignore
                                              if int(event['metagame_event_id']) in ANOMALY_IDS]  # type: ignore
            except KeyError:
                log.info('Could not retrieve anomaly events from REST API. Retrying...')
                await asyncio.sleep(5)
                return await self.update_all_from_rest()

            ended = []
            for event in data:
                if anom := self.events.get(f'{event["world_id"]}-{event["instance_id"]}'):
                    # if event is already stored, update it
                    anom.update_from_dict(event)
                    if not anom.is_active:  # remove inactive events
                        log.debug(f'Removing inactive anomaly {anom.unique_id}')
                        self.update_event_embed(anom)  # Update Message here as it is being removed from self.events
                        ended.append(anom.unique_id)
                        removed.append(self.events.pop(anom.unique_id))

                elif event['metagame_event_state_name'] == 'ended':
                    # if event is not stored and is ended, add it to ended list to check against started events
                    ended.append(f"{event['world_id']}-{event['instance_id']}")

                elif event['metagame_event_state_name'] == 'started':
                    # check if there is an ended event with the same world and instance id
                    if f"{event['world_id']}-{event['instance_id']}" in ended or \
                            int(event['timestamp']) + 108000 < tools.timestamp_now():  # if event is older than 30 mins
                        log.debug(f'Skipping anomaly {event["world_id"]}-{event["instance_id"]} as it is ended')
                        continue

                    # if event is not stored and is active, store it
                    unique_id = f'{event["world_id"]}-{event["instance_id"]}'
                    self.events[unique_id] = AnomalyEvent.from_dict(event)
                    log.debug(f'Adding new anomaly from REST {unique_id}')
        return removed

    async def update_all_from_graphql(self):
        """Update all events with the Saerro.ps2.live GraphQL API, fills out vehicle data"""
        query_url = 'https://saerro.ps2.live/graphql?query={ allWorlds { name id zones { all { name id population' \
                    '{ nc tr vs } vehicles { liberator { nc tr vs } dervish { nc tr vs } valkyrie { nc tr vs } galaxy ' \
                    '{ nc tr vs } scythe { vs } reaver { nc } mosquito { tr } } } } } }'
        #  yeah, it's gross

        async with aiohttp.ClientSession() as session:
            async with session.get(query_url) as resp:
                data = await resp.json()
        data = data['data']['allWorlds']
        for event in self.events.values():
            # Loop through all events, check if world / zone is in data
            for world in data:
                if world['id'] == event.world_id:
                    for zone in world['zones']['all']:
                        if zone['id'] == event.zone_id:
                            # Update vehicle data
                            event.update_vehicles(zone['vehicles'])
                            event.update_population(zone['population'])
                            break
                    break

    async def save_all_to_db(self):
        """Save all events to DB"""
        if self.events:
            await db.async_db_call(db.set_field, 'restart_data', 0,
                                   {'anomaly_events': [event.to_dict() for event in self.events.values()]})
        else:
            await db.async_db_call(db.unset_field, 'restart_data', 0, {'anomaly_events': []})
        log.info(f'Saved {len(self.events)} anomaly events to DB...')

    async def anomaly_event_handler(self, evt: auraxium.event):
        # Check if event is stored already
        unique_id = f'{evt.world_id}-{evt.instance_id}'
        if anom := self.events.get(unique_id):
            anom.update_from_evt(evt)

            if not anom.is_active:
                await self.populate_char_kills_info([anom])
                self.events.pop(unique_id)
            else:
                await self.update_all_from_graphql()
            self.update_event_embed(anom)

        else:
            self.events[unique_id] = AnomalyEvent.from_evt(evt)
            self.update_event_embed(self.events[unique_id])

    def vehicle_desteroy_event_handler(self, evt: auraxium.event):
        """Validate vehicle destroy events are relevant, and then update an anomaly with a vehicle destroy event"""

        # Check if vehicledestroy is on relevant world and zone
        relevant_anom = [anom for anom in self.events.values() if anom.world_id == evt.world_id
                         and anom.zone_id == evt.zone_id]
        if not relevant_anom:
            return

        elif len(relevant_anom) > 1:
            log.warning(f'Found more than one relevant anomaly for vehicle destroy event... ignoring event...')
            return

        # Check if VehicleDestroy is not aircraft on aircraft
        if evt.attacker_vehicle_id not in AIRCRAFT_ID_DICT.values() or evt.vehicle_id not in AIRCRAFT_ID_DICT.values():
            return

        # Check if VehicleDestroy is a teamkill
        if evt.attacker_team_id == evt.faction_id:
            return

        relevant_anom[0].add_kill(evt.attacker_character_id)
        log.debug(f'Added kill to anomaly {relevant_anom[0].unique_id} for {evt.attacker_character_id}')

    async def populate_char_kills_info(self, events: list = None):
        """Get player character names and factions for a top ten killers list"""

        character_ids_to_fetch = []
        # Find the 10 players with the most kills in kills_data for each event
        for event in events or self.all_events_list:
            top_ten = event.top_ten_data
            log.debug(f'Checking top ten for {event.unique_id}, pulling from {len(event.kills_data)} characters')
            for char_id, kills in event.kills_data.items():
                if not event.top_ten or kills > min(top_ten.values()):
                    log.debug(f'Adding {char_id} to top ten for {event.unique_id}')
                    top_ten[char_id] = kills
                    if len(top_ten) > 10:
                        top_ten.pop(min(top_ten, key=top_ten.get))

            # Add the top ten to the list of character ids to fetch from the API
            character_ids_to_fetch.extend([str(char_id) for char_id in top_ten.keys()])

        if not character_ids_to_fetch:
            log.debug('No character ids to fetch from API')
            return

        # Fetch the character data from the API
        query = auraxium.census.Query(collection='character', service_id=cfg.general['api_key']).limit(10000)
        query.add_term(field='character_id', value=','.join(character_ids_to_fetch))

        async with aiohttp.ClientSession() as session:
            async with session.get(query.url()) as resp:
                data = await resp.json()

        data = data.get('character_list')

        # Create a dict of character id to name and faction emoji
        for character in data:
            char_id = int(character['character_id'])
            fac_emoji = cfg.emojis[cfg.factions[int(character['faction_id'])]]
            self.char_id_to_name[char_id] = f"{fac_emoji}{character['name']['first']}"

        # Build the display top ten dict
        for event in self.all_events_list:
            event.top_ten = {self.char_id_to_name[char_id]: kills for char_id, kills in event.top_ten_data.items()}
            log.debug(f"Top ten for {event.unique_id}: {event.top_ten}")

    @tasks.loop(minutes=2, seconds=30)
    async def anomaly_update_loop(self):
        """Update all anomaly events through REST API calls, and GRAPHQL calls, and then update embeds"""
        log.debug('Updating anomaly events...')
        removed = await self.update_all_from_rest()
        all_events = list(self.events.values()) + removed
        await self.update_all_from_graphql()
        await self.populate_char_kills_info(all_events)
        for anom in all_events:
            self.update_event_embed(anom)
        log.debug('Finished updating anomaly events...')

    @anomaly_update_loop.after_loop
    async def after_anomaly_update_loop(self):
        """Save all events to DB after loop ends"""
        await self.save_all_to_db()

    anomaly_commands = discord.SlashCommandGroup(
        name='anomaly',
        description='Anomaly Notification Commands',
        guild_ids=[cfg.general['guild_id']],
        default_member_permissions=discord.Permissions(manage_guild=True)
    )

    @anomaly_commands.command(name="send_register")
    async def anomalyregistercreate(self, ctx: discord.ApplicationContext,
                                    channel: discord.Option(discord.TextChannel, "Register Channel", required=False)):
        """Creates anomaly notification registration message"""
        channel = channel or ctx.channel
        await disp.ANOMALY_REGISTER_MSG.send(channel, view=self.view)
        await disp.ANOMALY_REGISTER_CREATED.send_priv(ctx, channel.mention, delete_after=5)

    @anomaly_commands.command(name="manual_update")
    async def anomalymanualupdate(self, ctx: discord.ApplicationContext):
        """Manually run update loop"""
        await ctx.defer(ephemeral=True)
        await self.anomaly_update_loop()
        await disp.ANOMALY_MANUAL_LOOP.send_priv(ctx, delete_after=5)


def setup(client):
    client.add_cog(AnomalyCog(client))

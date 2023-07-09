"""Cog to create a temporary room for a user to join and use.
Allows giving other users access to their own room."""

# External Imports
import discord
from discord.ext import commands
import asyncio
import atexit

# Internal Imports
from modules import discord_obj as d_obj, config as cfg
from display.strings import AllStrings as disp


class PrivateVoiceChannels(commands.Cog):
    _voice_channels: dict = {}

    def __init__(self, bot):
        self.bot = bot
        self._initial_channel_id: int = cfg.channels['private_voice_creator']
        self._voice_channels = PrivateVoiceChannels._voice_channels = {}  # dict of {voice_channel_obj: creator_id}

    async def _create_room(self, member: discord.Member):
        """Create a room for a user to join"""

        # Create a new channel
        new_channel = await member.guild.create_voice_channel(
            name=f"{member.name or member.display_name}'s Room",
            category=member.guild.get_channel(self._initial_channel_id).category,
            # Set permissions for the channel (allow the user, admins, and mods to view and connect
            overwrites={d_obj.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                        member: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True,
                                                            mute_members=True, deafen_members=True, manage_roles=True),
                        d_obj.roles['app_admin']: discord.PermissionOverwrite(view_channel=True, connect=True,
                                                                              send_messages=True),
                        d_obj.roles['admin']: discord.PermissionOverwrite(view_channel=True, connect=True),
                        d_obj.roles['mod']: discord.PermissionOverwrite(view_channel=True, connect=True),
                        d_obj.roles['bot']: discord.PermissionOverwrite(view_channel=True, connect=True)}
        )

        # Move the user to the new channel
        await member.move_to(new_channel)
        # Add the channel to the dict
        self._voice_channels[new_channel] = member.id

        # Send a message to the user
        # await disp.ROOM_CREATED.send(new_channel, member.mention,
        #                              self.invite_to_room.mention, self.kick_from_room.mention)
        await disp.ROOM_CREATED.send(new_channel, member.mention, '/room invite', '/room kick')

    async def _delete_room(self, channel: discord.VoiceChannel):
        """Delete a room that a user created"""
        await channel.delete()
        del self._voice_channels[channel]

    @classmethod
    async def delete_all(cls):
        """Delete all temporary channels"""
        await asyncio.gather(*[channel.delete() for channel in cls._voice_channels.keys()])
        cls._voice_channels = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState,
                                    after: discord.VoiceState):
        """Create a room if a user joins the creator channel, or delete a channel if the owner leaves"""

        # if the user joins the creator channel from their voice room, move them to their room
        if before.channel and before.channel.id in self._voice_channels.keys() and \
                self._voice_channels[before.channel] == member.id and after.channel.id == self._initial_channel_id:
            await member.move_to(before.channel)

        # Make new channel if user joins the creator channel
        if after.channel and after.channel.id == self._initial_channel_id:
            await self._create_room(member)

        # Delete channel if owner leaves
        elif before.channel and before.channel in self._voice_channels.keys() \
                and member.id == self._voice_channels[before.channel]:
            await self._delete_room(before.channel)

    voice_room_commands = discord.SlashCommandGroup(
        name='room',
        description='Voice Room Commands',
        guild_ids=[cfg.general['guild_id']],

    )

    async def _room_permissions_check(self, ctx: discord.ApplicationContext, channel: discord.VoiceChannel = None):
        # Check if the user is in a voice channel and that channel is in the dict
        if not ctx.user.voice or (room := channel or ctx.user.voice.channel) not in self._voice_channels.keys():
            await disp.ROOM_NOT_IN.send(ctx, delete_after=5)
            return False

        # Check the user is the owner or an admin of their channel
        if not ctx.user.id == self._voice_channels[room] or not d_obj.is_admin(ctx.user):
            await disp.ROOM_NOT_OWNER.send_priv(ctx, delete_after=5)
            return False

        return room

    @voice_room_commands.command(name='invite')
    async def invite_to_room(self, ctx: discord.ApplicationContext, member: discord.Member,
                             channel: discord.Option(discord.VoiceChannel,
                                                     "Admin Only: Room to invite a user to", required=False)):
        """Allow a user to see your voice room"""

        # Check permissions and room presence
        if not (room := await self._room_permissions_check(ctx, channel)):
            return

        # Check if the invited user already has permissions
        if member in room.members or member in room.overwrites.keys():
            await disp.ROOM_INVITED_ALREADY.send(ctx, member.mention, room.mention, delete_after=5)
            return

        # Add the user to the channel
        await asyncio.gather(
            room.set_permissions(member, connect=True, speak=True, view_channel=True),
            disp.ROOM_INVITED.send(room, ctx.user.mention),
            disp.ROOM_INVITE.send_priv(ctx, member.mention, room.mention, delete_after=5)
        )

    @voice_room_commands.command(name='kick')
    async def kick_from_room(self, ctx: discord.ApplicationContext, member: discord.Member,
                             channel: discord.Option(discord.VoiceChannel,
                                                     "Admin Only: Room to remove a user from",
                                                     required=False)):
        """Remove a user's access to your voice room"""

        # Check permissions and room presence
        if not (room := await self._room_permissions_check(ctx, channel)):
            return

        # Check if the removed user is actually in the room
        if member not in room.members and member not in room.overwrites.keys():
            await disp.ROOM_NOT_MEMBER.send_priv(ctx, member.mention, delete_after=5)
            return

        # Remove the user from the channel, and display a kicked message
        corus = [room.set_permissions(member, overwrite=None),
                 disp.ROOM_KICKED.send(room, member.mention),
                 disp.ROOM_KICK.send_priv(ctx, member.mention, room.mention, delete_after=5)]
        if member in room.members:
            corus.append(member.move_to(None))  # type: ignore

        await asyncio.gather(*corus)


def setup(bot):
    bot.add_cog(PrivateVoiceChannels(bot))

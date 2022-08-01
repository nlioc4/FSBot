"""Direct Messages cog, build to handle commands in DM's as well as modmail."""

# External Imports
import os

import discord
from discord.ext import commands
from logging import getLogger

# Internal Imports
import modules.config as cfg
import modules.discord_obj as d_obj
import modules.database as db
from display import AllStrings as disp, views

log = getLogger('fs_bot')

DM_THREADS = {}  # dict of threads by user_id: thread_id


def dm_threads_by_thread():
    return {v: k for k, v in DM_THREADS.items()}


def dm_threads_to_str():
    return {str(k): v for k, v in DM_THREADS.items()}


def int_dict_from_str(data: dict):
    return {int(k): int(v) for k, v in data.items()}


async def _stop_dm_thread(user_id, user_side):
    if user_id not in DM_THREADS:  # if thread does not exist
        return
    user = d_obj.bot.get_user(user_id)
    thread = d_obj.bot.get_channel(DM_THREADS[user_id])
    try:  # if thread hasn't been manually deleted, find message
        msg = await thread.parent.fetch_message(DM_THREADS[user_id])
    except AttributeError:
        log.info('No thread found when deleting thread %s', DM_THREADS[user_id])
    else:
        await thread.archive(locked=True)  # if thread was retrieved
        if user_side:
            await disp.DM_THREAD_CLOSE.edit(msg, view=False)
    finally:
        del DM_THREADS[user_id]
        await db.async_db_call(db.set_field, 'restart_data', 0, {'dm_threads': DM_THREADS})
        await disp.DM_THREAD_CLOSE.send(user)

class DMCog(commands.Cog):

    def __init__(self, client):
        self.bot = client
        self.bot.add_view(self.ThreadStopView())

    @commands.dm_only()
    @commands.slash_command(name="modmail")
    async def modmail(self, ctx: discord.ApplicationContext,
                      init_msg: discord.Option(str, 'Input your initial message to the mods here', required=True),
                      files=None):
        """Send a message to the staff of FS bot"""
        if ctx.author.id in DM_THREADS:
            await disp.DM_ALREADY.send_temp(ctx)
            return

        msg = await disp.DM_TO_STAFF.send(d_obj.channels['staff'], d_obj.roles['app_admin'].mention, author=ctx.author,
                                          msg=init_msg, view=self.ThreadStopView(), files=files)
        thread = await msg.create_thread(name=f'Modmail from {ctx.author.name}')
        await disp.DM_RECEIVED.send(ctx, init_msg)
        DM_THREADS[ctx.author.id] = thread.id
        await db.async_db_call(db.set_element, 'restart_data', 0, {'dm_threads': dm_threads_to_str()})

    @commands.Cog.listener(name='on_message')
    async def dm_listener(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        # If Mod response in a thread
        if isinstance(message.channel, discord.Thread) and message.channel.id in DM_THREADS.values():
            if not message.content.startswith(('~ ', '! ')):
                return
            files = []
            for file in message.attachments:
                files.append(await file.to_file())
            user = d_obj.bot.get_user(dm_threads_by_thread()[message.channel.id])
            await message.add_reaction('📨')
            await disp.DM_TO_USER.send(user, msg=message, files=files)
            return

        # alternate to /modmail
        if not message.guild and message.content.startswith(('modmail ', 'dm ', 'staff ')):
            files = []
            for file in message.attachments:
                files.append(await file.to_file())
            msg = message.clean_content
            i = msg.index(' ')
            msg = msg[i + 1:]
            await self.modmail.callback(self, ctx=message, init_msg=msg, files=files)
            return


        #  If player side request to stop DM thread
        if not message.guild and message.author.id in DM_THREADS and \
                message.content.startswith(('=stop', '=quit')):
            await _stop_dm_thread(message.author.id, user_side=True)
            return

        # if player response in dm
        if not message.guild and message.author.id in DM_THREADS:
            files = []
            for file in message.attachments:
                files.append(await file.to_file())
            thread = d_obj.bot.get_channel(DM_THREADS[message.author.id])
            await message.add_reaction('📨')
            await disp.DM_IN_THREAD.send(thread, message.author.mention, message.clean_content, allowed_mentions=False,
                                         files=files)

    class ThreadStopView(views.FSBotView):

        def __init__(self):
            super().__init__()

        @discord.ui.button(label="Stop thread", custom_id="stop_thread", style=discord.ButtonStyle.red)
        async def stop_thread_button(self, button: discord.Button, inter: discord.Interaction):
            try:
                user_id = dm_threads_by_thread()[inter.message.id]
            except KeyError:
                pass
            else:
                await _stop_dm_thread(user_id, user_side=False)
            await disp.DM_THREAD_CLOSE.edit(inter, view=False)
            self.stop()


def setup(client):
    client.add_cog(DMCog(client))

    #  init DM_THREADS from db
    data = db.get_field('restart_data', 0, 'dm_threads')
    if not data:
        log.info("No DM threads data found in database")
        return
    DM_THREADS.update(int_dict_from_str(data))
    log.info(f'{len(DM_THREADS)} DM thread{"s" if len(DM_THREADS) > 1 else ""} found in database')

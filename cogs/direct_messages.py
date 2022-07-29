"""Direct Messages cog, build to handle commands in DM's as well as modmail."""

# External Imports
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


async def init():
    global DM_THREADS
    DM_THREADS = await db.async_db_call(db.get_field, 'restart_data', 0, 'dm_threads')


def dm_threads_by_thread():
    return {v: k for k, v in DM_THREADS}


async def _stop_dm_thread(user_id):
    user = d_obj.bot.get_user(user_id)
    thread = d_obj.bot.get_channel(DM_THREADS[user_id])
    del DM_THREADS[user]
    await disp.DM_THREAD_CLOSE.send(user)
    await disp.DM_THREAD_CLOSE.send(thread)


class DMCog(commands.Cog):

    def __init__(self, client):
        self.bot = client
        self.bot.add_view(self.ThreadStopView())

    @commands.dm_only()
    @discord.slash_command(name="modmail")
    async def modmail(self, ctx: discord.ApplicationContext,
                      init_msg: discord.Option(str, 'Input your initial message to the mods here', required=True)
                      ):
        """Send a message to the staff of FS bot"""
        if ctx.author.id in DM_THREADS:
            await disp.DM_ALREADY.send_priv(ctx)
            return

        msg = await disp.DM_TO_STAFF.send(d_obj.channels['staff'], d_obj.roles['app_admin'].mention, author=ctx.author,
                                          msg=init_msg, view=self.ThreadStopView())
        thread = await msg.create_thread(name=f'Modmail from {ctx.author}')
        DM_THREADS[ctx.author.id] = thread.id
        await disp.DM_RECEIVED.send(ctx, init_msg)

    @commands.on

    @commands.Cog.listener(name='on_message')
    async def dm_listener(self, message: discord.Message):

        if message.author == self.bot.user:
            return

        # If Mod response in a thread
        if type(message.channel, discord.Thread) and message.channel.id in DM_THREADS.values():
            user = d_obj.bot.get_user(dm_threads_by_thread()[message.channel])
            await disp.DM_TO_USER.send(user, msg=message)
            return

        # if player response in dm
        if not message.guild and message.author.id in DM_THREADS:
            thread = d_obj.bot.get_channel(DM_THREADS[message.author.id])
            await disp.DM_RECEIVED.send(thread, message.author.mention, message.clean_content)

        # alternate to /modmail
        if not message.guild and message.content.startswith(('modmail', 'dm', 'tostaff')):
            await self.modmail.callback(message)

    class ThreadStopView(views.FSBotView):

        def __init__(self):
            super().__init__()

        @discord.ui.button(label="Stop thread", custom_id="stopthread")
        async def stop_thread_button(self, button: discord.Button, inter: discord.Interaction):
            user_id = dm_threads_by_thread()[inter.message.id]

            await _stop_dm_thread(user_id)
            await disp.DM_THREAD_CLOSE.send(inter)


def setup(client):
    client.add_cog(DMCog(client))

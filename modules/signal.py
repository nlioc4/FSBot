"""Intercept SIGINT and save restart data"""

#  External Imports
import asyncio
import signal
import sys
from logging import getLogger
import discord


# Internal Imports
import modules.database as db
import cogs.direct_messages
import modules.accounts_handler as accounts
import modules.census as census


log = getLogger('fs_bot')


async def save_state(loop):
    log.info('SIGINT caught, saving state...')

    # End all Matches


    # Terminate all active account sessions
    await accounts.terminate_all()

    # Ensure Auraxium event client's session is closed
    if census.EVENT_CLIENT.websocket:
        await census.EVENT_CLIENT.close()

    # save dm threads to DB, likely unnecesssary as threads are saved on creation/deletion
    dm_dict = cogs.direct_messages.dm_threads_to_str()
    db.set_field('restart_data', 0, {'dm_threads': dm_dict})

    # stop loop and exit
    log.info('Stopping...')
    loop.stop()
    sys.exit(0)


def init(client: 'discord.Bot'):
    try:
        loop = client.loop
        loop.add_signal_handler(signal.SIGINT, asyncio.create_task(save_state(loop)))
    except Exception as e:
        log.error('Error in signal init %s', e)

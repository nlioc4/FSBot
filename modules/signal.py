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
import cogs.private_voice_channels
import modules.accounts_handler as accounts
import modules.census as census
import classes.match


log = getLogger('fs_bot')


async def save_state(loop):
    log.info('SIGINT caught, saving state...')

    # End all Matches
    await classes.match.BaseMatch.end_all_matches()

    # Terminate all active account sessions
    await accounts.terminate_all()

    # Ensure Auraxium event client's session is closed
    if census.EVENT_CLIENT and census.EVENT_CLIENT.websocket:
        try:
            await census.EVENT_CLIENT.close()
        except Exception as e:
            log.error('Error closing event client %s', e)

    # save dm threads to DB, likely unnecessary as threads are saved on creation/deletion
    dm_dict = cogs.direct_messages.dm_threads_to_str()
    db.set_field('restart_data', 0, {'dm_threads': dm_dict})

    # delete active voice rooms
    try:
        await cogs.private_voice_channels.PrivateVoiceChannels.delete_all()
    except Exception as e:
        log.error('Error deleting voice channels %s', e)

    # stop loop and exit
    log.info('Stopping...')
    loop.stop()
    sys.exit(0)


def init(client: 'discord.Bot'):
    try:
        loop = client.loop
        loop.add_signal_handler(signal.SIGINT, loop.create_task, save_state(loop))
    except Exception as e:
        log.error('Error in signal init %s', e)

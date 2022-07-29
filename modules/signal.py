"""Intercept SIGINT and save restart data"""

#  External Imports
import signal
import sys
from logging import getLogger

# Internal Imports
import modules.database as db
import cogs.direct_messages
import discord

log = getLogger('fs_bot')


def save_state(loop):
    log.info('SIGINT caught, saving state...')
    dm_dict = cogs.direct_messages.dm_threads_to_str()
    db.set_field('restart_data', 0, {'dm_threads': dm_dict})
    log.info('Stopping...')
    loop.stop()
    sys.exit(0)


def init(client: 'discord.Bot'):
    try:
        loop = client.loop
        loop.add_signal_handler(signal.SIGINT, lambda: save_state(loop))
    except Exception as e:
        log.error('Error in signal init %s', e)

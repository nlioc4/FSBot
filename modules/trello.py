import asyncio
from logging import getLogger

import aiohttp
from aiohttp.abc import HTTPException

key = "5436804843f30f68797083532214f22b"  # API Key for Trello
token = "a814da22c985da09bca8e64b4c523d16e6a572e07ea17242b183c4f0d9de5724"  # Token they want
list_id = "62ed98a02d875925d90ff558"  # This is the ID of the list it is adding cards to

log = getLogger('fs_bot')


async def create_card(card_name, card_description):
    try:
        querystring = {"name": card_name, "desc": card_description, "idList": list_id, "key": key, "token": token}
        url = f"https://api.trello.com/1/cards"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=querystring) as r:
                if r.status == 200:
                    log.info("Created Trello Suggestion Card")
                else:
                    log.error("Failed to create Trello Suggestion Card with response: %s", r.json())

    except HTTPException as ex:
        log.error(f"Error creating Trello suggestion card with trace {ex}")


"""
| Handle asynchronous http requests. Taken from PogBot.
| Request to PS2 api: use :meth:`api_request_and_retry`.
| Standard HTTP request: use :meth:`request_code`.
"""

# External imports
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientError
from json import loads
from json.decoder import JSONDecodeError
from logging import getLogger
from discord.backoff import ExponentialBackoff
import asyncio
import modules.config as cfg



log = getLogger("fs_bot")


class ApiNotReachable(Exception):
    """
    Custom API request exception.

    :param url: Url which led to the error.
    """
    def __init__(self, url: str):
        self.url = url
        message = f"Cannot resolve Api ({url})!"
        log.error(message)
        super().__init__(message)


async def request_code(url: str) -> int:
    """
    Get the url requested.

    :param url: URL to get.
    :return: HTTP code returned.
    """
    async with ClientSession() as client:
        result = await _fetch_code(client, url)
        return result


async def post_request(url, data=None):
    # async with ClientSession(connector=TCPConnector(verify_ssl=False)) as client:
    ssl = cfg.LAUNCH_STR != "_test"
    async with ClientSession(connector=TCPConnector(verify_ssl=ssl)) as client:
        if data:
            kwargs = {"data": f'{data}', "headers": {'content-type': 'application/json'}}
        else:
            kwargs = dict()
        async with client.post(url, **kwargs) as response:
            log.debug(f"POST call at {url} returned: {response}")


async def api_request_and_retry(url: str, retries: int = 3) -> dict:
    """
    Try to query Planetside2 API.

    :param retries: (Optional, default: 3) Number of retries.
    :param url: URL to get.
    :return: Json dictionary returned by the API.
    :raise ApiNotReachable: if the request failed.
    """
    backoff = ExponentialBackoff()
    for i in range(retries):
        try:
            if i != 0:
                await asyncio.sleep(backoff.delay())
            j_data = await _request(url)
        except (ClientError, JSONDecodeError) as e:
            log.warning(f"API request: {e} on try {i} for {url}")
            # Try again
            continue
        if "returned" in j_data:
            # If something returned
            return j_data
        else:
            # If not, try again
            log.warning(f"Nothing returned on try {i} for {url}")
    # If nothing returned after retries, raise exception
    raise ApiNotReachable(url)


# PRIVATE FUNCTIONS:
async def _request(url: str) -> dict:
    """
    Simple HTTP request, parse the result as a json dictionary.

    :param url: URL to get.
    :return: Json dictionary of the result.
    """
    async with ClientSession() as client:
        result = await _fetch(client, url)
        return loads(result)


async def _fetch(client: ClientSession, url: str) -> str:
    """
    HTTP request.

    :param client: Asynchttp ClientSession object.
    :param url: URL to get.
    :return: result of the request as text.
    :raise: UnexpectedError if OK is not returned by the request.
    """
    async with client.get(url) as resp:
        if resp.status != 200:
            log.error(f'Status {resp.status} for url {url}')
            raise UnexpectedError(f'Received wrong status from http page: {resp.status}')
        return await resp.text()


async def _fetch_code(client, url):
    """
    HTTP request.

    :param client: Asynchttp ClientSession object.
    :param url: URL to get.
    :return: Code returned by the HTTP request.
    """
    async with client.get(url) as resp:
        return resp.status

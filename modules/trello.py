import requests
from logging import getLogger
from requests import HTTPError, Timeout, ConnectionError

key = "5436804843f30f68797083532214f22b"  # API Key for Trello
token = "a814da22c985da09bca8e64b4c523d16e6a572e07ea17242b183c4f0d9de5724"  # Token they want
list_id = "62ed98a02d875925d90ff558"  # This is the ID of the list it is adding cards to

log = getLogger('fs_bot')


def create_card(card_name, card_description):
    try:
        url = f"https://api.trello.com/1/cards"
        querystring = {"name": card_name, "desc": card_description, "idList": list_id, "key": key, "token": token}
        response = requests.request("POST", url, params=querystring)
        card_id = response.json()["id"]
        log.info(f"Created suggestion card under ID {card_id}")
    except (HTTPError, ConnectionError, Timeout) as ex:
        log.error(f"Error posting card on trello with trace{ex}")

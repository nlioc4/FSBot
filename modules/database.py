"""
| Handle interaction with the mongodb database.
Taken from POGBot, https://github.com/yakMM/POG-bot
"""

# External modules
import pymongo.collection
from pymongo import MongoClient
from asyncio import get_event_loop
from logging import getLogger
from typing import Callable

log = getLogger("fs_bot")

# dict for the collections
_collections: dict[str, pymongo.collection.Collection] = dict()


class DatabaseError(Exception):
    """
    Raised when an error occur when interacting with the database.

    :param msg: Error message.
    """
    def __init__(self, msg: str):
        message = "Error in database: " + msg
        super().__init__(message)


def init(config: dict):
    """
    Initialize the MongoClient and create a dictionary of available collections.

    :param config: Dictionary containing database config. Check :data:`modules.config.database`.
    """
    cluster = MongoClient(config["url"])
    db = cluster[config["cluster"]]
    for collection in config["collections"]:
        _collections[collection] = db[config["collections"][collection]]


def get_all_elements(init_class_method: Callable, collection: str):
    """
    Get all elements of a given collection.

    :param init_class_method: The data will be passed to this method.
    :param collection: Collection name.
    :raise DatabaseError: If an error occurs while passing data.
    """
    # Get all elements
    items = _collections[collection].find()
    # Pass them to the method
    try:
        for result in items:
            init_class_method(result)
    except KeyError as e:
        raise DatabaseError(f"KeyError when retrieving {collection} from database: {e}")


async def async_db_call(call: Callable, *args):
    """
    Call a db function asynchronously.

    :param call: Function to call.
    :param args: Args to pass to the called function.
    :return: Return the result of the call.
    """
    loop = get_event_loop()
    return await loop.run_in_executor(None, call, *args)


def force_update(collection: str, elements):
    """
    This is typically called from external scripts for db maintenance.
    Replace the whole collection by the provided elements.

    :param collection: Collection name.
    :param elements: Elements to insert.
    """
    _collections[collection].delete_many({})
    _collections[collection].insert_many(elements)


def set_field(collection: str, e_id: int, doc: dict):
    """
    Set the field of an element. In other words, update an element.

    :param collection: Collection name.
    :param e_id: Element id.
    :param doc: Data to set.
    :raise DatabaseError: If the element is not in the collection.
    """
    if _collections[collection].count_documents({"_id": e_id}) != 0:
        _collections[collection].update_one({"_id": e_id}, {"$set": doc})
    else:
        raise DatabaseError(f"set_field: Element {e_id} doesn't exist in collection {collection}")


def unset_field(collection: str, e_id: int, doc: dict):
    """
    Unset (remove) the field of an element. In other words, update an element.

    :param collection: Collection name.
    :param e_id: Element id.
    :param doc: Data to unset.
    :raise DatabaseError: If the element is not in the collection.
    """
    if _collections[collection].count_documents({"_id": e_id}) != 0:
        _collections[collection].update_one({"_id": e_id}, {"$unset": doc})
    else:
        raise DatabaseError(f"set_field: Element {e_id} doesn't exist in collection {collection}")


def push_element(collection: str, e_id: int, doc: dict):
    """
    Push data in the field of an element.

    :param collection: Collection name.
    :param e_id: Element id.
    :param doc: Data to push. The key should be the field to push to.
    :raise DatabaseError: If the element is not in the collection.
    """
    if _collections[collection].count_documents({"_id": e_id}) != 0:
        _collections[collection].update_one({"_id": e_id}, {"$push": doc})
    else:
        raise DatabaseError(f"set_field: Element {e_id} doesn't exist in collection {collection}")


def get_element(collection: str, item_id: int) -> (dict, None):
    """
    Get a single element.

    :param collection: Collection name.
    :param item_id: Element id.
    :return: Element found, or None if not found.
    """
    if _collections[collection].count_documents({"_id": item_id}) == 0:
        return
    item = _collections[collection].find_one({"_id": item_id})
    return item


def count_documents(collection: str) -> int:
    return _collections[collection].count_documents()




def get_field(collection: str, e_id: int, specific: str):
    """
    Get one field of a single element.

    :param collection: Collection name.
    :param e_id: Element id.
    :param specific: Field name.
    :return: Element found, or None if not found.
    """
    if _collections[collection].count_documents({"_id": e_id}) == 0:
        return
    item = _collections[collection].find_one({"_id": e_id}, {"_id": 0, specific: 1})[specific]
    return item


def set_element(collection: str, e_id: id, data: dict):
    """
    Set a whole element (with all its field). Replace if the element already exists.

    :param collection: Collection name.
    :param e_id: Element id.
    :param data: Element data.
    """
    if _collections[collection].count_documents({"_id": e_id}) != 0:
        _collections[collection].replace_one({"_id": e_id}, data)
    else:
        _collections[collection].insert_one(data)


def remove_element(collection: str, e_id: int):
    """
    Remove an element from the database.

    :param collection: Collection name
    :param e_id: Element id.
    :raise DatabaseError: If the element is not in the collection.
    """
    if _collections[collection].count_documents({"_id": e_id}) != 0:
        _collections[collection].delete_one({"_id": e_id})
    else:
        raise DatabaseError(f"Element {e_id} doesn't exist in collection {collection}")

"""
Display utilities, involving Message Enum for easier sending.
"""

#  External Imports
import discord


# Internal Imports


class Message:
    """Class for all_strings to use.  Enables cleaner code through string relocation"""

    def __init__(self, string, embed=None):
        self.__string = string
        self.__embed = embed

    def string(self, args):
        if self.__string:
            return self.__string.format(*args)
        else:
            return False




'''

Class to represent Jaeger Accounts available to the app
'''


class Account:
    # each Jaeger account

    def __init__(self, a_id, username, password, in_game, unique_usages):
        self.__id = a_id
        self.__username = username
        self.__password = password
        self.__in_game = in_game
        self.a_player = None
        self.__last_usage = dict()
        self.__unique_usages = unique_usages

    def update(self, username, password):
        self.__username = username
        self.__password = password

    @property
    def username(self):
        return self.__username

    @property
    def password(self):
        return self.__password

    @property
    def id(self):
        return self.__id

    @property
    def in_game(self):
        return self.__in_game

    @property
    def unique_usages(self):
        return self.__unique_usages

    @property
    def nb_unique_usages(self):
        return len(self.__unique_usages)

    def last_usage(self):
        return self.__last_usage

    def clean(self):
        self.a_player = None
        self.__last_usage = None

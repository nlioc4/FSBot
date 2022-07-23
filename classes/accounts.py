'''

Class to represent Jaeger Accounts available to the app
'''


class Account:
    # each Jaeger account

    def __init__(self, a_id, username, password, in_game, unique_usages):
        self.__id = a_id
        self.__username = username
        self.__password = password
        self.__ig_name = in_game
        self.__ig_ids = [0, 0, 0]
        self.a_player = None
        self.__last_usage = dict()
        self.__unique_usages = unique_usages
        self.message = None
        self.__validated = False
        self.__terminated = False

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
    def ig_name(self):
        return self.__ig_name

    @property
    def ig_ids(self):
        return self.__ig_ids

    @property
    def ig_names(self):
        return [f'{self.__ig_name}VS', f'{self.__ig_name}NC', f'{self.__ig_name}TR']

    @property
    def unique_usages(self):
        return self.__unique_usages

    @property
    def nb_unique_usages(self):
        return len(self.__unique_usages)

    def last_usage(self):
        return self.__last_usage

    @property
    def last_user_id(self):
        return self.__unique_usages[:-1]

    def clean(self):
        self.a_player = None
        self.__last_usage = None



"""
Class to represent Jaeger Accounts available to the app
"""
import discord.ui

import modules.tools as tools


class Account:
    # each Jaeger account

    def __init__(self, a_id, username, password, in_game, unique_usages):
        self.__id = a_id
        self.__username = username
        self.__password = password
        self.__ig_name = in_game
        self.__ig_ids = [0, 0, 0, 0]
        self.__online_id = None
        self.a_player = None
        self.__last_usage = {"account_id": self.id}
        self.__unique_usages = unique_usages
        self.message = None
        self.view = None
        self.timeout_coro = None
        self.logout_reminders = 0
        self.__validated = False
        self.__terminated = False
        self.__timeout_at: int = 0
        self.__cleaned = True

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
        return [f'{self.__ig_name}VS', f'{self.__ig_name}NC', f'{self.__ig_name}TR', f'{self.__ig_name}NS']

    @property
    def online_name(self):
        if self.__online_id:
            return self.ig_names[self.__ig_ids.index(self.__online_id)]
        return None

    def online_name_by_id(self, char_id):
        if char_id in self.ig_ids:
            return self.ig_names[self.__ig_ids.index(char_id)]
        return False

    @property
    def online_id(self):
        return self.__online_id

    @online_id.setter
    def online_id(self, value):
        self.__online_id = value

    @property
    def unique_usages(self):
        return self.__unique_usages

    @property
    def nb_unique_usages(self):
        return len(self.__unique_usages)

    @property
    def last_usage(self):
        return self.__last_usage

    @property
    def last_user_id(self):
        return self.__unique_usages[-1]

    @property
    def is_validated(self):
        return self.__validated

    @property
    def is_terminated(self):
        return self.__terminated

    @property
    def is_clean(self):
        return self.__cleaned

    @property
    def timeout_at(self):
        """Return the timestamp for the account timeout"""
        return self.__timeout_at

    def set_timeout(self, timeout_delay):
        """Set a new timestamp for the account timeout"""
        self.__timeout_at = tools.timestamp_now() + timeout_delay

    def timeout_delta(self):
        """Return the remaining time before the account timeout"""
        return self.__timeout_at - tools.timestamp_now()

    def clean(self):
        """Reset account usage variables"""
        self.a_player = None
        self.__last_usage = {"account_id": self.id}
        self.__validated = False
        self.__terminated = False
        if self.view and not self.view.is_finished():
            self.view.stop()
        self.view = None
        self.logout_reminders = 0
        if self.timeout_coro:
            self.timeout_coro.cancel()
            self.timeout_coro = None
        self.__cleaned = True

    def add_usage(self, player):
        """Add a new usage to the account, includes only initial usage data."""
        self.__cleaned = False
        self.a_player = player
        self.__last_usage.update({"user_id": self.a_player.id,
                                  "match_id": self.a_player.match.id if self.a_player.match else 0,
                                  "character_usage": []})

    def validate(self):
        if self.__validated:
            return False
        self.__validated = True
        self.__unique_usages.append(self.a_player.id)
        self.__last_usage.update({"start_time": tools.timestamp_now()})
        return True

    def terminate(self):
        """Mark account as terminated, add end time to last usage."""
        self.__terminated = True
        self.__last_usage['end_time'] = tools.timestamp_now()

    def login(self):
        """Add login usage to last usage."""
        if self.a_player:
            self.last_usage['character_usage'].append(f"Login:{self.online_name}:{tools.timestamp_now()}")

    def logout(self):
        """Add logout usage to last usage."""
        if self.a_player:
            self.last_usage['character_usage'].append(f"Logout:{self.online_name}:{tools.timestamp_now()}")

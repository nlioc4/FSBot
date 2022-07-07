"""
Main display classes, involving Message Enum for easier sending.
"""

#  External Imports
import discord


# Internal Imports


class Message:
    """Class for all_strings to use.  Enables cleaner code through string relocation"""

    def __init__(self, string, ping=True, embed=None):
        self.__string = string
        self.__ping = ping
        self.__embed = embed

    def get_string(self, ctx, elements, args):
        if self.__string:
            string = self.string.format(*args)

        if self.__ping:
            try:
                mention = ctx.author.mention
                string = f'{mention} {string}'
            except AttributeError:
                pass

        elements['content'] = string

    def get_ui(self, ctx, elements, **kwargs):
        if self.__embed:
            embed = self.__embed(ctx, **kwargs)

            embed.set_author(name="FS Bot",
                             url="https://www.discord.gg/flightschool",
                             icon_url="https://cdn.discordapp.com/attachments/875624069544939570/993393648559476776"
                                      "/pfp.png")
            elements['embed'] = embed

    def get_file(self, ctx, elements, file_path):
        if file_path:
            elements['file'] = discord.File(file_path)

    def get_elements(self, ctx, **kwargs):

        elements = dict()
        self.get_string(ctx, elements, kwargs.get('string_args'))
        self.get_ui(ctx, elements, kwargs.get('ui_kwargs'))
        self.get_image(ctx, elements, kwargs.get('file_path'))

        return elements

    def string(self, args):
        if self.__string:
            return self.__string.format(*args)
        else:
            return False


class ContextWrapper:

    client = None

    @classmethod
    def init(cls, client):
        cls.client = client

    @classmethod
    def wrap(cls, ctx, author=None):
        if isinstance(ctx, cls):
            channel_id = ctx.channel_id
            author = ctx.author
            message = ctx.message
            original_ctx = ctx.original_ctx
            return cls(author, channel_id, message, original_ctx)
        elif isinstance(ctx, discord.Interaction.followup):
            return FollowupContext(ctx)
        elif isinstance(ctx, discord.Interaction):
            return InteractionContext(ctx)
        try:
            channel_id = ctx.channel.id
        except AttributeError:
            channel_id = 0
        if not author:
            try:
                author = ctx.author
            except AttributeError:
                pass
        if not author:
            try:
                author = ctx.user
            except AttributeError:
                pass
        try:
            message = ctx.message
        except AttributeError:
            message = None
        return cls(author, channel_id, message, ctx)

    def __init__(self, author, channel_id, message, original_ctx):
        self.author = author,
        self.channel_id = channel_id,
        self.message = message,
        self.original_ctx = original_ctx
        self.interaction_obj = None

    @classmethod
    def user(cls, user_id: int):
        user = cls.client.get_user(user_id)
        return cls(user, user_id, None, user)

    @classmethod
    def channel(cls, channel_id: int):
        channel = cls.client.get_channel(channel_id)
        return cls(None, channel.id, None, channel)

    async def send(self, **kwargs):
        return await self._do_send('send', kwargs)

    async def edit(self, **kwargs):
        return await self._do_send('edit', kwargs)

    async def _do_send(self, command, kwargs):
        msg = await getattr(self.original_ctx, command)(**kwargs)  #  add interaction handler
        return msg


class InteractionContext(ContextWrapper):
    def __init__(self, interaction, ephemeral=True):
        channel_id = interaction.channel_id
        author = interaction.user
        message = interaction.message
        ctx = interaction.response
        self.ephemeral = ephemeral
        super().__init__(author, channel_id, message, ctx)

    async def send(self, **kwargs):
        if self.ephemeral:
            kwargs['ephemeral'] = True
        return await self._do_send('send_message', kwargs)


class FollowupContext(ContextWrapper):
    def __init__(self, interaction, ephemeral=True):
        channel_id = interaction.channel_id
        author = interaction.user
        message = interaction.message
        ctx = interaction.followup
        self.ephemeral = ephemeral
        super().__init__(author, channel_id, message, ctx)

    async def send(self, **kwargs):
        if self.ephemeral:
            kwargs['ephemeral'] = True
        return await self._do_send('send', kwargs)
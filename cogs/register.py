"""
Cog to handle registration, de-registration and parameter modification,
 mostly through message components."""

# Internal Imports
import modules.config as cfg
import classes
from classes.players import Player, SkillLevel
import modules.database as db
from display import AllStrings as disp
import modules.discord_obj as d_obj

# External Imports
import discord
from discord.ext import commands


# Views
class RulesView(discord.ui.View):
    """Defines view to accept rules and start a player profile"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept Rules", custom_id="rules-accept", style=discord.ButtonStyle.green)
    async def rules_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        p: classes.Player = classes.Player.get(interaction.user.id)
        if p and p.hidden:
            await interaction.response.send_message(content=f'Welcome back {interaction.user.mention}! We missed you!',
                                                    ephemeral=True, delete_after=15)
            p.hidden = False
            await p.db_update('hidden')
            await interaction.user.add_roles(d_obj.roles['view_channels'], reason="Rules Accepted")
        elif p and not p.hidden:
            await interaction.response.send_message(content=f"You've already accepted the rules "
                                                            f"{interaction.user.mention}!",
                                                    ephemeral=True, delete_after=15)
        else:
            p = classes.Player(interaction.user.id, interaction.user.display_name)
            await db.async_db_call(db.set_element, 'users', p.id, p.get_data())
            await interaction.user.add_roles(d_obj.roles['view_channels'], reason="Rules Accepted")
            await interaction.response.send_message(content=f"You have accepted the rules "
                                                            f"{interaction.user.mention}, have fun!",
                                                    ephemeral=True, delete_after=15)

    @discord.ui.button(label="Hide Category", custom_id="rules-hide", style=discord.ButtonStyle.red)
    async def hide_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        p: classes.Player = classes.Player.get(interaction.user.id)
        if p and p.hidden:
            await interaction.response.send_message(content=f"You've already hidden the FSBot "
                                                            f"channels {interaction.user.mention}!",
                                                    ephemeral=True, delete_after=15)

        elif p and not p.hidden:
            await interaction.response.send_message(content=f"See you soon {interaction.user.mention}, "
                                                            f"you're always welcome back!",
                                                    ephemeral=True, delete_after=15)
            await interaction.user.remove_roles(d_obj.roles['view_channels'], reason="Chose Hidden")
            p.hidden = True
            await p.db_update('hidden')
        else:
            await interaction.response.send_message(content=f"You can't hide something you have never seen!",
                                                    ephemeral=True, delete_after=15)


class SkillLevelDropdown(discord.ui.Select):
    """Select Menu for Register View, defines player skill level"""

    def __init__(self):
        options = []
        for level in list(SkillLevel):
            options.append(discord.SelectOption(label=str(level), value=level.name, description=level.description))

        super().__init__(placeholder="Choose your own skill level...",
                         min_values=1,
                         max_values=1,
                         options=options,
                         custom_id="register-skill_level"
                         )

    async def callback(self, inter: discord.Interaction):
        p: classes.Player = classes.Player.get(inter.user.id)
        p.skill_level = SkillLevel[self.values[0]]
        await p.db_update('skill_level')
        await disp.SKILL_LEVEL.send_priv(inter, str(p.skill_level))


class RequestedSkillLevelDropdown(discord.ui.Select):
    """Select Menu for Register View, defines requested player skill level"""

    def __init__(self):
        options = [discord.SelectOption(label='Any', description='No preference on opponent skill level')]
        for level in list(SkillLevel):
            options.append(discord.SelectOption(label=str(level), value=level.name, description=level.description))

        super().__init__(placeholder="Choose the level(s) you'd like to duel...",
                         min_values=1,
                         max_values=1+len(list(SkillLevel)),
                         options=options,
                         custom_id="register-requested_skill_level"
                         )

    async def callback(self, inter: discord.Interaction):
        p: classes.Player = classes.Player.get(inter.user.id)
        if 'Any' in self.values or len(self.values) >= len(list(SkillLevel)):
            p.req_skill_levels = []
            await p.db_update('req_skill_levels')
            await disp.SKILL_LEVEL_REQ_ONE.send_priv(inter, 'No Preference')
            return

        p.req_skill_levels = [SkillLevel[value] for value in self.values]
        p.req_skill_levels.sort(key=SkillLevel.sort)
        skill_level_str = ' '.join([f'[{level.rank}:{str(level)}]' for level in p.req_skill_levels])
        await p.db_update('req_skill_levels')

        if len(self.values) > 1:
            await disp.SKILL_LEVEL_REQ_MORE.send_priv(inter, skill_level_str)
        elif len(self.values) == 1:
            await disp.SKILL_LEVEL_REQ_ONE.send_priv(inter, skill_level_str)


class PreferredFactionDropdown(discord.ui.Select):
    """Select Menu for Register View, defines player preferred faction"""

    def __init__(self):
        options = []
        esfs_dict = {'VS': 'Scythe', 'NC': 'Reaver', 'TR': 'Mosquito'}
        for faction in cfg.factions.values():
            options.append(discord.SelectOption(label=faction,
                                                description=esfs_dict[faction],
                                                emoji=cfg.emojis[faction]))

        super().__init__(placeholder="Choose your preferred faction(s)...",
                         min_values=1,
                         max_values=3,
                         options=options,
                         custom_id="register-pref_faction"
                         )

    async def callback(self, interaction: discord.Interaction):
        p: classes.Player = classes.Player.get(interaction.user.id)
        p.pref_factions.clear()
        p.pref_factions = self.values
        await p.db_update('pref_factions')
        factions_str = ''
        for fac in self.values:
            factions_str += f'[{fac}:{cfg.emojis[fac]}]'
        string = f"Your preferred faction is now: {factions_str}" if len(self.values) == 1 else \
            f"Your preferred factions are now: {factions_str}"
        await interaction.response.send_message(content=string,
                                                ephemeral=True, delete_after=15)


class RegisterCharacterModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.InputText(
                label="Input Character(s)",
                placeholder="Examples: AIMxColin or AIMxColinVS,AIMxColinNC,AIMxColinTR",
                style=discord.InputTextStyle.long,
                min_length=2,
                max_length=150
            ),
            title="Jaeger Character Registration",

        )

    async def callback(self, inter: discord.Interaction):
        p: classes.Player = classes.Player.get(inter.user.id)
        char_list = self.children[0].value.split(',')
        for char in char_list:
            char.strip()
        await inter.response.defer(ephemeral=True)
        inter = inter.followup
        if len(char_list) == 1 or len(char_list) == 3:  # if base char name, or individual names provided
            try:
                registered = await p.register(char_list)
                if registered:
                    await disp.REG_SUCCESSFUL_CHARS.send_priv(inter, *p.ig_names)
                else:
                    await disp.REG_ALREADY_CHARS.send_priv(inter, *p.ig_names)
            except classes.players.CharMissingFaction as e:
                await disp.REG_MISSING_FACTION.send_priv(inter, e.faction)
            except classes.players.CharAlreadyRegistered as e:
                await disp.REG_ALREADY_CHARS.send_priv(inter, e.char, e.player)
            except classes.players.CharInvalidWorld as e:
                await disp.REG_NOT_JAEGER.send_priv(inter, e.char)
            except classes.players.CharNotFound as e:
                await disp.REG_CHAR_NOT_FOUND.send_priv(inter, e.char)
        else:  # if any other format provided
            await disp.REG_WRONG_FORMAT.send_priv(inter)


class RegisterView(discord.ui.View):
    """
    Defines a view for registering skill level, jaeger accounts and other preferences.
    """

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SkillLevelDropdown())
        self.add_item(RequestedSkillLevelDropdown())
        self.add_item(PreferredFactionDropdown())

    @discord.ui.button(label="Register: Personal Jaeger Account", custom_id="register-own_account",
                       style=discord.ButtonStyle.green)
    async def register_account_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterCharacterModal())

    @discord.ui.button(label="Register: No Jaeger Account", custom_id="register-no_account",
                       style=discord.ButtonStyle.green)
    async def register_no_account_button(self, button: discord.ui.Button, inter: discord.Interaction):
        p = classes.Player.get(inter.user.id)
        registered = await p.register(None)
        if registered:
            await disp.REG_SUCCESFUL_NO_CHARS.send_priv(inter)
        else:
            await disp.REG_ALREADY_NO_CHARS.send_priv(inter)


class RegisterCog(discord.Cog, name='RegisterCog', command_attrs=dict(guild_ids=[cfg.general['guild_id']],
                                                                      default_permission=False)):
    def __init__(self, bot):
        self.bot = bot
        self.register_message = None
        self.rules_message = None

    @commands.slash_command(name="rulesinit")
    async def rulesinit(self, ctx: discord.ApplicationContext):
        """Posts Rules Message in current channel"""
        self.rules_message = await ctx.channel.send(content="Click below to accept the rules or hide the FSBot "
                                                            "channels!", view=RulesView())
        await ctx.respond(content="Rules Message Posted", ephemeral=True, delete_after=15)

    @commands.slash_command(name="registerinit")
    async def registerinit(self, ctx: discord.ApplicationContext):
        """Posts Register Message in current channel"""
        self.register_message = await ctx.channel.send(content="PLACEHOLDER: REGISTER/Settings", view=RegisterView())
        await ctx.respond(content="Register and Settings Message Posted", ephemeral=True, delete_after=15)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(RulesView())
        self.bot.add_view(RegisterView())


def setup(client):
    client.add_cog(RegisterCog(client))

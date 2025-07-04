# cogs/armor_events.py - Complete working version with recruit system
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, UserSelect, Select, Modal, TextInput
import logging
import datetime
from typing import Optional, Dict, List

from utils.database import EventDatabase
from utils.config import *

logger = logging.getLogger(__name__)

class ArmorEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Armor Events cog initialized")

    @app_commands.command(name="schedule_event")
    @app_commands.describe(
        event_type="Type of armor event",
        date="Date in YYYY-MM-DD format (e.g., 2025-06-15)",
        time="Time in HH:MM format, 24-hour (e.g., 20:00)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Saturday Brawl", value="saturday_brawl"),
        app_commands.Choice(name="Sunday Operations", value="sunday_ops"),
        app_commands.Choice(name="Training Event", value="training"),
        app_commands.Choice(name="Tournament", value="tournament"),
        app_commands.Choice(name="Custom Event", value="custom")
    ])
    async def schedule_event(self, interaction: discord.Interaction, event_type: app_commands.Choice[str],
                           date: str = None, time: str = None):
        
        if not any(role.name in ADMIN_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        
        # Parse datetime
        event_datetime = None
        if date:
            if not time:
                time = "20:00"
            try:
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                time_obj = datetime.datetime.strptime(time, "%H:%M").time()
                event_datetime = datetime.datetime.combine(date_obj, time_obj)
                if event_datetime < datetime.datetime.now():
                    await interaction.response.send_message("❌ Cannot schedule in the past!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Invalid date/time format.", ephemeral=True)
                return

        # Get preset (no custom title, use default)
        preset = self.get_event_preset(event_type.value)
        
        # Create event in database (with error handling)
        try:
            event_id = self.db.create_event(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                creator_id=interaction.user.id,
                title=preset["title"],
                description=preset["description"],
                event_time=event_datetime,
                event_type=event_type.value
            )
        except Exception as e:
            # If database fails, create without it
            logger.error(f"Database error: {e}")
            event_id = 99999  # Fake ID
        
        # Create event signup with full functionality
        view = EventSignupView(preset["title"], preset["description"], event_datetime, event_type.value, event_id)
        embed = view.build_embed(interaction.user)
        message = await interaction.channel.send(embed=embed, view=view)
        view.message = message
        
        # Auto-create map vote (separate message) - FIXED VERSION FOR 7 DAYS
        map_vote_success = await self.create_map_vote(interaction.channel, event_datetime, event_id)
        
        # Response
        response = f"✅ {event_type.value.replace('_', ' ').title()} created!"
        if event_datetime:
            response += f"\n📅 <t:{int(event_datetime.timestamp())}:F>"
        
        if map_vote_success:
            response += f"\n🗳️ Map vote created automatically!"
        else:
            response += f"\n⚠️ Map vote could not be created (MapVoting cog not available)"
            
        await interaction.response.send_message(response, ephemeral=True)

    def get_event_preset(self, event_type: str):
        presets = {
            "saturday_brawl": {
                "title": "🮦 504th HellFire SATURDAY Armor Brawl",
                "description": "**Victory Condition:** Team with the most time on the middle cap wins.\n**Format:** 6v6 Crew Battles"
            },
            "sunday_ops": {
                "title": "🎯 Sunday Armor Operations", 
                "description": "**Mission Type:** Combined Arms Operations\n**Format:** Tactical Gameplay"
            },
            "training": {
                "title": "🎓 Armor Training Session",
                "description": "**Focus:** Skill Development & Practice\n**Format:** Training Exercises"
            },
            "tournament": {
                "title": "🏆 Armor Tournament",
                "description": "**Format:** Competitive Bracket\n**Stakes:** Championship Event"
            },
            "custom": {
                "title": "⚔️ Custom Armor Event",
                "description": "**Format:** Custom Event\n**Details:** TBD"
            }
        }
        return presets.get(event_type, presets["custom"])

    async def create_map_vote(self, channel, event_datetime, event_id):
        """Create map vote that ends 1 hour before event starts"""
        try:
            logger.info(f"🔍 DEBUG: Looking for MapVoting cog...")
            map_voting_cog = self.bot.get_cog('MapVoting')
            
            if not map_voting_cog:
                logger.warning(f"❌ DEBUG: MapVoting cog not found!")
                logger.info(f"Available cogs: {list(self.bot.cogs.keys())}")
                return False
            
            logger.info(f"✅ DEBUG: Found MapVoting cog")
            
            # Calculate vote duration
            if event_datetime:
                now = datetime.datetime.now()
                
                # Calculate when the vote should END (1 hour before event)
                vote_end_time = event_datetime - datetime.timedelta(hours=1)
                
                # Calculate how long the vote should run (from now until vote_end_time)
                vote_duration_seconds = (vote_end_time - now).total_seconds()
                vote_duration_minutes = int(vote_duration_seconds / 60)
                
                logger.info(f"🔍 DEBUG: Event time: {event_datetime}")
                logger.info(f"🔍 DEBUG: Current time: {now}")
                logger.info(f"🔍 DEBUG: Vote should END at: {vote_end_time}")
                logger.info(f"🔍 DEBUG: Calculated vote duration: {vote_duration_minutes} minutes")
                
                # Handle edge cases
                if vote_duration_minutes <= 15:
                    # Event is very soon (less than 1 hour 15 minutes away)
                    duration_minutes = 30  # Give at least 30 minutes
                    logger.info(f"🔍 DEBUG: Event too soon, using minimum 30 minute vote")
                else:
                    # Use the calculated duration (vote ends 1 hour before event)
                    # No maximum cap - vote runs however long needed
                    duration_minutes = vote_duration_minutes
                    logger.info(f"🔍 DEBUG: Using calculated duration to end 1 hour before event")
            else:
                # No event time set, use default 7 days
                duration_minutes = 10080  # 7 days
                logger.info(f"🔍 DEBUG: No event time set, using default 7 day vote")
            
            logger.info(f"🔍 DEBUG: Final vote duration: {duration_minutes} minutes ({duration_minutes/1440:.1f} days)")
            actual_end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
            logger.info(f"🔍 DEBUG: Vote will actually end at: {actual_end_time}")
            
            # Create the map vote
            if hasattr(map_voting_cog, 'create_auto_mapvote'):
                result = await map_voting_cog.create_auto_mapvote(event_id, channel, duration_minutes)
                if result:
                    logger.info(f"✅ DEBUG: Map vote created successfully for {duration_minutes} minutes")
                    return True
                else:
                    logger.error(f"❌ DEBUG: Map vote creation returned None/False")
                    return False
            else:
                logger.error(f"❌ DEBUG: create_auto_mapvote method not found")
                available_methods = [method for method in dir(map_voting_cog) if not method.startswith('_')]
                logger.info(f"Available methods: {available_methods}")
                return False
                
        except Exception as e:
            logger.error(f"❌ DEBUG: Error creating map vote: {e}")
            return False

class EventSignupView(View):
    def __init__(self, title, description, event_time=None, event_type="custom", event_id=None):
        super().__init__(timeout=None)
        self.title = title
        self.description = description
        self.event_time = event_time
        self.event_type = event_type
        self.event_id = event_id
        self.message = None
        
        # Initialize data
        self.commander_a = None
        self.commander_b = None
        self.crews_a = [None] * MAX_CREWS_PER_TEAM
        self.crews_b = [None] * MAX_CREWS_PER_TEAM
        self.recruits = []  # Changed from solo_players to recruits
        
        # Add buttons (WITH recruit system)
        self.add_item(CommanderSelect(self))
        self.add_item(JoinCrewAButton(self))
        self.add_item(JoinCrewBButton(self))
        self.add_item(RecruitMeButton(self))  # Changed from SoloSignupButton
        self.add_item(RecruitPlayersButton(self))  # NEW button for commanders
        self.add_item(EditCrewButton(self))
        self.add_item(LeaveEventButton(self))

    def build_embed(self, author=None):
        embed = discord.Embed(title=self.title, description=self.description, color=0xFF0000)
        
        if self.event_time:
            embed.add_field(name="⏰ Event Time", 
                          value=f"<t:{int(self.event_time.timestamp())}:F>\n<t:{int(self.event_time.timestamp())}:R>", 
                          inline=False)
        
        # Commanders
        commanders = f"**Allies:** {self.commander_a.mention if self.commander_a else '[Unclaimed]'}\n"
        commanders += f"**Axis:** {self.commander_b.mention if self.commander_b else '[Unclaimed]'}"
        embed.add_field(name="👑 Commanders", value=commanders, inline=False)

        # Format crews
        def format_crew(slot):
            if slot is None:
                return "[Empty Slot]"
            cmd = slot['commander'].mention
            gun = slot['gunner'].mention if slot['gunner'] != slot['commander'] else "*Self*"
            drv = slot['driver'].mention if slot['driver'] != slot['commander'] else "*Self*"
            return f"**[{slot['crew_name']}]**\nCmd: {cmd}\nGun: {gun}\nDrv: {drv}"

        allies_text = "\n\n".join([f"{i+1}. {format_crew(crew)}" for i, crew in enumerate(self.crews_a)])
        axis_text = "\n\n".join([f"{i+1}. {format_crew(crew)}" for i, crew in enumerate(self.crews_b)])
        
        embed.add_field(name="🗾 Allies Crews", value=allies_text, inline=True)
        embed.add_field(name="🔵 Axis Crews", value=axis_text, inline=True)
        
        # Available recruits (changed from solo players)
        recruit_text = "\n".join([f"- {user.mention}" for user in self.recruits]) or "[None Available]"
        embed.add_field(name="🎯 Available Recruits", value=recruit_text, inline=False)
        
        if author:
            embed.set_footer(text=f"Created by {author.display_name}")
        
        return embed

    def is_user_registered(self, user):
        """Check if user is already registered"""
        if user in [self.commander_a, self.commander_b]:
            return True
        for crew_list in [self.crews_a, self.crews_b]:
            for crew in crew_list:
                if isinstance(crew, dict) and user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    return True
        return user in self.recruits

    def get_user_crew(self, user):
        """Get the crew and team for a user"""
        for team, crew_list in [("A", self.crews_a), ("B", self.crews_b)]:
            for i, crew in enumerate(crew_list):
                if isinstance(crew, dict) and crew["commander"] == user:
                    return crew, team, i
        return None, None, None

    def is_user_commander(self, user):
        """Check if user is a crew commander"""
        crew, team, slot_index = self.get_user_crew(user)
        return crew is not None

    async def update_embed(self, interaction):
        if self.message:
            embed = self.build_embed()
            await self.message.edit(embed=embed, view=self)

# UI Components
class CommanderSelect(Select):
    def __init__(self, view):
        options = [
            discord.SelectOption(label="Allies Commander", value="A", emoji="🗾"),
            discord.SelectOption(label="Axis Commander", value="B", emoji="🔵")
        ]
        super().__init__(placeholder="Become a Team Commander", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        team = self.values[0]
        if team == "A":
            self.view_ref.commander_a = interaction.user
        else:
            self.view_ref.commander_b = interaction.user
        
        await self.view_ref.update_embed(interaction)
        await interaction.response.send_message(f"✅ You are now {team} Commander!", ephemeral=True)

class JoinCrewAButton(Button):
    def __init__(self, view):
        super().__init__(label="🗾 Join Allies Crew", style=discord.ButtonStyle.primary)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        await interaction.response.send_message(view=CrewSelectView(self.view_ref, "A", interaction.user), ephemeral=True)

class JoinCrewBButton(Button):
    def __init__(self, view):
        super().__init__(label="🔵 Join Axis Crew", style=discord.ButtonStyle.danger)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        await interaction.response.send_message(view=CrewSelectView(self.view_ref, "B", interaction.user), ephemeral=True)

class RecruitMeButton(Button):
    def __init__(self, view):
        super().__init__(label="🎯 Recruit Me", style=discord.ButtonStyle.success)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        self.view_ref.recruits.append(interaction.user)
        await self.view_ref.update_embed(interaction)
        await interaction.response.send_message("✅ Added to recruit pool!", ephemeral=True)

class RecruitPlayersButton(Button):
    def __init__(self, view):
        super().__init__(label="👥 Recruit Players", style=discord.ButtonStyle.secondary)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        # Check if user is a crew commander
        if not self.view_ref.is_user_commander(interaction.user):
            await interaction.response.send_message("⚠️ Only crew commanders can recruit players.", ephemeral=True)
            return
        
        # Check if there are any recruits available
        if not self.view_ref.recruits:
            await interaction.response.send_message("⚠️ No recruits available to recruit.", ephemeral=True)
            return
        
        await interaction.response.send_message(view=RecruitSelectionView(self.view_ref, interaction.user), ephemeral=True)

class EditCrewButton(Button):
    def __init__(self, view):
        super().__init__(label="✏️ Edit My Crew", style=discord.ButtonStyle.secondary)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        crew, team, slot_index = self.view_ref.get_user_crew(interaction.user)
        
        if not crew:
            await interaction.response.send_message("⚠️ You must be a crew commander to edit your crew.", ephemeral=True)
            return
        
        await interaction.response.send_message(view=EditCrewView(self.view_ref, crew, team, slot_index), ephemeral=True)

class LeaveEventButton(Button):
    def __init__(self, view):
        super().__init__(label="❌ Leave Event", style=discord.ButtonStyle.danger)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        user = interaction.user
        removed = False

        # Remove from all positions
        if user == view.commander_a:
            view.commander_a = None
            removed = True
        elif user == view.commander_b:
            view.commander_b = None
            removed = True

        for i in range(MAX_CREWS_PER_TEAM):
            if isinstance(view.crews_a[i], dict):
                crew = view.crews_a[i]
                if user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    view.crews_a[i] = None
                    removed = True
            if isinstance(view.crews_b[i], dict):
                crew = view.crews_b[i]
                if user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    view.crews_b[i] = None
                    removed = True

        if user in view.recruits:
            view.recruits.remove(user)
            removed = True

        if removed:
            await view.update_embed(interaction)
            await interaction.response.send_message("❌ Removed from event!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Not registered!", ephemeral=True)

# NEW: Recruit Selection System
class RecruitSelectionView(View):
    def __init__(self, main_view, commander):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.commander = commander
        self.selected_recruit = None
        
        # Get commander's crew info
        self.crew, self.team, self.slot_index = main_view.get_user_crew(commander)
        
        self.add_item(RecruitSelect(self))

class RecruitSelect(Select):
    def __init__(self, parent):
        # Create options from available recruits
        options = []
        for recruit in parent.main_view.recruits:
            options.append(discord.SelectOption(
                label=recruit.display_name,
                value=str(recruit.id),
                description=f"Recruit {recruit.display_name}"
            ))
        
        super().__init__(
            placeholder="Select a recruit to add to your crew...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # Find the selected recruit
        selected_id = int(self.values[0])
        selected_recruit = None
        
        for recruit in self.parent.main_view.recruits:
            if recruit.id == selected_id:
                selected_recruit = recruit
                break
        
        if not selected_recruit:
            await interaction.response.send_message("❌ Recruit not found!", ephemeral=True)
            return
        
        self.parent.selected_recruit = selected_recruit
        
        # Now show position selection
        await interaction.response.send_message(
            f"Selected **{selected_recruit.display_name}** - choose their position:",
            view=PositionSelectView(self.parent),
            ephemeral=True
        )

class PositionSelectView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        
        self.add_item(AssignGunnerButton(parent))
        self.add_item(AssignDriverButton(parent))

class AssignGunnerButton(Button):
    def __init__(self, parent):
        super().__init__(label="🎯 Assign as Gunner", style=discord.ButtonStyle.primary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        recruit = self.parent.selected_recruit
        crew = self.parent.crew
        
        # Assign recruit as gunner
        crew['gunner'] = recruit
        
        # Remove from recruit pool
        self.parent.main_view.recruits.remove(recruit)
        
        await self.parent.main_view.update_embed(interaction)
        await interaction.response.send_message(
            f"✅ **{recruit.display_name}** recruited as gunner for **{crew['crew_name']}**!",
            ephemeral=True
        )

class AssignDriverButton(Button):
    def __init__(self, parent):
        super().__init__(label="🚗 Assign as Driver", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        recruit = self.parent.selected_recruit
        crew = self.parent.crew
        
        # Assign recruit as driver
        crew['driver'] = recruit
        
        # Remove from recruit pool
        self.parent.main_view.recruits.remove(recruit)
        
        await self.parent.main_view.update_embed(interaction)
        await interaction.response.send_message(
            f"✅ **{recruit.display_name}** recruited as driver for **{crew['crew_name']}**!",
            ephemeral=True
        )

# Edit Crew System (unchanged)
class EditCrewView(View):
    def __init__(self, main_view, crew, team, slot_index):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.crew = crew
        self.team = team
        self.slot_index = slot_index
        
        self.add_item(EditGunnerButton(self))
        self.add_item(EditDriverButton(self))
        self.add_item(EditCrewNameButton(self))

class EditGunnerButton(Button):
    def __init__(self, parent):
        super().__init__(label="🎯 Change Gunner", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=EditGunnerView(self.parent), ephemeral=True)

class EditDriverButton(Button):
    def __init__(self, parent):
        super().__init__(label="🚗 Change Driver", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=EditDriverView(self.parent), ephemeral=True)

class EditCrewNameButton(Button):
    def __init__(self, parent):
        super().__init__(label="📝 Change Name", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditCrewNameModal(self.parent))

class EditGunnerView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(UpdateGunnerSelect(self))

class UpdateGunnerSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select new gunner (or leave empty to clear)", min_values=0, max_values=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.values:
            new_gunner = self.values[0]
            if self.parent.main_view.is_user_registered(new_gunner):
                await interaction.response.send_message("❌ User already registered!", ephemeral=True)
                return
            self.parent.crew['gunner'] = new_gunner
            await interaction.response.send_message(f"✅ Gunner updated to {new_gunner.mention}!", ephemeral=True)
        else:
            self.parent.crew['gunner'] = self.parent.crew['commander']
            await interaction.response.send_message("✅ Gunner cleared - commander will gun!", ephemeral=True)
        
        await self.parent.main_view.update_embed(interaction)

class EditDriverView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(UpdateDriverSelect(self))

class UpdateDriverSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select new driver (or leave empty to clear)", min_values=0, max_values=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.values:
            new_driver = self.values[0]
            if self.parent.main_view.is_user_registered(new_driver):
                await interaction.response.send_message("❌ User already registered!", ephemeral=True)
                return
            self.parent.crew['driver'] = new_driver
            await interaction.response.send_message(f"✅ Driver updated to {new_driver.mention}!", ephemeral=True)
        else:
            self.parent.crew['driver'] = self.parent.crew['commander']
            await interaction.response.send_message("✅ Driver cleared - commander will drive!", ephemeral=True)
        
        await self.parent.main_view.update_embed(interaction)

class EditCrewNameModal(Modal):
    def __init__(self, parent):
        super().__init__(title="Edit Crew Name")
        self.parent = parent
        
        self.name_input = TextInput(
            label="New Crew Name",
            placeholder="Enter new crew name...",
            default=self.parent.crew['crew_name'],
            max_length=30
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message("❌ Crew name cannot be empty!", ephemeral=True)
            return
        
        self.parent.crew['crew_name'] = new_name
        await self.parent.main_view.update_embed(interaction)
        await interaction.response.send_message(f"✅ Crew name updated to '{new_name}'!", ephemeral=True)

# Crew selection system (unchanged)
class CrewSelectView(View):
    def __init__(self, main_view, team, commander):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.team = team
        self.commander = commander
        self.gunner = None
        self.add_item(GunnerSelect(self))

class GunnerSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select Gunner", min_values=1, max_values=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.parent.main_view.is_user_registered(self.values[0]):
            await interaction.response.send_message("❌ User already registered!", ephemeral=True)
            return
        self.parent.gunner = self.values[0]
        await interaction.response.send_message(view=DriverSelectView(self.parent), ephemeral=True)

class DriverSelectView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(DriverSelect(parent))

class DriverSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select Driver", min_values=1, max_values=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.parent.main_view.is_user_registered(self.values[0]):
            await interaction.response.send_message("❌ User already registered!", ephemeral=True)
            return
        driver = self.values[0]
        await interaction.response.send_modal(CrewNameModal(self.parent, driver))

class CrewNameModal(Modal):
    def __init__(self, parent, driver):
        super().__init__(title="Name Your Crew")
        self.parent = parent
        self.driver = driver
        self.name_input = TextInput(
            label="Crew Name",
            placeholder="Enter crew name...",
            default=f"{self.parent.commander.display_name}'s Crew",
            max_length=30
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        crew_name = self.name_input.value.strip() or f"{self.parent.commander.display_name}'s Crew"
        main_view = self.parent.main_view
        slot_list = main_view.crews_a if self.parent.team == "A" else main_view.crews_b

        for i in range(MAX_CREWS_PER_TEAM):
            if slot_list[i] is None:
                slot_list[i] = {
                    "commander": self.parent.commander,
                    "crew_name": crew_name,
                    "gunner": self.parent.gunner,
                    "driver": self.driver
                }
                await main_view.update_embed(interaction)
                await interaction.response.send_message(f"✅ Crew '{crew_name}' registered!", ephemeral=True)
                return

        await interaction.response.send_message("❌ Team is full!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ArmorEvents(bot))

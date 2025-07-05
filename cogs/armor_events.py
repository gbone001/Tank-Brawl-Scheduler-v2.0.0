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
        time="Time in HH:MM format, 24-hour (e.g., 20:00)",
        map_vote_channel="Channel for map vote (optional - defaults to current channel)",
        map_vote_channel="Channel for map vote (optional - defaults to current channel)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Saturday Brawl", value="saturday_brawl"),
        app_commands.Choice(name="Sunday Operations", value="sunday_ops"),
        app_commands.Choice(name="Training Event", value="training"),
        app_commands.Choice(name="Tournament", value="tournament"),
        app_commands.Choice(name="Custom Event", value="custom")
    ])

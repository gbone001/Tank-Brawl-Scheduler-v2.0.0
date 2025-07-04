# cogs/admin_tools.py - Administrative tools and server configuration
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
import logging
from typing import Optional, List, Dict

from utils.database import EventDatabase
from utils.config import *

logger = logging.getLogger(__name__)

class AdminTools(commands.Cog):
    """Administrative tools and server configuration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Admin Tools cog initialized")

    def has_admin_permissions(self, user: discord.Member) -> bool:
        """Check if user has admin permissions"""
        if not hasattr(user, 'roles'):
            return False
        return any(role.name in ADMIN_ROLES for role in user.roles)

    @app_commands.command(name="settings")
    async def server_settings(self, interaction: discord.Interaction):
        """Configure bot settings for this server"""
        
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message(
                f"❌ You need one of these roles: {', '.join(ADMIN_ROLES)}", 
                ephemeral=True
            )
            return
        
        # Get current settings
        settings = self.db.get_guild_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="⚙️ Bot Configuration",
            description="Configure bot settings for this server",
            color=COLORS["info"]
        )
        
        # Display current settings
        embed.add_field(
            name="🛡️ Admin Roles",
            value=", ".join(settings['admin_roles']) or "None set",
            inline=False
        )
        
        embed.add_field(
            name="📅 Event Settings",
            value=f"**Auto Map Votes:** {'✅' if settings.get('auto_map_votes', True) else '❌'}\n"
                  f"**Auto Role Assignment:** {'✅' if settings.get('auto_role_assignment', True) else '❌'}\n"
                  f"**Recruitment System:** {'✅' if settings.get('recruitment_enabled', True) else '❌'}\n"
                  f"**Max Crews per Team:** {settings.get('max_crews_per_team', 6)}",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Reminder Times",
            value=f"{', '.join(map(str, settings.get('reminder_times', [60, 30, 10])))} minutes before events",
            inline=False
        )
        
        view = BotSettingsView(settings, self.db)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="purge_messages")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user (optional)"
    )
    async def purge_messages(self, interaction: discord.Interaction, amount: int, user: discord.Member = None):
        """Delete multiple messages at once"""
        
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message("❌ I don't have permission to manage messages in this channel.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if user:
                # Delete messages from specific user
                def check(m):
                    return m.author == user
                
                deleted = await interaction.channel.purge(limit=amount, check=check)
                await interaction.followup.send(f"✅ Deleted {len(deleted)} messages from {user.mention}.", ephemeral=True)
            else:
                # Delete any messages
                deleted = await interaction.channel.purge(limit=amount)
                await interaction.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
                
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error deleting messages: {e}", ephemeral=True)

    @app_commands.command(name="role_manager")
    @app_commands.describe(
        action="What to do with the role",
        role="The role to manage",
        user="User to add/remove role from (optional - shows role info if not specified)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add to User", value="add"),
        app_commands.Choice(name="Remove from User", value="remove"),
        app_commands.Choice(name="Role Info", value="info"),
        app_commands.Choice(name="List Members", value="members")
    ])
    async def role_manager(self, interaction: discord.Interaction, action: app_commands.Choice[str], 
                          role: discord.Role, user: discord.Member = None):
        """Manage server roles"""
        
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        if action.value == "info":
            embed = discord.Embed(
                title=f"📋 Role Information: {role.name}",
                color=role.color
            )
            
            embed.add_field(name="ID", value=role.id, inline=True)
            embed.add_field(name="Color", value=str(role.color), inline=True)
            embed.add_field(name="Position", value=role.position, inline=True)
            embed.add_field(name="Members", value=len(role.members), inline=True)
            embed.add_field(name="Mentionable", value="✅" if role.mentionable else "❌", inline=True)
            embed.add_field(name="Hoisted", value="✅" if role.hoist else "❌", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif action.value == "members":
            if not role.members:
                await interaction.response.send_message(f"❌ No members have the role {role.mention}.", ephemeral=True)
                return
            
            member_list = [member.mention for member in role.members[:20]]  # Limit to 20
            if len(role.members) > 20:
                member_list.append(f"... and {len(role.members) - 20} more")
            
            embed = discord.Embed(
                title=f"👥 Members with role: {role.name}",
                description="\n".join(member_list),
                color=role.color
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif action.value in ["add", "remove"]:
            if not user:
                await interaction.response.send_message("❌ You must specify a user for add/remove actions.", ephemeral=True)
                return
            
            # Check permissions
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot manage this role (it's higher than my highest role).", ephemeral=True)
                return
            
            if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
                await interaction.response.send_message("❌ You cannot manage this role (it's higher than your highest role).", ephemeral=True)
                return
            
            try:
                if action.value == "add":
                    if role in user.roles:
                        await interaction.response.send_message(f"❌ {user.mention} already has the role {role.mention}.", ephemeral=True)
                        return
                    
                    await user.add_roles(role, reason=f"Added by {interaction.user}")
                    await interaction.response.send_message(f"✅ Added role {role.mention} to {user.mention}.", ephemeral=True)
                    
                else:  # remove
                    if role not in user.roles:
                        await interaction.response.send_message(f"❌ {user.mention} doesn't have the role {role.mention}.", ephemeral=True)
                        return
                    
                    await user.remove_roles(role, reason=f"Removed by {interaction.user}")
                    await interaction.response.send_message(f"✅ Removed role {role.mention} from {user.mention}.", ephemeral=True)
                    
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to manage this role.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error managing role: {e}", ephemeral=True)

    @app_commands.command(name="event_cleanup")
    @app_commands.describe(days_old="Delete completed events older than this many days (default: 90)")
    async def event_cleanup(self, interaction: discord.Interaction, days_old: int = 90):
        """Clean up old completed events from the database"""
        
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        if days_old < 1 or days_old > 365:
            await interaction.response.send_message("❌ Days must be between 1 and 365.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get count before cleanup
            stats_before = self.db.get_database_stats()
            
            # Perform cleanup
            self.db.cleanup_old_data(days_old)
            
            # Get count after cleanup
            stats_after = self.db.get_database_stats()
            
            events_cleaned = stats_before.get('events', 0) - stats_after.get('events', 0)
            signups_cleaned = stats_before.get('signups', 0) - stats_after.get('signups', 0)
            
            embed = discord.Embed(
                title="🧹 Database Cleanup Complete",
                color=COLORS["success"]
            )
            
            embed.add_field(
                name="Cleaned Up",
                value=f"**Events:** {events_cleaned}\n**Signups:** {signups_cleaned}",
                inline=True
            )
            
            embed.add_field(
                name="Remaining",
                value=f"**Events:** {stats_after.get('events', 0)}\n**Signups:** {stats_after.get('signups', 0)}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during cleanup: {e}", ephemeral=True)

    @app_commands.command(name="database_stats")
    async def database_stats(self, interaction: discord.Interaction):
        """Show database statistics"""
        
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        stats = self.db.get_database_stats()
        
        embed = discord.Embed(
            title="📊 Database Statistics",
            color=COLORS["info"]
        )
        
        for table, count in stats.items():
            embed.add_field(
                name=table.replace('_', ' ').title(),
                value=f"{count:,}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready"""
        logger.info("Admin Tools cog is ready")

# UI Components for Bot Settings

class BotSettingsView(View):
    def __init__(self, settings: Dict, db: EventDatabase):
        super().__init__(timeout=TIMEOUTS["admin_controls"])
        self.settings = settings
        self.db = db
        
        self.add_item(ToggleAutoMapVotesButton(self))
        self.add_item(ToggleAutoRolesButton(self))
        self.add_item(ToggleRecruitmentButton(self))
        self.add_item(EditAdminRolesButton(self))
        self.add_item(EditReminderTimesButton(self))

class ToggleAutoMapVotesButton(Button):
    def __init__(self, parent):
        current_state = parent.settings.get('auto_map_votes', True)
        label = "🗳️ Disable Auto Map Votes" if current_state else "🗳️ Enable Auto Map Votes"
        style = discord.ButtonStyle.danger if current_state else discord.ButtonStyle.success
        
        super().__init__(label=label, style=style)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        current_state = self.parent.settings.get('auto_map_votes', True)
        new_state = not current_state
        
        # Update database
        self.parent.db.update_guild_setting(interaction.guild.id, 'auto_map_votes', new_state)
        self.parent.settings['auto_map_votes'] = new_state
        
        # Update button
        self.label = "🗳️ Disable Auto Map Votes" if new_state else "🗳️ Enable Auto Map Votes"
        self.style = discord.ButtonStyle.danger if new_state else discord.ButtonStyle.success
        
        await interaction.response.send_message(
            f"✅ Auto map votes {'enabled' if new_state else 'disabled'}.", 
            ephemeral=True
        )
        await interaction.edit_original_response(view=self.parent)

class ToggleAutoRolesButton(Button):
    def __init__(self, parent):
        current_state = parent.settings.get('auto_role_assignment', True)
        label = "🎭 Disable Auto Roles" if current_state else "🎭 Enable Auto Roles"
        style = discord.ButtonStyle.danger if current_state else discord.ButtonStyle.success
        
        super().__init__(label=label, style=style)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        current_state = self.parent.settings.get('auto_role_assignment', True)
        new_state = not current_state
        
        self.parent.db.update_guild_setting(interaction.guild.id, 'auto_role_assignment', new_state)
        self.parent.settings['auto_role_assignment'] = new_state
        
        self.label = "🎭 Disable Auto Roles" if new_state else "🎭 Enable Auto Roles"
        self.style = discord.ButtonStyle.danger if new_state else discord.ButtonStyle.success
        
        await interaction.response.send_message(
            f"✅ Auto role assignment {'enabled' if new_state else 'disabled'}.", 
            ephemeral=True
        )
        await interaction.edit_original_response(view=self.parent)

class ToggleRecruitmentButton(Button):
    def __init__(self, parent):
        current_state = parent.settings.get('recruitment_enabled', True)
        label = "🎯 Disable Recruitment" if current_state else "🎯 Enable Recruitment"
        style = discord.ButtonStyle.danger if current_state else discord.ButtonStyle.success
        
        super().__init__(label=label, style=style)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        current_state = self.parent.settings.get('recruitment_enabled', True)
        new_state = not current_state
        
        self.parent.db.update_guild_setting(interaction.guild.id, 'recruitment_enabled', new_state)
        self.parent.settings['recruitment_enabled'] = new_state
        
        self.label = "🎯 Disable Recruitment" if new_state else "🎯 Enable Recruitment"
        self.style = discord.ButtonStyle.danger if new_state else discord.ButtonStyle.success
        
        await interaction.response.send_message(
            f"✅ Recruitment system {'enabled' if new_state else 'disabled'}.", 
            ephemeral=True
        )
        await interaction.edit_original_response(view=self.parent)

class EditAdminRolesButton(Button):
    def __init__(self, parent):
        super().__init__(label="🛡️ Edit Admin Roles", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditAdminRolesModal(self.parent))

class EditReminderTimesButton(Button):
    def __init__(self, parent):
        super().__init__(label="⏰ Edit Reminder Times", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditReminderTimesModal(self.parent))

class EditAdminRolesModal(Modal):
    def __init__(self, settings_view):
        super().__init__(title="Edit Admin Roles")
        self.settings_view = settings_view
        
        current_roles = ", ".join(self.settings_view.settings.get('admin_roles', []))
        
        self.roles_input = TextInput(
            label="Admin Role Names",
            placeholder="Moderator, Admin, Event Organizer",
            default=current_roles,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.roles_input)

    async def on_submit(self, interaction: discord.Interaction):
        role_names = [name.strip() for name in self.roles_input.value.split(',') if name.strip()]
        
        if not role_names:
            await interaction.response.send_message("❌ You must specify at least one admin role.", ephemeral=True)
            return
        
        # Update database
        self.settings_view.db.update_guild_setting(interaction.guild.id, 'admin_roles', role_names)
        self.settings_view.settings['admin_roles'] = role_names
        
        await interaction.response.send_message(
            f"✅ Admin roles updated: {', '.join(role_names)}", 
            ephemeral=True
        )

class EditReminderTimesModal(Modal):
    def __init__(self, settings_view):
        super().__init__(title="Edit Reminder Times")
        self.settings_view = settings_view
        
        current_times = ", ".join(map(str, self.settings_view.settings.get('reminder_times', [60, 30, 10])))
        
        self.times_input = TextInput(
            label="Reminder Times (minutes)",
            placeholder="60, 30, 10",
            default=current_times,
            max_length=100
        )
        self.add_item(self.times_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            time_values = [int(time.strip()) for time in self.times_input.value.split(',') if time.strip()]
            
            if not time_values:
                await interaction.response.send_message("❌ You must specify at least one reminder time.", ephemeral=True)
                return
            
            if any(t < 1 or t > 10080 for t in time_values):  # Max 1 week
                await interaction.response.send_message("❌ Reminder times must be between 1 and 10080 minutes.", ephemeral=True)
                return
            
            # Update database
            self.settings_view.db.update_guild_setting(interaction.guild.id, 'reminder_times', time_values)
            self.settings_view.settings['reminder_times'] = time_values
            
            await interaction.response.send_message(
                f"✅ Reminder times updated: {', '.join(map(str, time_values))} minutes", 
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers separated by commas.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminTools(bot))

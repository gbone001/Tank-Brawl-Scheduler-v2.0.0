# Add this to your crew_management.py file

# Add this new command to the CrewManagement class
@app_commands.command(name="crew_panel")
async def crew_panel(self, interaction: discord.Interaction):
    """Open the crew management panel"""
    
    embed = discord.Embed(
        title="🎛️ Crew Management Panel",
        description="Manage your persistent crews using the buttons below.",
        color=COLORS["info"]
    )
    
    embed.add_field(
        name="📋 Available Actions",
        value="🆕 **Create Crew** - Form a new crew\n"
              "ℹ️ **Crew Info** - View crew details\n"
              "✏️ **Edit Crew** - Modify crew settings\n"
              "📨 **Invite Player** - Add members to crew\n"
              "🚪 **Leave Crew** - Exit a crew\n"
              "📜 **List Crews** - Browse server crews",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="• Only commanders can edit and invite\n"
              "• Crews persist across events\n"
              "• You can be in multiple crews",
        inline=False
    )
    
    view = CrewManagementPanelView(self.db)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Add these new UI classes at the end of the file

class CrewManagementPanelView(View):
    def __init__(self, db: EventDatabase):
        super().__init__(timeout=TIMEOUTS["view"])
        self.db = db
        
        # Add all the crew management buttons
        self.add_item(CreateCrewPanelButton(db))
        self.add_item(CrewInfoPanelButton(db))
        self.add_item(EditCrewPanelButton(db))
        self.add_item(InvitePlayerPanelButton(db))
        self.add_item(LeaveCrewPanelButton(db))
        self.add_item(ListCrewsPanelButton(db))

class CreateCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="🆕 Create Crew", style=discord.ButtonStyle.success, row=0)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateCrewPanelModal(self.db))

class CrewInfoPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="ℹ️ Crew Info", style=discord.ButtonStyle.primary, row=0)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        # Get user's crews
        cog = interaction.client.get_cog('CrewManagement')
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        
        if not user_crews:
            await interaction.response.send_message(
                "❌ You're not part of any crews. Create one with the **Create Crew** button!", 
                ephemeral=True
            )
            return
        
        if len(user_crews) == 1:
            embed = cog.build_crew_info_embed(user_crews[0], interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Multiple crews - show selection
            await interaction.response.send_message(
                "Select a crew to view:",
                view=CrewInfoSelectionView(user_crews, interaction.guild), 
                ephemeral=True
            )

class EditCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="✏️ Edit Crew", style=discord.ButtonStyle.secondary, row=0)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to edit crew details.", 
                ephemeral=True
            )
            return
        
        if len(commander_crews) == 1:
            await interaction.response.send_message(
                view=CrewEditView(commander_crews[0]), 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Select a crew to edit:",
                view=CrewEditSelectionView(commander_crews), 
                ephemeral=True
            )

class InvitePlayerPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="📨 Invite Player", style=discord.ButtonStyle.secondary, row=1)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        # Get user's crews where they're commander
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to invite members.", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            view=CrewInviteSetupView(commander_crews), 
            ephemeral=True
        )

class LeaveCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="🚪 Leave Crew", style=discord.ButtonStyle.danger, row=1)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        
        if not user_crews:
            await interaction.response.send_message("❌ You're not part of any crews.", ephemeral=True)
            return
        
        if len(user_crews) == 1:
            cog = interaction.client.get_cog('CrewManagement')
            await cog.process_crew_leave(interaction, user_crews[0])
        else:
            await interaction.response.send_message(
                "Select a crew to leave:",
                view=CrewLeaveSelectionView(user_crews), 
                ephemeral=True
            )

class ListCrewsPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(label="📜 List Crews", style=discord.ButtonStyle.primary, row=1)
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('CrewManagement')
        crews = cog.get_all_guild_crews(interaction.guild.id, 1)
        
        if not crews:
            await interaction.response.send_message("❌ No crews found in this server.", ephemeral=True)
            return
        
        embed = cog.build_crew_list_embed(crews, 1, interaction.guild)
        
        # Add pagination if needed
        if len(crews) >= 10:
            view = CrewListPaginationView(cog, interaction.guild, 1)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

# Modal for creating crews from the panel
class CreateCrewPanelModal(Modal):
    def __init__(self, db: EventDatabase):
        super().__init__(title="Create New Crew")
        self.db = db
        
        self.name_input = TextInput(
            label="Crew Name",
            placeholder="Enter a unique crew name...",
            max_length=30
        )
        self.add_item(self.name_input)
        
        self.description_input = TextInput(
            label="Crew Description (Optional)",
            placeholder="Describe your crew...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        description = self.description_input.value.strip() or None
        
        # Validate crew name
        if len(name) > 30:
            await interaction.response.send_message("❌ Crew name must be 30 characters or less.", ephemeral=True)
            return
        
        if not name.replace(' ', '').replace('-', '').replace('_', '').isalnum():
            await interaction.response.send_message("❌ Crew name can only contain letters, numbers, spaces, hyphens, and underscores.", ephemeral=True)
            return
        
        try:
            crew_id = self.db.create_persistent_crew(
                guild_id=interaction.guild.id,
                crew_name=name,
                commander_id=interaction.user.id,
                description=description
            )
            
            embed = discord.Embed(
                title="🎉 Crew Created Successfully!",
                description=f"Your crew **{name}** has been created.",
                color=COLORS["success"]
            )
            
            embed.add_field(
                name="Crew Details",
                value=f"**Name:** {name}\n"
                      f"**Commander:** {interaction.user.mention}\n"
                      f"**ID:** {crew_id}\n"
                      f"**Description:** {description or 'No description set'}",
                inline=False
            )
            
            embed.add_field(
                name="Next Steps",
                value="• Use **Invite Player** to add members\n"
                      "• Use **Crew Info** to view your crew\n"
                      "• Use **Edit Crew** to modify details",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

# Selection views for crews
class CrewInfoSelectionView(View):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.guild = guild
        self.add_item(CrewInfoSelectDropdown(crews, guild))

class CrewInfoSelectDropdown(Select):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description=f"W: {crew['wins']} L: {crew['losses']}"
            )
            for crew in crews[:25]  # Discord limit
        ]
        
        super().__init__(placeholder="Select a crew to view info", options=options)
        self.crews = {crew['id']: crew for crew in crews}
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        # Build crew info embed
        cog = interaction.client.get_cog('CrewManagement')
        embed = cog.build_crew_info_embed(crew, self.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Crew invitation setup from panel
class CrewInviteSetupView(View):
    def __init__(self, crews: List[Dict]):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.add_item(CrewInviteCrewSelect(crews))

class CrewInviteCrewSelect(Select):
    def __init__(self, crews: List[Dict]):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description="Select this crew to invite to"
            )
            for crew in crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to invite to", options=options)
        self.crews = {crew['id']: crew for crew in crews}

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        await interaction.response.send_message(
            f"Selected crew: **{crew['crew_name']}**\nNow select a user and role:",
            view=CrewInviteUserRoleView(crew),
            ephemeral=True
        )

class CrewInviteUserRoleView(View):
    def __init__(self, crew: Dict):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crew = crew
        self.selected_user = None
        self.selected_role = None
        
        self.add_item(InviteUserSelect(self))
        self.add_item(InviteRoleSelect(self))
        self.add_item(SendInviteButton(self))

class InviteUserSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select user to invite", min_values=1, max_values=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        self.parent.selected_user = self.values[0]
        await interaction.response.send_message(
            f"✅ Selected user: {self.values[0].mention}\nNow select a role and click Send Invite.",
            ephemeral=True
        )

class InviteRoleSelect(Select):
    def __init__(self, parent):
        options = [
            discord.SelectOption(label="Gunner", value="gunner", emoji="🎯"),
            discord.SelectOption(label="Driver", value="driver", emoji="🚗")
        ]
        super().__init__(placeholder="Select role to offer", options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        self.parent.selected_role = self.values[0]
        await interaction.response.send_message(
            f"✅ Selected role: {self.values[0].title()}\nNow click Send Invite.",
            ephemeral=True
        )

class SendInviteButton(Button):
    def __init__(self, parent):
        super().__init__(label="📨 Send Invite", style=discord.ButtonStyle.success)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not self.parent.selected_user:
            await interaction.response.send_message("❌ Please select a user first.", ephemeral=True)
            return
        
        if not self.parent.selected_role:
            await interaction.response.send_message("❌ Please select a role first.", ephemeral=True)
            return
        
        # Get the cog instance to call process_crew_invite
        cog = interaction.client.get_cog('CrewManagement')
        await cog.process_crew_invite(
            interaction, 
            self.parent.crew, 
            self.parent.selected_user, 
            self.parent.selected_role
        )

# Pagination for crew list
class CrewListPaginationView(View):
    def __init__(self, cog, guild: discord.Guild, current_page: int):
        super().__init__(timeout=TIMEOUTS["view"])
        self.cog = cog
        self.guild = guild
        self.current_page = current_page
        
        self.add_item(PreviousPageButton(self))
        self.add_item(NextPageButton(self))

class PreviousPageButton(Button):
    def __init__(self, parent):
        super().__init__(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.parent.current_page <= 1:
            await interaction.response.send_message("❌ Already on first page.", ephemeral=True)
            return
        
        new_page = self.parent.current_page - 1
        crews = self.parent.cog.get_all_guild_crews(interaction.guild.id, new_page)
        
        if not crews:
            await interaction.response.send_message("❌ No crews on previous page.", ephemeral=True)
            return
        
        embed = self.parent.cog.build_crew_list_embed(crews, new_page, self.parent.guild)
        self.parent.current_page = new_page
        
        await interaction.response.send_message(embed=embed, view=self.parent, ephemeral=True)

class NextPageButton(Button):
    def __init__(self, parent):
        super().__init__(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        new_page = self.parent.current_page + 1
        crews = self.parent.cog.get_all_guild_crews(interaction.guild.id, new_page)
        
        if not crews:
            await interaction.response.send_message("❌ No more crews to display.", ephemeral=True)
            return
        
        embed = self.parent.cog.build_crew_list_embed(crews, new_page, self.parent.guild)
        self.parent.current_page = new_page
        
        await interaction.response.send_message(embed=embed, view=self.parent, ephemeral=True)

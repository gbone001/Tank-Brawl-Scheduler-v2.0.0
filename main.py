# main.py - Tank Brawl Match Scheduler Bot
import discord
from discord.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class TankBrawlBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description="Tank Brawl Match Scheduler - Hell Let Loose Event Management Bot",
            help_command=None
        )
        
        self.initial_extensions = [
            'cogs.armor_events',
            'cogs.map_voting',
            'cogs.crew_management',
            'cogs.admin_tools',
        ]

    async def setup_hook(self):
        """Load all cogs when bot starts"""
        logger.info("Loading cogs...")
        
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Tank Brawl Scheduler is active in {len(self.guilds)} guilds')
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="for tank battles | /schedule_event"
        )
        await self.change_presence(activity=activity)

    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        logger.error(f"Command error in {ctx.command}: {error}")
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have the required permissions to execute this command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
        else:
            await ctx.send("❌ An error occurred while processing the command.")

async def main():
    bot = TankBrawlBot()
    
    # Get token from environment variable
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("No bot token found! Set DISCORD_BOT_TOKEN in .env file.")
        return
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())

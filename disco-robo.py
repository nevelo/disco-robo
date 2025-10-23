import os
import asyncio
from dotenv import commands
from discord import Intents
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv("/code/disc_bot/.env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("TEST_CHANNEL_ID"))

# Discord intents
intents = Intents.default()
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Scheduler
scheduler = AsyncIOScheduler(timezone="America/Toronto")  # adjust timezone

async def post_scheduled_message():
    channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    msg = await channel.send("⏰ Scheduled post! React with ✅ or ❌ to vote.")
    # Optional: pre-add reactions
    for emoji in ("✅", "❌"):
        await msg.add_reaction(emoji)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # Example schedules:
    scheduler.add_job(post_scheduled_message, CronTrigger(hour=9, minute=0))          # every day 09:00
    scheduler.add_job(post_scheduled_message, CronTrigger(day_of_week="mon", hour=13))# Mondays 13:00
    scheduler.start()

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    # Example: simple tally or branching on emoji
    if str(reaction.emoji) == "✅":
        print(f"{user} voted YES on message {reaction.message.id}")
    elif str(reaction.emoji) == "❌":
        print(f"{user} voted NO on message {reaction.message.id}")

if __name__ == "__main__":
    bot.run(TOKEN)

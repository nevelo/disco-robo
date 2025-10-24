import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from discord.ext import commands
from discord import Intents
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv("/code/disc_bot/.env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Discord intents
intents = Intents.default()
intents.guilds = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Scheduler
scheduler = AsyncIOScheduler(timezone="America/Toronto")  # adjust timezone

# Defined emojis
EMOJI_DISC           = "\U0001F94F"
EMOJI_THUMBS_UP      = "\U0001F44D"
EMOJI_THUMBS_DOWN    = "\U0001F44E"
EMOJI_CLOCK          = "\U0001F550"
EMOJI_MAP            = "\U0001F4CD"

CONFUSED_EMOJI       = "\u2049\uFE0F"

YES_EMOJI_LIST = {}
NO_EMOJI_LIST = {}

# Team colours per the emoji standard (i.e. what circles are available).
circles = {
    "black":  "\u26AB",
    "white":  "\u26AA",
    "green":  "\U0001F7E2",
    "blue":   "\U0001F535",
    "yellow": "\U0001F7E1",
    "orange": "\U0001F7E0",
    "brown":  "\U0001F7E4",
    "red":    "\U0001F534",
    "purple": "\U0001F7E3",
}

async def post_gametime_message(
    team: str,
    opponent: str,
    team_colour: str,
    opp_colour: str,
    gametime: str,   # for now -- switch to unix time once the bot is more interactive
    park: str,
    field: int
):
    channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    team_colour_emoji = circles.get(team_colour, CONFUSED_EMOJI)
    opp_colour_emoji = circles.get(opp_colour, CONFUSED_EMOJI)

    msg_content = f"""```
{EMOJI_DISC} {EMOJI_DISC} GAME ALERT!! {EMOJI_DISC} {EMOJI_DISC}

{team_colour_emoji} {team} vs {opp_colour_emoji} {opponent}

{EMOJI_CLOCK} {gametime}
{EMOJI_MAP} {park}, Field {field}

Coming? {EMOJI_THUMBS_UP} or {EMOJI_THUMBS_DOWN}!
```"""

    await channel.send(msg_content)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    await channel.send("I'm... alive!")
    # Example schedules:
#    scheduler.add_job(post_scheduled_message, CronTrigger(hour=9, minute=0))          # every day 09:00
#    scheduler.add_job(post_scheduled_message, CronTrigger(day_of_week="mon", hour=13))# Mondays 13:00
#    scheduler.start()

#@bot.event
#async def on_reaction_add(reaction, user):
#    if user.bot:
#        return
#    # Example: simple tally or branching on emoji
#    if str(reaction.emoji) == "✅":
#        print(f"{user} voted YES on message {reaction.message.id}")
#    elif str(reaction.emoji) == "❌":
#        print(f"{user} voted NO on message {reaction.message.id}")

@bot.command(name="nextgame")
async def test_gametime(ctx):
    """
    Trigger the post_gametime_message function for testing
    Only responds in the designated test channel
    """
    if ctx.channel.id != CHANNEL_ID:
        return  # ignore commands in other channels

    

    # Example arguments for the test
    from datetime import datetime, timezone

    team = "Big Disc Energy"
    opponent = "Aldous Hucksley"
    team_colour = "black"
    opp_colour = "orange"
    gametime = "Sunday, October 26, 7:00 PM" # datetime(2025, 10, 26, 19, 0, tzinfo=timezone.utc)  # UTC datetime
    park = "Marden Field House"
    field = 1

    # Call your function
    await post_gametime_message(team, opponent, team_colour, opp_colour, gametime, park, field)

    # Optional: acknowledge in the chat
#    await ctx.send("Test game message posted!")

if __name__ == "__main__":
    bot.run(TOKEN)

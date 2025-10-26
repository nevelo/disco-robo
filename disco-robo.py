import os
import asyncio
import json
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from discord.ext import commands
from discord import Intents
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from models import SessionLocal, Team, Player, Game, init_db, dispose_db
from db_utils import (
    create_team,
    create_player,
    create_game,    
    edit_player,
    edit_game
)

# Load environment variables
load_dotenv("config/.env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BOT_COMMS_CHANNEL_ID = int(os.getenv("BOT_COMMS_CHANNEL_ID"))
DB_URL = os.getenv("DATABASE_URL", "sqlite:///disc_bot.db")

# Load configuration from JSON file
def load_config() -> dict:
    try:
        with open('config/config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: config.json not found. Creating default config file.")
        default_config = {
            "tracked_teams": [],
            "privileged_users": [],
            "timezone": "America/Toronto",
            "channels": {
                "announcements": None,
                "bot_commands": None
            }
        }
        os.makedirs('config', exist_ok=True)
        with open('config/config.json', 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

# Get tracked teams from config
def get_tracked_teams() -> List[int]:
    """Get the list of team IDs that this bot instance cares about."""
    config = load_config()
    return config.get("tracked_teams", [])

# Check if user is privileged
def is_privileged():
    async def predicate(ctx):
        config = load_config()
        privileged_users = config.get("privileged_users", [])
        return ctx.author.id in privileged_users
    return commands.check(predicate)

# Discord intents
intents = Intents.default()
intents.guilds = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents) 

# Scheduler
scheduler = AsyncIOScheduler(timezone="America/Toronto")  # adjust timezone 
## TODO: Load time zone from config file

# Defined emojis
EMOJI_DISC           = "\U0001F94F"
EMOJI_THUMBS_UP      = "\U0001F44D"
EMOJI_THUMBS_DOWN    = "\U0001F44E"
EMOJI_CLOCK          = "\U0001F550"
EMOJI_MAP            = "\U0001F4CD"

CONFUSED_EMOJI       = "\u2049\uFE0F"

YES_EMOJI_LIST = {EMOJI_DISC, EMOJI_THUMBS_UP} ## TODO: Add skin tone variations
NO_EMOJI_LIST = {EMOJI_THUMBS_DOWN} ## TODO: Add skin tone variations

# Team colours per the emoji standard (i.e. what circles are available).
circles = {
    "black":   "\u26AB",
    "white":   "\u26AA",
    "green":   "\U0001F7E2",
    "blue":    "\U0001F535",
    "yellow":  "\U0001F7E1",
    "orange":  "\U0001F7E0",
    "brown":   "\U0001F7E4",
    "red":     "\U0001F534",
    "purple":  "\U0001F7E3",
    "rainbow": "\U0001F308",
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


# Commands for interfacing with database.

# !create_team name="team name" year=Integer season="season String" 
# (optional: home_color="color string" away_color="color string", defaults to white/black)  
# (returns: integer team_ID)
@bot.command()
@is_privileged()
async def create_team(ctx, *, args):
    """Create a new team. Usage: !create_team name="Team Name" year=2025 season="Fall" [home_color="white"] [away_color="black"]"""
    try:
        # Parse arguments
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        
        # Extract and validate required parameters
        name = params.get('name', '').strip('"')
        year = int(params.get('year', 0))
        season = params.get('season', '').strip('"')
        
        if not all([name, year, season]):
            raise ValueError("Missing required parameters")

        # Optional parameters with defaults from your circles dict
        home_colour = params.get('home_colour', 'white').strip('"').lower()
        away_colour = params.get('away_colour', 'black').strip('"').lower()
        home_colour = params.get('home_color', 'white').strip('"').lower()
        away_colour = params.get('away_color', 'black').strip('"').lower()        

        # Validate colors exist in the circles dictionary
        if home_colour not in circles or away_colour not in circles:
            available_colors = ", ".join(circles.keys())
            raise ValueError(f"Invalid color. Available colors are: {available_colors}")

        # Create team
        with SessionLocal() as session:
            team = create_team(session, name, year, season)
            await ctx.send(f"Team created successfully! Team ID: {team.id}")

    except Exception as e:
        await ctx.send(f"Error creating team: {str(e)}")

# !create_player lastname="lastname" firstname="firstname" gender=(m OR f) (with optional discord_ID="discord_ID")  (returns: player ID)
@bot.command()
@is_privileged()
async def create_player(ctx, *, args):
    """Create a new player. Usage: !create_player lastname="Smith" firstname="John" gender=(m|f) [discord_ID="123456789"]"""
    try:
        # Parse arguments
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        
        # Extract and validate required parameters
        lastname = params.get('lastname', '').strip('"')
        firstname = params.get('firstname', '').strip('"')
        gender = params.get('gender', '').lower()
        
        if not all([lastname, firstname]) or gender not in ['m', 'f']:
            raise ValueError("Missing or invalid required parameters")

        # Optional discord ID
        discord_id = params.get('discord_ID', '').strip('"')
        
        with SessionLocal() as session:
            player = create_player(
                session,
                real_name=f"{firstname} {lastname}",
                discord_username=discord_id if discord_id else None,
                gender=gender
            )
            await ctx.send(f"Player created successfully! Player ID: {player.id}")

    except Exception as e:
        await ctx.send(f"Error creating player: {str(e)}")

# --------------------------------------
# ADD PLAYER TO TEAM
#
# Purpose:  Add a player to a team.
# Syntax:   !add_player player=player_ID team=team_ID
# INPUTS:   FIELD       TYPE        DATA            DESCRIPTION
#           player      Integer     player_ID       Player's unique integer ID.
#           team        Integer     team_ID         Home team's unique integer ID.
# --------------------------------------
@bot.command()
@is_privileged()
async def add_player(ctx, *, args):
    """Add a player to a team. Usage: !add_player player=123 team=456"""
    try:
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        player_id = int(params.get('player', 0))
        team_id = int(params.get('team', 0))

        if not all([player_id, team_id]):
            raise ValueError("Missing required parameters")

        with SessionLocal() as session:
            player = session.query(Player).filter_by(id=player_id).first()
            if not player:
                raise ValueError(f"Player {player_id} not found")
            
            player.team_id = team_id
            session.commit()
            await ctx.send(f"Player {player_id} added to team {team_id}")

    except Exception as e:
        await ctx.send(f"Error adding player to team: {str(e)}")
# --------------------------------------
# CREATE GAME
#
# Purpose:  Add a new game to the database.
# Syntax:   !add_game awayteam=team1_ID hometeam=team2_ID date=String time=HH:mm park="park" field=Int
# INPUTS:   FIELD       TYPE        DATA            DESCRIPTION
#           awayteam    Integer     team1_ID        Away team's unique integer ID.
#           hometeam    Integer     team2_ID        Home team's unique integer ID.
#           date        String      date            Date of the game in YYYY-MM-DD format.
#           time        String      time            Time of the game in HH:mm (24-hour)
#           park        String      park            Name of the park where the game will be held.
#           field       Integer     field           Field number at the park.
# --------------------------------------
@bot.command()
@is_privileged()
async def create_game(ctx, *, args):
    try:
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        
        # Extract and validate parameters
        away_team_id = int(params.get('awayteam', 0))
        home_team_id = int(params.get('hometeam', 0))
        date_str = params.get('date', '').strip('"')
        time_str = params.get('time', '').strip('"')
        park = params.get('park', '').strip('"')
        field = int(params.get('field', 0))

        if not all([away_team_id, home_team_id, date_str, time_str, park, field]):
            raise ValueError("Missing required parameters")

        # Parse datetime
        game_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        with SessionLocal() as session:
            game = create_game(
                session,
                team1_id=away_team_id,
                team2_id=home_team_id,
                datetime=game_datetime,
                park=park,
                field=field
            )
            # After creating the game, schedule a game alert
            team1 = session.query(Team).filter_by(id=away_team_id).first()
            team2 = session.query(Team).filter_by(id=home_team_id).first()
            
            # Schedule the game announcement
            scheduler.add_job(
                post_gametime_message,
                'date',
                run_date=game_datetime,
                args=[
                    team1.name,
                    team2.name,
                    'white',  # TODO: Add team colors to Team model
                    'black',
                    game_datetime.strftime("%A, %B %d, %I:%M %p"),
                    park,
                    field
                ]
            )
            
            await ctx.send(f"Game created successfully! Game ID: {game.id}")

    except Exception as e:
        await ctx.send(f"Error creating game: {str(e)}")


# --------------------------------------
# EDIT PLAYER  
#
# Purpose:  Edit a player's information.
# Syntax:   !edit_player player_id=ID field_name="field_value"
# INPUTS:   Name        player_id       Required field name for player ID. Always "player_id"
#           Integer     ID              Player's unique integer ID.   ##TODO: Add a lookup layer by discord username
#           Name        field_name      Name of the field to edit.
#                                       Valid options include "datetime", "park", "field", "team1_id", "team2_id".
#           String/Int  field_value     New value for the specified field.
# --------------------------------------
@bot.command()
@is_privileged()
async def edit_player(ctx, *, args):
    """Edit a player's information. Usage: !edit_player id=123 field_name="new_value" """
    try:
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        player_id = int(params.get('id', 0))
        
        if not player_id:
            raise ValueError("Player ID is required")

        # Remove id from params to process remaining fields
        del params['id']

        with SessionLocal() as session:
            player = session.query(Player).filter_by(id=player_id).first()
            if not player:
                raise ValueError(f"Player {player_id} not found")

            # Update each provided field
            for field, value in params.items():
                value = value.strip('"')
                if hasattr(player, field):
                    setattr(player, field, value)
                else:
                    await ctx.send(f"Warning: Field '{field}' does not exist and was skipped")

            session.commit()
            await ctx.send(f"Player {player_id} updated successfully")

    except Exception as e:
        await ctx.send(f"Error updating player: {str(e)}")


# --------------------------------------
# EDIT GAME
#
# Purpose:  Edit a game's information.
# Syntax:   !edit_game game_id=ID field_name="field_value"
# INPUTS:   Name        game_id         Required field name for game ID. Always "game_id"
#           Integer     ID              Game's unique integer ID.
#           Name        field_name      Name of the field to edit.
#                                       Valid options include "datetime", "park", "field", "team1_id", "team2_id".
#           String/Int  field_value     New value for the specified field.
# --------------------------------------
@bot.command()
@is_privileged()
async def edit_game(ctx, *, args):
    """Edit a game's information. Usage: !edit_game id=123 field_name="new_value" """
    try:
        params = dict(arg.split('=') for arg in args.split(' ') if '=' in arg)
        game_id = int(params.get('id', 0))
        
        if not game_id:
            raise ValueError("Game ID is required")

        # Remove id from params to process remaining fields
        del params['id']

        with SessionLocal() as session:
            game = session.query(Game).filter_by(id=game_id).first()
            if not game:
                raise ValueError(f"Game {game_id} not found")

            # Update each provided field
            for field, value in params.items():
                value = value.strip('"')
                if hasattr(game, field):
                    # Special handling for datetime field
                    if field == 'datetime':
                        value = datetime.strptime(value, "%Y-%m-%d %H:%M")
                    setattr(game, field, value)
                else:
                    await ctx.send(f"Warning: Field '{field}' does not exist and was skipped")

            session.commit()
            await ctx.send(f"Game {game_id} updated successfully")

    except Exception as e:
        await ctx.send(f"Error updating game: {str(e)}")

# Start the scheduler ##TODO: Move to on_ready?
scheduler.start()

## --- ON_READY event --- 

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Initialize database
    init_db(DB_URL, echo=True)
    print("Database initialized!")
    
    channel = bot.get_channel(BOT_COMMS_CHANNEL_ID) or await bot.fetch_channel(BOT_COMMS_CHANNEL_ID)
    await channel.send("I'm... alive!")


if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    finally:
        # Properly dispose of database resources on shutdown
        dispose_db()

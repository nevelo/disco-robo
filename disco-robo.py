import os
import asyncio
import json
import shlex
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import Intents, NotFound
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import (
    SessionLocal, Player, Game, Team,
    init_db, dispose_db, Genders, AttendanceStatus
)
from db_utils import (
    create_team, edit_team, delete_team, get_team_data,
    create_player, edit_player, delete_player, get_player_data,
    create_game, edit_game, delete_game, get_game_data,
    get_game_from_message, get_player_by_discord_id,
    set_attendance_status,
    get_team_games,
    get_team_roster,
    get_game_attendance,
    add_player_to_team,
    UNKNOWN_DISCORD
)

DISCORD_TOKEN = None
DATABASE_URL = None
LOGFILE = None
TRACKED_TEAMS = []
PRIVILEGED_USERS = []
TIMEZONE = "America/Toronto"
CHANNELS = {
    "announcements": None,
    "bot_commands": None,
}

# Load configuration from JSON file
def load_config() -> dict:
    try:
        with open('config/config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: config.json not found. Creating default config file.")
        default_config = {
            "discord_token": None,
            "database_url": "db/disco_robo.db",
            "logfile": "logs/disco_robo.log",
            "tracked_teams": [],
            "privileged_users": [],
            "timezone": "America/Toronto",
            "channels": {
                "announcements": None,
                "bot_commands": None,
            },
        }
        os.makedirs('config', exist_ok=True)
        with open('config/config.json', 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def read_config() -> dict:
    config = load_config()
    DISCORD_TOKEN = config.get("discord_token", DISCORD_TOKEN)
    DATABASE_URL = config.get("database_url", DATABASE_URL)
    LOGFILE = config.get("logfile", LOGFILE)
    TRACKED_TEAMS = config.get("tracked_teams", TRACKED_TEAMS)
    PRIVILEGED_USERS = config.get("privileged_users", PRIVILEGED_USERS)
    TIMEZONE = config.get("timezone", TIMEZONE)
    CHANNELS["announcements"] = config.get("channels", CHANNELS).get("announcements", None)
    CHANNELS["bot_commands"] = config.get("channels", CHANNELS).get("bot_commands", None)   
    return config

def get_timezone() -> str:
    """Get the timezone from config."""
    config = load_config()
    return config.get("timezone", "America/Toronto")

def get_announcement_channel_id() -> Optional[int]:
    """Get the announcements channel ID from config."""
    config = load_config()
    channels = config.get("channels", {})
    return channels.get("announcements", None)

def get_comms_channel_id() -> Optional[int]:
    """Get the bot communications channel ID from config."""
    config = load_config()
    channels = config.get("channels", {})
    return channels.get("bot_commands", None)

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

def parse_args(args_str):
    # Split the string into tokens, respecting quotes
    tokens = shlex.split(args_str)
    params = {}
    for token in tokens:
        if '=' in token:
            key, value = token.split('=', 1)
            params[key] = value.strip('"')
    return params

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
EMOJI_GREEN_CHECK    = "\u2705"
EMOJI_RED_X          = "\u274C"
EMOJI_HOURGLASS      = "\u23F3"

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

async def send_game_announcement(game_id: int):
    with SessionLocal() as session:
        home_id = get_game_data(session, game_id, "hometeam_id")
        if (home_id == None):
            raise ValueError(f"Game {game_id} has no hometeam_id")
        away_id = get_game_data(session, game_id, "awayteam_id")
        gametime = get_game_data(session, game_id, "gametime")
        park = get_game_data(session, game_id, "park")
        field = get_game_data(session, game_id, "field")
        hometeam = get_team_data(session, home_id, "name")
        awayteam = get_team_data(session, away_id, "name")
        away_colour = get_team_data(session, away_id, "away_colour")
        home_colour = get_team_data(session, home_id, "home_colour")    

    await send_game_announcement(
        game_id=game_id,
        awayteam=awayteam,
        hometeam=hometeam,
        away_colour=away_colour,
        home_colour=home_colour,
        gametime=gametime,
        park=park,
        field=field
    )

async def send_game_announcement(
    game_id: int,
    awayteam: str,
    hometeam: str,
    team_colour: str,
    opp_colour: str,
    gametime: str,   # for now -- switch to unix time once the bot is more interactive
    park: str,
    field: int
):
    """Post initial game announcement and return the message for reaction tracking"""
    channel = bot.get_channel(CHANNELS["announcements"]) or await bot.fetch_channel(CHANNELS["announcements"])
    team_colour_emoji = circles.get(team_colour, CONFUSED_EMOJI)
    opp_colour_emoji = circles.get(opp_colour, CONFUSED_EMOJI)

    # Get current attendance
    with SessionLocal() as session:
        attendance = get_game_attendance(session, game_id)
        attending = [f"{p.real_first} {p.real_last}" for p in attendance["attending"]]
        not_attending = [f"{p.real_first} {p.real_last}" for p in attendance["not_attending"]]
        pending = [f"{p.real_first} {p.real_last}" for p in attendance["pending"]]

    msg_content = f"""```
{EMOJI_DISC} {EMOJI_DISC} GAME ALERT!! {EMOJI_DISC} {EMOJI_DISC}

{team_colour_emoji} {awayteam} vs {opp_colour_emoji} {hometeam}

{EMOJI_CLOCK} {gametime}
{EMOJI_MAP} {park}, Field {field}

{EMOJI_GREEN_CHECK} {attending}
{EMOJI_RED_X} {not_attending}
{EMOJI_HOURGLASS} {pending}

React with {EMOJI_THUMBS_UP} or {EMOJI_THUMBS_DOWN} to update your status!
```"""
    msg = await channel.send(msg_content)

    # Add reactions for attendance tracking
    for emoji in YES_EMOJI_LIST:
        await msg.add_reaction(emoji)
    for emoji in NO_EMOJI_LIST:
        await msg.add_reaction(emoji)
    return msg


async def send_bother_message(game_id: int):
    """Send message to bother pending players"""
    with SessionLocal() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        attendance = get_game_attendance(session, game_id)
        
        # Get discord IDs for pending players
        pending_players = [p for p in attendance["pending"] if p.discord_username != UNKNOWN_DISCORD]
        if not pending_players:
            return

        mentions = " ".join(f"<@{p.discord_username}>" for p in pending_players)
        channel = bot.get_channel(CHANNEL_ID)
        
        await channel.send(
            f"🔔 Hey {mentions}! Still waiting on your response for the game in 2 days!\n"
            f"({game.awayteam.name} @ {game.hometeam.name}, "
            f"{game.datetime.strftime('%A at %I:%M %p')})"
        )

async def send_pester_message(game_id: int):
    """Send final warning to pending players"""
    # Similar to bother_message but with more urgent tone
    return

async def send_day_of_game_reminder_message(game_id: int):
    """Send day-of game reminder"""
    # Send reminder to all attending players
    return



# Commands for interfacing with database.

@bot.command(name="schedule")
async def bot_get_schedule(ctx):
    """Display the schedule for tracked teams.
    Usage: !schedule
    
    Shows all upcoming games for the team(s) being tracked by this bot instance.
    Configure tracked teams in config/config.json under "tracked_teams".
    """
    try:
        # Get tracked teams from config
        tracked_teams = get_tracked_teams()
        if not tracked_teams:
            await ctx.send("No teams are currently being tracked. Add team IDs to config/config.json")
            return

        with SessionLocal() as session:
            # Get games for each tracked team
            for team_id in tracked_teams:
                team_name = get_team_data(session, team_id, param='name')
                games = get_team_games(session, team_id)
                if not games:
                    await ctx.send(f"No scheduled games found for {team_name}")
                    continue

                # Build schedule message
                schedule_msg = [f"📅 Schedule for {team_name}:"]
                for game in games:
                    # Determine if team is home or away
                    is_home = game.hometeam_id == team_id
                    opponent = game.awayteam if is_home else game.hometeam
                    home_away = "vs" if is_home else "@"

                    # Format the game info
                    weekday = game.datetime.strftime("%A")
                    month = game.datetime.strftime("%B")
                    day = str(game.datetime.day)  # This will not have leading zeros
                    date_str = f"{weekday}, {month} {day}"
                    time_str = game.datetime.strftime("%I:%M %p")
                    game_line = (
                        f"{date_str} {time_str}\n"
                        f"{EMOJI_DISC} {team_name} {home_away} {opponent.name}\n"
                        f"{EMOJI_MAP} {game.park}, Field {game.field}\n"
                    )
                    schedule_msg.append(game_line)

                # Send the schedule
                await ctx.send("\n".join(schedule_msg))

    except Exception as e:
        await ctx.send(f"Error retrieving schedule: {str(e)}")
        print(f"Error in get_schedule: {e}", flush=True)

@bot.command(name="set_attendance")
@is_privileged()
async def bot_set_attendance_status(ctx, *, args):
    """Set a player's attendance status for a game.
    Usage: !set_attendance game=123 player=456 status=(yes|no|pending)
    
    Arguments:
    - game: Game ID (required)
    - player: Player ID (required)
    - status: Attendance status (required)
      - yes: Will attend
      - no: Will not attend
      - pending: Status not yet determined
    """
    try:
        # Parse arguments
        params = parse_args(args)
        
        # Extract and validate required parameters
        game_id = int(params.get('game', 0))
        player_id = int(params.get('player', 0))
        status_str = params.get('status', '').lower()
        
        # Validate required fields
        if not game_id:
            raise ValueError("Game ID is required")
        if not player_id:
            raise ValueError("Player ID is required")
        if not status_str:
            raise ValueError("Status is required (yes, no, or pending)")
            
        # Convert status string to enum
        status_map = {
            'yes': AttendanceStatus.ATTENDING,
            'no': AttendanceStatus.NOT_ATTENDING,
            'pending': AttendanceStatus.PENDING
        }
        status = status_map.get(status_str)
        if not status:
            raise ValueError("Status must be 'yes', 'no', or 'pending'")
        
        with SessionLocal() as session:
            # Set attendance status
            attendance = set_attendance_status(
                session=session,
                game_id=game_id,
                player_id=player_id,
                status=status,
            )
            
            # Format success message
            status_emoji = {
                AttendanceStatus.ATTENDING: EMOJI_THUMBS_UP,
                AttendanceStatus.NOT_ATTENDING: EMOJI_THUMBS_DOWN,
                AttendanceStatus.PENDING: CONFUSED_EMOJI
            }
            emoji = status_emoji[attendance.status]
            
            await ctx.send(
                f"{emoji} Attendance status set for Player {player_id} in Game {game_id}"
            )

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"Error setting attendance: {str(e)}")
        print(f"Error in set_attendance: {e}", flush=True)

@bot.command(name="create_team")
@is_privileged()
async def bot_create_team(ctx, *, args):
    """Create a new team. 
    Usage: !create_team name="Team Name" year=2025 season="Season Name" [home_colour="white"] [away_colour="black"]
    
    Arguments:
    - name: Team name (required)
    - year: Year (required, must be current year or later)
    - season: Season name (required)
    - home_colour: Home jersey colour (optional, default: white)
    - away_colour: Away jersey colour (optional, default: black)

    Available colours: black, white, green, blue, yellow, orange, brown, red, purple, rainbow
    """
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !create_team name=\"Team Name\" year=2025 season=\"Season Name\" [home_colour=\"white\"] [away_colour=\"black\"]")
            return
        
        params = parse_args(args)
        name = params.get('name')
        
        try:
            year = int(params.get('year', 0))
            current_year = datetime.now().year
            if year < current_year:
                raise ValueError(f"Year must be {current_year} or later")
        except ValueError as ve:
            if "must be" in str(ve):
                raise ve
            raise ValueError("Year must be a valid number")
            
        season = params.get('season', '').strip('"')
        if not season:
            raise ValueError("Season name is required")
        
        if not name:
            raise ValueError("Team name is required")

        # Handle colours (support both UK and US spellings)
        home_colour = params.get('home_color', params.get('home_colour', 'white')).strip('"').lower()
        away_colour = params.get('away_color', params.get('away_colour', 'black')).strip('"').lower()

        # Validate colours exist in the circles dictionary
        if home_colour not in circles:
            raise ValueError(f"Invalid home colour. Available colours: {', '.join(circles.keys())}")
        if away_colour not in circles:
            raise ValueError(f"Invalid away colour. Available colours: {', '.join(circles.keys())}")

        # Create team
        with SessionLocal() as session:
            team = create_team(
                session=session,
                name=name,
                year=year,
                season=season,
                home_colour=home_colour,
                away_colour=away_colour
            )
            
            # Format success message with emojis
            home_circle = circles[home_colour]
            away_circle = circles[away_colour]
            await ctx.send(
                f"Team created successfully! {home_circle}{away_circle}\n"
                f"ID: {team.id}\n"
                f"Name: {team.name}\n"
                f"Season: {season} {year}"
            )

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        # Log the full error for debugging
        print(f"Error in create_team: {e}", flush=True)
        await ctx.send(f"Error creating team: {str(e)}")

@bot.command(name="delete_team")
@is_privileged()
async def bot_delete_team(ctx, *, args):
    """Delete a team and all its associated records.
    Usage: !delete_team id=<team_id> CONFIRM="Team Name"
    
    Arguments:
    - id: Team ID (required)
    - CONFIRM: Team name for confirmation (required, must match exactly)
    
    Note: This will also delete all games associated with the team.
    """
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !delete_team id=<team_id>")
            return
        
        params = parse_args(args)
        try:
            team_id = int(params.get('id', 0))
            if team_id <= 0:
                raise ValueError("Team ID must be a positive number")
        except ValueError:
            raise ValueError("Team ID must be a valid number")

        with SessionLocal() as session:
            # Find the team first
            team = session.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise ValueError(f"No team found with ID {team_id}")
            
            # Store team info for confirmation message
            team_name = team.name
            team_season = f"{team.season} {team.year}"

            # Check for confirmation
            confirmation = params.get('CONFIRM', '').strip('"')
            if not confirmation:
                await ctx.send(
                    f'You are trying to delete TEAM "{team_name}"\n'
                    f'If you really mean to do this, use the following syntax:\n'
                    f'!delete_team id={team_id} CONFIRM="{team_name}"'
                )
                return

            # Validate confirmation matches team name
            if confirmation != team_name:
                raise ValueError(f'Confirmation "{confirmation}" does not match team name "{team_name}"')
            
            # Delete the team
            delete_team(session=session, team=team)
            
            await ctx.send(
                f"Team deleted successfully!\n"
                f"Name: {team_name}\n"
                f"Season: {team_season}"
            )

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        # Log the full error for debugging
        print(f"Error in delete_team: {e}", flush=True)

@bot.command(name="delete_game")
@is_privileged()
async def bot_delete_game(ctx, *, args):
    """Delete a game and all associated records.
    Usage: !delete_game id=<game_id> CONFIRM=<date>
    
    Arguments:
    - id: Game ID (required)
    - CONFIRM: Game date for confirmation (required, must match exactly in YYYY-MM-DD format)
    
    Note: This will also delete all attendance records associated with the game.
    """
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !delete_game id=<game_id> CONFIRM=<date>")
            return
        
        params = parse_args(args)
        try:
            game_id = int(params.get('id', 0))
            if game_id <= 0:
                raise ValueError("Game ID must be a positive number")
        except ValueError:
            raise ValueError("Game ID must be a valid number")

        with SessionLocal() as session:
            # Find the game first
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                raise ValueError(f"No game found with ID {game_id}")
            
            # Store game info for confirmation message
            game_date = game.datetime.strftime("%Y-%m-%d")
            game_info = f"{game.awayteam.name} @ {game.hometeam.name}"

            # Check for confirmation
            confirmation = params.get('CONFIRM', '').strip('"')
            if not confirmation:
                await ctx.send(
                    f'You are trying to delete GAME "{game_info}" on {game_date}\n'
                    f'If you really mean to do this, use the following syntax:\n'
                    f'!delete_game id={game_id} CONFIRM="{game_date}"'
                )
                return

            # Validate confirmation matches game date
            if confirmation != game_date:
                raise ValueError(f'Confirmation date "{confirmation}" does not match game date "{game_date}"')
            
            # Delete the game
            delete_game(session=session, game_id=game_id)
            
            await ctx.send(
                f"Game deleted successfully!\n"
                f"Game: {game_info}\n"
                f"Date: {game_date}"
            )

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        # Log the full error for debugging
        print(f"Error in delete_game: {e}", flush=True)

@bot.command(name="roster")
async def bot_get_roster(ctx, *, args):
    """Display the roster for a team with players grouped by gender.
    Usage: !roster id=<team_id>
    
    Shows all players on the team, organized by gender matching.
    Players will be displayed with their discord username if available.
    """
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !roster id=<team_id>")
            return

        params = parse_args(args)
        try:
            team_id = int(params.get('id', 0))
            if team_id <= 0:
                raise ValueError("Team ID must be a positive number")
        except ValueError:
            raise ValueError("Team ID must be a valid number")

        with SessionLocal() as session:
            # Get the team to verify it exists and get its name
            team = session.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise ValueError(f"No team found with ID {team_id}")

            # Get the roster
            players = get_team_roster(session, team_id, include_unknown=True)
            
            # Split players by gender
            female_matching = []
            open_matching = []
            for player in players:
                if player.gender == Genders.FEMALE_MATCHING:
                    female_matching.append(player)
                else:
                    open_matching.append(player)
            
            # Sort each list by last name
            female_matching.sort(key=lambda p: p.real_last)
            open_matching.sort(key=lambda p: p.real_last)

            # Calculate maximum lengths for formatting
            max_name_length = max([len(f"{p.real_first} {p.real_last}") for p in players], default=0)
            max_discord_length = max([len(p.discord_username) for p in players], default=0)
            col_width = max(max_name_length + max_discord_length + 3, 30)  # +3 for parentheses and space
            
            # Build the roster display
            lines = []
            lines.append(f"Team Roster: {team.name}")
            lines.append("|" + "-" * (col_width * 2 + 5) + "|")  # 5 for margins and separator
            lines.append(f"| {'FEMALE MATCHING'.ljust(col_width)} | {'OPEN MATCHING'.ljust(col_width)} |")
            lines.append("|" + "-" * (col_width * 2 + 5) + "|")

            # Create rows, padding shorter list with empty strings
            max_rows = max(len(female_matching), len(open_matching))
            for i in range(max_rows):
                f_player = female_matching[i] if i < len(female_matching) else None
                o_player = open_matching[i] if i < len(open_matching) else None
                
                f_text = ""
                if f_player:
                    f_text = f"{f_player.real_first} {f_player.real_last}"
                    if f_player.discord_username != UNKNOWN_DISCORD:
                        f_text += f" ({f_player.discord_username})"
                
                o_text = ""
                if o_player:
                    o_text = f"{o_player.real_first} {o_player.real_last}"
                    if o_player.discord_username != UNKNOWN_DISCORD:
                        o_text += f" ({o_player.discord_username})"
                
                lines.append(f"| {f_text.ljust(col_width)} | {o_text.ljust(col_width)} |")
            
            lines.append("|" + "-" * (col_width * 2 + 5) + "|")
            
            await ctx.send("```\n" + "\n".join(lines) + "\n```")

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        # Log the full error for debugging
        print(f"Error in get_roster: {e}", flush=True)

@bot.command(name="attendance")
async def bot_get_attendance(ctx, *, args):
    """Display the attendance list for a game.
    Usage: !attendance game=<game_id>
    
    Shows all players grouped by their attendance status (attending, not attending, pending).
    """
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !attendance game=<game_id>")
            return

        params = parse_args(args)
        try:
            game_id = int(params.get('game', 0))
            if game_id <= 0:
                raise ValueError("Game ID must be a positive number")
        except ValueError:
            raise ValueError("Game ID must be a valid number")

        with SessionLocal() as session:
            # Get the game to verify it exists and get teams
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                raise ValueError(f"No game found with ID {game_id}")
            
            # Get attendance details
            attendance = get_game_attendance(session, game_id, include_details=False)
            
            # Format the output
            lines = []
            lines.append(f"Game Attendance: {game.awayteam.name} @ {game.hometeam.name}")
            lines.append(f"Date: {game.datetime.strftime('%A, %B %d %I:%M %p')}")
            lines.append(f"Location: {game.park}, Field {game.field}")
            lines.append("")
            
            # Format attendance lists
            for status, players in attendance.items():
                if status == "attending":
                    title = "✅ Attending"
                elif status == "not_attending":
                    title = "❌ Not Attending"
                else:
                    title = "⏳ Pending Response"
                
                lines.append(title + ":")
                if players:
                    for player in players:
                        if player.discord_username != UNKNOWN_DISCORD:
                            lines.append(f"  • {player.real_first} {player.real_last} ({player.discord_username})")
                        else:
                            lines.append(f"  • {player.real_first} {player.real_last}")
                else:
                    lines.append("  (none)")
                lines.append("")
            
            await ctx.send("```\n" + "\n".join(lines) + "\n```")

    except ValueError as ve:
        await ctx.send(f"Error: {str(ve)}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        # Log the full error for debugging
        print(f"Error in get_attendance: {e}", flush=True)

@bot.command(name="create_player")
@is_privileged()    
async def bot_create_player(ctx, *, args):
# --------------------------------------
# CREATE PLAYER
#
# Purpose:  Create a new player.
# Syntax:   !create_player lastname="lastname" firstname="firstname" gender=(m|f) [discord_ID="123456789"]
# INPUTS:   FIELD       TYPE        DATA            DESCRIPTION
#           player      Integer     player_ID       Player's unique integer ID.
#           team        Integer     team_ID         Home team's unique integer ID.
# --------------------------------------
# !create_player lastname="lastname" firstname="firstname" gender=(m OR f) (with optional discord_ID="discord_ID")  (returns: player ID)
    """Create a new player. Usage: !create_player lastname="Smith" firstname="John" gender=(m|f) [discord_ID="123456789"]"""
    try:
        if not args:
            await ctx.send("Error: Missing arguments. Usage: !create_player first=\"John\" last=\"Smith\" gender=(m|f) [discord=\"123456789\"]")
            return
            
        # Parse arguments using shlex to handle quoted strings
        params = parse_args(args)
        
        # Extract and validate required parameters
        lastname = params.get('last', '').strip('"')
        firstname = params.get('first', '').strip('"')
        gender = params.get('gender', '').lower()
        
        if not all([lastname, firstname]):
            raise ValueError("Missing required parameters")
        
        if gender not in ['m', 'f', 'o']:
            raise ValueError("Gender must be 'm', 'f', or 'o'")

        # Handle Discord user identification
        discord_param = params.get('discord', '').strip('"')
        discord_user = None
        
        if discord_param:
            try:
                # First try to parse as ID
                user_id = int(discord_param)
                discord_user = await bot.fetch_user(user_id)
            except ValueError:
                # If not an ID, try as username
                # Note: This requires the members intent to be enabled
                guild = ctx.guild
                if guild:
                    discord_user = await guild.fetch_member_named(discord_param)
            except discord.NotFound:
                await ctx.send(f"Warning: Could not find Discord user with ID {discord_param}")
            except Exception as e:
                await ctx.send(f"Warning: Error looking up Discord user: {str(e)}")
        
        with SessionLocal() as session:
            # Convert gender string to the correct enum value
            if gender == 'm' or gender == 'o':
                gender = Genders.OPEN_MATCHING.value
            else:  # gender == 'f'
                gender = Genders.FEMALE_MATCHING.value

            # Create player with both username and ID if found
            player = create_player(
                session,
                first_name=firstname,
                last_name=lastname,
                discord_username=discord_user.name if discord_user else None,
                discord_id=str(discord_user.id) if discord_user else None,
                gender=gender
            )
            
            if discord_user:
                await ctx.send(f"Player created successfully! Player ID: {player.id}\nLinked to Discord user: {discord_user.name} (ID: {discord_user.id})")
            else:
                await ctx.send(f"Player created successfully! Player ID: {player.id}\nNo Discord user linked")

    except Exception as e:
        await ctx.send(f"Error creating player: {str(e)}")
        # Log the full error for debugging
        print(f"Error in create_player: {e}", flush=True)

@bot.command(name="add_player")
@is_privileged()
async def bot_add_player(ctx, *, args):
# --------------------------------------
# ADD PLAYER TO TEAM
#
# Purpose:  Add a player to a team.
# Syntax:   !add_player player=player_ID team=team_ID
# INPUTS:   FIELD       TYPE        DATA            DESCRIPTION
#           player      Integer     player_ID       Player's unique integer ID.
#           team        Integer     team_ID         Home team's unique integer ID.
# --------------------------------------
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

            # Verify the team exists
            team = session.query(Team).filter_by(id=team_id).first()
            if not team:
                raise ValueError(f"Team {team_id} not found")
            
            # Use add_player_to_team to properly set up the relationship
            add_player_to_team(session, team_id, player)
            await ctx.send(f"Player {player_id} ({player.real_first} {player.real_last}) added to team {team_id} ({team.name})")

    except Exception as e:
        await ctx.send(f"Error adding player to team: {str(e)}")

@bot.command(name="create_game")
@is_privileged()
async def bot_create_game(ctx, *, args):
# --------------------------------------
# CREATE GAME
#
# Purpose:  Add a new game to the database.
# Syntax:   !add_game awayteam=team1_ID hometeam=team2_ID date="YYYY-MM-DD" time="HH:mm" park="park" field=Int
# INPUTS:   FIELD       TYPE        DATA            DESCRIPTION
#           awayteam    Integer     team1_ID        Away team's unique integer ID.
#           hometeam    Integer     team2_ID        Home team's unique integer ID.
#           date        String      date            Date of the game in YYYY-MM-DD format.
#           time        String      time            Time of the game in HH:mm (24-hour)
#           park        String      park            Name of the park where the game will be held.
#           field       Integer     field           Field number at the park.
# --------------------------------------
    try:

        # Parse arguments
        params = parse_args(args)
        
        # Extract and validate parameters
        away_team_id = int(params.get('away', 0))
        home_team_id = int(params.get('home', 0))
        date_str = params.get('date', '').strip('"')
        time_str = params.get('time', '').strip('"')
        park = params.get('park', '').strip('"')
        field = int(params.get('field', 0))

        print(f"Creating game: away={away_team_id}, home={home_team_id}, date={date_str}, time={time_str}, park={park}, field={field}", flush=True)

        # Validate each parameter individually
        if not away_team_id:
            raise ValueError("Missing or invalid away team ID")
        if not home_team_id:
            raise ValueError("Missing or invalid home team ID")
        if not date_str:
            raise ValueError("Missing date")
        if not time_str:
            raise ValueError("Missing time")
        if not park:
            raise ValueError("Missing park name")
        if not field:
            raise ValueError("Missing or invalid field number")

        # Parse datetime
        try:
            game_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError as ve:
            raise ValueError(
                "Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time (24-hour)"
            ) from ve

        with SessionLocal() as session:
            game = create_game(
                session,
                awayteam_id=away_team_id,
                hometeam_id=home_team_id,
                datetime=game_datetime,
                park=park,
                field=field
            )
            # After creating the game, schedule a game alert
            team1 = session.query(Team).filter_by(id=away_team_id).first()
            team2 = session.query(Team).filter_by(id=home_team_id).first()
            
            await ctx.send(f"Game created successfully! Game ID: {game.id}")

    except Exception as e:
        await ctx.send(f"Error creating game: {str(e)}")

@bot.command(name="edit_player")
@is_privileged()
async def bot_edit_player(ctx, *, args):
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
    """Edit a player's information. Usage: !edit_player id=123 field_name="new_value" """
    try:
        params = parse_args(args)
        player_id = int(params.get('id', 0))
        
        if not player_id:
            raise ValueError("Player ID is required")

        # Remove id from params to process remaining fields
        del params['id']

        with SessionLocal() as session:
            player = session.query(Player).filter_by(id=player_id).first()
            if not player:
                raise ValueError(f"Player {player_id} not found")

            # Map command parameters to database field names
            field_mapping = {
                'first': 'real_first',
                'last': 'real_last',
                'discord': 'discord_username',
                'gender': 'gender'
            }
            
            # Update each provided field using the mapping
            for field, value in params.items():
                value = value.strip('"')
                db_field = field_mapping.get(field)
                if not db_field:
                    await ctx.send(f"Warning: Field '{field}' is not a valid field name")
                    continue
                
                # Special handling for gender field
                if field == 'gender':
                    if value.lower() == 'm' or value.lower() == 'o':
                        value = Genders.OPEN_MATCHING
                    elif value.lower() == 'f':
                        value = Genders.FEMALE_MATCHING
                    else:
                        raise ValueError("Gender must be 'm', 'f', or 'o'")
                
                setattr(player, db_field, value)

            session.commit()
            await ctx.send(f"Player {player_id} updated successfully")

    except Exception as e:
        await ctx.send(f"Error updating player: {str(e)}")

@bot.command(name="edit_game")
@is_privileged()
async def bot_edit_game(ctx, *, args):
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
    """Edit a game's information. Usage: !edit_game id=123 field_name="new_value" """
    try:
        params = parse_args(args)
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

## --- Tasks and Event Handlers --- 

@tasks.loop(hours=1)
async def check_messages():
    """Check for upcoming games and send announcements if needed."""
    try:
        with SessionLocal() as session:
            # Get upcoming games in next 3 days
            now = datetime.utcnow()
            three_days_from_now = now + timedelta(days=3)

            # Query for games within the next 3 days
            upcoming_games = session.query(Game).filter(
                and_(
                    Game.datetime > now,
                    Game.datetime <= three_days_from_now,
                    Game.announcement_msg == None  # Only get games without announcements
                )
            ).all()

            # If no upcoming unannounced games, we're done
            if not upcoming_games:
                return

            # For each unannounced game, send the announcement
            for game in upcoming_games:
                await send_game_announcement(game.id)

    except Exception as e:
        print(f"Error in check_messages: {e}", flush=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # Initialize database
    config = read_config()
    init_db(config["database_url"], echo=True)
    print("Database initialized!")
    
    # Start the message check loop
    check_messages.start()
    print("Message check loop started!")
    BOT_COMMS_CHANNEL_ID = get_comms_channel_id()
    CHANNEL_ID = get_announcement_channel_id()
    channel = bot.get_channel(BOT_COMMS_CHANNEL_ID) or await bot.fetch_channel(BOT_COMMS_CHANNEL_ID)
    await channel.send("I'm... alive!") 

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reactions."""
    if payload.user_id == bot.user.id:
        return
    
    try:
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        with SessionLocal() as session:
            # Check if this is a game announcement message
            game = get_game_from_message(session, message.id)
            if not game:
                return        

            # Get player from discord ID
            player = get_player_by_discord_id(session, str(payload.user_id))
            if not player:
                return

            # Set attendance based on reaction
            if str(payload.emoji) in YES_EMOJI_LIST:
                status = AttendanceStatus.ATTENDING
            elif str(payload.emoji) in NO_EMOJI_LIST:
                status = AttendanceStatus.NOT_ATTENDING
            else:
                return

            # Update attendance
            set_attendance_status(session, game_id, player.id, status)
            
        # Update message with new attendance


    except Exception as e:
        print(f"Error handling reaction: {e}", flush=True)

if __name__ == "__main__":
    try:
        config = load_config()
        DISCORD_TOKEN = config.get("discord_token", None)
        if (DISCORD_TOKEN is None) or (DISCORD_TOKEN == ""):
            print("Error: Discord token not found in config.json", flush=True)
            exit(1)
        bot.run(DISCORD_TOKEN)
    finally:
        scheduler.shutdown()
        dispose_db()
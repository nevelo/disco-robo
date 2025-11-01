import unittest
import os
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Team, Player, Game, Genders, AttendanceStatus, Attendance
from db_utils import UNKNOWN_DISCORD, get_game_attendance

# Test data for commands
VALID_COMMANDS = [
    '!create_team name="Cobra Snakes" year=2025 season="Fall" home_colour="blue" away_colour="white"',
    '!create_team name="Python Pirates" year=2025 season="Fall" home_colour="purple" away_colour="black"',
    '!create_player first="John" last="Agda" gender="m" discord="johna1234"',
    '!create_player first="Sarah" last="Connor" gender="f" discord="sconnor"',
    '!create_player first="Alex" last="Kim" gender="m" discord="akim"',
    '!create_game away=1 home=2 date="2025-11-15" time="19:30" park="Riverside Park" field=2',
    '!create_player first="Maria" last="Rodriguez" gender="f" discord="mrodriguez"',
    '!create_player first="James" last="Wilson" gender="m"',
    '!create_player first="Emily" last="Chen" gender="f" discord="echen123"',
    '!create_player first="Sam" last="Taylor" gender="o" discord="staylor"',
    '!create_team name="Red Dragons" year=2025 season="Fall" home_colour="red" away_colour="yellow"',
    '!create_team name="Green Geckos" year=2025 season="Fall" home_colour="green" away_colour="orange"',
    '!create_game away=3 home=1 date="2025-11-23" time="19:30" park="Riverside Park" field=1',
    '!create_game away=4 home=1 date="2025-11-30" time="19:30" park="Riverside Park" field=2',
    '!add_player player=1 team=1',  # John to Cobra Snakes
    '!add_player player=2 team=1',  # Sarah to Cobra Snakes
    '!add_player player=3 team=1',  # Alex to Cobra Snakes
    '!add_player player=4 team=1',  # Maria to Cobra Snakes
    '!add_player player=5 team=1',  # James to Cobra Snakes
    '!add_player player=6 team=1',  # Emily to Cobra Snakes
    '!add_player player=7 team=1',  # Sam to Cobra Snakes
]

class CommandIterator:
    def __init__(self):
        self.index = 0
    
    def next(self):
        if self.index >= len(VALID_COMMANDS):
            raise IndexError("No more test commands available")
        command = VALID_COMMANDS[self.index]
        self.index += 1
        return command
    
    def reset(self):
        self.index = 0

# Set up test environment variables
os.environ["CHANNEL_ID"] = "123456789"
os.environ["BOT_COMMS_CHANNEL_ID"] = "987654321"
os.environ["DISCORD_TOKEN"] = "test_token"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

class MockBot:
    """Mock Discord bot that simulates command processing"""
    def __init__(self):
        self.commands = {}
        self.events = {}

    def command(self, name=None):
        """Simulates the @bot.command() decorator with optional name argument"""
        def decorator(func):
            cmd_name = name or func.__name__
            self.commands[cmd_name] = func
            return func
        return decorator

    def event(self, func):
        """Simulates the @bot.event decorator"""
        self.events[func.__name__] = func
        return func

    async def process_command(self, ctx, message: str):
        """Simulates Discord's command processing"""
        if not message.startswith('!'):
            return
            
        parts = message[1:].split(maxsplit=1)
        command_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if command_name in self.commands:
            command_func = self.commands[command_name]
            
            if args:    
                try:
                    await command_func(ctx, args=args)
                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")
            else:
                try:
                    await command_func(ctx)
                except TypeError as te:
                    if "missing 1 required keyword-only argument: 'args'" in str(te):
                        # Show command help for missing args (Discord.py behavior)
                        if command_func.__doc__:
                            await ctx.send(command_func.__doc__)
                        else:
                            await ctx.send(f"Usage: !{command_name} [arguments required but no help available]")
                    else:
                        # Different type error, show it
                        await ctx.send(f"Error: {str(te)}")
                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")

    async def simulate_ready(self):
        """Simulates the bot's on_ready event"""
        if 'on_ready' in self.events:
            await self.events['on_ready']()

class MockContext:
    """Mock Discord context object"""
    def __init__(self):
        self.sent_messages = []
        self.author = Mock(id=12345)

    async def send(self, message):
        self.sent_messages.append(message)

class TestDiscordCommands(unittest.TestCase):
    def setUp(self):
        """Set up test database and mocks"""
        # Create in-memory test database
        self.engine = create_engine('sqlite:///:memory:', echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Create a mock config
        self.mock_config = {
            "tracked_teams": [1],  # Cobra Snakes is the default tracked team
            "privileged_users": [12345],
            "timezone": "America/Toronto",
            "channels": {
                "announcements": None,
                "bot_commands": None
            }
        }
        
        # Initialize command iterator
        self.commands = CommandIterator()

        # Create mock context and bot
        self.ctx = MockContext()
        self.bot = MockBot()

        # Import disco-robo with our mock bot
        import importlib.util
        spec = importlib.util.spec_from_file_location("disco_robo", "disco-robo.py")
        self.disco_robo = importlib.util.module_from_spec(spec)
        
        # Replace the real bot with our mock
        with patch('discord.ext.commands.Bot', return_value=self.bot):
            spec.loader.exec_module(self.disco_robo)

        # Set up other patches
        self.privileged_patch = patch.object(self.disco_robo, 'is_privileged', return_value=lambda: True)
        self.privileged_patch.start()
        self.session_patch = patch.object(self.disco_robo, 'SessionLocal', self.Session)
        self.session_patch.start()
        self.config_patch = patch.object(self.disco_robo, 'load_config', return_value=self.mock_config)
        self.config_patch.start()

    def tearDown(self):
        self.privileged_patch.stop()
        self.session_patch.stop()
        self.config_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        print("\n ------------------------")

    def run_async_test(self, coro):
        import asyncio
        asyncio.run(coro)

    def test_attendance_workflow(self):
        """Test the full attendance workflow"""
        self.run_async_test(self._test_attendance_workflow())

    async def _test_attendance_workflow(self):
        """Implementation of attendance workflow test"""
        # First set up the database with our test data
        for command in VALID_COMMANDS:
            await self.execute_command(command, verbose=True)

        # Verify that all players were added to the team correctly
        with self.Session() as session:
            cobra_snakes = session.query(Team).filter_by(name="Cobra Snakes").first()
            self.assertIsNotNone(cobra_snakes, "Cobra Snakes team not found")

            # Get all players that should be on the team
            expected_players = {
                "johna1234": "John Agda",
                "sconnor": "Sarah Connor",
                "akim": "Alex Kim",
                "mrodriguez": "Maria Rodriguez",
                UNKNOWN_DISCORD: "James Wilson",
                "echen123": "Emily Chen",
                "staylor": "Sam Taylor"
            }

            # Verify each player is on the team
            team_players = {p.discord_username: f"{p.real_first} {p.real_last}" for p in cobra_snakes.players}
            self.assertEqual(set(expected_players.keys()), set(team_players.keys()),
                           f"Team roster mismatch.\nExpected players: {sorted(expected_players.keys())}\n"
                           f"Actual players: {sorted(team_players.keys())}")

            # Verify player details are correct
            for discord_id, full_name in expected_players.items():
                self.assertIn(discord_id, team_players, f"Player {full_name} not found in team")
                self.assertEqual(team_players[discord_id], full_name,
                               f"Name mismatch for {discord_id}. Expected {full_name}, got {team_players[discord_id]}")

        # Verify that all players start in PENDING state
        with self.Session() as session:
            game = session.query(Game).filter(Game.datetime == datetime(2025, 11, 30, 19, 30)).first()
            self.assertIsNotNone(game, "Test game was not created")
            
            attendance = get_game_attendance(session, game.id)
            
            # Initially no one should be in attending or not_attending lists
            self.assertEqual(len(attendance["attending"]), 0, "Expected no players in attending list initially")
            self.assertEqual(len(attendance["not_attending"]), 0, "Expected no players in not_attending list initially")
            
            # Get all players from both teams
            all_players = set()
            for team in [game.hometeam, game.awayteam]:
                all_players.update(p.id for p in team.players)
            
            # Convert pending list to set of IDs
            pending_ids = {p.id for p in attendance["pending"]}
            
            # Players should all be pending initially
            self.assertEqual(pending_ids, all_players, 
                           f"Expected all players to be pending initially.\nPending: {pending_ids}\nAll players: {all_players}")

        with self.Session() as session:
            # Get player IDs
            players = {
                p.discord_username: p.id 
                for p in session.query(Player).all() 
                if p.discord_username != UNKNOWN_DISCORD
            }

            # Find the game between Cobra Snakes and Green Geckos
            game = session.query(Game)\
                .filter(Game.datetime == datetime(2025, 11, 30, 19, 30))\
                .first()
            game_id = game.id
            print(f"\nTesting attendance for Game ID: {game_id} ({game.awayteam.name} vs {game.hometeam.name})")
            attendance_commands = [
                (f'!set_attendance game={game_id} player={players["johna1234"]} status=yes', 'johna1234'),  # John attending
                (f'!attendance game={game_id}', None),  # Check status
                (f'!set_attendance game={game_id} player={players["sconnor"]} status=yes', 'sconnor'),  # Sarah attending
                (f'!attendance game={game_id}', None),  # Check status
                (f'!set_attendance game={game_id} player={players["akim"]} status=no', 'akim'),  # Alex not attending
                (f'!attendance game={game_id}', None),  # Check status
                (f'!set_attendance game={game_id} player={players["mrodriguez"]} status=yes', 'mrodriguez'),  # Maria attending
                (f'!attendance game={game_id}', None),  # Check status
                (f'!set_attendance game={game_id} player={players["echen123"]} status=yes', 'echen123'),  # Emily attending
                (f'!attendance game={game_id}', None),  # Check status
                (f'!set_attendance game={game_id} player={players["staylor"]} status=no', 'staylor'),  # Sam not attending
                (f'!attendance game={game_id}', None),  # Final status check
            ]

        print("\nAttendance Command Test Outputs:")
        print("--------------------------------")
        
        # Keep track of current attendance state for verification
        expected_attending_usernames = []
        expected_not_attending_usernames = []
        expected_pending_usernames = []

        # Execute each command and display output
        for command, username in attendance_commands:
            if username:
                # Set author for attendance setting commands
                self.ctx.author = Mock(name=username)
                messages = await self.execute_command(command, verbose=True)
                self.assertTrue(any("status set" in msg for msg in messages), 
                              f"Expected success message for {command}")
                
                # Verify the database was updated correctly
                with self.Session() as session:
                    game = session.query(Game).filter(Game.id == game_id).first()
                    player = session.query(Player).filter_by(discord_username=username).first()
                    attendance = session.query(Attendance).filter_by(
                        game_id=game_id,
                        player_id=player.id
                    ).first()
                    print("ATTENDANCE: ", attendance)
                    self.assertTrue(attendance is not None and 
                                  attendance.status == (AttendanceStatus.ATTENDING if "status=yes" in command 
                                                     else AttendanceStatus.NOT_ATTENDING),
                                  f"Expected player {username} to have status {'ATTENDING' if 'status=yes' in command else 'NOT_ATTENDING'} "
                                  f"for game {game_id}")
                
                    current_game_attendance = get_game_attendance(session, game_id, include_details=False)
                    print("CURRENT GAME ATTENDANCE: ", current_game_attendance)


                # Update our expected state
                status = "yes" if "status=yes" in command else "no"
                if status == "yes":
                    expected_attending_usernames.append(username)
                else:
                    expected_not_attending_usernames.append(username)
                print(f"\nCommand: {command}")
                print(f"Expected attending: {expected_attending_usernames}")
                print(f"Expected not attending: {expected_not_attending_usernames}")
                
                print("##########################################\n\n")
###########################################################################################
            else:
                # This is an attendance check - verify the output format and content
                messages = await self.execute_command(command, verbose=True)
                
                # There should be exactly one message with the attendance info
                self.assertEqual(len(messages), 1, "Expected exactly one response message")
                output = messages[0]
                
                # Remove the code block markers and split into lines
                lines = output.strip('`').strip().split('\n')
                
                # Track where we are in the output
                current_section = None
                attending = []
                not_attending = []
                pending = []
                
                # Parse the output
                for line in lines:
                    if "✅ Attending:" in line:
                        current_section = "attending"
                    elif "❌ Not Attending:" in line:
                        current_section = "not_attending"
                    elif "⏳ Pending Response:" in line:
                        current_section = "pending"
                    elif line.strip().startswith("•"):
                        # This is a player line
                        player_line = line.strip('• ').strip()
                        if current_section == "attending":
                            attending.append(player_line)
                        elif current_section == "not_attending":
                            not_attending.append(player_line)
                        elif current_section == "pending":
                            pending.append(player_line)
                
                # Get expected state from database
                with self.Session() as session:
                    game = session.query(Game).filter(Game.datetime == datetime(2025, 11, 30, 19, 30)).first()
                    attendance = get_game_attendance(session, game.id, include_details=False)
                    
                    # Convert database state to expected output format
                    def format_player(p):
                        return f"{p.real_first} {p.real_last} ({p.discord_username})" if p.discord_username != UNKNOWN_DISCORD else f"{p.real_first} {p.real_last}"
                    
                    current_attending_names = sorted([format_player(p) for p in attendance["attending"]])
                    current_not_attending_names = sorted([format_player(p) for p in attendance["not_attending"]])
                    current_pending_names = sorted([format_player(p) for p in attendance["pending"]])
                    
                    # Convert the bot output lists to sorted lists for comparison
                    output_attending = sorted(attending)
                    output_not_attending = sorted(not_attending)
                    output_pending = sorted(pending)
                    
                    # Verify the bot's output matches the database state
                    self.assertEqual(current_attending_names, output_attending,
                                   f"Attending list mismatch\nExpected: {current_attending_names}\nGot: {output_attending}")
                    self.assertEqual(current_not_attending_names, output_not_attending,
                                   f"Not attending list mismatch\nExpected: {current_not_attending_names}\nGot: {output_not_attending}")
                    self.assertEqual(current_pending_names, output_pending,
                                   f"Pending list mismatch\nExpected: {current_pending_names}\nGot: {output_pending}")
                    
                    # Also verify against our running expected state
                    # Convert usernames to full player names for comparison
                    username_to_full_name = {p.discord_username: format_player(p) 
                                           for p in session.query(Player).all() 
                                           if p.discord_username != UNKNOWN_DISCORD}
                    
                    expected_attending_names = sorted([username_to_full_name[u] for u in expected_attending_usernames])
                    expected_not_attending_names = sorted([username_to_full_name[u] for u in expected_not_attending_usernames])
                    
                    self.assertEqual(current_attending_names, expected_attending_names,
                                   f"Attendance state mismatch\nExpected attending: {expected_attending_names}\nGot: {current_attending_names}")
                    self.assertEqual(current_not_attending_names, expected_not_attending_names,
                                   f"Not attending state mismatch\nExpected: {expected_not_attending_names}\nGot: {current_not_attending_names}")
                    
                    # Log the current state for debugging
                    print(f"\nAfter command: {command}")
                    print("Current state from database:")
                    print(f"Attending: {current_attending_names}")
                    print(f"Not Attending: {current_not_attending_names}")
                    print(f"Pending: {current_pending_names}")
                    print("Bot output:")
                    print(f"Attending: {output_attending}")
                    print(f"Not Attending: {output_not_attending}")
                    print(f"Pending: {output_pending}")


            # Print actual database state at the end
        with self.Session() as session:
            game = session.query(Game).filter(Game.datetime == datetime(2025, 11, 30, 19, 30)).first()
            attendance_records = {
                record.player.discord_username: record.status 
                for record in game.attendances
            }
            
            # Get all actual states
            actual_attending = {username for username, status in attendance_records.items() 
                              if status == AttendanceStatus.ATTENDING}
            actual_not_attending = {username for username, status in attendance_records.items() 
                                  if status == AttendanceStatus.NOT_ATTENDING}
            
            # Verify the states match our expectations
            print("\nFinal state verification:")
            print("Actual attending:") 
            print(actual_attending)
            print("Actual not attending:")
            print(actual_not_attending)

            print("Expected attending usernames:")
            print(expected_attending_usernames)
            print("Expected not attending usernames:")
            print(expected_not_attending_usernames)
            
            self.assertEqual(set(expected_attending_usernames), actual_attending,
                           f"Attending players don't match.\nExpected: {expected_attending_usernames}\nGot: {actual_attending}")
            self.assertEqual(set(expected_not_attending_usernames), actual_not_attending,
                           f"Not attending players don't match.\nExpected: {expected_not_attending_usernames}\nGot: {actual_not_attending}")
            
            # Verify James Wilson (no discord) is still pending (no record)
            james = session.query(Player).filter_by(discord_username=UNKNOWN_DISCORD).first()
            self.assertIsNotNone(james, "Could not find James Wilson (player with no Discord)")
            self.assertNotIn(james.id, [rec.player_id for rec in game.attendances],
                           "Expected James Wilson to still be pending (no attendance record)")
            
    async def execute_command(self, command=None, expect_error=False, verbose=False):
        """Execute a command and verify its result.
        
        Args:
            command: Command string to execute. If None, gets next command from iterator.
            expect_error: If True, don't raise on error messages (for testing invalid inputs)
            verbose: If True, print debugging information about command execution
        """
        if command is None:
            command = self.commands.next()
        
        if verbose:
            print(f"\nExecuting command: {command}")
        
        # Clear previous messages
        self.ctx.sent_messages.clear()
        
        try:
            # Execute command
            await self.bot.process_command(self.ctx, command)
            
            # Print responses for debugging
            if verbose:
                print("Bot responses:")
                for msg in self.ctx.sent_messages:
                    print(f"  {msg}")

            # No responses could indicate a problem
            if not self.ctx.sent_messages:
                if not expect_error:
                    raise ValueError(f"Command produced no response: {command}")
                return []

            if not expect_error:
                # Verify success (no error messages)
                error_messages = [msg for msg in self.ctx.sent_messages 
                                if any(err in msg.lower() for err in ["error:", "missing", "invalid", "failed"])]
                if error_messages:
                    raise ValueError(f"Command failed: {error_messages[0]}")
            
            return self.ctx.sent_messages
            
        except Exception as e:
            if not expect_error:
                raise
            return [str(e)]
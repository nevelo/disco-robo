import unittest
import os
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Team, Player, Game, Genders, AttendanceStatus
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
            await self.execute_command(command)

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
        expected_attending = []
        expected_not_attending = []
        
        # Execute each command and display output
        for command, username in attendance_commands:
            if username:
                # Set author for attendance setting commands
                self.ctx.author = Mock(name=username)
                messages = await self.execute_command(command, verbose=True)
                self.assertTrue(any("status set" in msg for msg in messages), 
                              f"Expected success message for {command}")
                
                # Update our expected state
                status = "yes" if "status=yes" in command else "no"
                if status == "yes":
                    expected_attending.append(username)
                else:
                    expected_not_attending.append(username)
                print(f"\nCommand: {command}")
                print(f"Expected attending: {expected_attending}")
                print(f"Expected not attending: {expected_not_attending}")
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
                    
                    expected_attending = [format_player(p) for p in attendance["attending"]]
                    expected_not_attending = [format_player(p) for p in attendance["not_attending"]]
                    expected_pending = [format_player(p) for p in attendance["pending"]]
                    
                    # Verify counts
                    self.assertEqual(len(attending), len(expected_attending), 
                                   f"Wrong number of attending players. Expected {len(expected_attending)}, got {len(attending)}")
                    self.assertEqual(len(not_attending), len(expected_not_attending), 
                                   f"Wrong number of not attending players. Expected {len(expected_not_attending)}, got {len(not_attending)}")
                    self.assertEqual(len(pending), len(expected_pending), 
                                   f"Wrong number of pending players. Expected {len(expected_pending)}, got {len(pending)}")
                    
                    # Verify correct players in each section
                    self.assertEqual(set(attending), set(expected_attending), 
                                   "Attending list doesn't match expected players")
                    self.assertEqual(set(not_attending), set(expected_not_attending), 
                                   "Not attending list doesn't match expected players")
                    self.assertEqual(set(pending), set(expected_pending), 
                                   "Pending list doesn't match expected players")

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
            self.assertEqual(set(actual_attending), set(expected_attending),
                           f"Attending players don't match.\nExpected: {expected_attending}\nGot: {actual_attending}")
            self.assertEqual(set(actual_not_attending), set(expected_not_attending),
                           f"Not attending players don't match.\nExpected: {expected_not_attending}\nGot: {actual_not_attending}")
            
            # Verify James Wilson (no discord) is still pending (no record)

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

    def test_create_team_valid(self):
        """Test creating a team with valid parameters"""
        async def run_test():
            command = "!create_team name=\"Test Team\" year=2025 season=\"Late Fall\" home_colour=\"blue\" away_colour=\"white\""
            await self.bot.process_command(self.ctx, command)
            
            # Check if success message was sent
            self.assertTrue(any("Team created successfully!" in msg for msg in self.ctx.sent_messages))
            
            # Verify team was created in database
            with self.Session() as session:
                team = session.query(Team).first()
                self.assertIsNotNone(team)
                self.assertEqual(team.name, "Test Team")
                self.assertEqual(team.season, "Late Fall")
                self.assertEqual(team.home_colour, "blue")
        
        self.run_async_test(run_test())

    def test_create_team_invalid_command(self):
        """Test with malformed command"""
        async def run_test():
            command = "!create_team"  # Missing all arguments
            await self.bot.process_command(self.ctx, command)
            
            # Should show the command's help message
            self.assertTrue(any("Usage: !create_team" in msg for msg in self.ctx.sent_messages))
            help_text = '\n'.join(self.ctx.sent_messages)
            # Verify help message contains important parameter information
            self.assertIn("name=", help_text)
            self.assertIn("year=", help_text)
            self.assertIn("season=", help_text)
        
        self.run_async_test(run_test())

    def test_create_player_valid(self):
        """Test creating a player with valid parameters"""
        async def run_test():
            command = '!create_player first="John" last="Romel Agda" gender="m" discord="johna1234"'
            await self.bot.process_command(self.ctx, command)
            
            # Check if success message was sent
            self.assertTrue(any("Player created successfully!" in msg for msg in self.ctx.sent_messages))
            
            # Verify player was created in database
            with self.Session() as session:
                player = session.query(Player).first()
                self.assertIsNotNone(player)
                self.assertEqual(player.real_first, "John")
                self.assertEqual(player.real_last, "Romel Agda")
                self.assertEqual(player.gender, Genders.OPEN_MATCHING)
                self.assertEqual(player.discord_username, "johna1234")
        
        self.run_async_test(run_test())

    def test_setup_game_scenario(self):
        """Test setting up a more complex scenario with multiple entities"""
        async def run_test():
            # Create two teams
            await self.execute_command()  # Cobra Snakes
            await self.execute_command()  # Python Pirates
            
            # Create three players
            await self.execute_command()  # John Agda
            await self.execute_command()  # Sarah Connor
            await self.execute_command()  # Alex Kim
            
            # Create a game
            await self.execute_command()  # Game between teams
            
            # Verify database state
            with self.Session() as session:
                # Check teams
                teams = session.query(Team).all()
                self.assertEqual(len(teams), 2)
                self.assertEqual(teams[0].name, "Cobra Snakes")
                self.assertEqual(teams[1].name, "Python Pirates")
                
                # Check players
                players = session.query(Player).all()
                self.assertEqual(len(players), 3)
                
                # Check game
                game = session.query(Game).first()
                self.assertIsNotNone(game)
                self.assertEqual(game.park, "Riverside Park")
                self.assertEqual(game.field, 2)
        
        self.run_async_test(run_test())

    def test_invalid_create_game(self):
        """Test creating a game with invalid date format after setting up teams and players"""
        async def run_test():
            # Set up teams and players first
            for _ in range(5):  # First 5 commands from VALID_COMMANDS
                await self.execute_command()
            
            # Try to create a game with invalid date format
            invalid_date = '!create_game away=1 home=2 date="11/12/25" time="19:30" park="Riverside Park" field=2'
            responses = await self.execute_command(invalid_date, expect_error=True)

            # Verify error message
            expected_error = "Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time (24-hour)"
            self.assertTrue(any(expected_error in msg for msg in responses))
            self.assertTrue(any("format" in msg.lower() for msg in responses))

            # Verify no game was created
            with self.Session() as session:
                game_count = session.query(Game).count()
                self.assertEqual(game_count, 0)

            # Create game with missing parameter
            missing_param_command = '!create_game away=1 date="2025-11-15" time="19:30" park="Riverside Park" field=2'
            responses = await self.execute_command(missing_param_command, expect_error=True)
            expected_error = "Missing or invalid home team ID"
            self.assertTrue(any(expected_error in msg for msg in responses))
            with self.Session() as session:
                game_count = session.query(Game).count()
                self.assertEqual(game_count, 0)

            # Create game with park that has a space in its name
            print("\nCreating game with park name that includes spaces ...")
            park_command = '!create_game away=1 home=2 date="2025-11-15" time="19:30" park="Riverside Park" field=2'
            responses = await self.execute_command(park_command, expect_error=False)
            with self.Session() as session:
                game = session.query(Game).first()
                self.assertIsNotNone(game)
                self.assertEqual(game.park, "Riverside Park", "Full park name should be saved, including spaces")
                print("Game created with park name:", game.park)

        self.run_async_test(run_test())

    def test_get_schedule(self):
        """Test retrieving the schedule for tracked teams"""
        async def run_test():
            # First create the teams and games
            for _ in range(len(VALID_COMMANDS)):
                await self.execute_command()

            # Get the schedule
            responses = await self.execute_command('!schedule')
            
            # Print the schedule as it would appear in Discord
            print("\n=== Discord Bot Output ===")
            for msg in responses:
                print(f"🤖 disco-robo BOT:")
                print("╭─────────────────────")
                for line in msg.split('\n'):
                    print(f"│ {line}")
                print("╰─────────────────────\n")

            # Verify schedule includes all games
            schedule_text = '\n'.join(responses)
            self.assertIn("Cobra Snakes", schedule_text)
            self.assertIn("November 15", schedule_text)
            self.assertIn("November 23", schedule_text)
            self.assertIn("November 30", schedule_text)
            self.assertIn("Python Pirates", schedule_text)
            self.assertIn("Red Dragons", schedule_text)
            self.assertIn("Green Geckos", schedule_text)
            self.assertIn("Riverside Park", schedule_text)

            # Now delete one team and check schedule again
            # First try without confirmation - should not delete
            delete_command = '!delete_team id=2'  # Delete Python Pirates 
            responses = await self.execute_command(delete_command)
            confirmation_text = '\n'.join(responses)
            self.assertIn('You are trying to delete TEAM "Python Pirates"', confirmation_text)
            self.assertIn('!delete_team id=2 CONFIRM="Python Pirates"', confirmation_text)
            
            # Verify team still exists in schedule
            responses = await self.execute_command('!schedule')
            schedule_text = '\n'.join(responses)
            self.assertIn("Python Pirates", schedule_text)  # Should still be there

            # Now delete with proper confirmation
            delete_command = '!delete_team id=2 CONFIRM="Python Pirates"'
            await self.execute_command(delete_command)
            responses = await self.execute_command('!schedule')
            schedule_text = '\n'.join(responses)
            self.assertNotIn("Python Pirates", schedule_text)  # Now it should be gone

            # Create a new game between remaining teams
            create_game_command = '!create_game away=3 home=4 date="2025-11-25" time="19:30" park="Riverside Park" field=3'
            print(create_game_command)
            responses = await self.execute_command(create_game_command)
            game_creation_text = '\n'.join(responses)
            self.assertIn("Game created successfully", game_creation_text)
            
            # Get the game ID and team names from the creation response
            game_id = None
            away_team = "Red Dragons"  # Team 3
            home_team = "Green Geckos"  # Team 4
            for line in responses:
                if "ID:" in line:
                    game_id = line.split("ID:")[1].strip()
            self.assertIsNotNone(game_id)
            
            # Verify game exists in database
            with self.Session() as session:
                game = session.query(Game).filter(Game.id == int(game_id)).first()
                self.assertIsNotNone(game)
                print(game.awayteam.name, "vs", game.hometeam.name, "@", game.datetime)
                self.assertEqual(game.awayteam.name, "Red Dragons")
                self.assertEqual(game.hometeam.name, "Green Geckos")
                self.assertEqual(game.datetime.strftime("%Y-%m-%d %H:%M"), "2025-11-25 19:30")
                self.assertEqual(game.park, "Riverside Park")
                self.assertEqual(game.field, 3)

            # Try to delete game without confirmation
            delete_game_command = f'!delete_game id={game_id}'
            responses = await self.execute_command(delete_game_command)
            confirmation_text = '\n'.join(responses)
            self.assertIn(f'You are trying to delete GAME "{away_team} @ {home_team}"', confirmation_text)
            self.assertIn('2025-11-25', confirmation_text)
            self.assertIn(f'!delete_game id={game_id} CONFIRM="2025-11-25"', confirmation_text)
            
            # Check game still exists
            with self.Session() as session:
                game = session.query(Game).filter(Game.id == int(game_id)).first()
                self.assertIsNotNone(game)
                self.assertEqual(game.datetime.strftime("%Y-%m-%d %H:%M"), "2025-11-25 19:30")
            
            # Delete game with proper confirmation
            delete_game_command = f'!delete_game id={game_id} CONFIRM="2025-11-25"'
            await self.execute_command(delete_game_command)
            
            # Verify game is deleted from database
            with self.Session() as session:
                deleted_game = session.query(Game).filter(Game.id == int(game_id)).first()
                self.assertIsNone(deleted_game, "Game should be deleted from database")

        self.run_async_test(run_test())

    def test_team_roster(self):
        """Test displaying team roster with players grouped by gender"""
        async def run_test():
            # First create all teams and players from VALID_COMMANDS
            for command in VALID_COMMANDS:
                if command.startswith('!create_team') or command.startswith('!create_player'):
                    await self.execute_command(command)
                    
            # Add some players to team 1 (Cobra Snakes)
            with self.Session() as session:
                team = session.query(Team).filter_by(id=1).first()
                players = session.query(Player).all()
                for player in players:
                    team.players.append(player)
                session.commit()
            
            # Get the roster
            roster_command = '!roster id=1'
            responses = await self.execute_command(roster_command)
            roster_text = '\n'.join(responses)
            
            # Print the roster as it would appear in Discord
            print("\n=== Discord Bot Output ===")
            print(roster_text)
            print("=== End Discord Bot Output ===\n")
            
            # First verify column headers
            roster_lines = roster_text.strip('`').split('\n')
            # Title is line 1, separator is line 2, headers are line 3
            self.assertIn("Team Roster: Cobra Snakes", roster_lines[1], "Missing team name")
            self.assertIn("FEMALE MATCHING", roster_lines[3], "Missing female matching header")
            self.assertIn("OPEN MATCHING", roster_lines[3], "Missing open matching header")
            
            # Then verify some specific players
            # Female matching players
            self.assertIn("Sarah Connor (sconnor)", roster_text)
            self.assertIn("Maria Rodriguez (mrodriguez)", roster_text)
            self.assertIn("Emily Chen (echen123)", roster_text)
            
            # Open matching players
            self.assertIn("John Agda (johna1234)", roster_text)
            self.assertIn("Alex Kim (akim)", roster_text)
            self.assertIn("James Wilson", roster_text)  # No discord ID
            self.assertIn("Sam Taylor (staylor)", roster_text)

        self.run_async_test(run_test())

    def test_edit_player(self):
        """Test editing a player's information"""
        async def run_test():
            # Create a player first
            for _ in range(6):  # First 5 commands from VALID_COMMANDS
                await self.execute_command()

            # Verify player's current name
            with self.Session() as session:
                player = session.query(Player).filter_by(id=1).first()
                self.assertIsNotNone(player)
                self.assertEqual(player.real_first, "John")
                self.assertEqual(player.real_last, "Agda")
            # Edit the player's name
            edit_command = '!edit_player id=1 first="John" last="Rom"'
            responses = await self.execute_command(edit_command)
            self.assertTrue(any("Player 1 updated successfully" in msg for msg in responses))

            # Verify player's updated name
            with self.Session() as session:
                player = session.query(Player).filter_by(id=1).first()
                self.assertIsNotNone(player)
                self.assertEqual(player.real_first, "John")
                self.assertEqual(player.real_last, "Rom")
        self.run_async_test(run_test())
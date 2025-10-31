import unittest
import os
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Team, Player, Game, Genders

# Test data for commands
VALID_COMMANDS = [
    '!create_team name="Cobra Snakes" year=2025 season="Fall" home_color="blue" away_color="white"',
    '!create_team name="Python Pirates" year=2025 season="Fall" home_color="purple" away_color="black"',
    '!create_player first="John" last="Agda" gender="m" discord="johna1234"',
    '!create_player first="Sarah" last="Connor" gender="f" discord="sconnor"',
    '!create_player first="Alex" last="Kim" gender="m" discord="akim"',
    '!create_game away=1 home=2 date="2025-11-15" time="19:30" park="Riverside Park" field=2',
    '!create_player first="Maria" last="Rodriguez" gender="f" discord="mrodriguez"',
    '!create_player first="James" last="Wilson" gender="m"',
    '!create_player first="Emily" last="Chen" gender="f" discord="echen123"',
    '!create_player first="Sam" last="Taylor" gender="o" discord="staylor"',
    '!create_team name="Red Dragons" year=2025 season="Fall" home_color="red" away_color="yellow"',
    '!create_team name="Green Geckos" year=2025 season="Fall" home_color="green" away_color="orange"',
    '!create_game away=3 home=1 date="2025-11-23" time="19:30" park="Riverside Park" field=1',
    '!create_game away=4 home=1 date="2025-11-30" time="19:30" park="Riverside Park" field=2',
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
            command = "!create_team name=\"Test Team\" year=2025 season=\"Late Fall\" home_color=\"blue\" away_color=\"white\""
            await self.bot.process_command(self.ctx, command)
            
            # Check if success message was sent
            self.assertTrue(any("Team created successfully!" in msg for msg in self.ctx.sent_messages))
            
            # Verify team was created in database
            with self.Session() as session:
                team = session.query(Team).first()
                self.assertIsNotNone(team)
                self.assertEqual(team.name, "Test Team")
                self.assertEqual(team.season, "Late Fall")
                self.assertEqual(team.home_color, "blue")
        
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
            delete_command = '!delete_team id=2'  # Delete Python Pirates 
            await self.execute_command(delete_command)
            responses = await self.execute_command('!schedule')
            schedule_text = '\n'.join(responses)
            self.assertNotIn("Python Pirates", schedule_text)

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
import unittest
import os
import asyncio
import importlib.util
import importlib.machinery
from unittest.mock import Mock, patch, DEFAULT
from discord import NotFound
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Team, Player, Game, Genders, AttendanceStatus, Attendance
from db_utils import get_game_attendance

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

VALID_COMMANDS_2 = [
    # Create teams
    '!create_team name="Disc Wizards" year=2026 season="Winter I" home_colour="white" away_colour="black"',
    '!create_team name="Storm Chasers" year=2026 season="Winter I" home_colour="red" away_colour="red"',
    '!create_team name="Gravity Breakers" year=2026 season="Winter I" home_colour="white" away_colour="black"',
    '!create_team name="Wind Warriors" year=2026 season="Winter I" home_colour="white" away_colour="black"',
    '!create_team name="Sky Raiders" year=2026 season="Winter I" home_colour="orange" away_colour="orange"',
    '!create_team name="Spiral Force" year=2026 season="Winter I" home_colour="purple" away_colour="purple"',
    '!create_team name="Cloud Runners" year=2026 season="Winter I" home_colour="white" away_colour="black"',
    '!create_team name="Air Masters" year=2026 season="Winter I" home_colour="white" away_colour="black"',
    
    # Create players
    '!create_player first="Marcus" last="Thompson" gender="m" discord="mthompson_92"',
    '!create_player first="Nina" last="Chen" gender="f" discord="ninachen_"',
    '!create_player first="Rebecca" last="Martinez" gender="f" discord="becca528"',
    '!create_player first="Daniel" last="Parker" gender="m" discord="dparker807"',
    '!create_player first="Thomas" last="Wright" gender="m" discord="twright054"',
    '!create_player first="Sophia" last="Anderson" gender="f" discord="sophiaa"',
    '!create_player first="Lucas" last="Cooper" gender="m" discord="lc660"',
    '!create_player first="Emma" last="Fisher" gender="f" discord="emmafisher"',
    '!create_player first="Ryan" last="Mitchell" gender="m" discord="ryan_33"',
    '!create_player first="Isabel" last="Turner" gender="f" discord="isaturner"',
    '!create_player first="Michael" last="Hayes" gender="m" discord="mhayes"',
    '!create_player first="Robert" last="Bennett" gender="m" discord="rbennett97"',
    
    # Add players to team 1 (Disc Wizards)
    '!add_player player=1 team=1',  # Marcus Thompson
    '!add_player player=2 team=1',  # Nina Chen
    '!add_player player=3 team=1',  # Rebecca Martinez
    '!add_player player=4 team=1',  # Daniel Parker
    '!add_player player=5 team=1',  # Thomas Wright
    '!add_player player=6 team=1',  # Sophia Anderson
    '!add_player player=7 team=1',  # Lucas Cooper
    '!add_player player=8 team=1',  # Emma Fisher
    '!add_player player=9 team=1',  # Ryan Mitchell
    '!add_player player=10 team=1', # Isabel Turner
    '!add_player player=11 team=1', # Michael Hayes
    '!add_player player=12 team=1', # Robert Bennett
    
    # Create games
    '!create_game away=1 home=5 date="2025-10-26" time="19:00" park="Riverside" field=1',
    '!create_game away=7 home=1 date="2025-11-02" time="20:00" park="Riverside" field=1',
    '!create_game away=6 home=1 date="2025-11-09" time="16:00" park="Riverside" field=1',
    '!create_game away=1 home=8 date="2025-11-16" time="19:00" park="Riverside" field=2',
    '!create_game away=1 home=4 date="2025-11-23" time="21:00" park="Riverside" field=2',
    '!create_game away=1 home=3 date="2025-11-30" time="16:00" park="Riverside" field=2',
    '!create_game away=2 home=1 date="2025-12-07" time="16:00" park="Riverside" field=2',
    '!create_game away=5 home=1 date="2025-12-14" time="20:00" park="Riverside" field=1'
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
        self._users = {}  # Dict to store user IDs -> MockMember objects

    async def fetch_user(self, user_id):
        """Simulate fetching a user by their ID"""
        # Convert to string since Discord IDs are strings
        user_id = str(user_id)
        if user_id in self._users:
            return self._users[user_id]
        raise NotFound("User not found")

    def command(self, name=None, **kwargs):
        """Simulates the @bot.command() decorator with optional name and aliases"""
        def decorator(func):
            cmd_name = name or func.__name__
            self.commands[cmd_name] = func
            for alias in kwargs.get('aliases', []):
                self.commands[alias] = func
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

class MockGuild:
    """Mock Discord guild (server) object"""
    def __init__(self):
        self.members = {}  # Dict of username -> MockMember

    async def fetch_members(self, *, limit=1000):
        """Simulate the async iterator for fetching members"""
        for member in self.members.values():
            yield member

    async def fetch_member(self, member_id):
        """Simulate fetching a member by their ID"""
        for member in self.members.values():
            if str(member.id) == str(member_id):
                return member
        raise NotFound('Member not found')

class MockMember:
    """Mock Discord member object"""
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.display_name = name  # Add display_name to match Discord's Member object

class MockContext:
    """Mock Discord context object"""
    def __init__(self):
        self.sent_messages = []
        self.author = Mock(id=12345)
        self.guild = MockGuild()

    async def send(self, message):
        self.sent_messages.append(message)

class TestDiscordCommands(unittest.TestCase):
    def setUp(self):
        """Set up test database and mocks"""
        global importlib
        # Create in-memory test database
        self.engine = create_engine('sqlite:///:memory:', echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Create mock config
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

        # Set up mock Discord members in the guild
        test_members = [
            # First test members
            ("johna1234", "123456789123456789"),
            ("sconnor", "223456789123456789"),
            ("akim", "323456789123456789"),
            ("mrodriguez", "423456789123456789"),
            ("echen123", "523456789123456789"),
            ("staylor", "623456789123456789"),
            
            # Winter league members
            ("mthompson_92", "723456789123456789"),
            ("ninachen_", "823456789123456789"),
            ("becca528", "923456789123456789"),
            ("dparker807", "1023456789123456789"),
            ("twright054", "1123456789123456789"),
            ("sophiaa", "1223456789123456789"),
            ("lc660", "1323456789123456789"),
            ("emmafisher", "1423456789123456789"),
            ("ryan_33", "1523456789123456789"),
            ("isaturner", "1623456789123456789"),
            ("mhayes", "1723456789123456789"),
            ("rbennett97", "1823456789123456789")
        ]
        
        for username, user_id in test_members:
            member = MockMember(id=user_id, name=username)
            self.ctx.guild.members[username] = member
            self.bot._users[user_id] = member

        # Import disco-robo with our mock bot
        loader = importlib.machinery.SourceFileLoader("disco_robo", "disco-robo.py")
        spec = importlib.util.spec_from_file_location("disco_robo", "disco-robo.py", loader=loader)
        self.disco_robo = importlib.util.module_from_spec(spec)
        
        # Replace the real bot with our mock and execute the module
        with patch('discord.ext.commands.Bot', return_value=self.bot):
            loader.exec_module(self.disco_robo)

        # Mock datetime.now() on disco_robo module only, so test games appear as "upcoming"
        # Patching only the module-level reference keeps the global datetime.datetime intact for SQLAlchemy
        mock_date = datetime(2025, 10, 1)
        class MockDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return mock_date.replace(tzinfo=tz) if tz else mock_date
        self.MockDatetime = MockDatetime
        self.datetime_patch = patch.object(self.disco_robo, 'datetime', MockDatetime)
        self.datetime_patch.start()

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
        self.datetime_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

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
            await self.execute_command(command, verbose=False)

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
                None: "James Wilson",
                "echen123": "Emily Chen",
                "staylor": "Sam Taylor"
            }

            # Verify each player is on the team
            team_players = {p.discord_username: f"{p.real_first} {p.real_last}" for p in cobra_snakes.players}
            # Define a sort key function that handles None values
            def sort_key(x):
                return (x or "")  # Convert None to empty string for sorting

            self.assertEqual(set(expected_players.keys()), set(team_players.keys()),
                           f"Team roster mismatch.\nExpected players: {sorted(expected_players.keys(), key=sort_key)}\n"
                           f"Actual players: {sorted(team_players.keys(), key=sort_key)}")

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
                if p.discord_username != None
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
        
        # Keep track of current attendance state for verification
        expected_attending_usernames = []
        expected_not_attending_usernames = []
        expected_pending_usernames = []

        # Execute each command and display output
        for command, username in attendance_commands:
            if username:
                # Set author for attendance setting commands
                self.ctx.author = Mock(name=username)
                messages = await self.execute_command(command, verbose=False)
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
                    self.assertTrue(attendance is not None and 
                                  attendance.status == (AttendanceStatus.ATTENDING if "status=yes" in command 
                                                     else AttendanceStatus.NOT_ATTENDING),
                                  f"Expected player {username} to have status {'ATTENDING' if 'status=yes' in command else 'NOT_ATTENDING'} "
                                  f"for game {game_id}")
                
                    current_game_attendance = get_game_attendance(session, game_id, include_details=False)

                # Update our expected state
                status = "yes" if "status=yes" in command else "no"
                if status == "yes":
                    expected_attending_usernames.append(username)
                else:
                    expected_not_attending_usernames.append(username)
                
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
                    print("##########################")
                    print("##########################")
                    print(attendance, flush=True)
                    print("##########################")
                    print("##########################")

                    # Convert database state to expected output format
                    def format_player(p):
                        return f"{p.real_first} {p.real_last} ({p.discord_username})" if p.discord_username is not None else f"{p.real_first} {p.real_last}"
                    
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
                                           if p.discord_username is not None}
                    
                    expected_attending_names = sorted([username_to_full_name[u] for u in expected_attending_usernames])
                    expected_not_attending_names = sorted([username_to_full_name[u] for u in expected_not_attending_usernames])
                    
                    self.assertEqual(current_attending_names, expected_attending_names,
                                   f"Attendance state mismatch\nExpected attending: {expected_attending_names}\nGot: {current_attending_names}")
                    self.assertEqual(current_not_attending_names, expected_not_attending_names,
                                   f"Not attending state mismatch\nExpected: {expected_not_attending_names}\nGot: {current_not_attending_names}")
                    
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
            self.assertEqual(set(expected_attending_usernames), actual_attending,
                           f"Attending players don't match.\nExpected: {expected_attending_usernames}\nGot: {actual_attending}")
            self.assertEqual(set(expected_not_attending_usernames), actual_not_attending,
                           f"Not attending players don't match.\nExpected: {expected_not_attending_usernames}\nGot: {actual_not_attending}")
            
            # Verify James Wilson (no discord) is still pending (no record)
            james = session.query(Player).filter_by(discord_username=None).first()
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
            # Check for team names (they might be truncated in mobile format)
            self.assertIn("Cobra Snakes", schedule_text)
            # Check for dates in new format (Nov 15, Nov 23)
            self.assertIn("Nov 15", schedule_text)
            self.assertIn("Nov 23", schedule_text)
            # Verify format markers
            self.assertIn("UPCOMING GAMES", schedule_text)
            self.assertIn(" vs ", schedule_text)
            self.assertIn("Nov 30", schedule_text)
            self.assertIn("Python Pirates", schedule_text)
            self.assertIn("Red Dragons", schedule_text)
            self.assertIn("Green Geckos", schedule_text)
            self.assertIn("Riverside Park", schedule_text)

            # Now delete one team and check schedule again
            # First try without confirmation - should not delete
            delete_command = '!delete_team id=2'  # Delete Python Pirates 
            responses = await self.execute_command(delete_command)
            confirmation_text = '\n'.join(responses)
            self.assertIn('You are trying to delete TEAM "Python Pirates Fall 2025"', confirmation_text)
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
            self.assertIn("Emily Chen (echen123)", roster_lines[4])
            self.assertIn("Sarah Connor (sconnor)", roster_lines[5])
            self.assertIn("Maria Rodriguez (mrodriguez)", roster_lines[6])
            
            self.assertIn("OPEN MATCHING", roster_lines[8], "Missing open matching header")
            self.assertIn("John Agda (johna1234)", roster_lines[9])
            self.assertIn("Alex Kim (akim)", roster_lines[10])
            self.assertIn("James Wilson", roster_lines[12])  # No discord ID
            self.assertIn("Sam Taylor (staylor)", roster_lines[11])           

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
            print("FARTS", flush=True)
            print(responses, flush=True)
            self.assertTrue(any("Player 1 updated successfully" in msg for msg in responses))

            # Verify player's updated name
            with self.Session() as session:
                player = session.query(Player).filter_by(id=1).first()
                self.assertIsNotNone(player)
                self.assertEqual(player.real_first, "John")
                self.assertEqual(player.real_last, "Rom")

            # Edit discord username and ensure discord_id is updated with it
            edit_discord_command = '!edit_player id=1 discord="mthompson_92"'
            responses = await self.execute_command(edit_discord_command)
            self.assertTrue(any("Player 1 updated successfully" in msg for msg in responses))

            with self.Session() as session:
                player = session.query(Player).filter_by(id=1).first()
                self.assertIsNotNone(player)
                self.assertEqual(player.discord_username, "mthompson_92")
                self.assertEqual(player.discord_id, "723456789123456789")
        self.run_async_test(run_test())

    def test_winter_2026_league(self):
        """Test the complete Winter 2026 league setup with teams, players, and games"""
        async def run_test():
            # Execute all commands from VALID_COMMANDS_2
            for command in VALID_COMMANDS_2:
                responses = await self.execute_command(command, verbose=True)
                print(responses)
                self.assertTrue(any("created successfully" in msg.lower() or "added to team" in msg.lower() for msg in responses), 
                              f"Command failed: {command}")

            # Test roster for Big Disc Energy (team 1)
            roster_command = '!roster id=1'
            responses = await self.execute_command(roster_command)
            print(responses)
            roster_text = '\n'.join(responses)
            
            print(roster_text)
            
            # Verify roster content
            self.assertIn("Team Roster: Disc Wizards", roster_text)

            # Female matching players
            self.assertIn("Nina Chen (ninachen_)", roster_text)
            self.assertIn("Rebecca Martinez (becca528)", roster_text)
            self.assertIn("Sophia Anderson (sophiaa)", roster_text)
            self.assertIn("Emma Fisher (emmafisher)", roster_text)
            self.assertIn("Isabel Turner (isaturner)", roster_text)

            # Open matching players
            self.assertIn("Marcus Thompson (mthompson_92)", roster_text)
            self.assertIn("Daniel Parker (dparker807)", roster_text)
            self.assertIn("Thomas Wright (twright054)", roster_text)
            self.assertIn("Lucas Cooper (lc660)", roster_text)
            self.assertIn("Ryan Mitchell (ryan_33)", roster_text)
            self.assertIn("Michael Hayes (mhayes)", roster_text)
            self.assertIn("Robert Bennett (rbennett97)", roster_text)

            # Verify the mock date is set to before all test games
            self.assertEqual(self.disco_robo.datetime.now(), datetime(2025, 10, 1))

            # Test schedule
            schedule_command = '!schedule'
            responses = await self.execute_command(schedule_command)
            print(responses)
            schedule_text = '\n'.join(responses)
            
            print("\n=== League Schedule ===")
            print(schedule_text)
            print("=== End Schedule ===\n")
            
            # Verify all teams appear in schedule
            self.assertIn("Disc Wizards", schedule_text)
            self.assertIn("Storm Chasers", schedule_text)
            self.assertIn("Gravity Breakers", schedule_text)
            self.assertIn("Wind Warriors", schedule_text)
            self.assertIn("Sky Raiders", schedule_text)
            self.assertIn("Spiral Force", schedule_text)
            self.assertIn("Cloud Runners", schedule_text)
            self.assertIn("Air Masters", schedule_text)
            
            # Verify all game dates appear
            self.assertIn("Oct 26", schedule_text)
            self.assertIn("Nov  2", schedule_text)
            self.assertIn("Nov  9", schedule_text)
            self.assertIn("Nov 16", schedule_text)
            self.assertIn("Nov 23", schedule_text)
            self.assertIn("Nov 30", schedule_text)
            self.assertIn("Dec  7", schedule_text)
            self.assertIn("Dec 14", schedule_text)
            
            # Verify field locations
            self.assertIn("Riverside 1", schedule_text)
            self.assertIn("Riverside 2", schedule_text)

        self.run_async_test(run_test())

    def test_edit_game_change_datetime(self):
        """Test editing a game's datetime via the bot command"""
        async def run_test():
            # Set up teams, players, and a game
            for command in VALID_COMMANDS[:6]:
                await self.execute_command(command)

            # Verify the game exists with original datetime
            with self.Session() as session:
                game = session.query(Game).first()
                self.assertIsNotNone(game)
                original_id = game.id
                self.assertEqual(game.datetime, datetime(2025, 11, 15, 19, 30))

            # Edit the game's datetime
            edit_command = f'!edit_game id={original_id} datetime="2025-12-25 20:00"'
            responses = await self.execute_command(edit_command)
            self.assertTrue(any("updated successfully" in msg for msg in responses))

            # Verify the datetime was changed
            with self.Session() as session:
                game = session.query(Game).filter_by(id=original_id).first()
                self.assertEqual(game.datetime, datetime(2025, 12, 25, 20, 0))
                # Other fields unchanged
                self.assertEqual(game.park, "Riverside Park")
                self.assertEqual(game.field, 2)

        self.run_async_test(run_test())

    def test_edit_game_change_both_teams(self):
        """Test editing both away and home teams via the bot command"""
        async def run_test():
            # Set up all teams, players, and games
            for command in VALID_COMMANDS:
                await self.execute_command(command)

            # Get the first game
            with self.Session() as session:
                game = session.query(Game).first()
                original_id = game.id
                # Originally: away=Cobra Snakes(1), home=Python Pirates(2)
                self.assertEqual(game.awayteam.name, "Cobra Snakes")
                self.assertEqual(game.hometeam.name, "Python Pirates")

            # Edit both teams: swap to Red Dragons(3) away, Green Geckos(4) home
            edit_command = f'!edit_game id={original_id} away=3 home=4'
            responses = await self.execute_command(edit_command)
            self.assertTrue(any("updated successfully" in msg for msg in responses))

            # Verify both teams changed
            with self.Session() as session:
                game = session.query(Game).filter_by(id=original_id).first()
                self.assertEqual(game.awayteam.name, "Red Dragons")
                self.assertEqual(game.hometeam.name, "Green Geckos")
                # Other fields unchanged
                self.assertEqual(game.datetime, datetime(2025, 11, 15, 19, 30))
                self.assertEqual(game.park, "Riverside Park")

        self.run_async_test(run_test())

    def test_edit_game_nonexistent_team(self):
        """Test that editing with a nonexistent team ID returns an error"""
        async def run_test():
            # Set up teams and a game
            for command in VALID_COMMANDS[:6]:
                await self.execute_command(command)

            with self.Session() as session:
                game = session.query(Game).first()
                game_id = game.id

            # Try to set away team to nonexistent ID
            edit_command = f'!edit_game id={game_id} away=9999'
            responses = await self.execute_command(edit_command, expect_error=True)
            self.assertTrue(any("9999" in msg for msg in responses))
            self.assertTrue(any("error" in msg.lower() for msg in responses))

            # Verify game was not modified
            with self.Session() as session:
                game = session.query(Game).filter_by(id=game_id).first()
                self.assertEqual(game.awayteam.name, "Cobra Snakes")

        self.run_async_test(run_test())

    def test_edit_game_bad_datetime_format(self):
        """Test that a badly formatted datetime returns an error via the bot command"""
        async def run_test():
            # Set up teams and a game
            for command in VALID_COMMANDS[:6]:
                await self.execute_command(command)

            with self.Session() as session:
                game = session.query(Game).first()
                game_id = game.id

            # Try to edit with a bad datetime string
            edit_command = f'!edit_game id={game_id} datetime="not-a-date"'
            responses = await self.execute_command(edit_command, expect_error=True)
            self.assertTrue(any("error" in msg.lower() for msg in responses))

            # Verify game datetime was not modified
            with self.Session() as session:
                game = session.query(Game).filter_by(id=game_id).first()
                self.assertEqual(game.datetime, datetime(2025, 11, 15, 19, 30))

        self.run_async_test(run_test())
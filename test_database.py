import unittest
from datetime import datetime
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from models import Base, Team, Player, Game, Attendance, AttendanceStatus, Genders
from db_utils import (
    create_team, create_player, create_game, edit_game, get_team_roster, get_team_roster_obj,
    add_player_to_team, get_player, remove_player_from_team, delete_game,
    get_team_games, set_attendance_status, get_game_attendance, get_player_by_discord_id
)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Create an in-memory database for testing."""
        # Create an in-memory SQLite database
        self.engine = create_engine('sqlite:///:memory:', echo=False)
        
        # Create all tables
        Base.metadata.create_all(self.engine)
        
        # Create a session factory
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Create test data
        self.create_test_data()

    def tearDown(self):
        """Clean up after each test."""
        # Rollback any pending transactions
        self.session.rollback()
        
        # Close the session
        self.session.close()
        
        # Drop all tables (this will close any remaining connections)
        Base.metadata.drop_all(self.engine)
        
        # Dispose of the engine and all its connections
        self.engine.dispose()
        
        # Remove the session
        self.session = None

    def create_test_data(self):
        """Create sample teams, players, and games for testing."""
        # Create four teams
        self.disco_ninjas = create_team(
            self.session,
            name="Disco Ninjas",
            year=2025,
            season="Fall",
            home_colour="purple",
            away_colour="black"
        )
        
        self.ultimate_warriors = create_team(
            self.session,
            name="Ultimate Warriors",
            year=2025,
            season="Fall",
            home_colour="blue",
            away_colour="white"
        )
        
        self.flying_squirrels = create_team(
            self.session,
            name="Flying Squirrels",
            year=2025,
            season="Fall",
            home_colour="brown",
            away_colour="green"
        )
        
        self.cosmic_rays = create_team(
            self.session,
            name="Cosmic Rays",
            year=2025,
            season="Fall",
            home_colour="yellow",
            away_colour="orange"
        )

        # Create six players with mock Discord IDs and usernames
        self.players = [
            create_player(self.session, "Alice", "Johnson", "f", 
                        discord_username="alicejohnson", discord_id="123456789123456789"),
            create_player(self.session, "Bob", "Smith", "m", 
                        discord_username="bobsmith", discord_id="223456789123456789"),
            create_player(self.session, "Carol", "Davis", "f", 
                        discord_username="caroldavis", discord_id="323456789123456789"),
            create_player(self.session, "David", "Wilson", "m", 
                        discord_username="davidwilson", discord_id="423456789123456789"),
            create_player(self.session, "Eve", "Brown", "f", 
                        discord_username="evebrown", discord_id="523456789123456789"),
            create_player(self.session, "Frank", "Miller", "m", 
                        discord_username="frankmiller", discord_id="623456789123456789")
        ]
        
        # Add players to Cosmic Rays team
        for player in self.players:
            add_player_to_team(self.session, self.cosmic_rays.id, player)
        
        # Create the game schedule
        self.games = [
            # Game 1: Cosmic Rays (at) Disco Ninjas
            create_game(
                self.session,
                self.cosmic_rays.id,  # away
                self.disco_ninjas.id,  # home
                datetime(2025, 10, 29, 18, 0),  # 6:00 PM
                "Guelph Lake",
                2
            ),
            # Game 2: Ultimate Warriors (at) Cosmic Rays
            create_game(
                self.session,
                self.ultimate_warriors.id,  # away
                self.cosmic_rays.id,  # home
                datetime(2025, 11, 6, 19, 0),  # 7:00 PM
                "Margaret Greene",
                4
            ),
            # Game 3: Cosmic Rays (at) Flying Squirrels
            create_game(
                self.session,
                self.cosmic_rays.id,  # away
                self.flying_squirrels.id,  # home
                datetime(2025, 11, 13, 16, 0),  # 4:00 PM
                "Marden Park",
                1
            )
        ]

        # Commit all changes
        self.session.commit()

    def display_database_contents(self):
        """Display all contents of the test database."""
        # Create a new session for this display to avoid interfering with test sessions
        display_session = sessionmaker(bind=self.engine)()
        
        try:
            print("\n=== Database Contents ===")
            
            # Display Teams
            print("\nTeams:")
            teams = display_session.query(Team).all()
            print(f"    Found {len(teams)} teams in the database")
            for team in teams:
                print(f"  {team.id}: {team.name} ({team.year} {team.season})")
                print(f"     Colours: {team.home_colour}/{team.away_colour}")
                print(f"     Players: {len(team.players)}")
            
            # Display Players
            print("\nPlayers:")
            players = display_session.query(Player).all()
            print(f"    Found {len(players)} players in the database")
            for player in players:
                print(f"  {player.id}: {player.real_first} {player.real_last}")
                print(f"     Discord: {player.discord_username}")
                print(f"     Gender: {player.gender}")
                print(f"     Teams: {[team.name for team in player.teams]}")
            
            # Display Games
            print("\nGames:")
            games = display_session.query(Game).all()
            print(f"    Found {len(games)} games in the database")
            for game in games:
                print(f"  {game.id}: {game.awayteam.name} @ {game.hometeam.name}")
                print(f"     When: {game.datetime.strftime('%I:%M %p, %B %d, %Y')}")
                print(f"     Where: {game.park} Field {game.field}")
            
            # Display Attendance
            print("\nAttendance:")
            attendance = display_session.query(Attendance).all()
            if attendance:
                for record in attendance:
                    print(f"  {record.id}: {record.player.get_full_name()} - {record.status}")
        finally:
            # Ensure the session is closed even if an error occurs
            display_session.close()

    def test_database_setup(self):
        """Test that the database was set up correctly."""        
        # Verify teams were created
        teams = self.session.query(Team).all()
        self.assertEqual(len(teams), 4, "Should have created 4 teams")
        
        # Verify team names
        team_names = {team.name for team in teams}
        expected_names = {
            "Disco Ninjas",
            "Ultimate Warriors",
            "Flying Squirrels",
            "Cosmic Rays"
        }
        self.assertEqual(team_names, expected_names, "Team names don't match expected values")

    def test_player_team_relationships(self):
        """Test verifying player-team relationships."""
        # Verify Cosmic Rays roster
        roster = get_team_roster_obj(self.session, self.cosmic_rays.id)
        

        # Verify counts and membership
        self.assertEqual(len(roster), 6, "Should have 6 players on the team")
        roster_names = {f"{p.real_first} {p.real_last}" for p in roster}
        expected_names = {
            "Alice Johnson",
            "Bob Smith",
            "Carol Davis",
            "David Wilson",
            "Eve Brown",
            "Frank Miller"
        }
        self.assertEqual(roster_names, expected_names, "Roster names don't match expected values")

    def test_get_player(self):
        """Test getting a player by ID."""
        # Get an existing player
        alice = self.players[0]  # Alice Johnson
        retrieved_player = get_player(self.session, alice.id)
        self.assertIsNotNone(retrieved_player)
        self.assertEqual(retrieved_player.real_first, "Alice")
        self.assertEqual(retrieved_player.real_last, "Johnson")
        self.assertEqual(retrieved_player.discord_username, "alicejohnson")
        
        # Try getting a non-existent player
        nonexistent_player = get_player(self.session, 9999)
        self.assertIsNone(nonexistent_player)

    def test_game_schedule(self):
        """Test that games were created correctly and can be retrieved."""
        # Verify each game exists and has correct data
        for game in self.games:
            retrieved_game = self.session.query(Game).filter_by(id=game.id).first()
            self.assertIsNotNone(retrieved_game, f"Game {game.id} should exist")
            
            # Verify game details
            self.assertEqual(retrieved_game.park, game.park)
            self.assertEqual(retrieved_game.field, game.field)
            self.assertEqual(retrieved_game.datetime, game.datetime)
            self.assertEqual(retrieved_game.awayteam.id, game.awayteam.id)
            self.assertEqual(retrieved_game.hometeam.id, game.hometeam.id)

        # Get all games for Cosmic Rays
        cosmic_rays_games = get_team_games(self.session, self.cosmic_rays.id)

        # Print the schedule for debugging
        print("\nCosmic Rays Schedule:")
        for game in cosmic_rays_games:
            away_team = game.awayteam
            home_team = game.hometeam
            print(f"{game.datetime.strftime('%I:%M %p')}: "
                  f"{away_team.name} @ {home_team.name}, "
                  f"{game.park} Field {game.field}")

        # Verify correct number of games
        self.assertEqual(len(cosmic_rays_games), 3, "Should have 3 games for Cosmic Rays")

    def test_delete_game(self):
        """Test deleting a game and its attendance records."""
        # Get initial game and attendance counts
        initial_games = self.session.query(Game).count()
        initial_attendance = self.session.query(Attendance).count()
        
        # Get a specific game to delete (first game)
        game_to_delete = self.games[0]
        game_id = game_to_delete.id
        
        # Count attendance records for this specific game
        game_attendance_count = self.session.query(Attendance)\
            .filter_by(game_id=game_id)\
            .count()
        
        # Delete the game
        delete_game(self.session, game_id)
        
        # Verify game no longer exists
        deleted_game = self.session.query(Game).filter_by(id=game_id).first()
        self.assertIsNone(deleted_game, "Game should be deleted")
        
        # Verify game's attendance records are gone
        game_attendance = self.session.query(Attendance).filter_by(game_id=game_id).all()
        self.assertEqual(len(game_attendance), 0, "Game attendance records should be deleted")
        
        # Verify overall counts
        self.assertEqual(
            self.session.query(Game).count(),
            initial_games - 1,
            "Should have one less game"
        )
        self.assertEqual(
            self.session.query(Attendance).count(),
            initial_attendance - game_attendance_count,
            "Should have fewer attendance records"
        )
        
        # Try to delete non-existent game
        with self.assertRaises(ValueError):
            delete_game(self.session, 9999)

    def display_attendance_summary(self, game):
        """Helper method to display attendance summary for a game."""
        # Get attendance grouped by status
        attendance = get_game_attendance(self.session, game.id)
        
        # Format each group into first names only
        attending = sorted([p.real_first for p in attendance["attending"]])
        not_attending = sorted([p.real_first for p in attendance["not_attending"]])
        pending = sorted([p.real_first for p in attendance["pending"]])
        
        # Print concise summary
        print(f"Y: {', '.join(attending) if attending else '-'}")
        print(f"N: {', '.join(not_attending) if not_attending else '-'}")
        print(f"?: {', '.join(pending) if pending else '-'}")

    def test_attendance_tracking(self):
        """Test tracking attendance for a game with various status changes."""
        # We'll use the first game (Cosmic Rays @ Disco Ninjas)
        game = self.games[0]
        
        # Create initial PENDING attendance records if they don't exist
        existing_attendance = self.session.query(Attendance)\
            .filter_by(game_id=game.id)\
            .all()

        print("\nInitial state:")
        self.display_attendance_summary(game)
        
        # Two players set ATTENDING
        print("\nStep 1: Alice and Bob set to ATTENDING")
        alice = get_player_by_discord_id(self.session, "123456789123456789")
        set_attendance_status(self.session, game.id, alice.id, AttendanceStatus.ATTENDING)
        bob = get_player_by_discord_id(self.session, "223456789123456789")
        set_attendance_status(self.session, game.id, bob.id, AttendanceStatus.ATTENDING)
        self.display_attendance_summary(game)
        
        # One player set NOT ATTENDING
        print("\nStep 2: Carol sets to NOT ATTENDING")
        carol = get_player_by_discord_id(self.session, "323456789123456789")
        set_attendance_status(self.session, game.id, carol.id, AttendanceStatus.NOT_ATTENDING)
        self.display_attendance_summary(game)
        
        # One more player set ATTENDING
        print("\nStep 3: David sets to ATTENDING")
        david = get_player_by_discord_id(self.session, "423456789123456789")
        set_attendance_status(self.session, game.id, david.id, AttendanceStatus.ATTENDING)
        self.display_attendance_summary(game)

        # Frank leaves the team
        print("\nStep 3.5: Frank leaves the team")
        frank = get_player_by_discord_id(self.session, "623456789123456789")
        # Use the new utility function to remove Frank from the team
        remove_player_from_team(self.session, self.cosmic_rays.id, frank)
        self.display_attendance_summary(game)
        
        # One more player set NOT ATTENDING
        print("\nStep 4: Eve sets to NOT ATTENDING")
        eve = get_player_by_discord_id(self.session, "523456789123456789")
        set_attendance_status(self.session, game.id, eve.id, AttendanceStatus.NOT_ATTENDING)
        self.display_attendance_summary(game)

        # Add a new player George
        print("\nStep 4.5: Adding new player George")
        george = create_player(
            self.session,
            "George",
            "Wallis",
            "m",
            discord_username="georgewallis",
            discord_id="723456789123456789"
        )
        add_player_to_team(self.session, self.cosmic_rays.id, george)
        
        # Create attendance record for George (starts as PENDING)
        attendance = Attendance(
            player=george,
            game=game,
            status=AttendanceStatus.PENDING
        )
        self.session.add(attendance)
        self.session.commit()
        self.display_attendance_summary(game)
        
        # One player switches from ATTENDING to NOT ATTENDING
        print("\nStep 5: Bob switches from ATTENDING to NOT ATTENDING")
        self.session.query(Attendance)\
            .filter_by(game_id=game.id, player_id=self.players[1].id)\
            .update({Attendance.status: AttendanceStatus.NOT_ATTENDING})
        self.session.commit()
        self.display_attendance_summary(game)
        
        # Final state
        print("\nFinal state")
        self.display_attendance_summary(game)
        
        # Verify final attendance counts
        final_attendance = self.session.query(Attendance)\
            .filter_by(game_id=game.id)\
            .all()
        
        attending_count = sum(1 for a in final_attendance if a.status == AttendanceStatus.ATTENDING)
        not_attending_count = sum(1 for a in final_attendance if a.status == AttendanceStatus.NOT_ATTENDING)
        pending_count = sum(1 for a in final_attendance if a.status == AttendanceStatus.PENDING)
        
        self.assertEqual(attending_count, 2, "Should have 2 players attending")
        self.assertEqual(not_attending_count, 3, "Should have 3 players not attending")
        self.assertEqual(pending_count, 1, "Should have 1 player pending (George)")

    def test_edit_game_change_datetime(self):
        """Test editing a game's datetime."""
        game = self.games[0]
        new_dt = datetime(2025, 12, 25, 20, 0)

        updated = edit_game(self.session, game.id, game_datetime=new_dt)

        self.assertEqual(updated.datetime, new_dt)
        # Verify other fields unchanged
        self.assertEqual(updated.awayteam_id, self.cosmic_rays.id)
        self.assertEqual(updated.hometeam_id, self.disco_ninjas.id)
        self.assertEqual(updated.park, "Guelph Lake")
        self.assertEqual(updated.field, 2)

    def test_edit_game_change_both_teams(self):
        """Test editing both away and home teams at once."""
        game = self.games[0]

        updated = edit_game(
            self.session, game.id,
            away=self.flying_squirrels.id,
            home=self.ultimate_warriors.id
        )

        self.assertEqual(updated.awayteam_id, self.flying_squirrels.id)
        self.assertEqual(updated.hometeam_id, self.ultimate_warriors.id)
        # Verify other fields unchanged
        self.assertEqual(updated.datetime, datetime(2025, 10, 29, 18, 0))
        self.assertEqual(updated.park, "Guelph Lake")

    def test_edit_game_nonexistent_team(self):
        """Test that editing with a nonexistent team ID raises ValueError."""
        game = self.games[0]

        with self.assertRaises(ValueError) as cm:
            edit_game(self.session, game.id, away=9999)
        self.assertIn("9999", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            edit_game(self.session, game.id, home=9999)
        self.assertIn("9999", str(cm.exception))

    def test_edit_game_bad_datetime_format(self):
        """Test that a badly formatted datetime raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            edit_game(self.session, self.games[0].id, game_datetime="not-a-date")
        self.assertIn("datetime", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
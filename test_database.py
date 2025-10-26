import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Team, Player, Game, Attendance, AttendanceStatus
from db_utils import create_team, create_player, create_game

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
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def create_test_data(self):
        """Create sample teams for testing."""
        # Create four teams
        self.disco_ninjas = create_team(
            self.session,
            name="Disco Ninjas",
            year=2025,
            season="Fall",
            home_color="purple",
            away_color="black"
        )
        
        self.ultimate_warriors = create_team(
            self.session,
            name="Ultimate Warriors",
            year=2025,
            season="Fall",
            home_color="blue",
            away_color="white"
        )
        
        self.flying_squirrels = create_team(
            self.session,
            name="Flying Squirrels",
            year=2025,
            season="Fall",
            home_color="brown",
            away_color="green"
        )
        
        self.cosmic_rays = create_team(
            self.session,
            name="Cosmic Rays",
            year=2025,
            season="Fall",
            home_color="yellow",
            away_color="orange"
        )

    def display_database_contents(self):
        """Display all contents of the test database."""
        print("\n=== Database Contents ===")
        
        # Display Teams
        print("\nTeams:")
        teams = self.session.query(Team).all()
        for team in teams:
            print(f"  {team.id}: {team.name} ({team.year} {team.season})")
            print(f"     Colors: {team.home_color}/{team.away_color}")
            print(f"     Players: {len(team.players)}")
        
        # Display Players
        print("\nPlayers:")
        players = self.session.query(Player).all()
        for player in players:
            print(f"  {player.id}: {player.real_first} {player.real_last}")
            print(f"     Discord: {player.discord_username}")
            print(f"     Gender: {player.gender}")
            print(f"     Teams: {[team.name for team in player.teams]}")
        
        # Display Games
        print("\nGames:")
        games = self.session.query(Game).all()
        for game in games:
            print(f"  {game.id}: {game.awayteam.name} vs {game.hometeam.name}")
            print(f"     When: {game.datetime}")
            print(f"     Where: {game.park} Field {game.field}")
        
        # Display Attendance
        print("\nAttendance:")
        attendance = self.session.query(Attendance).all()
        for record in attendance:
            print(f"  Game {record.game_id}, Player {record.player.real_first}: {record.status.value}")
            if record.response_time:
                print(f"     Responded: {record.response_time}")
            if record.notes:
                print(f"     Notes: {record.notes}")

    def test_database_setup(self):
        """Test that the database was set up correctly."""
        # Display the contents
        self.display_database_contents()
        
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

if __name__ == '__main__':
    unittest.main()
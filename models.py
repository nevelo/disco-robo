from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table, UniqueConstraint, Enum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum
from datetime import datetime

Base = declarative_base()

# --- Enums ---
class AttendanceStatus(enum.Enum):
    PENDING = "pending"      # Haven't responded yet
    ATTENDING = "yes"       # Confirmed attending
    NOT_ATTENDING = "no"    # Confirmed not attending

class MessageType(enum.Enum):
    GAME_ANNOUNCEMENT = "game_announcement"
    BOTHER_MSG = "bother_msg"
    PESTER_MSG = "pester_msg"
    GAMEDAY_REMINDER = "gameday_reminder"

class Genders(enum.Enum):
    OPEN_MATCHING = "m"
    FEMALE_MATCHING = "f"

# --- Association Tables ---

player_team_association = Table(
    'player_team', Base.metadata,
    Column('player_id', Integer, ForeignKey('players.id'), primary_key=True),
    Column('team_id', Integer, ForeignKey('teams.id'), primary_key=True)
)

# --- Models ---

class Team(Base):
    __tablename__= "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    home_colour = Column(String, nullable=False, default="white")
    away_colour = Column(String, nullable=False, default="black")

    # Ensure no duplicate team with the same name-year-season combination exists
    __table_args__ = (UniqueConstraint("name", "year", "season"),)

    # Many-to-many: Team <-> Players through player_team_association
    players = relationship(
        "Player",
        secondary=player_team_association,
        back_populates="teams"
    )

    # One-to-many: Team -> Games (as away or home team)
    games_as_away = relationship("Game", back_populates="awayteam", foreign_keys="Game.awayteam_id")
    games_as_home = relationship("Game", back_populates="hometeam", foreign_keys="Game.hometeam_id")

    def __repr__(self):
        return f"<Team(name='{self.name}', year={self.year}, season='{self.season}')>"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)  
    discord_username = Column(String, nullable=False)
    real_first = Column(String, nullable=False)
    real_last = Column(String, nullable=False)
    gender = Column(Enum(Genders), nullable=False)
    shortname = Column(String, nullable=True)  # Optional nickname
    discord_id = Column(String, nullable=False, unique=True)  # Discord user ID

    # Many-to-many: Player <-> Teams through player_team_association
    teams = relationship(
        "Team",
        secondary=player_team_association,
        back_populates="players"
    )

    # Relationship with Attendance
    attendances = relationship("Attendance", back_populates="player")

    def __repr__(self):
        return f"<Player(discord='{self.discord_username}', real='{self.real_first} {self.real_last}')>"

    def get_full_name(self):
        return f"{self.real_first} {self.real_last}"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False)
    park = Column(String, nullable=False)
    field = Column(Integer, nullable=False)
    announcement_msg = Column(String, nullable=True)  # Discord message ID for the announcement
    bother_msg = Column(String, nullable=True)        # Discord message ID for the bother message
    pester_msg = Column(String, nullable=True)       # Discord message ID for the pester message
    gameday_msg = Column(String, nullable=True)       # Discord message ID for the gameday reminder

    # Two participating teams
    awayteam_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    hometeam_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    # Relationships
    awayteam = relationship("Team", back_populates="games_as_away", foreign_keys=[awayteam_id])
    hometeam = relationship("Team", back_populates="games_as_home", foreign_keys=[hometeam_id])
    attendances = relationship("Attendance", back_populates="game")

    def __repr__(self):
        return f"<Game({self.awayteam.name} vs {self.hometeam.name} @ {self.datetime})>"

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PENDING)
    response_time = Column(DateTime, nullable=True)  # When they last responded
    reminder_sent = Column(DateTime, nullable=True)  # When the last reminder was sent

    # Relationships
    game = relationship("Game", back_populates="attendances")
    player = relationship("Player", back_populates="attendances")

    # Ensure a player can only have one attendance record per game
    __table_args__ = (UniqueConstraint("game_id", "player_id"),)

    def __repr__(self):
        return f"<Attendance(player='{self.player.discord_username}', game='{self.game.id}', status='{self.status.value}')>"

# --- Database setup ---

# Global variables to hold engine and SessionLocal
engine = None
SessionLocal = None

def init_db(db_url: str = "sqlite:///disc_bot.db", echo: bool = True):
    """
    Initialize the database connection and session factory.
    
    Args:
        db_url: Database URL (default: sqlite:///disc_bot.db)
        echo: Whether to echo SQL statements (default: True)
    """
    global engine, SessionLocal
    
    # Create engine with the given URL
    engine = create_engine(db_url, echo=echo)
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    Base.metadata.create_all(engine)

def dispose_db():
    """
    Properly dispose of the database engine and connection pool.
    Call this when shutting down the application.
    """
    global engine
    if engine:
        engine.dispose()

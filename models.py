from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative.base()

# --- Models ---

class Team(Base):
    __tablename__= "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String, nullable=False)

    # Ensure no duplicate team with the asme name-year-season combination exists
    __table_args__ = (UniqueConstraint("name", "year", "season"),)

    # One-to-many: Team -> Players
    players = relationship("Player", back_populates="team")

    # One-to-many: Team -> Games (as team1 or team2)
    games_as_team1 = relationship("Game", back_populates="team1", foreign_keys="Game.team1_id")
    games_as_team2 = relationship("Game", back_populates="team2", foreign_keys="Game.team2_id")

    def __repr__(self):
        return f"<Team(name='{self.name}', year={self.year}, season='{self.season}')>"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    discord_username = Column(String, nullable=False)
    real_name = Column(String, nullable=False)
    gender = Column(String, nullable=True)

    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team = relationship("Team", back_populates="players")

    def __repr__(self):
        return f"<Player(discord='{self.discord_username}', real='{self.real_name}')>"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False)
    park = Column(String, nullable=False)
    field = Column(Integer, nullable=False)

    # Two participating teams
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    team1 = relationship("Team", back_populates="games_as_team1", foreign_keys=[team1_id])
    team2 = relationship("Team", back_populates="games_as_team2", foreign_keys=[team2_id])

    def __repr__(self):
        return f"<Game({self.team1.name} vs {self.team2.name} @ {self.datetime})>"

player_team_association = Table(
    'player_team', Base.metadata,
    Column('player_id', Integer, ForeignKey('players.id'), primary_key=True),
    Column('team_id', Integer, ForeignKey('teams.id'), primary_key=True)
)

# Example engine & session factory (you can import these in your bot file)
engine = create_engine("sqlite:///disc_bot.db", echo=True)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Call this once to create tables."""
    Base.metadata.create_all(engine)

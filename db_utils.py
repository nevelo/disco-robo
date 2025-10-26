from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from models import Team, Player, Game, Attendance, AttendanceStatus

# Constants for unknown/placeholder values
UNKNOWN_DISCORD = "pending_discord"
UNKNOWN_NAME = "Unknown Player"


# Create a new team. 
def create_team(
    session: Session,
    name: str,
    year: int,
    season: str,
    home_color: str = "white",
    away_color: str = "black"
) -> Team:
    """Create a new team."""
    team = Team(
        name=name,
        year=year,
        season=season,
        home_color=home_color,
        away_color=away_color
    )
    session.add(team)
    session.commit()
    return team

# Create a new player.
def create_player(
    session: Session,
    first_name: str,
    last_name: str,
    gender: str,
    discord_username: Optional[str] = None,
    initial_team_id: Optional[int] = None
) -> Player:
    """Create a new player and optionally add them to a team.
    
    Args:
        session: SQLAlchemy session
        first_name: Player's first name
        last_name: Player's last name
        gender: 'm' or 'f'
        discord_username: Optional Discord username
        initial_team_id: Optional ID of team to add player to
    """
    player = Player(
        real_first=first_name,
        real_last=last_name,
        discord_username=discord_username or UNKNOWN_DISCORD,
        gender=gender
    )
    session.add(player)
    
    # If an initial team is specified, add the player to it
    if initial_team_id is not None:
        team = session.query(Team).filter_by(id=initial_team_id).first()
        if team:
            team.players.append(player)
    
    session.commit()
    return player

# Create a new game and initialize attendance records for all players.
def create_game(
    session: Session,
    awayteam_id: int,
    hometeam_id: int,
    datetime: datetime,
    park: str,
    field: int
) -> Game:
    """Create a new game and initialize attendance records for all players on both teams.
    
    Args:
        session: SQLAlchemy session
        awayteam_id: ID of the away team
        hometeam_id: ID of the home team
        datetime: Date and time of the game
        park: Name of the park/venue
        field: Field number
    """
    # Get both teams first to validate they exist
    awayteam = session.query(Team).filter_by(id=awayteam_id).first()
    hometeam = session.query(Team).filter_by(id=hometeam_id).first()
    
    if not awayteam or not hometeam:
        raise ValueError("Both teams must exist")

    # Create the game
    game = Game(
        awayteam_id=awayteam_id,
        hometeam_id=hometeam_id,
        datetime=datetime,
        park=park,
        field=field
    )
    session.add(game)
    session.commit()

    # Get all players from both teams using the many-to-many relationship
    awayteam_players = set(awayteam.players)  # Using set to handle potential duplicates
    hometeam_players = set(hometeam.players)
    all_players = awayteam_players.union(hometeam_players)
    
    # Create attendance records for all players
    for player in all_players:
        attendance = Attendance(
            game_id=game.id,
            player_id=player.id,
            status=AttendanceStatus.PENDING
        )
        session.add(attendance)
    
    session.commit()
    return game

# Get the full roster of a team.
def get_team_roster(
    session: Session,
    team_id: int,
    include_unknown: bool = True
) -> List[Player]:
    """
    Get all players on a team.
    If include_unknown is False, excludes players with placeholder Discord usernames.
    """
    team = session.query(Team).filter_by(id=team_id).first()
    if not team:
        return []
    
    if include_unknown:
        return team.players
    else:
        return [p for p in team.players if p.discord_username != UNKNOWN_DISCORD]

def get_game_attendance(
    session: Session,
    game_id: int
) -> dict:
    """
    Get attendance status for a game, grouped by status.
    If tracked_team_ids is provided, only show attendance for those teams.
    
    Args:
        session: SQLAlchemy session
        game_id: ID of the game to check
        tracked_team_ids: Optional list of team IDs we care about. If None, show all attendance.
    
    Returns:
        Dict with lists of players grouped by attendance status
    """
    game = session.query(Game).filter_by(id=game_id).first()
    if not game:
        return {}

    # Get all attendance records for this game
    attendances = session.query(Attendance).filter_by(game_id=game_id).all()
    
    result = {
        "attending": [],
        "not_attending": [],
        "pending": []
    }

    for attendance in attendances:
        if attendance.status == AttendanceStatus.ATTENDING:
            result["attending"].append(attendance.player)
        elif attendance.status == AttendanceStatus.NOT_ATTENDING:
            result["not_attending"].append(attendance.player)
        else:  # PENDING
            result["pending"].append(attendance.player)

    return result

def update_attendance(
    session: Session,
    game_id: int,
    player_id: int,
    status: AttendanceStatus,
    notes: Optional[str] = None
) -> Attendance:
    """Update a player's attendance status for a game."""
    attendance = session.query(Attendance).filter_by(
        game_id=game_id,
        player_id=player_id
    ).first()
    
    if attendance:
        attendance.status = status
        attendance.response_time = datetime.now()
        if notes is not None:
            attendance.notes = notes
        session.commit()
    
    return attendance

def add_player_to_team(
    session: Session,
    team_id: int,
    player: Player
) -> None:
    """Add an existing player to a team."""
    team = session.query(Team).filter_by(id=team_id).first()
    if team and player not in team.players:
        team.players.append(player)
        session.commit()
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from models import Team, Player, Game, Attendance, AttendanceStatus, Genders

# Constants for unknown/placeholder values
UNKNOWN_DISCORD = "pending_discord"  # Local constant used by both disco-robo.py and this module
UNKNOWN_NAME = "Unknown Player"

# Delete a team and all its relationships.
def delete_team(
    session: Session,
    team: Team
) -> None:  
    """Delete a team and all its relationships."""
    # Delete all games associated with this team
    for game in team.games_as_away + team.games_as_home:
        session.delete(game)
    
    # The player-team associations will be automatically deleted due to SQLAlchemy cascade
    session.delete(team)
    session.commit()

# Create a new team. 
def create_team(
    session: Session,
    name: str,
    year: int,
    season: str,
    home_colour: str = "white",
    away_colour: str = "black"
) -> Team:
    """Create a new team."""
    team = Team(
        name=name,
        year=year,
        season=season,
        home_colour=home_colour,
        away_colour=away_colour
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
        gender: 'm' or 'f' (will be converted to Genders enum)
        discord_username: Optional Discord username
        initial_team_id: Optional ID of team to add player to
    """
    # Convert gender string to enum
    if gender.lower() == 'm' or gender.lower() == 'o':
        gender_enum = Genders.OPEN_MATCHING
    elif gender.lower() == 'f':
        gender_enum = Genders.FEMALE_MATCHING
    else:
        raise ValueError("Gender must be 'm', 'f', or 'o'")
    player = Player(
        real_first=first_name,
        real_last=last_name,
        discord_username=discord_username or UNKNOWN_DISCORD,
        gender=gender_enum
    )
    session.add(player)
    
    # If an initial team is specified, add the player to it
    if initial_team_id is not None:
        team = session.query(Team).filter_by(id=initial_team_id).first()
        if team:
            team.players.append(player)
    
    session.commit()
    return player

# Edit an existing player's details.
# NOT YET IMPLEMENTED
def edit_player(
    session: Session,
    player_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    gender: Optional[str] = None,
    discord_username: Optional[str] = None
)   -> Optional[Player]:
    # First retrieve the player
    player = session.query(Player).filter_by(id=player_id).first()
    if not player:
        return None
    
    if first_name is not None:
        player.real_first = first_name
    if last_name is not None:
        player.real_last = last_name
    if gender is not None:
        # Convert gender string to enum
        if gender.lower() == 'm' or gender.lower() == 'o':
            player.gender = Genders.OPEN_MATCHING
        elif gender.lower() == 'f':
            player.gender = Genders.FEMALE_MATCHING
        else:
            raise ValueError("Gender must be 'm', 'f', or 'o'")
    if discord_username is not None:
        player.discord_username = discord_username
    
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
    """Create a new game.
    
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
    return game

def edit_game(
    session: Session,
    awayteam_id: Optional[int] = None,
    hometeam_id: Optional[int] = None,
    datetime: Optional[datetime] = None,
    park: Optional[str] = None,
    field: Optional[int] = None
) -> Optional[Game]:
    if awayteam_id is not None:
        pass  # Implementation goes here
    if hometeam_id is not None:
        pass  # Implementation goes here
    if datetime is not None:
        pass  # Implementation goes here
    if park is not None:
        pass  # Implementation goes here
    if field is not None:
        pass  # Implementation goes here
    return None

def set_attendance_status(
    session: Session,
    game_id: int,
    player_id: int,
    status: AttendanceStatus,
) -> Attendance:
    """Update attendance status for a player in a game.
    
    Args:
        session: SQLAlchemy session
        game_id: ID of the game
        player_id: ID of the player
        status: New attendance status
        
    Returns:
        The updated or created Attendance record
        
    Raises:
        ValueError: If the game or player doesn't exist
    """
    # Verify game and player exist
    game = session.query(Game).filter_by(id=game_id).first()
    if not game:
        raise ValueError(f"Game with ID {game_id} not found")
        
    player = session.query(Player).filter_by(id=player_id).first()
    if not player:
        raise ValueError(f"Player with ID {player_id} not found")
        
    # Update status
    attendance = session.query(Attendance)\
        .filter_by(game_id=game_id, player_id=player_id)\
        .first()
        
    if attendance:
        attendance.status = status
    else:
        attendance = Attendance(
            game_id=game_id,
            player_id=player_id,
            status=status
        )
        session.add(attendance)
    
    session.commit()
    return attendance

def get_team_games(
    session: Session,
    team_id: int
) -> List[Game]:
    """Get all games for a team, ordered by datetime.
    
    Args:
        session: SQLAlchemy session
        team_id: ID of the team
        
    Returns:
        List of games the team is part of
        
    Raises:
        ValueError: If the team doesn't exist
    """
    team = session.query(Team).filter_by(id=team_id).first()
    if not team:
        raise ValueError(f"Team with ID {team_id} not found")
        
    return session.query(Game)\
        .filter((Game.hometeam_id == team_id) | (Game.awayteam_id == team_id))\
        .order_by(Game.datetime)\
        .all()

def delete_game(
    session: Session,
    game_id: int
) -> None:
    """Delete a game and all associated attendance records.
    
    Args:
        session: SQLAlchemy session
        game_id: ID of the game to delete
        
    Raises:
        ValueError: If the game with the given ID doesn't exist
    """
    # Get the game first to verify it exists
    game = session.query(Game).filter_by(id=game_id).first()
    if not game:
        raise ValueError(f"Game with ID {game_id} not found")
    
    # Delete all attendance records for this game first (due to foreign key constraint)
    session.query(Attendance).filter_by(game_id=game_id).delete()
    
    # Delete the game
    session.query(Game).filter_by(id=game_id).delete()
    
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

def get_player(
    session: Session,
    player_id: int
) -> Optional[Player]:
    """
    Get a player by their ID.
    Returns None if player not found.
    """
    return session.query(Player).filter_by(id=player_id).first()

def get_player_by_discord(
    session: Session,
    discord_username: str
) -> Optional[Player]:
    """
    Get a player by their Discord username.
    Returns None if player not found.
    """
    return session.query(Player).filter_by(discord_username=discord_username).first()

def get_game_attendance(
    session: Session,
    game_id: int,
    team_id: int = -1,
    include_details: bool = False
) -> dict:
    """Get attendance status for a game, grouped by status.
    
    Args:
        session: SQLAlchemy session
        game_id: ID of the game to check
        include_details: If True, includes full Attendance records instead of just Players
    
    Returns:
        Dict with lists of either Players (include_details=False) or Attendance records 
        (include_details=True) grouped by status
        
    Raises:
        ValueError: If the game doesn't exist
    """
    game = session.query(Game).filter_by(id=game_id).first()
    if not game:
        raise ValueError(f"Game with ID {game_id} not found")

    # initialize results structure    
    result = {
        "attending": [],
        "not_attending": [],
        "pending": []
    }

    # Get all players from both teams
    players = []
    teams = [game.hometeam, game.awayteam] if team_id == -1 else [team for team in [game.hometeam, game.awayteam] if team.id == team_id]
    if not teams:
        raise ValueError(f"Team with ID {team_id} not found in this game")
    for team in teams:
        players.extend(team.players)
    
    # Get all attendance records for this game
    attendances = session.query(Attendance).filter_by(game_id=game_id).all()
    attendance_by_player = {a.player_id: a for a in attendances}
    
    # Process each player
    for player in players:
        attendance = attendance_by_player.get(player.id)
        if attendance:
            if include_details:
                item = attendance
            else:
                item = player
            
            if attendance.status == AttendanceStatus.ATTENDING:
                result["attending"].append(item)
            elif attendance.status == AttendanceStatus.NOT_ATTENDING:
                result["not_attending"].append(item)
            else:  # PENDING
                result["pending"].append(item)
        else:
            # If no attendance record exists, player is pending
            result["pending"].append(player if not include_details else None)

    return result

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

def remove_player_from_team(
    session: Session,
    team_id: int,
    player: Player
) -> None:
    """Remove a player from a team and delete their attendance records for future games.
    
    Args:
        session: SQLAlchemy session
        team_id: ID of the team to remove the player from
        player: Player object to remove
        
    Note:
        This will:
        1. Remove the player from the team roster
        2. Delete all attendance records for future games with this team
        3. Leave historical attendance records intact
    """
    team = session.query(Team).filter_by(id=team_id).first()
    if not team:
        raise ValueError(f"Team with ID {team_id} not found")
        
    if player not in team.players:
        raise ValueError(f"Player {player.get_full_name()} is not on team {team.name}")
    
    # Remove player from the team
    team.players.remove(player)
    
    # Get all games this team is part of
    games = session.query(Game).filter(
        (Game.hometeam_id == team_id) | (Game.awayteam_id == team_id)
    ).all()
    
    for game in games:
        # Delete attendance record if it exists
        session.query(Attendance)\
            .filter_by(game_id=game.id, player_id=player.id)\
            .delete()
    
    session.commit()
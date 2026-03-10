"""
Data models for structured gamesheet data.

These dataclasses provide consistent data structures for parsed gamesheet data,
enabling JSON serialization/deserialization and type-safe data handling.

Requirements: 8.1, 8.2, 8.3
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class GameMetadata:
    """
    Game metadata extracted from gamesheet.

    Contains basic game information including teams, scores, date, time, and location.

    Attributes:
        game_id: Unique identifier for the game
        date: Game date in YYYY-MM-DD format
        time: Game start time
        location: Rink/arena name
        home_team: Home team name
        away_team: Away team name
        home_score: Final score for home team
        away_score: Final score for away team
    """
    game_id: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


@dataclass
class Player:
    """
    Player information from gamesheet roster.

    Represents a player with jersey number, name, and optional position.
    Position is simplified to 'Skater' or 'Goalie' for youth hockey.

    Attributes:
        number: Jersey number (as string to preserve leading zeros)
        name: Player name in "First Last" format
        position: 'Skater', 'Goalie', or None if unknown
    """
    number: str
    name: str
    position: Optional[str] = None


@dataclass
class Goal:
    """
    Goal information from scoring summary.

    Represents a single goal with all associated details including
    period, time, scorer, assists, and strength.

    Attributes:
        period: Period number (1, 2, 3, or 4 for OT)
        time: Time of goal in MM:SS format
        team: 'home' or 'away'
        scorer: Name of goal scorer
        assists: List of assist player names (0-2 elements)
        strength: Goal type - 'EV' (even), 'PP' (power play), 'SH' (shorthanded), 'EN' (empty net)
    """
    period: int
    time: str
    team: str
    scorer: str
    assists: List[str] = field(default_factory=list)
    strength: str = 'EV'


@dataclass
class Penalty:
    """
    Penalty information from penalty summary.

    Represents a single penalty with all associated details.

    Attributes:
        period: Period number (1, 2, 3, or 4 for OT)
        time: Time penalty was called in MM:SS format
        team: 'home' or 'away'
        player: Name of penalized player
        infraction: Type of penalty (e.g., "Tripping", "Interference")
        duration: Penalty duration in minutes (2, 5, or 10)
    """
    period: int
    time: str
    team: str
    player: str
    infraction: str
    duration: int


@dataclass
class GoalieStats:
    """
    Goalie statistics from gamesheet.

    Contains performance metrics for a goalie including saves,
    goals allowed, and calculated save percentage.

    Attributes:
        team: 'home' or 'away'
        number: Jersey number (as string)
        name: Goalie name
        shots_against: Total shots faced
        saves: Total saves made
        goals_allowed: Total goals allowed
        save_percentage: Save percentage (0.0 to 1.0)
    """
    team: str
    number: str
    name: str
    shots_against: Optional[int] = None
    saves: Optional[int] = None
    goals_allowed: Optional[int] = None
    save_percentage: Optional[float] = None


@dataclass
class GamesheetData:
    """
    Container for all parsed gamesheet data.

    Aggregates all extracted data from a gamesheet PDF into a single
    structured object that can be serialized to/from JSON.

    Attributes:
        game_metadata: Basic game information
        home_roster: List of home team players
        away_roster: List of away team players
        scoring_summary: List of goals
        penalty_summary: List of penalties
        goalie_stats: List of goalie statistics
    """
    game_metadata: GameMetadata
    home_roster: List[Player] = field(default_factory=list)
    away_roster: List[Player] = field(default_factory=list)
    scoring_summary: List[Goal] = field(default_factory=list)
    penalty_summary: List[Penalty] = field(default_factory=list)
    goalie_stats: List[GoalieStats] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert GamesheetData to dictionary for JSON serialization.

        Returns:
            Dictionary representation of all gamesheet data with consistent schema.
        """
        return {
            'game_metadata': asdict(self.game_metadata),
            'home_roster': [asdict(p) for p in self.home_roster],
            'away_roster': [asdict(p) for p in self.away_roster],
            'scoring_summary': [asdict(g) for g in self.scoring_summary],
            'penalty_summary': [asdict(p) for p in self.penalty_summary],
            'goalie_stats': [asdict(g) for g in self.goalie_stats],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GamesheetData':
        """
        Create GamesheetData from dictionary (for loading JSON).

        Args:
            data: Dictionary with gamesheet data (typically from JSON)

        Returns:
            GamesheetData instance populated from the dictionary
        """
        # Parse game metadata
        metadata_dict = data.get('game_metadata', {})
        game_metadata = GameMetadata(
            game_id=metadata_dict.get('game_id'),
            date=metadata_dict.get('date'),
            time=metadata_dict.get('time'),
            location=metadata_dict.get('location'),
            home_team=metadata_dict.get('home_team'),
            away_team=metadata_dict.get('away_team'),
            home_score=metadata_dict.get('home_score'),
            away_score=metadata_dict.get('away_score'),
        )

        # Parse home roster
        home_roster = [
            Player(
                number=p.get('number', ''),
                name=p.get('name', ''),
                position=p.get('position'),
            )
            for p in data.get('home_roster', [])
        ]

        # Parse away roster
        away_roster = [
            Player(
                number=p.get('number', ''),
                name=p.get('name', ''),
                position=p.get('position'),
            )
            for p in data.get('away_roster', [])
        ]

        # Parse scoring summary
        scoring_summary = [
            Goal(
                period=g.get('period', 0),
                time=g.get('time', ''),
                team=g.get('team', ''),
                scorer=g.get('scorer', ''),
                assists=g.get('assists', []),
                strength=g.get('strength', 'EV'),
            )
            for g in data.get('scoring_summary', [])
        ]

        # Parse penalty summary
        penalty_summary = [
            Penalty(
                period=p.get('period', 0),
                time=p.get('time', ''),
                team=p.get('team', ''),
                player=p.get('player', ''),
                infraction=p.get('infraction', ''),
                duration=p.get('duration', 0),
            )
            for p in data.get('penalty_summary', [])
        ]

        # Parse goalie stats
        goalie_stats = [
            GoalieStats(
                team=g.get('team', ''),
                number=g.get('number', ''),
                name=g.get('name', ''),
                shots_against=g.get('shots_against'),
                saves=g.get('saves'),
                goals_allowed=g.get('goals_allowed'),
                save_percentage=g.get('save_percentage'),
            )
            for g in data.get('goalie_stats', [])
        ]

        return cls(
            game_metadata=game_metadata,
            home_roster=home_roster,
            away_roster=away_roster,
            scoring_summary=scoring_summary,
            penalty_summary=penalty_summary,
            goalie_stats=goalie_stats,
        )

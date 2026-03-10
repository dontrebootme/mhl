"""Game data model for cloud storage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Game:
    """Represents a hockey game with all associated data."""

    game_id: str
    season_id: str
    division_id: str
    home_team: str
    home_team_id: str
    away_team: str
    away_team_id: str
    home_score: Optional[int]
    away_score: Optional[int]
    date: str
    time: str
    location: str
    status: str
    recap_text: Optional[str]
    last_updated: datetime

    def to_dict(self) -> dict:
        return {
            'game_id': self.game_id,
            'season_id': self.season_id,
            'division_id': self.division_id,
            'home_team': self.home_team,
            'home_team_id': self.home_team_id,
            'away_team': self.away_team,
            'away_team_id': self.away_team_id,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'date': self.date,
            'time': self.time,
            'location': self.location,
            'status': self.status,
            'recap_text': self.recap_text,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Game':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        return cls(
            game_id=str(data['game_id']),
            season_id=str(data['season_id']),
            division_id=str(data['division_id']),
            home_team=str(data['home_team']),
            home_team_id=str(data['home_team_id']),
            away_team=str(data['away_team']),
            away_team_id=str(data['away_team_id']),
            home_score=int(data['home_score']) if data.get('home_score') is not None else None,
            away_score=int(data['away_score']) if data.get('away_score') is not None else None,
            date=str(data['date']),
            time=str(data['time']),
            location=str(data['location']),
            status=str(data['status']),
            recap_text=str(data['recap_text']) if data.get('recap_text') is not None else None,
            last_updated=last_updated,
        )

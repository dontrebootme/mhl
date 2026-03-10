"""Standing data model for cloud storage."""

from dataclasses import dataclass


@dataclass
class Standing:
    """Represents a team's standing in a division."""

    team_id: str
    team_name: str
    ranking: int
    games_played: int
    wins: int
    losses: int
    ties: int
    points: int
    goals_for: int
    goals_against: int

    def to_dict(self) -> dict:
        return {
            'team_id': self.team_id,
            'team_name': self.team_name,
            'ranking': self.ranking,
            'games_played': self.games_played,
            'wins': self.wins,
            'losses': self.losses,
            'ties': self.ties,
            'points': self.points,
            'goals_for': self.goals_for,
            'goals_against': self.goals_against,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Standing':
        return cls(
            team_id=str(data['team_id']),
            team_name=str(data['team_name']),
            ranking=int(data['ranking']),
            games_played=int(data['games_played']),
            wins=int(data['wins']),
            losses=int(data['losses']),
            ties=int(data['ties']),
            points=int(data['points']),
            goals_for=int(data['goals_for']),
            goals_against=int(data['goals_against']),
        )

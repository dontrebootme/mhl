"""
USA Hockey Patch Awards detection from gamesheet data.

Detects individual game achievements:
- Hat Trick: 3+ goals in a single game
- Playmaker: 3+ assists in a single game
- Shutout: 0 goals allowed by a goalie in a full game
"""

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from mhl_scraper.parsers.gamesheet_models import GamesheetData


class AwardType(str, Enum):
    """USA Hockey patch award types."""
    HAT_TRICK = 'hat_trick'
    PLAYMAKER = 'playmaker'
    SHUTOUT = 'shutout'


@dataclass
class PatchAward:
    """A single USA Hockey patch award earned in a game."""
    award_type: str
    player_name: str
    player_number: str
    team_name: str
    game_date: Optional[str]
    game_id: Optional[str]
    opponent: str
    details: str  # e.g. "4 goals", "3 assists", "22 saves"


@dataclass
class GameAwards:
    """All awards detected from a single game."""
    game_id: Optional[str]
    game_date: Optional[str]
    home_team: Optional[str]
    away_team: Optional[str]
    awards: List[PatchAward] = field(default_factory=list)


def _resolve_team_name(side: str, metadata) -> str:
    """Get team name for a 'home' or 'away' side."""
    if side == 'home':
        return metadata.home_team or 'Home'
    return metadata.away_team or 'Away'


def _resolve_opponent(side: str, metadata) -> str:
    """Get opponent name for a 'home' or 'away' side."""
    if side == 'home':
        return metadata.away_team or 'Away'
    return metadata.home_team or 'Home'


def _find_player_number(player_name: str, side: str, gamesheet: GamesheetData) -> str:
    """Look up a player's jersey number from the roster."""
    roster = gamesheet.home_roster if side == 'home' else gamesheet.away_roster
    for player in roster:
        if player.name == player_name:
            return player.number
    return ''


def _build_roster_maps(gamesheet: GamesheetData) -> dict:
    """Build name-to-number lookup maps for both rosters."""
    return {
        'home': {p.name: p.number for p in gamesheet.home_roster},
        'away': {p.name: p.number for p in gamesheet.away_roster},
    }


def detect_hat_tricks(gamesheet: GamesheetData) -> List[PatchAward]:
    """Detect hat tricks (3+ goals) from a gamesheet's scoring summary."""
    meta = gamesheet.game_metadata
    awards = []
    roster_maps = _build_roster_maps(gamesheet)

    # Count goals per (scorer, team_side)
    goal_counts = Counter()
    for goal in gamesheet.scoring_summary:
        goal_counts[(goal.scorer, goal.team)] += 1

    for (scorer, side), count in goal_counts.items():
        if count >= 3:
            # Get player number from roster (empty string if not found)
            # Note: Missing numbers may indicate roster data issues or players
            # incorrectly attributed to the wrong team in scoring data.
            player_number = roster_maps[side].get(scorer, '')

            awards.append(PatchAward(
                award_type=AwardType.HAT_TRICK,
                player_name=scorer,
                player_number=player_number,
                team_name=_resolve_team_name(side, meta),
                game_date=meta.date,
                game_id=meta.game_id,
                opponent=_resolve_opponent(side, meta),
                details=f"{count} goals",
            ))

    return awards


def detect_playmakers(gamesheet: GamesheetData) -> List[PatchAward]:
    """Detect playmaker awards (3+ assists) from a gamesheet's scoring summary."""
    meta = gamesheet.game_metadata
    awards = []
    roster_maps = _build_roster_maps(gamesheet)

    # Count assists per (player, team_side)
    assist_counts = Counter()
    for goal in gamesheet.scoring_summary:
        for assist_name in goal.assists:
            assist_counts[(assist_name, goal.team)] += 1

    for (player, side), count in assist_counts.items():
        if count >= 3:
            # Get player number from roster (empty string if not found)
            # Note: Missing numbers may indicate roster data issues or players
            # incorrectly attributed to the wrong team in scoring data.
            player_number = roster_maps[side].get(player, '')

            awards.append(PatchAward(
                award_type=AwardType.PLAYMAKER,
                player_name=player,
                player_number=player_number,
                team_name=_resolve_team_name(side, meta),
                game_date=meta.date,
                game_id=meta.game_id,
                opponent=_resolve_opponent(side, meta),
                details=f"{count} assists",
            ))

    return awards


def detect_shutouts(gamesheet: GamesheetData) -> List[PatchAward]:
    """Detect shutout awards from goalie stats.

    Conservative logic — only awards when confident a single goalie played the full game:
    - 1 goalie listed for team with GA == 0: award
    - 2+ goalies: only award if exactly 1 has non-null shots_against/saves (backup didn't play)
    - 0-0 tie: both teams' goalies eligible
    - opponent_score is None: skip (can't confirm shutout)
    """
    meta = gamesheet.game_metadata
    awards = []

    for side in ('home', 'away'):
        # Determine opponent's score
        if side == 'home':
            opponent_score = meta.away_score
        else:
            opponent_score = meta.home_score

        # Can't confirm shutout without a score
        if opponent_score is None:
            continue

        # No shutout if opponent scored
        if opponent_score > 0:
            continue

        # Find goalies for this side
        side_goalies = [g for g in gamesheet.goalie_stats if g.team == side]

        if not side_goalies:
            continue

        # Determine the single goalie candidate who played the full game
        candidate = None
        if len(side_goalies) == 1:
            candidate = side_goalies[0]
        else:
            # Multiple goalies listed — only award if exactly one actually played
            played = [g for g in side_goalies if g.shots_against is not None or g.saves is not None]
            if len(played) == 1:
                candidate = played[0]

        if candidate and candidate.goals_allowed is not None and candidate.goals_allowed == 0:
            saves_str = f"{candidate.saves} saves" if candidate.saves is not None else "shutout"
            awards.append(PatchAward(
                award_type=AwardType.SHUTOUT,
                player_name=candidate.name,
                player_number=candidate.number,
                team_name=_resolve_team_name(side, meta),
                game_date=meta.date,
                game_id=meta.game_id,
                opponent=_resolve_opponent(side, meta),
                details=saves_str,
            ))

    return awards


def detect_all_awards(gamesheet: GamesheetData) -> GameAwards:
    """Run all award detection on a gamesheet."""
    meta = gamesheet.game_metadata
    awards = []
    awards.extend(detect_hat_tricks(gamesheet))
    awards.extend(detect_playmakers(gamesheet))
    awards.extend(detect_shutouts(gamesheet))

    return GameAwards(
        game_id=meta.game_id,
        game_date=meta.date,
        home_team=meta.home_team,
        away_team=meta.away_team,
        awards=awards,
    )


def filter_awards_by_team(game_awards: GameAwards, team_filter: str) -> GameAwards:
    """Filter awards to only those matching a team name (case-insensitive substring match)."""
    team_lower = team_filter.lower()
    filtered = [a for a in game_awards.awards if team_lower in a.team_name.lower()]
    return GameAwards(
        game_id=game_awards.game_id,
        game_date=game_awards.game_date,
        home_team=game_awards.home_team,
        away_team=game_awards.away_team,
        awards=filtered,
    )

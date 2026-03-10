"""
Scouting report generation from game data.

This module provides functionality for generating comprehensive scouting reports
from game data, including integration with parsed gamesheet data for detailed
player statistics.

Requirements: 10.3, 10.4, 10.5, 10.6, 10.8
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from jinja2 import Template

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class GameSummary:
    """Summary of a single game for scouting purposes."""
    game_id: str
    date: str
    opponent: str
    score: str
    result: str  # 'W', 'L', or 'T'
    goals_for: int
    goals_against: int
    key_moments: List[str] = field(default_factory=list)
    style_keywords: List[str] = field(default_factory=list)


@dataclass
class ScoutingReportData:
    """Complete scouting report data structure."""
    # Team info
    team_name: str
    division: str = ""
    report_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    # Record and standings
    wins: int = 0
    losses: int = 0
    ties: int = 0
    division_rank: Optional[int] = None
    total_points: Optional[int] = None

    # Scoring stats
    avg_goals_for: float = 0.0
    avg_goals_against: float = 0.0
    total_goals_for: int = 0
    total_goals_against: int = 0

    # Game summaries
    games_analyzed: int = 0
    recent_games: List[GameSummary] = field(default_factory=list)

    # Player analysis
    top_scorers: List[Dict[str, Any]] = field(default_factory=list)
    goalies: List[Dict[str, Any]] = field(default_factory=list)
    playmakers: List[Dict[str, Any]] = field(default_factory=list)
    key_players: List[Dict[str, Any]] = field(default_factory=list)

    # Team tendencies
    play_style: str = "Balanced"
    common_keywords: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    # Statistics
    high_scoring_pct: float = 0.0
    close_game_pct: float = 0.0
    comeback_pct: float = 0.0
    physical_pct: float = 0.0

    # Period analysis
    period_strengths: Dict[str, int] = field(default_factory=dict)

    # Coaching recommendations
    recommendations: List[str] = field(default_factory=list)

    # Gamesheet-derived statistics (Requirements 10.3, 10.4, 10.5, 10.6)
    gamesheet_top_scorers: List[Dict[str, Any]] = field(default_factory=list)
    gamesheet_most_penalized: List[Dict[str, Any]] = field(default_factory=list)
    gamesheet_goalies: List[Dict[str, Any]] = field(default_factory=list)

    # Data coverage summary (Requirement 10.8)
    gamesheets_analyzed: int = 0
    gamesheets_available: int = 0


def aggregate_player_stats(
    gamesheet_data_list: List[Dict[str, Any]],
    team_name: str
) -> Dict[str, Any]:
    """
    Aggregate player statistics across multiple gamesheets.

    This function processes parsed gamesheet data to calculate cumulative
    statistics for players on the specified team, including:
    - Top scorers with goal/assist/point totals
    - Most penalized players with PIM totals
    - Goalie performance metrics

    Args:
        gamesheet_data_list: List of parsed gamesheet dictionaries from parse_gamesheet_pdf()
        team_name: Name of the team to aggregate stats for

    Returns:
        Dictionary containing:
        - top_scorers: List of dicts with name, goals, assists, points, games
        - most_penalized: List of dicts with name, pim, infractions, games
        - goalies: List of dicts with name, games, save_pct, ga_avg, goals_allowed

    Requirements:
        - 10.3: Enhance scouting report with player-level statistics
        - 10.4: Identify top scorers with goal and assist totals
        - 10.5: Identify most penalized players
        - 10.6: Include goalie performance metrics
    """
    logger.info(f"Aggregating player stats for team '{team_name}' from {len(gamesheet_data_list)} gamesheet(s)")

    # Player scoring stats: {name: {goals, assists, games}}
    player_scoring = defaultdict(lambda: {'goals': 0, 'assists': 0, 'games': set()})

    # Player penalty stats: {name: {pim, infractions, games}}
    player_penalties = defaultdict(lambda: {'pim': 0, 'infractions': [], 'games': set()})

    # Goalie stats: {name: {games, total_ga, total_saves, total_shots}}
    goalie_stats = defaultdict(lambda: {
        'games': 0,
        'total_goals_allowed': 0,
        'total_saves': 0,
        'total_shots': 0
    })

    games_processed = 0
    games_skipped = 0

    for gamesheet in gamesheet_data_list:
        if not gamesheet:
            games_skipped += 1
            logger.debug("Skipping empty gamesheet entry")
            continue

        metadata = gamesheet.get('game_metadata', {})
        game_id = metadata.get('game_id', 'unknown')

        # Determine which side (home/away) is the team we're scouting
        home_team = metadata.get('home_team', '')
        away_team = metadata.get('away_team', '')

        # Match team name (case-insensitive partial match)
        team_name_lower = team_name.lower()
        is_home = team_name_lower in home_team.lower() if home_team else False
        is_away = team_name_lower in away_team.lower() if away_team else False

        if not is_home and not is_away:
            # Team not found in this gamesheet, skip
            logger.debug(f"Team '{team_name}' not found in game {game_id} (home: {home_team}, away: {away_team})")
            games_skipped += 1
            continue

        team_side = 'home' if is_home else 'away'
        games_processed += 1
        logger.debug(f"Processing game {game_id}: team is {team_side} side")

        # Get roster for the team
        roster_key = f'{team_side}_roster'
        roster = gamesheet.get(roster_key, [])
        roster_numbers = {p.get('number') for p in roster}
        roster_names = {p.get('number'): p.get('name') for p in roster}

        # Process scoring summary
        for goal in gamesheet.get('scoring_summary', []):
            if goal.get('team') != team_side:
                continue

            scorer = goal.get('scorer', '')
            if scorer and not scorer.startswith('#'):
                player_scoring[scorer]['goals'] += 1
                player_scoring[scorer]['games'].add(game_id)

            for assist in goal.get('assists', []):
                if assist and not assist.startswith('#'):
                    player_scoring[assist]['assists'] += 1
                    player_scoring[assist]['games'].add(game_id)

        # Process penalty summary
        for penalty in gamesheet.get('penalty_summary', []):
            if penalty.get('team') != team_side:
                continue

            player = penalty.get('player', '')
            if player and not player.startswith('#'):
                duration = penalty.get('duration', 0)
                infraction = penalty.get('infraction', 'Unknown')

                player_penalties[player]['pim'] += duration
                player_penalties[player]['infractions'].append(infraction)
                player_penalties[player]['games'].add(game_id)

        # Process goalie stats
        for goalie in gamesheet.get('goalie_stats', []):
            if goalie.get('team') != team_side:
                continue

            name = goalie.get('name', '')
            if not name:
                continue

            # Only count goalies who actually played (have stats)
            goals_allowed = goalie.get('goals_allowed')
            saves = goalie.get('saves')
            shots = goalie.get('shots_against')

            # A goalie "played" if they have any non-None stats
            if goals_allowed is not None or saves is not None or shots is not None:
                goalie_stats[name]['games'] += 1

                if goals_allowed is not None:
                    goalie_stats[name]['total_goals_allowed'] += goals_allowed

                if saves is not None:
                    goalie_stats[name]['total_saves'] += saves

                if shots is not None:
                    goalie_stats[name]['total_shots'] += shots

    # Build top scorers list (sorted by points, then goals)
    top_scorers = []
    for name, stats in player_scoring.items():
        points = stats['goals'] + stats['assists']
        if points > 0:
            top_scorers.append({
                'name': name,
                'goals': stats['goals'],
                'assists': stats['assists'],
                'points': points,
                'games': len(stats['games'])
            })

    top_scorers.sort(key=lambda x: (-x['points'], -x['goals'], x['name']))

    # Build most penalized list (sorted by PIM)
    most_penalized = []
    for name, stats in player_penalties.items():
        if stats['pim'] > 0:
            # Get unique infractions
            unique_infractions = list(set(stats['infractions']))
            most_penalized.append({
                'name': name,
                'pim': stats['pim'],
                'infractions': unique_infractions,
                'games': len(stats['games'])
            })

    most_penalized.sort(key=lambda x: (-x['pim'], x['name']))

    # Build goalie stats list
    goalies = []
    for name, stats in goalie_stats.items():
        if stats['games'] > 0:
            games = stats['games']
            total_ga = stats['total_goals_allowed']
            total_saves = stats['total_saves']
            total_shots = stats['total_shots']

            # Calculate averages
            ga_avg = total_ga / games if games > 0 else 0

            # Calculate save percentage
            save_pct = None
            if total_shots > 0:
                save_pct = total_saves / total_shots

            goalies.append({
                'name': name,
                'games': games,
                'goals_allowed': total_ga,
                'ga_avg': round(ga_avg, 2),
                'saves': total_saves,
                'shots_against': total_shots,
                'save_pct': round(save_pct, 3) if save_pct is not None else None
            })

    goalies.sort(key=lambda x: (-x['games'], x['name']))

    # Log summary
    logger.info(
        f"Player stats aggregation complete: {games_processed} games processed, "
        f"{games_skipped} skipped, {len(top_scorers)} scorers, "
        f"{len(most_penalized)} penalized players, {len(goalies)} goalies"
    )

    return {
        'top_scorers': top_scorers,
        'most_penalized': most_penalized,
        'goalies': goalies
    }


def enhance_report_with_gamesheet_data(
    report_data: 'ScoutingReportData',
    gamesheet_data_list: List[Dict[str, Any]]
) -> 'ScoutingReportData':
    """
    Enhance scouting report with parsed gamesheet data.

    This function takes existing scouting report data and enriches it with
    detailed player statistics extracted from parsed gamesheets.

    Args:
        report_data: ScoutingReportData object to enhance
        gamesheet_data_list: List of parsed gamesheet dictionaries

    Returns:
        Enhanced ScoutingReportData with gamesheet-derived statistics

    Requirements:
        - 10.3: Enhance scouting report with player-level statistics
        - 10.4: Identify top scorers with goal and assist totals
        - 10.5: Identify most penalized players
        - 10.6: Include goalie performance metrics
        - 10.7: Generate report using available data without errors
        - 10.8: Include data coverage summary
    """
    logger.info(f"Enhancing report for team '{report_data.team_name}' with gamesheet data")

    # Filter out None/empty gamesheets
    valid_gamesheets = [g for g in gamesheet_data_list if g]

    # Update data coverage
    report_data.gamesheets_available = len(gamesheet_data_list)
    report_data.gamesheets_analyzed = len(valid_gamesheets)

    logger.info(
        f"Data coverage: {len(valid_gamesheets)} of {len(gamesheet_data_list)} "
        f"gamesheets available for analysis"
    )

    if not valid_gamesheets:
        # No gamesheet data available, return report as-is (Requirement 10.7)
        logger.warning(
            f"No valid gamesheet data available for team '{report_data.team_name}'. "
            "Report will be generated with partial data."
        )
        return report_data

    # Aggregate player statistics
    try:
        aggregated = aggregate_player_stats(valid_gamesheets, report_data.team_name)

        # Update report with gamesheet-derived data
        report_data.gamesheet_top_scorers = aggregated.get('top_scorers', [])[:10]  # Top 10
        report_data.gamesheet_most_penalized = aggregated.get('most_penalized', [])[:10]  # Top 10
        report_data.gamesheet_goalies = aggregated.get('goalies', [])

        logger.info(
            f"Report enhanced with gamesheet data: "
            f"{len(report_data.gamesheet_top_scorers)} top scorers, "
            f"{len(report_data.gamesheet_most_penalized)} penalized players, "
            f"{len(report_data.gamesheet_goalies)} goalies"
        )
    except Exception as e:
        logger.error(
            f"Failed to aggregate player stats for team '{report_data.team_name}': {e}",
            exc_info=True
        )
        # Continue with partial data (Requirement 10.7)

    return report_data


def generate_play_style_description(tendencies: Dict[str, Any]) -> str:
    """
    Generate a play style description from team tendencies.

    Args:
        tendencies: Team tendencies dict from analyze_team_tendencies()

    Returns:
        String description of play style
    """
    styles = []

    if tendencies.get('high_scoring_pct', 0) > 60:
        styles.append("high-scoring, offensive-minded")
    elif tendencies.get('high_scoring_pct', 0) < 30:
        styles.append("defensive, low-scoring")

    if tendencies.get('physical_pct', 0) > 50:
        styles.append("physical")

    if tendencies.get('close_game_pct', 0) > 50:
        styles.append("plays close games")

    if tendencies.get('comeback_pct', 0) > 30:
        styles.append("resilient, capable of comebacks")

    if not styles:
        return "Balanced team"

    return ", ".join(styles).capitalize()


def generate_recommendations(report_data: ScoutingReportData) -> List[str]:
    """
    Generate coaching recommendations based on scouting data.

    Args:
        report_data: ScoutingReportData object

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Goal differential analysis
    goal_diff = report_data.avg_goals_for - report_data.avg_goals_against
    if goal_diff > 2.0:
        recommendations.append(f"⚠️ Strong offensive team (+{goal_diff:.1f} goal differential) - focus on limiting scoring chances")
    elif goal_diff < -2.0:
        recommendations.append(f"✅ Struggling opponent ({goal_diff:.1f} goal differential) - capitalize on scoring opportunities")

    # High scoring team
    if report_data.avg_goals_for > 7.0:
        recommendations.append(f"⚠️ High-scoring opponent ({report_data.avg_goals_for:.1f} GPG) - expect offensive pressure")

    # Weak defense
    if report_data.avg_goals_against > 8.0:
        recommendations.append(f"🎯 Weak defense ({report_data.avg_goals_against:.1f} GAA) - push offense aggressively")

    # Physical play
    if report_data.physical_pct > 40:
        recommendations.append(f"💪 Physical team ({report_data.physical_pct:.0f}% of games) - prepare for hard-hitting play")

    # Comeback ability
    if report_data.comeback_pct > 30:
        recommendations.append(f"⏱️ Resilient team ({report_data.comeback_pct:.0f}% comebacks) - maintain lead, don't let up")

    # Close games
    if report_data.close_game_pct > 50:
        recommendations.append(f"🎯 Plays close games ({report_data.close_game_pct:.0f}%) - expect tight contest, every shift matters")

    # Strong defense
    if report_data.avg_goals_against < 4.0:
        recommendations.append(f"🛡️ Strong defense ({report_data.avg_goals_against:.1f} GAA) - need quality shots, make every chance count")

    return recommendations


def generate_scouting_report(report_data: ScoutingReportData, template_path: Optional[str] = None) -> str:
    """
    Generate a formatted scouting report from data.

    Args:
        report_data: ScoutingReportData object
        template_path: Optional path to custom Jinja2 template

    Returns:
        Formatted markdown scouting report
    """
    # Use default template if none provided
    if template_path is None or not os.path.exists(template_path):
        template_str = get_default_template()
    else:
        with open(template_path, 'r') as f:
            template_str = f.read()

    template = Template(template_str)

    # Render the template
    report = template.render(
        team=report_data.team_name,
        division=report_data.division,
        report_date=report_data.report_date,
        games_analyzed=report_data.games_analyzed,
        wins=report_data.wins,
        losses=report_data.losses,
        ties=report_data.ties,
        record=f"{report_data.wins}-{report_data.losses}-{report_data.ties}",
        division_rank=report_data.division_rank,
        total_points=report_data.total_points,
        avg_goals_for=report_data.avg_goals_for,
        avg_goals_against=report_data.avg_goals_against,
        recent_games=report_data.recent_games,
        top_scorers=report_data.top_scorers,
        goalies=report_data.goalies,
        playmakers=report_data.playmakers,
        key_players=report_data.key_players,
        play_style=report_data.play_style,
        common_keywords=report_data.common_keywords,
        strengths=report_data.strengths,
        weaknesses=report_data.weaknesses,
        high_scoring_pct=report_data.high_scoring_pct,
        close_game_pct=report_data.close_game_pct,
        comeback_pct=report_data.comeback_pct,
        physical_pct=report_data.physical_pct,
        recommendations=report_data.recommendations,
        # Gamesheet-derived data
        gamesheet_top_scorers=report_data.gamesheet_top_scorers,
        gamesheet_most_penalized=report_data.gamesheet_most_penalized,
        gamesheet_goalies=report_data.gamesheet_goalies,
        gamesheets_analyzed=report_data.gamesheets_analyzed,
        gamesheets_available=report_data.gamesheets_available,
    )

    return report


def get_default_template() -> str:
    """
    Get the default scouting report template.

    Returns:
        Jinja2 template string
    """
    return """# Scouting Report: {{ team }}
**Generated:** {{ report_date }} | **Games Analyzed:** {{ games_analyzed }}

## Team Overview
{% if division -%}
- **Division:** {{ division }}
{% endif -%}
- **Record:** {{ record }} (Win-Loss-Tie)
{% if division_rank -%}
- **Standing:** {{ division_rank }}{{ 'st' if division_rank == 1 else ('nd' if division_rank == 2 else ('rd' if division_rank == 3 else 'th')) }} place
{% endif -%}
{% if total_points -%}
- **Points:** {{ total_points }}
{% endif -%}
- **Goals For/Game:** {{ "%.1f"|format(avg_goals_for) }} | **Goals Against/Game:** {{ "%.1f"|format(avg_goals_against) }}

## Recent Form
{% for game in recent_games[:5] -%}
{% if game.result == 'W' -%}🟢{% elif game.result == 'L' -%}🔴{% else -%}🟡{% endif %} {{ game.result }} vs {{ game.opponent }} ({{ game.score }})
{% if game.style_keywords -%}  _{{ game.style_keywords|join(', ') }}_
{% endif -%}
{% endfor %}

## Key Statistics (API Data - Reliable)
- **Offensive Efficiency:** {{ "%.1f"|format(avg_goals_for) }} goals per game
- **Defensive Performance:** {{ "%.1f"|format(avg_goals_against) }} goals against per game
- **Goal Differential:** {{ "%+.1f"|format(avg_goals_for - avg_goals_against) }} per game
- **Win Percentage:** {{ "%.1f"|format((record.split('-')[0]|int / games_analyzed) * 100) }}%

## Team Tendencies
- **Play Style:** {{ play_style }}
{% if common_keywords -%}
- **Common Characteristics:** {{ common_keywords[:5]|join(', ') }}
{% endif -%}
{% if strengths -%}
- **Strengths:** {{ strengths|join(', ') }}
{% endif -%}
{% if weaknesses -%}
- **Weaknesses:** {{ weaknesses|join(', ') }}
{% endif %}

## Statistics
- **High-Scoring Games:** {{ "%.0f"|format(high_scoring_pct) }}% ({{ (games_analyzed * high_scoring_pct / 100)|round|int }} of {{ games_analyzed }})
- **Close Games:** {{ "%.0f"|format(close_game_pct) }}% ({{ (games_analyzed * close_game_pct / 100)|round|int }} of {{ games_analyzed }})
- **Comeback Wins:** {{ "%.0f"|format(comeback_pct) }}% ({{ (games_analyzed * comeback_pct / 100)|round|int }} of {{ games_analyzed }})
{% if physical_pct > 0 -%}
- **Physical Play:** {{ "%.0f"|format(physical_pct) }}% of games
{% endif %}

{% if gamesheets_analyzed > 0 -%}
## Player Statistics (from Gamesheets)
_Data from {{ gamesheets_analyzed }} of {{ gamesheets_available }} gamesheet(s)_

{% if gamesheet_top_scorers -%}
### Top Scorers
| Player | G | A | Pts | GP |
|--------|---|---|-----|-----|
{% for player in gamesheet_top_scorers[:10] -%}
| {{ player.name }} | {{ player.goals }} | {{ player.assists }} | {{ player.points }} | {{ player.games }} |
{% endfor %}
{% endif %}

{% if gamesheet_most_penalized -%}
### Most Penalized Players
| Player | PIM | Infractions | GP |
|--------|-----|-------------|-----|
{% for player in gamesheet_most_penalized[:5] -%}
| {{ player.name }} | {{ player.pim }} | {{ player.infractions|join(', ') }} | {{ player.games }} |
{% endfor %}
{% endif %}

{% if gamesheet_goalies -%}
### Goalie Performance
| Goalie | GP | GA | GAA | SV% |
|--------|-----|-----|------|------|
{% for goalie in gamesheet_goalies -%}
| {{ goalie.name }} | {{ goalie.games }} | {{ goalie.goals_allowed }} | {{ "%.2f"|format(goalie.ga_avg) }} | {% if goalie.save_pct %}{{ "%.1f"|format(goalie.save_pct * 100) }}%{% else %}-{% endif %} |
{% endfor %}
{% endif %}
{% endif %}

{% if recommendations -%}
## Coaching Recommendations
{% for rec in recommendations -%}
- {{ rec }}
{% endfor %}
{% endif %}

## Game-by-Game Breakdown
{% for game in recent_games -%}
### Game {{ loop.index }}: {% if game.result == 'W' -%}Win{% elif game.result == 'L' -%}Loss{% else -%}Tie{% endif %} vs {{ game.opponent }}
**Date:** {{ game.date }} | **Score:** {{ game.score }}
{% if game.key_moments -%}

**Key Moments:**
{% for moment in game.key_moments -%}
- {{ moment }}
{% endfor %}
{% endif %}
{% if game.style_keywords -%}

**Style:** {{ game.style_keywords|join(', ') }}
{% else -%}

_Score data only - no game recap available_
{% endif %}

{% endfor -%}

---
*This report was automatically generated from game recaps and score data. Player statistics are based on mentions in game summaries and may not reflect complete data.*
"""


__all__ = [
    'ScoutingReportData',
    'GameSummary',
    'generate_scouting_report',
    'generate_recommendations',
    'generate_play_style_description',
    'aggregate_player_stats',
    'enhance_report_with_gamesheet_data',
]

"""
TeamLinkt client wrapper for cloud services.

This module provides a clean interface to the TeamLinkt API by wrapping
the existing mhl_scraper.utils functions. It abstracts away the details
of credential handling and configuration loading for cloud deployments.
"""
import logging
from typing import List, Dict, Any, Optional

from mhl_scraper import utils


logger = logging.getLogger(__name__)


class TeamLinktClient:
    """
    Client wrapper for TeamLinkt API operations.

    This class wraps the mhl_scraper.utils functions to provide a clean
    interface for cloud services. It handles the translation between
    the raw API responses and the cloud service layer.

    Example:
        client = TeamLinktClient()
        seasons = client.get_seasons()
        games = client.get_games(season_id="45165", division_id="244225")
    """

    def __init__(self):
        """Initialize the TeamLinkt client."""
        logger.debug("TeamLinktClient initialized")

    def get_seasons(self) -> List[Dict[str, str]]:
        """
        Get all available seasons from TeamLinkt.

        Returns:
            List of dictionaries with 'id' and 'name' keys for each season.
            Example: [{'id': '45165', 'name': '2025-26 Season'}]
        """
        logger.debug("Fetching seasons from TeamLinkt")
        seasons = utils.get_seasons()
        logger.debug(f"Retrieved {len(seasons)} seasons")
        return seasons

    def get_divisions(self, season_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get all available divisions for a season from TeamLinkt.

        Args:
            season_id: Optional season ID to filter by.

        Returns:
            List of dictionaries with 'id' and 'name' keys for each division.
            Example: [{'id': '244225', 'name': '18U'}, {'id': '244226', 'name': '18U / Green'}]
        """
        logger.debug(f"Fetching divisions for season_id={season_id}")
        divisions = utils.get_divisions(season_id=season_id)
        logger.debug(f"Retrieved {len(divisions)} divisions")
        return divisions

    def get_games(
        self,
        season_id: Optional[str] = None,
        division_id: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all games (both completed and scheduled) for a season/division.

        Args:
            season_id: Optional season ID to filter by.
            division_id: Optional division ID to filter by.
            team_id: Optional team ID to filter by. Use 'all' for all teams.

        Returns:
            List of dictionaries with game information including:
            - game_id: Unique game identifier
            - date: Game date string
            - time: Game time string
            - home_team: Home team name
            - away_team: Away team name
            - home_score: Home team score (empty string if not played)
            - away_score: Away team score (empty string if not played)
            - location: Game location/rink name
        """
        logger.debug(
            f"Fetching games: season_id={season_id}, "
            f"division_id={division_id}, team_id={team_id}"
        )
        games = utils.get_games(
            season_id=season_id,
            division_id=division_id,
            team_id=team_id
        )
        logger.debug(f"Retrieved {len(games)} games")
        return games

    def get_scores(
        self,
        season_id: Optional[str] = None,
        division_id: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get completed games with scores for a season/division.

        Args:
            season_id: Optional season ID to filter by.
            division_id: Optional division ID to filter by.
            team_id: Optional team ID to filter by. Use 'all' for all teams.

        Returns:
            List of dictionaries with completed game information including scores.
        """
        logger.debug(
            f"Fetching scores: season_id={season_id}, "
            f"division_id={division_id}, team_id={team_id}"
        )
        scores = utils.get_scores(
            season_id=season_id,
            division_id=division_id,
            team_id=team_id
        )
        logger.debug(f"Retrieved {len(scores)} completed games")
        return scores

    def get_standings(
        self,
        season_id: Optional[str] = None,
        division_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get division standings from TeamLinkt.

        Args:
            season_id: Optional season ID to filter by.
            division_id: Optional division ID to filter by.

        Returns:
            List of dictionaries with standings information including:
            - team_name: Team name
            - team_id: Team identifier
            - games_played: Number of games played
            - total_wins: Total wins
            - total_losses: Total losses
            - total_ties: Total ties
            - total_points: Total points
            - score_for: Goals scored
            - score_against: Goals allowed
            - ranking: Team ranking in division
        """
        logger.debug(
            f"Fetching standings: season_id={season_id}, division_id={division_id}"
        )
        standings = utils.get_standings(
            season_id=season_id,
            division_id=division_id
        )
        logger.debug(f"Retrieved standings for {len(standings)} teams")
        return standings

    def get_game_details(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific game.

        Args:
            game_id: The game ID to fetch details for.

        Returns:
            Dictionary with game details or None if not found.
            Includes:
            - game_id: Game identifier
            - home_team: Home team name
            - away_team: Away team name
            - home_score: Home team score
            - away_score: Away team score
            - home_record: Home team record (e.g., "5-0-0")
            - away_record: Away team record
            - date: Game date
            - time: Game time
            - location: Game location
            - division: Division name
            - status: Game status (Final, In Progress, Scheduled)
            - recap_title: Recap headline (if available)
            - recap_text: Full recap text (if available)
        """
        logger.debug(f"Fetching game details for game_id={game_id}")
        details = utils.get_game_details(game_id=game_id)
        if details:
            logger.debug(f"Retrieved details for game {game_id}")
        else:
            logger.debug(f"No details found for game {game_id}")
        return details

    def get_teams(
        self,
        season_id: Optional[str] = None,
        division_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get all unique teams from a season and/or division.

        Args:
            season_id: Optional season ID to filter by.
            division_id: Optional division ID to filter by.

        Returns:
            List of dictionaries with 'id' and 'name' keys for each team.
            Example: [{'id': '723731', 'name': 'Sno-King Jr. Thunderbirds 18U C'}]
        """
        logger.debug(
            f"Fetching teams: season_id={season_id}, division_id={division_id}"
        )
        teams = utils.get_teams(
            season_id=season_id,
            division_id=division_id
        )
        logger.debug(f"Retrieved {len(teams)} teams")
        return teams

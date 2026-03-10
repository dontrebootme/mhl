"""
API Client for the MHL Cloud API.

This module provides a client for interacting with the MHL Cloud API,
which serves cached data from TeamLinkt. The client handles HTTP errors,
timeouts, and connection failures gracefully.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4
"""
import os
from typing import Any, Dict, List, Optional

import requests

from .config import UserConfig, ScraperConfig


# Default API configuration
DEFAULT_API_URL = ScraperConfig.DEFAULT_API_URL
DEFAULT_API_TIMEOUT = ScraperConfig.DEFAULT_API_TIMEOUT


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class APIConnectionError(APIError):
    """Exception raised when the API is unreachable."""
    pass


class APITimeoutError(APIError):
    """Exception raised when an API request times out."""
    pass


class APIResponseError(APIError):
    """Exception raised when the API returns an error response.

    Includes detailed error information for debugging (Requirement 7.1).

    Attributes:
        status_code: HTTP status code
        response_body: Raw response body text
        response_headers: Response headers dict
        endpoint: The API endpoint that was called
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        response_headers: Optional[Dict[str, str]] = None,
        endpoint: Optional[str] = None,
    ):
        super().__init__(message, status_code)
        self.response_body = response_body
        self.response_headers = response_headers or {}
        self.endpoint = endpoint

    def __str__(self) -> str:
        """Format error with detailed information."""
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        if self.endpoint:
            parts.append(f"Endpoint: {self.endpoint}")
        if self.response_body:
            parts.append(f"Response: {self.response_body[:500]}")
        return " | ".join(parts)


class APIClient:
    """Client for interacting with the MHL Cloud API.

    The client fetches data from the MHL API endpoints and handles
    errors gracefully with helpful error messages.

    Attributes:
        base_url: Base URL for the API
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API. If None, loads from config/env/default.
            timeout: Request timeout in seconds. If None, uses default of 30.
        """
        config = UserConfig()

        # Determine URL: explicit arg > config/env > default
        if base_url:
            url = base_url
        else:
            url = config.get_api_url()

        self.base_url = url.rstrip('/') if url else DEFAULT_API_URL

        # Determine timeout: explicit arg > config/env > default
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = config.get_api_timeout()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            APIConnectionError: If the API is unreachable
            APITimeoutError: If the request times out
            APIResponseError: If the API returns an error
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method,
                url,
                params=params,
                timeout=self.timeout
            )

            # Handle HTTP errors (Requirement 7.1: Include full response details)
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', f'HTTP {response.status_code}')
                except Exception:
                    error_msg = f'HTTP {response.status_code}'

                raise APIResponseError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    response_headers=dict(response.headers),
                    endpoint=endpoint,
                )

            return response.json()

        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out after {self.timeout}s: {url}"
            )
        except requests.exceptions.ConnectionError:
            raise APIConnectionError(
                f"Cannot connect to MHL API at {self.base_url}\n"
                "Tip: Use --direct flag to fetch data directly from TeamLinkt"
            )
        except APIError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")

    def get_games(
        self,
        season_id: str,
        division_id: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch games from the API.

        Requirement 2.1: Fetch data from /games endpoint

        Args:
            season_id: Season identifier
            division_id: Optional division identifier
            team_id: Optional team identifier to filter by

        Returns:
            List of game dictionaries
        """
        params = {'season_id': season_id}
        if division_id:
            params['division_id'] = division_id
        if team_id:
            params['team_id'] = team_id

        try:
            response = self._request('GET', '/games', params=params)
            return response.get('data', [])
        except APIResponseError as e:
            if e.status_code == 404:
                return []
            raise

    def get_scores(
        self,
        season_id: str,
        division_id: str,
        team_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch completed games with scores from the API.

        Requirement 2.2: Fetch data from /scores endpoint

        Args:
            season_id: Season identifier
            division_id: Division identifier
            team_id: Optional team identifier to filter by

        Returns:
            List of completed game dictionaries with scores
        """
        params = {
            'season_id': season_id,
            'division_id': division_id
        }
        if team_id:
            params['team_id'] = team_id

        try:
            response = self._request('GET', '/scores', params=params)
            return response.get('data', [])
        except APIResponseError as e:
            if e.status_code == 404:
                return []
            raise

    def get_standings(
        self,
        season_id: str,
        division_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch standings from the API.

        Requirement 2.3: Fetch data from /standings endpoint

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            List of standing dictionaries
        """
        params = {
            'season_id': season_id,
            'division_id': division_id
        }

        try:
            response = self._request('GET', '/standings', params=params)
            return response.get('data', [])
        except APIResponseError as e:
            if e.status_code == 404:
                return []
            raise

    def get_teams(
        self,
        season_id: str,
        division_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch teams from the API.

        Requirement 2.4: Fetch data from /teams endpoint

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            List of team dictionaries
        """
        params = {
            'season_id': season_id,
            'division_id': division_id
        }

        try:
            response = self._request('GET', '/teams', params=params)
            return response.get('data', [])
        except APIResponseError as e:
            if e.status_code == 404:
                return []
            raise

    def get_scout_report(
        self,
        team_id: str,
        games_count: int = 5
    ) -> Dict[str, Any]:
        """Fetch scout report from the API.

        Requirement 2.5: Fetch data from /scout endpoint

        Args:
            team_id: Team identifier
            games_count: Number of games to analyze (default: 5)

        Returns:
            Scout report dictionary
        """
        params = {'games_count': games_count}

        try:
            response = self._request('GET', f'/scout/{team_id}', params=params)
            return response.get('data', {})
        except APIResponseError as e:
            if e.status_code == 404:
                return {}
            raise

    def get_seasons(self) -> List[Dict[str, Any]]:
        """Fetch available seasons from the API.

        Requirement 8.1: Fetch data from /seasons endpoint

        Returns:
            List of season dictionaries with 'id' and 'name' keys
        """
        response = self._request('GET', '/seasons')
        return response.get('data', [])

    def get_divisions(self, season_id: str) -> List[Dict[str, Any]]:
        """Fetch divisions for a season from the API.

        Requirement 8.2: Fetch data from /divisions endpoint

        Args:
            season_id: Season identifier

        Returns:
            List of division dictionaries with 'id' and 'name' keys
        """
        params = {'season_id': season_id}
        try:
            response = self._request('GET', '/divisions', params=params)
            return response.get('data', [])
        except APIResponseError as e:
            if e.status_code == 404:
                return []
            raise

    def get_locations(self) -> List[Dict[str, Any]]:
        """Fetch all locations/rinks from the API.

        Requirement 8.11: Fetch data from /locations endpoint

        Returns:
            List of location dictionaries with 'id', 'name', 'address' keys
        """
        response = self._request('GET', '/locations')
        return response.get('data', [])

    def get_team_by_id(self, team_id: str) -> Dict[str, Any]:
        """Fetch team details by ID from the API.

        Args:
            team_id: Team identifier

        Returns:
            Team detail dictionary
        """
        response = self._request('GET', f'/teams/{team_id}')
        return response.get('data', {})

    def get_game_by_id(self, game_id: str) -> Dict[str, Any]:
        """Fetch game details by ID from the API.

        Args:
            game_id: Game identifier

        Returns:
            Game detail dictionary
        """
        response = self._request('GET', f'/games/{game_id}')
        return response.get('data', {})

    def health_check(self) -> Dict[str, Any]:
        """Check API health status.

        Returns:
            Health status dictionary with 'status', 'service', 'timestamp' keys
        """
        return self._request('GET', '/health')


__all__ = [
    'APIClient',
    'APIError',
    'APIConnectionError',
    'APITimeoutError',
    'APIResponseError',
    'DEFAULT_API_URL',
    'DEFAULT_API_TIMEOUT',
]

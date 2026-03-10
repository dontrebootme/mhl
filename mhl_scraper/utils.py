"""
Utility functions for MHL scraper.
"""
import os
import re
import time
import html
import logging
import threading
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from functools import lru_cache

from .config import ScraperConfig


# Configure module logger
logger = logging.getLogger(__name__)


# Compiled Regex Patterns
RE_API_KEY = re.compile(r'^[a-fA-F0-9]{20,40}$')
RE_ACCESS_CODE = re.compile(r'^[a-fA-F0-9]{40}$')
RE_GAME_ID_EXTENDED = re.compile(r'/Leagues/event/\d+/(\d+)')
RE_GAME_ID_SIMPLE = re.compile(r'/Leagues/event/(\d+)')
RE_TEAM_SCORE = re.compile(r'^(.+?)\s*\((\d+)\)$')
RE_SCORE_ONLY = re.compile(r'\((\d+)\)')
RE_HTML_TAGS = re.compile(r'<[^>]+>')
RE_RECORD_FORMAT = re.compile(r'^\d+-\d+-\d+$')
RE_PARENTHETICAL_SUFFIX = re.compile(r'\s*\([^)]*\)\s*$')
RE_SPECIAL_CHARS = re.compile(r'[^\w\s-]')
RE_WHITESPACE = re.compile(r'\s+')
RE_TEAM_LINK = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']*/leagues/team/[^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


class CredentialError(ValueError):
    """Exception raised for credential-related errors."""
    pass


class CredentialValidationError(CredentialError):
    """Exception raised when credentials fail validation."""
    pass


class CredentialMissingError(CredentialError):
    """Exception raised when required credentials are missing."""
    pass


class GamesheetDownloadError(Exception):
    """Exception raised when gamesheet download fails."""

    def __init__(self, message: str, game_id: str = None,
                 status_code: int = None, is_retryable: bool = False):
        super().__init__(message)
        self.game_id = game_id
        self.status_code = status_code
        self.is_retryable = is_retryable


class GamesheetUnavailableError(GamesheetDownloadError):
    """Exception raised when a gamesheet is not available (not an error condition)."""

    def __init__(self, message: str, game_id: str = None):
        super().__init__(message, game_id=game_id, is_retryable=False)


class AuthenticationError(GamesheetDownloadError):
    """Exception raised when API authentication fails."""

    def __init__(self, message: str, game_id: str = None, status_code: int = None):
        super().__init__(message, game_id=game_id, status_code=status_code, is_retryable=False)


# Transient HTTP status codes that warrant retry
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_BACKOFF = 2.0  # exponential backoff multiplier

# Global session for connection pooling
_session = requests.Session()


def _is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient error that should be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the error is transient and should be retried
    """
    if isinstance(exception, requests.exceptions.Timeout):
        return True
    if isinstance(exception, requests.exceptions.ConnectionError):
        return True
    if isinstance(exception, requests.exceptions.HTTPError):
        response = getattr(exception, 'response', None)
        if response is not None and response.status_code in RETRYABLE_STATUS_CODES:
            return True
    return False


def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    context: str = "request",
    **kwargs
) -> requests.Response:
    """
    Make an HTTP request with automatic retry for transient errors.

    Args:
        method: HTTP method ('GET' or 'POST')
        url: URL to request
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        retry_backoff: Multiplier for exponential backoff
        context: Description of the request for logging
        **kwargs: Additional arguments passed to requests.request()

    Returns:
        Response object if successful

    Raises:
        requests.RequestException: If all retries fail
    """
    last_exception = None
    current_delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            response = _session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.RequestException as e:
            last_exception = e
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)

            if attempt < max_retries and _is_retryable_error(e):
                logger.warning(
                    f"{context}: Attempt {attempt + 1}/{max_retries + 1} failed "
                    f"(status={status_code}): {e}. Retrying in {current_delay:.1f}s..."
                )
                time.sleep(current_delay)
                current_delay *= retry_backoff
            else:
                # Log final failure
                if attempt > 0:
                    logger.error(
                        f"{context}: All {attempt + 1} attempts failed. "
                        f"Last error (status={status_code}): {e}"
                    )
                raise

    # Should not reach here, but just in case
    raise last_exception


def _format_http_error(
    error: requests.RequestException,
    context: str,
    game_id: str = None
) -> str:
    """
    Format an HTTP error into a user-friendly message with context.

    Args:
        error: The requests exception
        context: Description of what operation failed
        game_id: Optional game ID for context

    Returns:
        Formatted error message
    """
    response = getattr(error, 'response', None)
    status_code = getattr(response, 'status_code', None) if response else None

    game_context = f" for game {game_id}" if game_id else ""

    if isinstance(error, requests.exceptions.Timeout):
        return f"{context}{game_context}: Request timed out. The server may be slow or unavailable."

    if isinstance(error, requests.exceptions.ConnectionError):
        return f"{context}{game_context}: Connection failed. Check your network connection."

    if status_code == 401:
        return (
            f"{context}{game_context}: Authentication failed (HTTP 401). "
            "Your API credentials may be invalid or expired. "
            "Try refreshing your credentials from the TeamLinkt app."
        )

    if status_code == 403:
        return (
            f"{context}{game_context}: Access denied (HTTP 403). "
            "You may not have permission to access this gamesheet."
        )

    if status_code == 404:
        return f"{context}{game_context}: Resource not found (HTTP 404). The gamesheet may not exist."

    if status_code in RETRYABLE_STATUS_CODES:
        return (
            f"{context}{game_context}: Server error (HTTP {status_code}). "
            "This is a temporary issue. Please try again later."
        )

    if status_code:
        return f"{context}{game_context}: HTTP error {status_code}: {error}"

    return f"{context}{game_context}: {error}"


def validate_api_key(api_key: str) -> bool:
    """
    Validate the format of a TeamLinkt API key.

    API keys are hexadecimal strings, typically 29-32 characters.

    Args:
        api_key: The API key to validate

    Returns:
        True if the API key format is valid

    Raises:
        CredentialValidationError: If the API key format is invalid
    """
    if not api_key:
        raise CredentialValidationError("API key cannot be empty")

    # API keys should be hex strings, typically 29-32 characters
    # We accept a range since actual keys have been observed at different lengths
    if not RE_API_KEY.match(api_key):
        raise CredentialValidationError(
            f"Invalid API key format. Expected 20-40 character hexadecimal string, "
            f"got {len(api_key)} characters. "
            f"Check that you copied the full api_key from the Authorization header."
        )

    return True


def validate_access_code(access_code: str) -> bool:
    """
    Validate the format of a TeamLinkt access code.

    Access codes are expected to be 40-character hexadecimal strings (session tokens).

    Args:
        access_code: The access code to validate

    Returns:
        True if the access code format is valid

    Raises:
        CredentialValidationError: If the access code format is invalid
    """
    if not access_code:
        raise CredentialValidationError("Access code cannot be empty")

    # Access codes should be 40-character hex strings
    if not RE_ACCESS_CODE.match(access_code):
        raise CredentialValidationError(
            f"Invalid access code format. Expected 40-character hexadecimal string, "
            f"got {len(access_code)} characters. "
            f"Check that you copied the full access_code from the API request."
        )

    return True


def load_credentials(
    api_key: Optional[str] = None,
    access_code: Optional[str] = None,
    user_id: Optional[str] = None,
    validate: bool = True
) -> Dict[str, Optional[str]]:
    """
    Load TeamLinkt API credentials with proper precedence and validation.

    Credential loading precedence (highest to lowest):
    1. Function parameters (if provided)
    2. Environment variables (TEAMLINKT_API_KEY, TEAMLINKT_ACCESS_CODE, TEAMLINKT_USER_ID)
    3. Config file (config.toml)

    Args:
        api_key: Optional API key (overrides env/config)
        access_code: Optional access code (overrides env/config)
        user_id: Optional user ID (overrides env/config)
        validate: Whether to validate credential formats (default: True)

    Returns:
        Dictionary with 'api_key', 'access_code', and 'user_id' keys

    Raises:
        CredentialMissingError: If required credentials (api_key, access_code) are missing
        CredentialValidationError: If credentials fail format validation

    Example:
        >>> creds = load_credentials()
        >>> print(creds['api_key'])
    """
    from .config import UserConfig

    result = {
        'api_key': None,
        'access_code': None,
        'user_id': None,
        'source': {
            'api_key': None,
            'access_code': None,
            'user_id': None
        }
    }

    # Load API key with precedence: param > env > config
    if api_key:
        result['api_key'] = api_key
        result['source']['api_key'] = 'parameter'
    else:
        env_api_key = os.getenv('TEAMLINKT_API_KEY')
        if env_api_key:
            result['api_key'] = env_api_key
            result['source']['api_key'] = 'environment'
        else:
            try:
                config = UserConfig()
                config_api_key = config.get_teamlinkt_api_key()
                if config_api_key:
                    result['api_key'] = config_api_key
                    result['source']['api_key'] = 'config'
            except Exception:
                pass

    # Load access code with precedence: param > env > config
    if access_code:
        result['access_code'] = access_code
        result['source']['access_code'] = 'parameter'
    else:
        env_access_code = os.getenv('TEAMLINKT_ACCESS_CODE')
        if env_access_code:
            result['access_code'] = env_access_code
            result['source']['access_code'] = 'environment'
        else:
            try:
                config = UserConfig()
                config_access_code = config.get_teamlinkt_access_code()
                if config_access_code:
                    result['access_code'] = config_access_code
                    result['source']['access_code'] = 'config'
            except Exception:
                pass

    # Load user ID with precedence: param > env > config (optional)
    if user_id:
        result['user_id'] = user_id
        result['source']['user_id'] = 'parameter'
    else:
        env_user_id = os.getenv('TEAMLINKT_USER_ID')
        if env_user_id:
            result['user_id'] = env_user_id
            result['source']['user_id'] = 'environment'
        else:
            try:
                config = UserConfig()
                config_user_id = config.get_teamlinkt_user_id()
                if config_user_id:
                    result['user_id'] = config_user_id
                    result['source']['user_id'] = 'config'
            except Exception:
                pass

    # Check for missing required credentials
    missing = []
    if not result['api_key']:
        missing.append('api_key')
    if not result['access_code']:
        missing.append('access_code')

    if missing:
        raise CredentialMissingError(
            _format_missing_credentials_error(missing)
        )

    # Validate credential formats if requested
    if validate:
        try:
            validate_api_key(result['api_key'])
        except CredentialValidationError as e:
            source = result['source']['api_key']
            raise CredentialValidationError(
                f"API key from {source} is invalid: {e}"
            )

        try:
            validate_access_code(result['access_code'])
        except CredentialValidationError as e:
            source = result['source']['access_code']
            raise CredentialValidationError(
                f"Access code from {source} is invalid: {e}"
            )

    return result


def _format_missing_credentials_error(missing: List[str]) -> str:
    """
    Format a helpful error message for missing credentials.

    Args:
        missing: List of missing credential names

    Returns:
        Formatted error message with troubleshooting steps
    """
    missing_str = ', '.join(missing)

    return f"""Missing required credentials: {missing_str}

TeamLinkt API credentials are required for gamesheet downloads.

To configure credentials, use one of these methods:

1. Environment variables (recommended for security):
   export TEAMLINKT_API_KEY="your_32_char_hex_api_key"
   export TEAMLINKT_ACCESS_CODE="your_40_char_hex_access_code"

2. Config file (config.toml):
   teamlinkt_api_key = "your_32_char_hex_api_key"
   teamlinkt_access_code = "your_40_char_hex_access_code"

To obtain credentials:
1. Install Charles Proxy (https://www.charlesproxy.com/)
2. Configure SSL proxying for app.teamlinkt.com
3. Open the TeamLinkt mobile app and navigate to a game
4. In Charles, find the getEventDetails request
5. Copy the 'api_key' from the Authorization header (32 hex chars)
6. Copy the 'access_code' from the request body (40 hex chars)

See GAMESHEET_API.md for detailed instructions."""


@lru_cache(maxsize=128)
def _fetch_filters_page(season_id: Optional[str] = None) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Fetch and parse the scores page to extract both seasons and divisions.
    This is cached to avoid redundant HTTP requests.

    Args:
        season_id: Optional season ID to load divisions for a specific season

    Returns:
        Tuple of (seasons_list, divisions_list)
    """
    url = "https://leagues.teamlinkt.com/metropolitanhockeyleague/Scores"

    # Add season_id as query parameter if provided
    if season_id:
        url = f"{url}?season_id={season_id}"

    try:
        response = _session.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract seasons from select#season_id
        seasons = []
        season_select = soup.find('select', {'id': 'season_id'})
        if season_select:
            for option in season_select.find_all('option'):
                season_id_val = option.get('value')
                season_name = option.get_text(strip=True)
                if season_id_val and season_name:
                    seasons.append({
                        'id': season_id_val,
                        'name': season_name
                    })

        # Extract divisions from select#hierarchy_filter
        divisions = []
        division_select = soup.find('select', {'id': 'hierarchy_filter'})
        if division_select:
            for option in division_select.find_all('option'):
                division_id = option.get('value')
                division_name = option.get_text(strip=True)
                # Skip the "All Divisions" option (empty value)
                if division_id and division_name and division_name != "All Divisions":
                    divisions.append({
                        'id': division_id,
                        'name': division_name
                    })

        return (seasons, divisions)

    except requests.RequestException as e:
        print(f"Error fetching filters page: {e}")
        return ([], [])
    except Exception as e:
        print(f"Error parsing filters page: {e}")
        return ([], [])


@lru_cache(maxsize=128)
def _fetch_location_map(season_id: Optional[str] = None) -> Dict[str, str]:
    """
    Fetch the schedule page to extract the location filter dropdown,
    which provides a mapping of Location Name -> Upstream ID.

    Args:
        season_id: Optional season ID to filter by

    Returns:
        Dictionary mapping location names to their upstream IDs.
    """
    url = "https://leagues.teamlinkt.com/metropolitanhockeyleague/Schedule"
    
    if season_id:
        url = f"{url}?season_id={season_id}"
        
    try:
        response = _session.get(url, timeout=10)
        # Don't raise for status here as this is an enhancement; 
        # format might change and we don't want to break the whole scraper if schedule fails
        if response.status_code != 200:
            return {}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        location_map = {}
        # Find the location filter dropdown
        location_select = soup.find('select', {'id': 'filter_location_id'})
        
        if location_select:
            for option in location_select.find_all('option'):
                loc_id = option.get('value')
                loc_name = option.get_text(strip=True)
                
                # Check for valid ID and Name (skip "All Locations" placeholders)
                if loc_id and loc_name and loc_id.isdigit():
                    location_map[loc_name] = loc_id
                    
        return location_map
        
    except Exception as e:
        logger.warning(f"Failed to fetch location map: {e}")
        return {}


def get_seasons() -> List[Dict[str, str]]:
    """
    Get all available seasons from the MHL scores page.
    Uses cached data to minimize HTTP requests.

    Returns:
        List of dictionaries with 'id' and 'name' keys for each season
        Example: [{'id': '45165', 'name': '2025-26 Season'}]
    """
    seasons, _ = _fetch_filters_page()
    return seasons


def get_divisions(season_id: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get all available divisions for a season from the MHL scores page.
    Uses cached data to minimize HTTP requests.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.

    Returns:
        List of dictionaries with 'id' and 'name' keys for each division
        Example: [{'id': '244225', 'name': '18U'}, {'id': '244226', 'name': '18U / Green'}]
    """
    # Try to load season_id from config if not provided
    if season_id is None:
        from .config import UserConfig
        user_config = UserConfig()
        season_id = user_config.get_season_id()

    # Use cached function to fetch both seasons and divisions
    # This reuses the same HTTP request if called multiple times
    _, divisions = _fetch_filters_page(season_id)
    return divisions


@lru_cache(maxsize=128)
def get_divisions_map(season_id: Optional[str] = None) -> Dict[str, str]:
    """
    Get a dictionary mapping division IDs to division names for a season.
    Uses cached data to minimize processing.

    Args:
        season_id: Optional season ID to filter by.

    Returns:
        Dictionary mapping division IDs to names.
    """
    divisions = get_divisions(season_id)
    # Use .get() for safety, though _fetch_filters_page guarantees keys
    return {
        div.get('id'): div.get('name')
        for div in divisions
        if div.get('id') and div.get('name')
    }


def get_full_division_name(
    division_id: str,
    short_name: str,
    season_id: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Resolve a short division name to its full format.

    Uses the cached division list to look up the full division name by ID.
    This ensures consistent division naming between API and direct modes.

    Requirements: 5.1, 5.2

    Args:
        division_id: The division ID to look up
        short_name: The short name to use as fallback (e.g., "10U")
        season_id: Optional season ID for lookup. If None, loads from config.

    Returns:
        Tuple of (full_division_name, was_resolved):
        - full_division_name: Full division name (e.g., "10U / Green") or short_name if not found
        - was_resolved: True if the full name was found, False if falling back to short_name

    Example:
        >>> name, resolved = get_full_division_name("244235", "10U", "45165")
        >>> print(name)  # "10U / Green"
        >>> print(resolved)  # True
    """
    if not division_id:
        return short_name, False

    # Get divisions map from cache
    divisions_map = get_divisions_map(season_id)

    # Look up division by ID
    full_name = divisions_map.get(division_id)

    if full_name:
        return full_name, True

    # Division not found - return short name with warning flag
    return short_name, False


def _fetch_games_from_api(
    season_id: Optional[str] = None,
    division_id: Optional[str] = None,
    team_id: Optional[str] = None,
    game_type: str = 'scores'
) -> List[Dict[str, Any]]:
    """
    Internal function to fetch games from the MHL API.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.
        division_id: Optional division ID to filter by. If None, uses first division from config.toml.
        team_id: Optional team ID to filter by. If None, tries to load from config.toml.
                Use 'all' to explicitly get all teams (no filtering).
        game_type: API type parameter - 'scores' for completed games only, 'schedule' for all games

    Returns:
        List of dictionaries with game information
        Example: [{'game_id': '2925384', 'date': 'Sun Oct 12, 2025', 'time': '1:15 PM - 2:15 PM',
                   'home_team': 'TJHA Firestreaks 16/14UC', 'home_score': '10',
                   'away_team': 'Jr Kraken 14U Girls (White)', 'away_score': '1', 'location': 'Tacoma Twin Rinks'}]
    """
    # Try to load from config if not provided
    if season_id is None or division_id is None or (team_id is None):
        from .config import UserConfig
        user_config = UserConfig()

        if season_id is None:
            season_id = user_config.get_season_id()

        if division_id is None:
            division_ids = user_config.get_division_ids()
            if division_ids:
                division_id = division_ids[0]  # Use first division from config

        # Only load team_id from config if it's None (not 'all')
        if team_id is None:
            team_id = user_config.get_team_id()

    url = f"https://leagues.teamlinkt.com/leagues/getAllEvents/{ScraperConfig.LEAGUE_ID}"

    # DataTables format - form-encoded data
    data = {
        'draw': '1',
        'start': '0',
        'length': '10000',  # Large number to get all results
        'status': 'past',
        'type': game_type,  # 'scores' for completed only, 'schedule' for all games
        'is_league_site': '1',
        'show_team_links': '1',
        'show_games_only': '1',
        'schedule_type': 'regular_season',
        # Minimal column definitions
        'columns[0][data]': '0',
        'columns[1][data]': '1',
        'columns[2][data]': '2',
        'columns[3][data]': '3',
        'columns[4][data]': '4',
        'columns[5][data]': '5',
    }

    if season_id:
        data['season_id'] = season_id
    if division_id:
        data['filters[tier]'] = division_id
        data['prev_filter_id'] = division_id

    if team_id and team_id != 'all':
        # Filter by specific team
        data['filters[team_id]'] = team_id
        data['team_id'] = team_id
        data['prev_team_id'] = 'all'
    else:
        # Show all teams in division
        data['filters[team_id]'] = 'all'
        data['team_id'] = 'all'
        data['prev_team_id'] = 'all'

    # Browser-like headers for the API
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://leagues.teamlinkt.com',
        'Referer': f'https://leagues.teamlinkt.com/metropolitanhockeyleague/Scores',
    }

    try:
        response = _session.post(url, data=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        games = []

        if 'data' in result:
            for game_data in result['data']:
                # Parse HTML from the API response
                # game_data is a dict with keys: '0'=date, '1'=time, '2'=title, '3'=home, '4'=away, '5'=location
                date_cell = game_data.get('0', '')
                time_cell = game_data.get('1', '')
                title_html = game_data.get('2', '')
                home_html = game_data.get('3', '')
                away_html = game_data.get('4', '')
                location_html = game_data.get('5', '')

                # Extract game ID from title HTML
                game_id = None
                if title_html:
                    # Look for /Leagues/event/{league_id}/{game_id}
                    game_id_match = RE_GAME_ID_EXTENDED.search(title_html)
                    if not game_id_match:
                        # Try broader pattern /Leagues/event/{id}
                        game_id_match = RE_GAME_ID_SIMPLE.search(title_html)

                    if game_id_match:
                        game_id = game_id_match.group(1)

                # Extract home team and score
                home_team = ""
                home_score = ""
                if home_html:
                    # Remove tags to get text and decode HTML entities
                    text = html.unescape(RE_HTML_TAGS.sub('', home_html)).strip()

                    # Try to match "Team Name (Score)"
                    score_match = RE_TEAM_SCORE.search(text)
                    if score_match:
                        home_team = score_match.group(1).strip()
                        home_score = score_match.group(2)
                    else:
                        home_team = text

                        # Try to find score in original HTML if not in text (sometimes formatting hides it)
                        score_match_html = RE_SCORE_ONLY.search(home_html)
                        if score_match_html:
                            home_score = score_match_html.group(1)

                # Extract away team and score
                away_team = ""
                away_score = ""
                if away_html:
                    # Remove tags to get text and decode HTML entities
                    text = html.unescape(RE_HTML_TAGS.sub('', away_html)).strip()

                    # Try to match "Team Name (Score)"
                    score_match = RE_TEAM_SCORE.search(text)
                    if score_match:
                        away_team = score_match.group(1).strip()
                        away_score = score_match.group(2)
                    else:
                        away_team = text

                        # Try to find score in original HTML
                        score_match_html = RE_SCORE_ONLY.search(away_html)
                        if score_match_html:
                            away_score = score_match_html.group(1)

                # Extract location
                location = ""
                if location_html:
                    # Remove tags to get text and decode HTML entities
                    location = html.unescape(RE_HTML_TAGS.sub('', location_html)).strip()

                if home_team or away_team:
                    game = {
                        'game_id': game_id,
                        'date': date_cell,
                        'time': time_cell,
                        'home_team': home_team,
                        'home_score': home_score,
                        'away_team': away_team,
                        'away_score': away_score,
                        'location': location
                    }
                    games.append(game)

        return games

    except requests.RequestException as e:
        print(f"Error fetching games: {e}")
        return []
    except Exception as e:
        print(f"Error parsing games: {e}")
        return []


def get_scores(season_id: Optional[str] = None, division_id: Optional[str] = None, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get completed games with scores for a season and/or division from the MHL API.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.
        division_id: Optional division ID to filter by. If None, uses first division from config.toml.
        team_id: Optional team ID to filter by. If None, tries to load from config.toml.
                Use 'all' to explicitly get all teams (no filtering).

    Returns:
        List of dictionaries with completed game information (scores included)
    """
    return _fetch_games_from_api(season_id, division_id, team_id, game_type='scores')


def get_games(season_id: Optional[str] = None, division_id: Optional[str] = None, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all games (both completed and scheduled) for a season and/or division from the MHL API.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.
        division_id: Optional division ID to filter by. If None, uses first division from config.toml.
        team_id: Optional team ID to filter by. If None, tries to load from config.toml.
                Use 'all' to explicitly get all teams (no filtering).

    Returns:
        List of dictionaries with game information (includes future games without scores)
    """
    return _fetch_games_from_api(season_id, division_id, team_id, game_type='schedule')


def get_standings(season_id: Optional[str] = None, division_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get division standings from the MHL API.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.
        division_id: Optional division ID to filter by. If None, uses first division from config.toml.

    Returns:
        List of dictionaries with standings information
        Example: [{'team_name': 'Team Name', 'team_id': 723860, 'games_played': 3, 'total_wins': 3,
                   'total_losses': 0, 'total_ties': 0, 'total_points': 6, 'score_for': 26,
                   'score_against': 6, 'win_percent': '1.000', 'ranking': 1, 'streak_type': 'w',
                   'streak_length': 3, 'last_ten': '3-0-0'}]
    """
    # Try to load from config if not provided
    if season_id is None or division_id is None:
        from .config import UserConfig
        user_config = UserConfig()

        if season_id is None:
            season_id = user_config.get_season_id()

        if division_id is None:
            division_ids = user_config.get_division_ids()
            if division_ids:
                division_id = division_ids[0]  # Use first division from config

    url = f"https://leagues.teamlinkt.com/leagues/getStandings/{ScraperConfig.LEAGUE_ID}/{season_id}"

    # Form-encoded data for standings
    data = {
        'group_ids[tier]': division_id,
        'season_id': season_id,
    }

    # Browser-like headers for the API
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://leagues.teamlinkt.com',
        'Referer': f'https://leagues.teamlinkt.com/metropolitanhockeyleague/Standings',
    }

    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()

        if 'standings' in result:
            standings = result['standings']

            # Parse HTML in team_name field to get clean text
            for team in standings:
                if 'team_name' in team:
                    team_name_html = team['team_name']
                    # Parse HTML to extract clean team name
                    soup = BeautifulSoup(team_name_html, 'html.parser')
                    # Try to find link first, otherwise get text
                    link = soup.find('a')
                    if link:
                        team['team_name'] = link.get_text(strip=True)
                    else:
                        team['team_name'] = soup.get_text(strip=True)

            return standings
        else:
            return []

    except requests.RequestException as e:
        print(f"Error fetching standings: {e}")
        return []
    except Exception as e:
        print(f"Error parsing standings: {e}")
        return []


def get_locations(season_id: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get all locations (rinks/arenas) for a season from the MHL website.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.

    Returns:
        List of dictionaries with location information
        Example: [{'name': 'Sno-King Snoqualmie - Rink A', 'address': '35323 SE Douglas St, Snoqualmie, WA, US',
                   'map_url': 'https://maps.google.com/maps?q=47.5246200,-121.8689150'}]
    """
    # Try to load from config if not provided
    if season_id is None:
        from .config import UserConfig
        user_config = UserConfig()
        season_id = user_config.get_season_id()

    url = "https://leagues.teamlinkt.com/metropolitanhockeyleague/Locations"

    # Add season_id as query parameter if provided
    if season_id:
        url = f"{url}?season_id={season_id}"

    # Fetch location map from Schedule page to get upstream IDs
    location_map = _fetch_location_map(season_id)

    try:
        response = _session.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        locations = []

        # Find the table with location data
        table = soup.find('table')
        if table:
            # Find all table rows (skip header row)
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        name = cells[0].get_text(strip=True)
                        address = cells[1].get_text(strip=True)

                        # Extract map URL from the View link
                        map_url = ""
                        map_link = cells[2].find('a')
                        if map_link:
                            map_url = map_link.get('href', '')

                        if name and address:
                            # Try to find upstream ID from the map
                            location_id = location_map.get(name)
                            
                            if not location_id:
                                # Fallback to deterministic ID if upstream ID not found
                                # This ensures the API doesn't crash even if the map is incomplete
                                import hashlib
                                location_id = hashlib.md5(name.encode()).hexdigest()
                                logger.warning(f"Upstream ID not found for location '{name}'. Generated fallback ID: {location_id}")
                            
                            locations.append({
                                'id': location_id,
                                'name': name,
                                'address': address,
                                'map_url': map_url
                            })

        return locations

    except requests.RequestException as e:
        print(f"Error fetching locations: {e}")
        return []
    except Exception as e:
        print(f"Error parsing locations: {e}")
        return []


def get_game_details(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a specific game.

    Args:
        game_id: The game ID to fetch details for

    Returns:
        Dictionary with game details or None if not found
        Example: {
            'game_id': '2951440',
            'home_team': 'Sno-King Jr. Thunderbirds 10U C (O\'Connor)',
            'home_score': '12',
            'home_record': '5-0-0',
            'away_team': 'Jr Kraken 10U (Maroon)',
            'away_score': '2',
            'away_record': '1-2-0',
            'date': 'Oct 25 2025',
            'time': '9:15 am - 10:15 am',
            'location': 'Sno-King Snoqualmie - Rink A',
            'division': '10U / Green',
            'status': 'Final',
            'recap_title': 'Thunderbirds Dominate, Defeat Jr. Kraken',
            'recap_text': 'In a dominant performance...'
        }
    """
    url = f"https://leagues.teamlinkt.com/Leagues/event/{ScraperConfig.LEAGUE_ID}/{game_id}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract game details from the page structure
        game_details = {'game_id': game_id}

        # Find all h4 headings (team names)
        h4_headings = soup.find_all('h4')
        if len(h4_headings) >= 2:
            # First h4 is away team, second is home team
            away_team_elem = h4_headings[0]
            home_team_elem = h4_headings[1] if len(h4_headings) > 1 else None

            if away_team_elem:
                game_details['away_team'] = away_team_elem.get_text(strip=True)
            if home_team_elem:
                game_details['home_team'] = home_team_elem.get_text(strip=True)

        # Find all h2 headings (scores)
        h2_headings = soup.find_all('h2')
        if len(h2_headings) >= 2:
            game_details['away_score'] = h2_headings[0].get_text(strip=True)
            game_details['home_score'] = h2_headings[1].get_text(strip=True)

        # Find all h6 headings (records, division, date, time, location, status)
        h6_headings = soup.find_all('h6')
        h6_texts = [h.get_text(strip=True) for h in h6_headings]

        # Look for specific patterns
        for text in h6_texts:
            # Records are in format "5-0-0"
            if RE_RECORD_FORMAT.match(text):
                if 'away_record' not in game_details:
                    game_details['away_record'] = text
                elif 'home_record' not in game_details:
                    game_details['home_record'] = text

            # Division contains "U" (e.g., "10U / Green")
            elif 'U' in text and '/' in text:
                game_details['division'] = text

            # Date contains month names
            elif any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                game_details['date'] = text

            # Time contains "am" or "pm"
            elif 'am' in text.lower() or 'pm' in text.lower():
                game_details['time'] = text

        # Find location - it's an h6 that doesn't match other patterns
        # Look for h6 that isn't a record, division, date, time, status, or banner
        for h6 in h6_headings:
            text = h6.get_text(strip=True)

            # Skip known patterns
            if RE_RECORD_FORMAT.match(text):  # Record like "5-0-0"
                continue
            if text in ['Metropolitan Hockey League', 'Final', 'In Progress', 'Scheduled']:  # Banner or status
                continue
            if text == game_details.get('division'):  # Division
                continue
            if text == game_details.get('date'):  # Date
                continue
            if text == game_details.get('time'):  # Time
                continue
            if 'U' in text and '/' in text:  # Division pattern
                continue
            if any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):  # Date
                continue
            if 'am' in text.lower() or 'pm' in text.lower():  # Time
                continue

            # This should be the location
            if 'location' not in game_details:
                game_details['location'] = text
                break

        # Find status (Final, In Progress, etc.)
        for h4 in soup.find_all('h4'):
            text = h4.get_text(strip=True)
            if text in ['Final', 'In Progress', 'Scheduled']:
                game_details['status'] = text

        # Find recap title and text
        # The recap title is an h4 after the navigation
        recap_h4s = [h for h in soup.find_all('h4') if h.get_text(strip=True) not in
                    [game_details.get('away_team'), game_details.get('home_team'),
                     game_details.get('status', '')]]

        if recap_h4s:
            game_details['recap_title'] = recap_h4s[0].get_text(strip=True)

            # The recap text usually follows the title
            # Look for the next substantial text element after the title
            next_elem = recap_h4s[0].find_next_sibling()
            while next_elem:
                text = next_elem.get_text(strip=True)
                # Check if it's actual recap text (not HTML/CSS, not too short)
                if (len(text) > 100 and
                    not text.startswith('<') and
                    not text.startswith('http') and
                    'font' not in text.lower() and
                    'stylesheet' not in text.lower()):
                    game_details['recap_text'] = text
                    break
                next_elem = next_elem.find_next_sibling()

        return game_details if game_details.get('home_team') else None

    except requests.RequestException as e:
        print(f"Error fetching game details: {e}")
        return None
    except Exception as e:
        print(f"Error parsing game details: {e}")
        return None


def get_gamesheet_url(
    game_id: str,
    api_key: Optional[str] = None,
    access_code: Optional[str] = None,
    user_id: Optional[str] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY
) -> Optional[str]:
    """
    Get the gamesheet PDF URL for a specific game from the TeamLinkt API.

    WARNING: This function is EXPERIMENTAL and requires authentication.
    See GAMESHEET_API.md for current research status.

    Args:
        game_id: The game/event ID (e.g., "2951440")
        api_key: TeamLinkt API key (optional - will load from env/config if not provided)
        access_code: Session access code (optional - will load from env/config if not provided)
        user_id: User ID (optional - may be redundant)
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Initial delay between retries in seconds

    Returns:
        URL to the gamesheet PDF if found, None otherwise
        Example: "https://cdn-app.teamlinkt.com/media/association_data/31917/gamesheets/2951440/gamesheet_1761412860.pdf"

    Raises:
        CredentialMissingError: If required credentials are not found
        CredentialValidationError: If credentials fail format validation
        AuthenticationError: If API authentication fails (HTTP 401/403)
        GamesheetDownloadError: If a non-retryable error occurs

    Note:
        Credential loading precedence (highest to lowest):
        1. Function parameters (if provided)
        2. Environment variables (TEAMLINKT_API_KEY, TEAMLINKT_ACCESS_CODE, TEAMLINKT_USER_ID)
        3. Config file (config.toml)
    """
    logger.debug(f"Getting gamesheet URL for game {game_id}")

    # Use centralized credential loading with validation
    credentials = load_credentials(
        api_key=api_key,
        access_code=access_code,
        user_id=user_id,
        validate=True
    )

    api_key = credentials['api_key']
    access_code = credentials['access_code']
    user_id = credentials['user_id']

    url = "https://app.teamlinkt.com/event_details_api/getEventDetails"

    # Build request data - api_key and access_code are required
    data = {
        'association_event_id': game_id,
        'api_key': api_key,
        'access_code': access_code,
    }

    # Add optional user_id if provided (may be redundant with access_code)
    if user_id:
        data['user_id'] = user_id

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': api_key,
    }

    try:
        response = _request_with_retry(
            method='POST',
            url=url,
            data=data,
            headers=headers,
            timeout=10,
            max_retries=max_retries,
            retry_delay=retry_delay,
            context=f"Fetching gamesheet URL for game {game_id}"
        )

        result = response.json()

        # Check API response code
        response_code = result.get('code')
        response_message = result.get('message', 'Unknown error')

        # Handle authentication errors from API response
        # Code 401 = unauthorized, Code 440 = session expired
        if response_code in ('401', 401, '440', 440):
            status_code = int(response_code) if isinstance(response_code, str) else response_code
            error_msg = (
                f"API authentication failed for game {game_id}: {response_message}. "
                "Your credentials may be invalid or expired. "
                "Try refreshing your credentials from the TeamLinkt app."
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg, game_id=game_id, status_code=status_code)

        # Navigate through the response structure to find gamesheet URL
        if response_code == '200' or response_code == 200:
            payload = result.get('payload', {})

            # Try TeamEventDetails first (preferred - has PDF gamesheets)
            team_details = payload.get('TeamEventDetails', {})
            if team_details:
                calendar_event = team_details.get('CalendarEvent', {})
                gamesheet_url = calendar_event.get('play_by_play_gamesheet_url', '')
                if gamesheet_url:
                    logger.debug(f"Found gamesheet URL for game {game_id}: {gamesheet_url}")
                    return gamesheet_url

            # Fallback to AssociationEventDetails (may have JPG gamesheets)
            assoc_details = payload.get('AssociationEventDetails', {})
            if assoc_details:
                assoc_event = assoc_details.get('AssociationEvent', {})
                gamesheet_url = assoc_event.get('gamesheet_url', '')
                if gamesheet_url:
                    logger.debug(f"Found gamesheet URL for game {game_id}: {gamesheet_url}")
                    return gamesheet_url

            # No gamesheet URL found - this is not an error, just unavailable
            logger.info(f"No gamesheet available for game {game_id}")
            return None
        else:
            logger.warning(
                f"API returned unexpected code for game {game_id}: "
                f"code={response_code}, message={response_message}"
            )
            return None

    except (AuthenticationError, CredentialError):
        # Re-raise credential and auth errors without wrapping
        raise

    except requests.exceptions.HTTPError as e:
        response = getattr(e, 'response', None)
        status_code = getattr(response, 'status_code', None) if response else None

        # Handle HTTP-level authentication errors
        if status_code in (401, 403):
            error_msg = _format_http_error(e, "Fetching gamesheet URL", game_id)
            logger.error(error_msg)
            raise AuthenticationError(error_msg, game_id=game_id, status_code=status_code)

        # Other HTTP errors
        error_msg = _format_http_error(e, "Fetching gamesheet URL", game_id)
        logger.error(error_msg)
        raise GamesheetDownloadError(
            error_msg,
            game_id=game_id,
            status_code=status_code,
            is_retryable=status_code in RETRYABLE_STATUS_CODES
        )

    except requests.RequestException as e:
        error_msg = _format_http_error(e, "Fetching gamesheet URL", game_id)
        logger.error(error_msg)
        raise GamesheetDownloadError(
            error_msg,
            game_id=game_id,
            is_retryable=_is_retryable_error(e)
        )

    except ValueError as e:
        # JSON parsing error
        error_msg = f"Failed to parse API response for game {game_id}: {e}"
        logger.error(error_msg)
        raise GamesheetDownloadError(error_msg, game_id=game_id)


def download_gamesheet(
    game_id: str,
    output_path: str,
    api_key: Optional[str] = None,
    access_code: Optional[str] = None,
    user_id: Optional[str] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY
) -> bool:
    """
    Download the gamesheet PDF for a specific game.

    Args:
        game_id: The game/event ID
        output_path: Where to save the PDF file
        api_key: TeamLinkt API key (optional)
        access_code: User session access code (optional)
        user_id: User ID (optional)
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Initial delay between retries in seconds

    Returns:
        True if download successful, False otherwise

    Note:
        This function returns False (not raises) for unavailable gamesheets
        to allow bulk operations to continue. Credential errors are still raised.
    """
    logger.debug(f"Downloading gamesheet for game {game_id} to {output_path}")

    try:
        # First get the gamesheet URL (may raise credential/auth errors)
        gamesheet_url = get_gamesheet_url(
            game_id,
            api_key,
            access_code,
            user_id,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        if not gamesheet_url:
            logger.info(f"No gamesheet available for game {game_id}")
            return False

        # Download the PDF with retry logic
        response = _request_with_retry(
            method='GET',
            url=gamesheet_url,
            timeout=30,
            max_retries=max_retries,
            retry_delay=retry_delay,
            context=f"Downloading gamesheet PDF for game {game_id}"
        )

        # Save to file
        with open(output_path, 'wb') as f:
            f.write(response.content)

        logger.info(f"Gamesheet downloaded to: {output_path}")
        return True

    except (CredentialError, AuthenticationError):
        # Re-raise credential and auth errors - these should stop processing
        raise

    except GamesheetDownloadError as e:
        # Log and return False for download errors (allows bulk to continue)
        logger.error(f"Failed to download gamesheet for game {game_id}: {e}")
        return False

    except requests.RequestException as e:
        error_msg = _format_http_error(e, "Downloading gamesheet PDF", game_id)
        logger.error(error_msg)
        return False

    except IOError as e:
        logger.error(f"Failed to save gamesheet for game {game_id} to {output_path}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error downloading gamesheet for game {game_id}: {e}")
        return False


def generate_gamesheet_filename(game_metadata: Dict[str, Any]) -> str:
    """
    Generate a descriptive filename for a gamesheet PDF.

    Args:
        game_metadata: Dictionary containing game information with keys:
            - game_id: The game ID
            - date: Game date string (e.g., "Sun Oct 20, 2025")
            - home_team: Home team name
            - away_team: Away team name
            - location: Game location/rink name

    Returns:
        A sanitized filename string like "2025-10-20_Team_A_vs_Team_B_Arena.pdf"
    """
    from dateutil import parser as date_parser

    game_id = game_metadata.get('game_id', 'unknown')
    date_str = game_metadata.get('date', '')
    home_team = game_metadata.get('home_team', 'Home')
    away_team = game_metadata.get('away_team', 'Away')
    location = game_metadata.get('location', '')

    # Parse and format date
    try:
        parsed_date = date_parser.parse(date_str)
        formatted_date = parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        formatted_date = 'unknown-date'

    # Sanitize team names and location for filename
    def sanitize(text: str) -> str:
        """Remove special characters and limit length."""
        # Remove parenthetical suffixes like "(O'Connor)" for cleaner names
        text = RE_PARENTHETICAL_SUFFIX.sub('', text)
        # Replace special characters with underscores
        text = RE_SPECIAL_CHARS.sub('', text)
        # Replace whitespace with underscores
        text = RE_WHITESPACE.sub('_', text.strip())
        # Limit length
        return text[:30] if len(text) > 30 else text

    home_clean = sanitize(home_team)
    away_clean = sanitize(away_team)
    location_clean = sanitize(location) if location else ''

    # Build filename: game_id_date_away_at_home_location.pdf
    parts = [game_id, formatted_date, away_clean, 'at', home_clean]
    if location_clean:
        parts.append(location_clean)

    filename = '_'.join(parts) + '.pdf'
    return filename


def download_gamesheets_bulk(
    game_ids: List[str],
    output_dir: str,
    game_metadata: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
    access_code: Optional[str] = None,
    user_id: Optional[str] = None,
    progress_callback: Optional[callable] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY
) -> Dict[str, Any]:
    """
    Download multiple gamesheets with organized naming and duplicate detection.
    Uses concurrent execution for faster bulk downloads.

    Args:
        game_ids: List of game IDs to download
        output_dir: Base directory for downloads (will be created if doesn't exist)
        game_metadata: Optional list of game info dicts for filename generation.
                      Each dict should have: game_id, date, home_team, away_team, location.
                      If not provided, uses simple game_id.pdf naming.
        api_key: TeamLinkt API key (optional, will try env/config)
        access_code: Session access code (optional, will try env/config)
        user_id: User ID (optional)
        progress_callback: Optional callback function(game_id, status, message) for progress
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Initial delay between retries in seconds

    Returns:
        Dictionary with download results:
        {
            'successful': int,
            'failed': int,
            'skipped': int,
            'unavailable': int,
            'downloads': [
                {
                    'game_id': str,
                    'pdf_path': str,
                    'status': 'success' | 'failed' | 'skipped' | 'unavailable',
                    'error': str (if failed)
                },
                ...
            ]
        }
    """
    from pathlib import Path

    logger.info(f"Starting bulk download of {len(game_ids)} gamesheets to {output_dir}")

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Output directory created/verified: {output_path}")

    # Build a lookup dict for game metadata by game_id
    metadata_lookup = {}
    if game_metadata:
        for meta in game_metadata:
            gid = meta.get('game_id')
            if gid:
                metadata_lookup[str(gid)] = meta

    results = {
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'unavailable': 0,
        'downloads': []
    }

    # Thread safety objects
    results_lock = threading.Lock()
    completed_count = 0
    total_games = len(game_ids)

    def process_game(game_id: str) -> None:
        """Process a single game download thread-safely."""
        nonlocal completed_count
        game_id_str = str(game_id)

        # Generate filename
        if game_id_str in metadata_lookup:
            filename = generate_gamesheet_filename(metadata_lookup[game_id_str])
        else:
            filename = f"game_{game_id_str}.pdf"

        pdf_path = output_path / filename

        download_result = {
            'game_id': game_id_str,
            'pdf_path': str(pdf_path),
            'status': 'pending'
        }

        # Check for duplicate (file already exists)
        if pdf_path.exists():
            download_result['status'] = 'skipped'

            with results_lock:
                completed_count += 1
                current_idx = completed_count
                results['skipped'] += 1
                results['downloads'].append(download_result)

                msg = f"[{current_idx}/{total_games}] Skipped {filename} (already exists)"
                logger.debug(msg)
                if progress_callback:
                    progress_callback(game_id_str, 'skipped', msg)
                else:
                    print(msg)

            return

        # Attempt download
        try:
            # Log start (without locking, order doesn't matter much)
            logger.debug(f"Starting download for {filename}")

            # Since we're parallel, we don't print "Downloading..." to console here
            # to avoid interleaved output. The completion message will serve as progress.
            if progress_callback:
                progress_callback(game_id_str, 'downloading', f"Downloading {filename}...")

            success = download_gamesheet(
                game_id=game_id_str,
                output_path=str(pdf_path),
                api_key=api_key,
                access_code=access_code,
                user_id=user_id,
                max_retries=max_retries,
                retry_delay=retry_delay
            )

            with results_lock:
                completed_count += 1
                current_idx = completed_count

                if success:
                    download_result['status'] = 'success'
                    results['successful'] += 1

                    msg = f"[{current_idx}/{total_games}] Downloaded {filename}"
                    logger.info(msg)
                    if progress_callback:
                        progress_callback(game_id_str, 'success', msg)
                else:
                    # Download returned False - gamesheet unavailable (not an error)
                    download_result['status'] = 'unavailable'
                    download_result['error'] = 'Gamesheet not available for this game'
                    results['unavailable'] += 1

                    msg = f"[{current_idx}/{total_games}] Gamesheet unavailable for {game_id_str}"
                    logger.info(msg)
                    if progress_callback:
                        progress_callback(game_id_str, 'unavailable', msg)
                    else:
                        print(msg)

        except (CredentialError, AuthenticationError) as e:
            with results_lock:
                completed_count += 1
                current_idx = completed_count

                # Credential/auth errors - log with full context
                download_result['status'] = 'failed'
                download_result['error'] = str(e)
                results['failed'] += 1

                error_msg = f"[{current_idx}/{total_games}] Authentication error for {filename}: {e}"
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(game_id_str, 'failed', error_msg)
                else:
                    print(error_msg)

        except GamesheetDownloadError as e:
            with results_lock:
                completed_count += 1
                current_idx = completed_count

                # Download errors with context
                download_result['status'] = 'failed'
                download_result['error'] = str(e)
                results['failed'] += 1

                error_msg = f"[{current_idx}/{total_games}] Download error for {filename}: {e}"
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(game_id_str, 'failed', error_msg)
                else:
                    print(error_msg)

        except Exception as e:
            with results_lock:
                completed_count += 1
                current_idx = completed_count

                # Unexpected errors
                download_result['status'] = 'failed'
                download_result['error'] = str(e)
                results['failed'] += 1

                error_msg = f"[{current_idx}/{total_games}] Unexpected error for {filename}: {e}"
                logger.error(error_msg, exc_info=True)
                if progress_callback:
                    progress_callback(game_id_str, 'failed', error_msg)
                else:
                    print(error_msg)

        with results_lock:
            results['downloads'].append(download_result)

    # Use ThreadPoolExecutor for parallel execution
    # Limit max_workers to avoid overwhelming the server or local resources
    # 20 is a reasonable default for network I/O bound tasks
    max_workers = min(20, total_games) if total_games > 0 else 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_game, gid): gid for gid in game_ids}

        # Wait for all tasks to complete
        concurrent.futures.wait(futures)

    # Log and print summary
    summary_msg = (
        f"\nDownload Summary:\n"
        f"  Successful: {results['successful']}\n"
        f"  Unavailable: {results['unavailable']}\n"
        f"  Failed: {results['failed']}\n"
        f"  Skipped: {results['skipped']}\n"
        f"  Total: {total_games}"
    )
    logger.info(summary_msg.replace('\n', ' | '))
    print(summary_msg)

    return results


def get_teams(season_id: Optional[str] = None, division_id: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get all unique teams from a season and/or division.

    Args:
        season_id: Optional season ID to filter by. If None, tries to load from config.toml.
        division_id: Optional division ID to filter by. If None, uses first division from config.toml.

    Returns:
        List of dictionaries with 'id' and 'name' keys for each team
        Example: [{'id': '723731', 'name': 'Sno-King Jr. Thunderbirds 18U C (Rotoli)'}]
    """
    # Try to load from config if not provided
    if season_id is None or division_id is None:
        from .config import UserConfig
        user_config = UserConfig()

        if season_id is None:
            season_id = user_config.get_season_id()

        if division_id is None:
            division_ids = user_config.get_division_ids()
            if division_ids:
                division_id = division_ids[0]  # Use first division from config

    url = f"https://leagues.teamlinkt.com/leagues/getAllEvents/{ScraperConfig.LEAGUE_ID}"

    # DataTables format - form-encoded data
    data = {
        'draw': '1',
        'start': '0',
        'length': '10000',  # Large number to get all results
        'status': 'all',  # Get all games (past and future) to find all teams
        'type': 'schedule',  # Use 'schedule' to get all games and find all teams
        'is_league_site': '1',
        'show_team_links': '1',
        'show_games_only': '1',
        'schedule_type': 'regular_season',
        # DataTables column definitions (required by API)
        'columns[0][data]': '0',
        'columns[0][searchable]': 'true',
        'columns[0][orderable]': 'false',
        'columns[1][data]': '1',
        'columns[1][searchable]': 'true',
        'columns[1][orderable]': 'false',
        'columns[2][data]': '2',
        'columns[2][searchable]': 'true',
        'columns[2][orderable]': 'false',
        'columns[3][data]': '3',
        'columns[3][searchable]': 'true',
        'columns[3][orderable]': 'false',
        'columns[4][data]': '4',
        'columns[4][searchable]': 'true',
        'columns[4][orderable]': 'false',
        'columns[5][data]': '5',
        'columns[5][searchable]': 'true',
        'columns[5][orderable]': 'false',
    }

    if season_id:
        data['season_id'] = season_id
    if division_id:
        data['filters[tier]'] = division_id  # Use 'tier' not 'division'

    # Browser-like headers for the API
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://leagues.teamlinkt.com',
        'Referer': f'https://leagues.teamlinkt.com/metropolitanhockeyleague/Scores',
    }

    try:
        response = _session.post(url, data=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        teams = {}  # Use dict to store unique teams by ID

        if 'data' in result:
            def _extract_team_info(html_content):
                """Helper to extract team ID and name from HTML using regex."""
                if not html_content:
                    return None, None

                # Optimized regex extraction (approx 20x faster than BeautifulSoup)
                match = RE_TEAM_LINK.search(html_content)
                if match:
                    href = match.group(1)
                    team_id = href.split('/')[-1]
                    raw_name = match.group(2)
                    team_name = html.unescape(RE_HTML_TAGS.sub('', raw_name)).strip()
                    if team_id and team_name:
                        return team_id, team_name
                return None, None

            for game_data in result['data']:
                home_html = game_data.get('3', '')
                away_html = game_data.get('4', '')

                # Extract home team ID and name
                team_id, team_name = _extract_team_info(home_html)
                if team_id:
                    teams[team_id] = team_name

                # Extract away team ID and name
                team_id, team_name = _extract_team_info(away_html)
                if team_id:
                    teams[team_id] = team_name

        # Return sorted list of teams by name
        return [
            {'id': team_id, 'name': name}
            for team_id, name in sorted(teams.items(), key=lambda x: x[1])
        ]

    except requests.RequestException as e:
        print(f"Error fetching teams: {e}")
        return []
    except Exception as e:
        print(f"Error parsing teams: {e}")
        return []

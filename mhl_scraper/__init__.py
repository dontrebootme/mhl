"""
MHL Scout - Extract game data from Metropolitan Hockey League website.
"""
from .config import UserConfig
from .api_client import (
    APIClient,
    APIError,
    APIConnectionError,
    APITimeoutError,
    APIResponseError,
    DEFAULT_API_URL,
    DEFAULT_API_TIMEOUT,
)
from .utils import (
    get_seasons,
    get_divisions,
    get_full_division_name,
    get_teams,
    get_games,
    get_scores,
    get_standings,
    get_locations,
    get_game_details,
    get_gamesheet_url,
    download_gamesheet,
    download_gamesheets_bulk,
    generate_gamesheet_filename,
    # Credential management
    load_credentials,
    validate_api_key,
    validate_access_code,
    CredentialError,
    CredentialMissingError,
    CredentialValidationError,
    # Download error handling
    GamesheetDownloadError,
    GamesheetUnavailableError,
    AuthenticationError,
    # Retry configuration
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_RETRY_BACKOFF,
    RETRYABLE_STATUS_CODES,
)

__version__ = '0.1.0'

__all__ = [
    'UserConfig',
    # API Client
    'APIClient',
    'APIError',
    'APIConnectionError',
    'APITimeoutError',
    'APIResponseError',
    'DEFAULT_API_URL',
    'DEFAULT_API_TIMEOUT',
    # Direct TeamLinkt functions
    'get_seasons',
    'get_divisions',
    'get_full_division_name',
    'get_teams',
    'get_games',
    'get_scores',
    'get_standings',
    'get_locations',
    'get_game_details',
    'get_gamesheet_url',
    'download_gamesheet',
    'download_gamesheets_bulk',
    'generate_gamesheet_filename',
    # Credential management
    'load_credentials',
    'validate_api_key',
    'validate_access_code',
    'CredentialError',
    'CredentialMissingError',
    'CredentialValidationError',
    # Download error handling
    'GamesheetDownloadError',
    'GamesheetUnavailableError',
    'AuthenticationError',
    # Retry configuration
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_RETRY_DELAY',
    'DEFAULT_RETRY_BACKOFF',
    'RETRYABLE_STATUS_CODES',
]

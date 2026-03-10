import sys
import logging
import click
from typing import Optional
from pathlib import Path

from mhl_scraper.config import UserConfig
from mhl_scraper.utils import (
    download_gamesheet, get_scores, load_credentials, get_gamesheet_url,
    CredentialMissingError, CredentialValidationError, AuthenticationError,
    GamesheetDownloadError
)
from mhl_scraper.parsers.gamesheet_parser import parse_gamesheet_pdf, save_gamesheet_json, GamesheetSerializationError

logger = logging.getLogger(__name__)

@click.command()
@click.argument('game_id', required=False)
@click.option('--last', '-n', type=int, help='Download gamesheets for last N games')
@click.option('--all', 'download_all', is_flag=True, help='Download gamesheets for all completed games')
@click.option('--output', '-o', help='Output file path for single game (default: gamesheet_<GAME_ID>.pdf)')
@click.option('--output-dir', '-d', default='.', help='Output directory for multiple games (default: current directory)')
@click.option('--team-id', '-t', help='Team ID to filter games (default: from config.toml)')
@click.option('--season-id', '-s', help='Season ID to filter games (default: from config.toml)')
@click.option('--division-id', help='Division ID to filter games (default: from config.toml)')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def gamesheets(game_id: Optional[str], last: Optional[int], download_all: bool,
               output: Optional[str], output_dir: str,
               team_id: Optional[str], season_id: Optional[str],
               division_id: Optional[str], config_path: str):
    """Download gamesheets using config.toml settings.

    Download a single game by ID, or multiple games for your team.

    GAME_ID: Optional - Download specific game by ID

    Requires TeamLinkt API credentials in config.toml or environment variables.
    See GAMESHEET_API.md for setup instructions.

    Examples:
      # Download specific game
      mhl.py gamesheets 2951440

      # Download last 5 games for your team
      mhl.py gamesheets --last 5

      # Download all games to organized directory
      mhl.py gamesheets --all --output-dir ./gamesheets/
    """
    import os
    from datetime import datetime

    user_config = UserConfig(config_path)

    # SINGLE GAME MODE: Download specific game by ID
    if game_id:
        output_file = output or f"gamesheet_{game_id}.pdf"
        click.echo(f"Downloading gamesheet for game {game_id}...")

        try:
            success = download_gamesheet(game_id, output_file)

            if success:
                click.echo()
                click.echo(f"✓ Gamesheet downloaded successfully!")
                click.echo(f"  Saved to: {output_file}")
                click.echo()
            else:
                click.echo("✗ Failed to download gamesheet", err=True)
                click.echo("  The game may not have a published scoresheet yet.", err=True)
                sys.exit(1)

        except ValueError as e:
            click.echo(f"✗ Error: {e}", err=True)
            click.echo()
            click.echo("Ensure your TeamLinkt credentials are configured:", err=True)
            click.echo("  1. Add to config.toml, or", err=True)
            click.echo("  2. Set environment variables TEAMLINKT_API_KEY and TEAMLINKT_ACCESS_CODE", err=True)
            click.echo()
            click.echo("See GAMESHEET_API.md for instructions.", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"✗ Unexpected error: {e}", err=True)
            sys.exit(1)
        return

    # BULK MODE: Download multiple games for team
    # Get filters from config or command line
    actual_season_id = season_id or user_config.get_season_id()
    actual_division_id = division_id or (user_config.get_division_ids()[0] if user_config.get_division_ids() else None)
    actual_team_id = team_id or user_config.get_team_id()

    if not actual_team_id:
        click.echo("✗ No team configured. Please run 'mhl.py config' first or specify --team-id.", err=True)
        sys.exit(1)

    # Display what we're doing
    team_name = user_config.get_team_name() or actual_team_id
    season_name = user_config.get_season_name() or actual_season_id

    if download_all:
        click.echo(f"Fetching all completed games for '{team_name}' in '{season_name}'...")
    elif last:
        click.echo(f"Fetching last {last} completed games for '{team_name}' in '{season_name}'...")
    else:
        click.echo("✗ Please specify GAME_ID, --last N, or --all", err=True)
        click.echo()
        click.echo("Examples:")
        click.echo("  mhl.py gamesheets 2951440        # Download specific game")
        click.echo("  mhl.py gamesheets --last 5       # Download last 5 games")
        click.echo("  mhl.py gamesheets --all          # Download all games")
        sys.exit(1)

    # Fetch completed games with scores
    games = get_scores(actual_season_id, actual_division_id, actual_team_id)

    if not games:
        click.echo("✗ No completed games found", err=True)
        sys.exit(1)

    # Games are returned in reverse chronological order (most recent first)
    # Limit to first N games to get the most recent
    if last and not download_all:
        games = games[:last]  # Get first N games (most recent)

    click.echo(f"Found {len(games)} completed game(s)")
    click.echo()

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Download gamesheets
    successful = 0
    failed = 0
    skipped = 0

    for i, game in enumerate(games, 1):
        game_id = game.get('game_id')
        date_str = game.get('date', 'unknown-date')
        home_team = game.get('home_team', 'Unknown')
        away_team = game.get('away_team', 'Unknown')

        # Parse date to get a clean format
        # Date format is typically "Sat Oct 18, 2024" or "Sat Oct 18"
        try:
            # Try to parse the date - handle various formats
            if ',' in date_str:
                # Format: "Sat Oct 18, 2024"
                date_obj = datetime.strptime(date_str, "%a %b %d, %Y")
            else:
                # Format: "Sat Oct 18" - assume current year
                date_obj = datetime.strptime(date_str + f", {datetime.now().year}", "%a %b %d, %Y")
            date_clean = date_obj.strftime("%Y-%m-%d")
        except:
            # Fallback to sanitized original
            date_clean = date_str.replace(',', '').replace(' ', '-')[:10]

        # Determine opponent
        if team_name in home_team:
            opponent = away_team
            location = 'vs'
        else:
            opponent = home_team
            location = 'at'

        # Sanitize opponent name for filename
        opponent_clean = opponent.replace('/', '-').replace(' ', '_').replace('(', '').replace(')', '')[:30]

        # Create filename: gamesheet_YYYY-MM-DD_vs_Opponent.pdf
        filename = f"gamesheet_{date_clean}_{location}_{opponent_clean}.pdf"
        output_file = output_path / filename

        if not game_id:
            click.echo(f"[{i}/{len(games)}] ⊘ Skipping game on {date_str}: No game ID")
            skipped += 1
            continue

        click.echo(f"[{i}/{len(games)}] Downloading {date_clean} {location} {opponent}...", nl=False)

        try:
            success = download_gamesheet(game_id, str(output_file))

            if success:
                click.echo(f" ✓")
                successful += 1
            else:
                click.echo(f" ✗ (not available)")
                failed += 1

        except ValueError as e:
            click.echo(f" ✗")
            click.echo(f"    Error: {e}", err=True)
            click.echo()
            click.echo("Ensure your TeamLinkt credentials are configured:", err=True)
            click.echo("  1. Add to config.toml, or", err=True)
            click.echo("  2. Set environment variables TEAMLINKT_API_KEY and TEAMLINKT_ACCESS_CODE", err=True)
            click.echo()
            click.echo("See GAMESHEET_API.md for instructions.", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f" ✗ ({str(e)})")
            failed += 1

    # Summary
    click.echo()
    click.echo("=" * 60)
    click.echo(f"Summary:")
    click.echo(f"  ✓ Downloaded:  {successful}")
    click.echo(f"  ✗ Failed:      {failed}")
    if skipped > 0:
        click.echo(f"  ⊘ Skipped:     {skipped}")
    click.echo(f"  Output dir:    {output_path.absolute()}")
    click.echo("=" * 60)
    click.echo()


@click.command()
@click.option('--game-id', help='Test with specific game ID (optional)')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def test_gamesheet_auth(game_id: Optional[str], config_path: str):
    """
    Test TeamLinkt API credentials for gamesheet access.

    Attempts to fetch a gamesheet URL using the configured credentials
    and reports success or failure with troubleshooting guidance.

    This command is useful for verifying your credential setup before
    attempting bulk downloads.

    Examples:
        mhl.py test-gamesheet-auth
        mhl.py test-gamesheet-auth --game-id 2951440
    """
    click.echo("\n🔐 Testing TeamLinkt API Credentials")
    click.echo("=" * 50)

    # Step 1: Try to load credentials
    click.echo("\n1. Loading credentials...")
    logger.info("Loading TeamLinkt API credentials for authentication test")
    try:
        credentials = load_credentials(validate=True)
        api_key = credentials['api_key']
        access_code = credentials['access_code']
        source_info = credentials.get('source', {})

        # Show where credentials were loaded from
        api_key_source = source_info.get('api_key', 'unknown')
        access_code_source = source_info.get('access_code', 'unknown')

        logger.info(f"Credentials loaded: api_key from {api_key_source}, access_code from {access_code_source}")
        click.echo(f"   ✓ API key loaded from: {api_key_source}")
        click.echo(f"   ✓ Access code loaded from: {access_code_source}")

        # Show masked credentials for verification
        masked_api_key = api_key[:4] + '...' + api_key[-4:] if len(api_key) > 8 else '****'
        masked_access_code = access_code[:4] + '...' + access_code[-4:] if len(access_code) > 8 else '****'
        click.echo(f"   ✓ API key: {masked_api_key} ({len(api_key)} chars)")
        click.echo(f"   ✓ Access code: {masked_access_code} ({len(access_code)} chars)")

    except CredentialMissingError as e:
        logger.error(f"Missing credentials: {e}")
        click.echo(f"\n   ✗ Missing credentials", err=True)
        click.echo()
        click.echo("=" * 50, err=True)
        click.echo("CREDENTIALS NOT FOUND", err=True)
        click.echo("=" * 50, err=True)
        click.echo()
        click.echo("TeamLinkt API credentials are required for gamesheet downloads.", err=True)
        click.echo()
        click.echo("To configure credentials, use one of these methods:", err=True)
        click.echo()
        click.echo("1. Environment variables (recommended for security):", err=True)
        click.echo('   export TEAMLINKT_API_KEY="your_32_char_hex_api_key"', err=True)
        click.echo('   export TEAMLINKT_ACCESS_CODE="your_40_char_hex_access_code"', err=True)
        click.echo()
        click.echo("2. Config file (config.toml):", err=True)
        click.echo('   teamlinkt_api_key = "your_32_char_hex_api_key"', err=True)
        click.echo('   teamlinkt_access_code = "your_40_char_hex_access_code"', err=True)
        click.echo()
        click.echo("To obtain credentials:", err=True)
        click.echo("  1. Install Charles Proxy (https://www.charlesproxy.com/)", err=True)
        click.echo("  2. Configure SSL proxying for app.teamlinkt.com", err=True)
        click.echo("  3. Open the TeamLinkt mobile app and navigate to a game", err=True)
        click.echo("  4. In Charles, find the getEventDetails request", err=True)
        click.echo("  5. Copy the 'api_key' from the Authorization header (32 hex chars)", err=True)
        click.echo("  6. Copy the 'access_code' from the request body (40 hex chars)", err=True)
        click.echo()
        click.echo("See GAMESHEET_API.md for detailed instructions.", err=True)
        sys.exit(1)

    except CredentialValidationError as e:
        logger.error(f"Credential validation failed: {e}")
        click.echo(f"\n   ✗ Invalid credential format", err=True)
        click.echo()
        click.echo("=" * 50, err=True)
        click.echo("CREDENTIAL FORMAT ERROR", err=True)
        click.echo("=" * 50, err=True)
        click.echo()
        click.echo(f"Error: {e}", err=True)
        click.echo()
        click.echo("Troubleshooting steps:", err=True)
        click.echo("  1. Verify you copied the complete credential values", err=True)
        click.echo("  2. API key should be exactly 32 hexadecimal characters", err=True)
        click.echo("  3. Access code should be exactly 40 hexadecimal characters", err=True)
        click.echo("  4. Check for extra spaces or line breaks in your config", err=True)
        click.echo()
        click.echo("See GAMESHEET_API.md for detailed instructions.", err=True)
        sys.exit(1)

    # Step 2: Test API connection
    click.echo("\n2. Testing API connection...")
    logger.info(f"Testing API connection with game ID: {game_id or '2951440'}")

    # Use provided game_id or a default test game
    test_game_id = game_id or '2951440'  # Default to a known game ID
    click.echo(f"   Testing with game ID: {test_game_id}")

    try:
        gamesheet_url = get_gamesheet_url(
            game_id=test_game_id,
            api_key=api_key,
            access_code=access_code,
            max_retries=1,  # Don't retry too much for auth test
            retry_delay=0.5
        )

        if gamesheet_url:
            logger.info(f"API connection successful - gamesheet URL retrieved for game {test_game_id}")
            click.echo(f"   ✓ API connection successful!")
            click.echo(f"   ✓ Gamesheet URL retrieved")
            click.echo()
            click.echo("=" * 50)
            click.echo("✓ CREDENTIALS VALID")
            click.echo("=" * 50)
            click.echo()
            click.echo("Your TeamLinkt API credentials are working correctly.")
            click.echo("You can now use the 'gamesheets' command to download gamesheets.")
            click.echo()
            click.echo("Examples:")
            click.echo("  mhl.py gamesheets 2951440           # Download specific game")
            click.echo("  mhl.py gamesheets --last 5          # Download last 5 games")
            click.echo("  mhl.py gamesheets --all             # Download all games")
            click.echo()
            sys.exit(0)
        else:
            # API returned success but no gamesheet URL - credentials work but game has no gamesheet
            logger.info(f"API connection successful - no gamesheet available for game {test_game_id}")
            click.echo(f"   ✓ API connection successful!")
            click.echo(f"   ⚠ No gamesheet available for game {test_game_id}")
            click.echo()
            click.echo("=" * 50)
            click.echo("✓ CREDENTIALS VALID")
            click.echo("=" * 50)
            click.echo()
            click.echo("Your TeamLinkt API credentials are working correctly.")
            click.echo(f"Note: Game {test_game_id} does not have a published gamesheet.")
            click.echo()
            click.echo("You can now use the 'gamesheets' command to download gamesheets.")
            click.echo()
            sys.exit(0)

    except AuthenticationError as e:
        logger.error(f"Authentication failed for game {test_game_id}: {e}")
        click.echo(f"   ✗ Authentication failed", err=True)
        click.echo()
        click.echo("=" * 50, err=True)
        click.echo("AUTHENTICATION FAILED", err=True)
        click.echo("=" * 50, err=True)
        click.echo()
        click.echo(f"Error: {e}", err=True)
        click.echo()
        click.echo("Troubleshooting steps:", err=True)
        click.echo("  1. Your credentials may have expired - TeamLinkt sessions expire", err=True)
        click.echo("  2. Re-capture fresh credentials from the TeamLinkt app", err=True)
        click.echo("  3. Make sure you're using credentials from YOUR account", err=True)
        click.echo("  4. Verify the api_key is from the Authorization header", err=True)
        click.echo("  5. Verify the access_code is from the request body", err=True)
        click.echo()
        click.echo("See GAMESHEET_API.md for detailed instructions.", err=True)
        sys.exit(1)

    except GamesheetDownloadError as e:
        status_code = getattr(e, 'status_code', None)
        logger.error(
            f"API request failed for game {test_game_id}: {e} "
            f"(status_code={status_code}, retryable={e.is_retryable})"
        )
        click.echo(f"   ✗ API request failed", err=True)
        click.echo()
        click.echo("=" * 50, err=True)
        click.echo("API REQUEST FAILED", err=True)
        click.echo("=" * 50, err=True)
        click.echo()
        click.echo(f"Error: {e}", err=True)
        if status_code:
            click.echo(f"HTTP Status Code: {status_code}", err=True)
        click.echo()
        if e.is_retryable:
            click.echo("This appears to be a temporary network issue.", err=True)
            click.echo("Please try again in a few moments.", err=True)
        else:
            click.echo("Troubleshooting steps:", err=True)
            click.echo("  1. Check your internet connection", err=True)
            click.echo("  2. Verify the TeamLinkt service is available", err=True)
            click.echo("  3. Try again with a different game ID using --game-id", err=True)
        click.echo()
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error during credential test: {e}", exc_info=True)
        click.echo(f"   ✗ Unexpected error", err=True)
        click.echo()
        click.echo("=" * 50, err=True)
        click.echo("UNEXPECTED ERROR", err=True)
        click.echo("=" * 50, err=True)
        click.echo()
        click.echo(f"Error: {e}", err=True)
        click.echo()
        click.echo("Please report this issue if it persists.", err=True)
        sys.exit(1)

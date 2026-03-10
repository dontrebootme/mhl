import sys
import click
from typing import Optional

from mhl_scraper.config import UserConfig
from mhl_scraper.utils import (
    get_seasons, get_divisions, get_teams, get_scores, get_games,
    get_standings, get_locations, get_full_division_name
)
from mhl_scraper.api_client import (
    APIClient, APIError, APIConnectionError, APITimeoutError, APIResponseError
)


def _standings_are_empty(standings: list) -> bool:
    """Check if standings data appears to be empty or all zeros.

    This is used to detect when API standings weren't synced properly
    and we should fall back to direct mode.

    Args:
        standings: List of standing dictionaries from API

    Returns:
        True if standings appear empty (all zeros), False otherwise
    """
    if not standings:
        return True

    # Check if all teams have zero values for key stats
    # If every team has 0 wins, 0 losses, 0 points, etc., data wasn't synced
    for team in standings:
        # Check both TeamLinkt field names and normalized names
        wins = team.get('total_wins', team.get('wins', 0))
        losses = team.get('total_losses', team.get('losses', 0))
        points = team.get('total_points', team.get('points', 0))
        games_played = team.get('games_played', 0)

        # If any team has non-zero stats, data is valid
        if wins > 0 or losses > 0 or points > 0 or games_played > 0:
            return False

    # All teams have zeros - data is empty
    return True


@click.command()
def list_seasons():
    """List all available seasons from MHL website."""
    click.echo("Fetching seasons...")

    seasons = get_seasons()

    if not seasons:
        click.echo("Error: Could not fetch seasons", err=True)
        sys.exit(1)

    click.echo(f"\nSeasons ({len(seasons)})")
    click.echo("-" * 50)
    for season in seasons:
        click.echo(f"  {season['id']:<8}  {season['name']}")
    click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to fetch divisions for')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_divisions(season_id: Optional[str], config_path: str):
    """List all available divisions from MHL website. Uses config.toml if season not specified."""
    user_config = UserConfig(config_path)

    if season_id:
        click.echo(f"Fetching divisions for season {season_id}...")
    else:
        config_season_id = user_config.get_season_id()
        if config_season_id:
            season_id = config_season_id
            click.echo(f"Fetching divisions for '{user_config.get_season_name()}'...")
        else:
            click.echo("Fetching divisions...")

    divisions = get_divisions(season_id)

    if not divisions:
        click.echo("Error: Could not fetch divisions", err=True)
        sys.exit(1)

    click.echo(f"\nDivisions ({len(divisions)})")
    click.echo("-" * 50)
    for division in divisions:
        click.echo(f"  {division['id']:<8}  {division['name']}")
    click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to filter teams')
@click.option('--division-id', '-d', help='Division ID to filter teams')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_teams(season_id: Optional[str], division_id: Optional[str], direct: bool, config_path: str):
    """List all teams from MHL website. Uses config.toml if season/division not specified."""
    user_config = UserConfig(config_path)

    # Determine actual IDs to use
    actual_season_id = season_id or user_config.get_season_id()
    actual_division_id = division_id
    if actual_division_id is None:
        division_ids = user_config.get_division_ids()
        if division_ids:
            actual_division_id = division_ids[0]

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")
        if season_id and division_id:
            click.echo(f"Fetching teams for season {season_id}, division {division_id}...")
        elif season_id:
            click.echo(f"Fetching teams for season {season_id}...")
        elif division_id:
            click.echo(f"Fetching teams for division {division_id}...")
        else:
            config_season = user_config.get_season_name()
            config_divs = user_config.get_division_names()

            if config_season and config_divs:
                click.echo(f"Fetching teams for '{config_season}', division '{config_divs[0]}'...")
            elif config_season:
                click.echo(f"Fetching teams for '{config_season}'...")
            else:
                click.echo("Fetching teams...")

        teams = get_teams(actual_season_id, actual_division_id)
    else:
        # Use API by default
        if season_id and division_id:
            click.echo(f"Fetching teams for season {season_id}, division {division_id}...")
        else:
            config_season = user_config.get_season_name()
            config_divs = user_config.get_division_names()

            if config_season and config_divs:
                click.echo(f"Fetching teams for '{config_season}', division '{config_divs[0]}'...")
            elif config_season:
                click.echo(f"Fetching teams for '{config_season}'...")
            else:
                click.echo("Fetching teams...")

        try:
            api_client = APIClient(
                base_url=user_config.get_api_url(),
                timeout=user_config.get_api_timeout()
            )
            teams = api_client.get_teams(actual_season_id, actual_division_id)
        except APIConnectionError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)
        except APITimeoutError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)
        except APIResponseError as e:
            click.echo(f"Error: API returned error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)
        except APIError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)

    if not teams:
        click.echo("Error: Could not fetch teams", err=True)
        sys.exit(1)

    click.echo(f"\nTeams ({len(teams)})")
    click.echo("-" * 70)
    for team in teams:
        click.echo(f"  {team['id']:<8}  {team['name']}")
    click.echo()


@click.command()
@click.argument('search_term')
@click.option('--season-id', '-s', help='Season ID to search within')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def find_team(search_term: str, season_id: Optional[str], direct: bool, config_path: str):
    """Search for teams by partial name match.

    SEARCH_TERM: Partial team name to search for (case-insensitive)

    Examples:
      mhl.py find-team "O'Connor"
      mhl.py find-team "Thunderbirds"
      mhl.py find-team "10U"

    Requirements: 5.1, 5.2, 5.3
    """
    user_config = UserConfig(config_path)

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")

    # Determine season to search
    actual_season_id = season_id or user_config.get_season_id()

    if actual_season_id:
        config_season = user_config.get_season_name() if not season_id else season_id
        click.echo(f"Searching for teams matching '{search_term}' in '{config_season}'...")
    else:
        click.echo(f"Searching for teams matching '{search_term}'...")

    # Get all divisions for the season
    divisions = get_divisions(actual_season_id)

    if not divisions:
        click.echo("Error: Could not fetch divisions", err=True)
        sys.exit(1)

    # Search across all divisions
    matching_teams = []
    search_lower = search_term.lower()

    if direct:
        # Direct mode: fetch from TeamLinkt
        for division in divisions:
            teams = get_teams(actual_season_id, division['id'])
            if teams:
                for team in teams:
                    if search_lower in team['name'].lower():
                        matching_teams.append({
                            'id': team['id'],
                            'name': team['name'],
                            'division_id': division['id'],
                            'division_name': division['name'],
                        })
    else:
        # API mode: fetch from MHL API
        api_client = APIClient(
            base_url=user_config.get_api_url(),
            timeout=user_config.get_api_timeout()
        )
        api_errors = 0
        for division in divisions:
            try:
                teams = api_client.get_teams(actual_season_id, division['id'])
                if teams:
                    for team in teams:
                        if search_lower in team['name'].lower():
                            matching_teams.append({
                                'id': team['id'],
                                'name': team['name'],
                                'division_id': division['id'],
                                'division_name': division['name'],
                            })
            except APIResponseError:
                # Division not cached, skip it
                api_errors += 1
                continue
            except (APIConnectionError, APITimeoutError, APIError) as e:
                click.echo(f"Error: {e}", err=True)
                click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
                sys.exit(1)

        # If all divisions failed, suggest direct mode
        if api_errors == len(divisions) and not matching_teams:
            click.echo("Error: No cached team data available", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)

    # Remove duplicates (same team might appear in multiple divisions)
    seen_ids = set()
    unique_teams = []
    for team in matching_teams:
        if team['id'] not in seen_ids:
            seen_ids.add(team['id'])
            unique_teams.append(team)

    if not unique_teams:
        click.echo(f"\nNo teams found matching: {search_term}")
        sys.exit(0)

    # Resolve full division names for all teams (Requirements: 5.1, 5.2, 5.3)
    unresolved_divisions = []
    for team in unique_teams:
        full_name, was_resolved = get_full_division_name(
            team['division_id'],
            team['division_name'],
            actual_season_id
        )
        team['division_name'] = full_name
        if not was_resolved and team['division_id'] not in [d['id'] for d in unresolved_divisions]:
            unresolved_divisions.append({
                'id': team['division_id'],
                'name': team['division_name']
            })

    click.echo(f"\nMatching Teams ({len(unique_teams)})")
    click.echo("-" * 90)
    click.echo(f"  {'ID':<10}  {'Team Name':<40}  {'Division':<30}")
    click.echo("-" * 90)

    for team in unique_teams:
        team_name = team['name'][:40]
        division_name = team['division_name'][:30]
        click.echo(f"  {team['id']:<10}  {team_name:<40}  {division_name:<30}")

    # Show warning for unresolved division names (Requirement 5.3)
    if unresolved_divisions:
        click.echo()
        click.echo("Warning: Could not resolve full division name for:", err=True)
        for div in unresolved_divisions:
            click.echo(f"  - {div['name']} (ID: {div['id']})", err=True)

    click.echo()
    click.echo("Use the team ID with --team-id option in list-games or list-scores commands.")
    click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to filter games')
@click.option('--division-id', '-d', help='Division ID to filter games')
@click.option('--team-id', '-t', help='Team ID to filter games')
@click.option('--all-division', is_flag=True, help='Show all games in division (ignore team filter)')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_scores(season_id: Optional[str], division_id: Optional[str], team_id: Optional[str], all_division: bool, direct: bool, config_path: str):
    """List completed games with scores from MHL website. Uses config.toml if parameters not specified."""
    user_config = UserConfig(config_path)

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")

    # Determine what filters to use
    actual_season_id = season_id or user_config.get_season_id()
    actual_division_id = division_id
    actual_team_id = team_id

    # If --all-division flag is set, ignore team filter
    if all_division:
        actual_team_id = 'all'  # Use 'all' to explicitly get all teams
        if actual_division_id is None:
            # Use first division from config if not specified
            division_ids = user_config.get_division_ids()
            if division_ids:
                actual_division_id = division_ids[0]
    else:
        # Use team from config if not specified
        if actual_team_id is None:
            actual_team_id = user_config.get_team_id()
        # Use first division from config if not specified
        if actual_division_id is None:
            division_ids = user_config.get_division_ids()
            if division_ids:
                actual_division_id = division_ids[0]

    # Display what we're fetching
    if season_id and division_id and team_id:
        click.echo(f"Fetching scores for season {season_id}, division {division_id}, team {team_id}...")
    elif all_division:
        config_season = user_config.get_season_name()
        config_divs = user_config.get_division_names()
        div_name = config_divs[0] if config_divs else actual_division_id
        click.echo(f"Fetching all scores in '{div_name}' for '{config_season}'...")
    else:
        config_season = user_config.get_season_name()
        config_team = user_config.get_team_name()
        if config_season and config_team:
            click.echo(f"Fetching scores for '{config_team}' in '{config_season}'...")
        elif config_season:
            click.echo(f"Fetching scores for '{config_season}'...")
        else:
            click.echo("Fetching scores...")

    if direct:
        games = get_scores(actual_season_id, actual_division_id, actual_team_id)
    else:
        # Use API by default
        try:
            api_client = APIClient(
                base_url=user_config.get_api_url(),
                timeout=user_config.get_api_timeout()
            )
            games = api_client.get_scores(actual_season_id, actual_division_id, actual_team_id)
        except (APIConnectionError, APITimeoutError, APIResponseError, APIError) as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)

    if not games:
        click.echo("No scores found", err=True)
        sys.exit(1)

    # Highlight user's team if configured
    user_team = user_config.get_team_name()

    click.echo(f"\nCompleted Games ({len(games)})")
    click.echo("-" * 130)

    for game in games:
        game_id = game.get('game_id', '')
        home_team = game.get('home_team', '')
        away_team = game.get('away_team', '')
        # Handle None values from API - convert to '-' for display
        home_score = game.get('home_score')
        away_score = game.get('away_score')
        home_score = '-' if home_score is None else home_score
        away_score = '-' if away_score is None else away_score
        date = game.get('date', '')
        time = game.get('time', '')

        # Format game_id - display full ID without truncation (Requirements 1.2, 1.3)
        game_id_display = str(game_id) if game_id else '-'

        # Truncate team names to fit in column (increased from 26 to 40 chars)
        home_display = home_team[:40]
        away_display = away_team[:40]

        # Add marker for user's team
        home_marker = " *" if user_team and home_team == user_team else "  "
        away_marker = " *" if user_team and away_team == user_team else "  "

        # Format score
        score = f"{home_score:>2}-{away_score:<2}"

        # Apply color coding if user's team is involved
        if user_team:
            is_home_user = (user_team == home_team)
            is_away_user = (user_team == away_team)

            if is_home_user or is_away_user:
                try:
                    h_score = int(home_score)
                    a_score = int(away_score)

                    if is_home_user:
                        if h_score > a_score:
                            score = click.style(score, fg='green')  # Win
                        elif h_score < a_score:
                            score = click.style(score, fg='red')    # Loss
                        else:
                            score = click.style(score, fg='yellow') # Tie
                    else: # is_away_user
                        if a_score > h_score:
                            score = click.style(score, fg='green')  # Win
                        elif a_score < h_score:
                            score = click.style(score, fg='red')    # Loss
                        else:
                            score = click.style(score, fg='yellow') # Tie
                except (ValueError, TypeError):
                    # Keep default color if scores aren't valid integers
                    pass

        # Compact date display
        date_short = date[:10] if len(date) > 10 else date[:10].ljust(10)
        time_short = time.split(' - ')[0] if ' - ' in time else time[:8].ljust(8)

        click.echo(f"  {game_id_display:<9} {date_short}  {time_short:<8}  {home_display:<40}{home_marker}  {score}  {away_marker}{away_display:<40}")

    click.echo()
    if user_team:
        click.echo("  * Your team")
        click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to filter games')
@click.option('--division-id', '-d', help='Division ID to filter games')
@click.option('--team-id', '-t', help='Team ID to filter games')
@click.option('--all-division', is_flag=True, help='Show all games in division (ignore team filter)')
@click.option('--future', is_flag=True, help='Show only future scheduled games (no scores yet)')
@click.option('--past', is_flag=True, help='Show only completed games with scores')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_games(season_id: Optional[str], division_id: Optional[str], team_id: Optional[str], all_division: bool, future: bool, past: bool, direct: bool, config_path: str):
    """List games from MHL website. Uses config.toml if parameters not specified.

    By default, shows ALL games (both completed and scheduled) with scores where available.

    Use --future to show only future scheduled games (games without scores).
    Use --past to show only completed games (games with scores).

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    user_config = UserConfig(config_path)

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")

    # Determine what filters to use
    actual_season_id = season_id or user_config.get_season_id()
    actual_division_id = division_id
    actual_team_id = team_id

    # If --all-division flag is set, ignore team filter
    if all_division:
        actual_team_id = 'all'  # Use 'all' to explicitly get all teams
        if actual_division_id is None:
            # Use first division from config if not specified
            division_ids = user_config.get_division_ids()
            if division_ids:
                actual_division_id = division_ids[0]
    else:
        # Use team from config if not specified
        if actual_team_id is None:
            actual_team_id = user_config.get_team_id()
        # Use first division from config if not specified
        if actual_division_id is None:
            division_ids = user_config.get_division_ids()
            if division_ids:
                actual_division_id = division_ids[0]

    # Display what we're fetching
    if season_id and division_id and team_id:
        click.echo(f"Fetching games for season {season_id}, division {division_id}, team {team_id}...")
    elif all_division:
        config_season = user_config.get_season_name()
        config_divs = user_config.get_division_names()
        div_name = config_divs[0] if config_divs else actual_division_id
        click.echo(f"Fetching all games in '{div_name}' for '{config_season}'...")
    else:
        config_season = user_config.get_season_name()
        config_team = user_config.get_team_name()
        if config_season and config_team:
            click.echo(f"Fetching games for '{config_team}' in '{config_season}'...")
        elif config_season:
            click.echo(f"Fetching games for '{config_season}'...")
        else:
            click.echo("Fetching games...")

    if direct:
        games = get_games(actual_season_id, actual_division_id, actual_team_id)
    else:
        # Use API by default
        try:
            api_client = APIClient(
                base_url=user_config.get_api_url(),
                timeout=user_config.get_api_timeout()
            )
            games = api_client.get_games(actual_season_id, actual_division_id, actual_team_id)
        except (APIConnectionError, APITimeoutError, APIResponseError, APIError) as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)

    if not games:
        click.echo("No games found", err=True)
        sys.exit(1)

    # Filter games based on --future and --past flags (Requirements 4.2, 4.3)
    if future and past:
        click.echo("Error: Cannot use both --future and --past flags together", err=True)
        sys.exit(1)

    if future or past:
        filtered_games = []
        for game in games:
            home_score = game.get('home_score')
            away_score = game.get('away_score')
            # A game is considered "completed" if it has scores (not None, not empty, not '-')
            has_scores = (
                home_score is not None and
                away_score is not None and
                str(home_score).strip() not in ('', '-') and
                str(away_score).strip() not in ('', '-')
            )

            if future and not has_scores:
                # Future games: no scores yet
                filtered_games.append(game)
            elif past and has_scores:
                # Past games: have scores
                filtered_games.append(game)

        games = filtered_games

        if not games:
            filter_type = "future" if future else "completed"
            click.echo(f"No {filter_type} games found", err=True)
            sys.exit(1)

    # Highlight user's team if configured
    user_team = user_config.get_team_name()

    # Determine header based on filter (Requirements 4.1, 4.2, 4.3)
    if future:
        header = f"\nFuture Games - Schedule ({len(games)})"
    elif past:
        header = f"\nCompleted Games ({len(games)})"
    else:
        header = f"\nAll Games - Schedule ({len(games)})"

    click.echo(header)
    click.echo("-" * 130)

    for game in games:
        game_id = game.get('game_id', '')
        home_team = game.get('home_team', '')
        away_team = game.get('away_team', '')
        # Handle None values from API - convert to '-' for display
        home_score = game.get('home_score')
        away_score = game.get('away_score')
        home_score = '-' if home_score is None else home_score
        away_score = '-' if away_score is None else away_score
        date = game.get('date', '')
        time = game.get('time', '')

        # Format game_id - display full ID without truncation (Requirements 1.1, 1.3)
        game_id_display = str(game_id) if game_id else '-'

        # Truncate team names to fit in column (increased from 26 to 40 chars)
        home_display = home_team[:40]
        away_display = away_team[:40]

        # Add marker for user's team
        home_marker = " *" if user_team and home_team == user_team else "  "
        away_marker = " *" if user_team and away_team == user_team else "  "

        # Format score
        score = f"{home_score:>2}-{away_score:<2}"

        # Compact date display
        date_short = date[:10] if len(date) > 10 else date[:10].ljust(10)
        time_short = time.split(' - ')[0] if ' - ' in time else time[:8].ljust(8)

        click.echo(f"  {game_id_display:<9} {date_short}  {time_short:<8}  {home_display:<40}{home_marker}  {score}  {away_marker}{away_display:<40}")

    click.echo()
    if user_team:
        click.echo("  * Your team")
        click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to filter standings')
@click.option('--division-id', '-d', help='Division ID to filter standings')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_standings(season_id: Optional[str], division_id: Optional[str], direct: bool, config_path: str):
    """List division standings from MHL website. Uses config.toml if parameters not specified."""
    user_config = UserConfig(config_path)

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")

    # Determine what filters to use
    actual_season_id = season_id or user_config.get_season_id()
    actual_division_id = division_id

    if actual_division_id is None:
        # Use first division from config if not specified
        division_ids = user_config.get_division_ids()
        if division_ids:
            actual_division_id = division_ids[0]

    # Display what we're fetching
    if season_id and division_id:
        click.echo(f"Fetching standings for season {season_id}, division {division_id}...")
    else:
        config_season = user_config.get_season_name()
        config_divs = user_config.get_division_names()
        if config_season and config_divs:
            div_name = config_divs[0] if config_divs else actual_division_id
            click.echo(f"Fetching standings for '{div_name}' in '{config_season}'...")
        elif config_season:
            click.echo(f"Fetching standings for '{config_season}'...")
        else:
            click.echo("Fetching standings...")

    if direct:
        standings = get_standings(actual_season_id, actual_division_id)
    else:
        # Use API by default
        try:
            api_client = APIClient(
                base_url=user_config.get_api_url(),
                timeout=user_config.get_api_timeout()
            )
            standings = api_client.get_standings(actual_season_id, actual_division_id)

            # Check if API returned empty or all-zeros data (Requirement 2.3)
            # This indicates standings weren't synced properly
            if standings and _standings_are_empty(standings):
                click.echo("Warning: API standings data appears incomplete, falling back to direct mode...", err=True)
                standings = get_standings(actual_season_id, actual_division_id)

        except (APIConnectionError, APITimeoutError, APIResponseError, APIError) as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
            sys.exit(1)

    if not standings:
        click.echo("No standings found", err=True)
        sys.exit(1)

    # Get user's team for highlighting
    user_team = user_config.get_team_name()

    click.echo(f"\nStandings ({len(standings)} teams)")
    click.echo("-" * 110)
    click.echo(f"  {'#':<3} {'Team Name':<35}  {'GP':>3}  {'W':>3}  {'L':>3}  {'T':>3}  {'PTS':>4}  {'GF':>4}  {'GA':>4}  {'Diff':>5}  {'Win%':>6}")
    click.echo("-" * 110)

    for team in standings:
        team_name = team.get('team_name', '')
        ranking = team.get('ranking', '-')
        games_played = team.get('games_played', 0)
        wins = team.get('total_wins', 0)
        losses = team.get('total_losses', 0)
        ties = team.get('total_ties', 0)
        points = team.get('total_points', 0)
        goals_for = team.get('score_for', 0)
        goals_against = team.get('score_against', 0)
        goal_diff = goals_for - goals_against
        win_percent = team.get('win_percent', '0.000')

        # Truncate team name if too long
        team_display = team_name[:35]

        # Add marker for user's team
        marker = "*" if user_team and team_name == user_team else " "

        click.echo(f" {marker}{ranking:<3} {team_display:<35}  {games_played:>3}  {wins:>3}  {losses:>3}  {ties:>3}  {points:>4}  {goals_for:>4}  {goals_against:>4}  {goal_diff:>+5}  {win_percent:>6}")

    click.echo()
    if user_team:
        click.echo("  * Your team")
        click.echo()


@click.command()
@click.option('--season-id', '-s', help='Season ID to filter locations')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def list_locations(season_id: Optional[str], config_path: str):
    """List all rinks/arenas from MHL website. Uses config.toml if season not specified."""
    user_config = UserConfig(config_path)

    # Determine what season to use
    actual_season_id = season_id or user_config.get_season_id()

    # Display what we're fetching
    if season_id:
        click.echo(f"Fetching locations for season {season_id}...")
    else:
        config_season = user_config.get_season_name()
        if config_season:
            click.echo(f"Fetching locations for '{config_season}'...")
        else:
            click.echo("Fetching locations...")

    locations = get_locations(actual_season_id)

    if not locations:
        click.echo("No locations found", err=True)
        sys.exit(1)

    click.echo(f"\nLocations ({len(locations)})")
    click.echo("-" * 100)
    click.echo(f"  {'Name':<35}  {'Address':<60}")
    click.echo("-" * 100)

    for location in locations:
        name = location.get('name', '')[:35]
        address = location.get('address', '')[:60]
        click.echo(f"  {name:<35}  {address:<60}")

    click.echo()

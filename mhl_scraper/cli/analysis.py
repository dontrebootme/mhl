import sys
import json
import logging
import concurrent.futures
import click
from typing import Optional
from collections import Counter
from pathlib import Path

from mhl_scraper.config import UserConfig
from mhl_scraper.utils import (
    get_scores, get_standings, get_game_details, download_gamesheet, get_teams
)
from mhl_scraper.api_client import APIClient, APIError, APIConnectionError, APITimeoutError, APIResponseError
from mhl_scraper.parsers.recap_parser import parse_game_recap
from mhl_scraper.parsers.gamesheet_parser import parse_gamesheet_pdf, save_gamesheet_json, GamesheetSerializationError
from mhl_scraper.analytics.player_extractor import identify_top_performers, analyze_team_tendencies
from mhl_scraper.reports.scout_report import (
    ScoutingReportData,
    GameSummary,
    generate_scouting_report,
    generate_recommendations,
    generate_play_style_description,
    enhance_report_with_gamesheet_data,
)

logger = logging.getLogger(__name__)

@click.command()
@click.argument('game_id')
def game_details(game_id: str):
    """Show detailed information for a specific game.

    GAME_ID: The game ID from a game URL (e.g., 2951440)
    """
    click.echo(f"Fetching game details for game {game_id}...")

    details = get_game_details(game_id)

    if not details:
        click.echo("Game not found or error fetching details", err=True)
        sys.exit(1)

    # Display game details
    click.echo()
    click.echo("=" * 100)
    click.echo(f"  {details.get('away_team', 'Unknown')} ({details.get('away_record', 'N/A')}) at {details.get('home_team', 'Unknown')} ({details.get('home_record', 'N/A')})")
    click.echo("=" * 100)
    click.echo()
    click.echo(f"  Final Score:  {details.get('away_team', 'Away')[:30]} {details.get('away_score', '-'):>3}  -  {details.get('home_score', '-'):<3} {details.get('home_team', 'Home')[:30]}")
    click.echo()
    click.echo(f"  Date:         {details.get('date', 'N/A')}")
    click.echo(f"  Time:         {details.get('time', 'N/A')}")
    click.echo(f"  Location:     {details.get('location', 'N/A')}")
    click.echo(f"  Division:     {details.get('division', 'N/A')}")
    click.echo(f"  Status:       {details.get('status', 'N/A')}")
    click.echo()

    # Display recap if available
    if details.get('recap_title') or details.get('recap_text'):
        click.echo("-" * 100)
        if details.get('recap_title'):
            click.echo(f"  {details['recap_title']}")
            click.echo()

        if details.get('recap_text'):
            # Wrap text at 96 characters to fit nicely
            import textwrap
            wrapped = textwrap.fill(details['recap_text'], width=96, initial_indent='  ', subsequent_indent='  ')
            click.echo(wrapped)
            click.echo()

    click.echo("=" * 100)
    click.echo()

@click.command()
@click.argument('team_identifier')
@click.option('--games', '-g', default=5, help='Number of recent games to analyze (default: 5)')
@click.option('--output', '-o', type=click.Path(), help='Output file path (default: print to stdout)')
@click.option('--season-id', '-s', help='Season ID to filter games')
@click.option('--division-id', '-d', help='Division ID to filter games')
@click.option('--direct', is_flag=True, help='Fetch directly from TeamLinkt instead of MHL API')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def scout_opponent(team_identifier: str, games: int, output: Optional[str], season_id: Optional[str], division_id: Optional[str], direct: bool, config_path: str):
    """
    Generate a scouting report for an opponent team.

    TEAM_IDENTIFIER: Team name or team ID to scout (e.g., "Jr Kraken 10U (Navy)" or "721793")

    This command will:
    1. Find recent games for the specified team
    2. Analyze game recaps for player mentions and team tendencies
    3. Generate a comprehensive scouting report with recommendations

    Example:
        mhl.py scout-opponent "Jr Kraken 10U (Navy)"
        mhl.py scout-opponent 721793
        mhl.py scout-opponent 721793 --games 3 --output navy_scout.md
    """
    # Load config
    user_config = UserConfig(config_path)

    if direct:
        click.echo("Direct mode: fetching from TeamLinkt")

    # Use config values if not provided
    if not season_id:
        season_id = user_config.get_season_id()
    if not division_id:
        division_ids = user_config.get_division_ids()
        division_id = division_ids[0] if division_ids else None

    if not season_id:
        click.echo("Error: No season ID configured. Run 'mhl.py config' first.", err=True)
        sys.exit(1)

    # Check if team_identifier is a team ID (numeric) or team name
    is_team_id = team_identifier.isdigit()

    # Helper function to fetch scores (API or direct)
    def fetch_scores(s_id, d_id, t_id):
        if direct:
            return get_scores(season_id=s_id, division_id=d_id, team_id=t_id)
        else:
            try:
                api_client = APIClient(
                    base_url=user_config.get_api_url(),
                    timeout=user_config.get_api_timeout()
                )
                return api_client.get_scores(s_id, d_id, t_id)
            except (APIConnectionError, APITimeoutError, APIResponseError, APIError) as e:
                click.echo(f"Error: {e}", err=True)
                click.echo("Tip: Use --direct flag to fetch data directly from TeamLinkt", err=True)
                sys.exit(1)

    # Helper function to fetch standings (API or direct)
    def fetch_standings(s_id, d_id):
        if direct:
            return get_standings(season_id=s_id, division_id=d_id)
        else:
            try:
                api_client = APIClient(
                    base_url=user_config.get_api_url(),
                    timeout=user_config.get_api_timeout()
                )
                return api_client.get_standings(s_id, d_id)
            except (APIConnectionError, APITimeoutError, APIResponseError, APIError):
                # Fallback to direct for standings lookup
                return get_standings(season_id=s_id, division_id=d_id)

    if is_team_id:
        # Fetch games directly using team ID
        click.echo(f"\n🔍 Scouting: Team ID {team_identifier}")
        click.echo("=" * 60)
        click.echo(f"Fetching games from season {user_config.get_season_name() or season_id}...")

        team_games = fetch_scores(season_id, division_id, team_identifier)

        if not team_games:
            click.echo(f"\nError: No games found for team ID '{team_identifier}'", err=True)
            sys.exit(1)

        # Get team name from standings API (more reliable than parsing game data)
        try:
            standings = fetch_standings(season_id, division_id)
            team_standing = next((s for s in standings if str(s['team_id']) == team_identifier), None)
            if team_standing:
                team_name = team_standing['team_name']
            else:
                # Fallback: get from first game
                team_name = team_games[0].get('home_team', team_identifier)
        except Exception:
            # Fallback: get from first game
            team_name = team_games[0].get('home_team', team_identifier)
    else:
        # Original behavior: search by team name
        click.echo(f"\n🔍 Scouting: {team_identifier}")
        click.echo("=" * 60)
        click.echo(f"Fetching games from season {user_config.get_season_name() or season_id}...")

        all_games = fetch_scores(season_id, division_id, None)

        if not all_games:
            click.echo("Error: Could not fetch games", err=True)
            sys.exit(1)

        # Filter games for the specified team
        team_games = [
            game for game in all_games
            if team_identifier.lower() in game.get('home_team', '').lower()
            or team_identifier.lower() in game.get('away_team', '').lower()
        ]

        if not team_games:
            click.echo(f"\nError: No games found for team '{team_identifier}'", err=True)
            click.echo("\nAvailable teams in this division:")
            # Show unique teams
            teams = set()
            for game in all_games:
                teams.add(game.get('home_team', ''))
                teams.add(game.get('away_team', ''))
            for team in sorted(teams):
                if team:
                    click.echo(f"  - {team}")
            sys.exit(1)

        team_name = team_identifier

    # Limit to requested number of games (most recent first)
    team_games = sorted(team_games, key=lambda x: x.get('date', ''), reverse=True)[:games]

    click.echo(f"Found {len(team_games)} recent game(s) for {team_name}")
    click.echo()

    # Fetch game details and recaps
    click.echo("Fetching game details and recaps...")
    game_recaps = []
    parsed_recaps = []
    game_summaries = []

    def process_game(game):
        game_id = game.get('game_id')
        if not game_id:
            return None

        # Get score data from API (available for all games)
        home_team = game.get('home_team', '')
        away_team = game.get('away_team', '')
        home_score = int(game.get('home_score', 0))
        away_score = int(game.get('away_score', 0))

        # Determine if this team was home or away
        is_home = team_name.lower() in home_team.lower()
        opponent = away_team if is_home else home_team
        team_score = home_score if is_home else away_score
        opp_score = away_score if is_home else home_score

        # Determine result
        if team_score > opp_score:
            result = 'W'
        elif team_score < opp_score:
            result = 'L'
        else:
            result = 'T'

        recap_text = ''
        parsed = None
        log_msg = ''

        try:
            # Try to get recap for additional context
            details = get_game_details(game_id)
            recap_text = details.get('recap_text', '') if details else ''

            if recap_text:
                # Parse the recap
                parsed = parse_game_recap(recap_text)

                # Create game summary WITH recap data
                summary = GameSummary(
                    game_id=game_id,
                    date=game.get('date', ''),
                    opponent=opponent,
                    score=f"{team_score}-{opp_score}",
                    result=result,
                    goals_for=team_score,
                    goals_against=opp_score,
                    key_moments=parsed['scoring_mentions'][:3],  # Top 3 scoring mentions
                    style_keywords=parsed['game_style']['keywords'][:3]
                )
                log_msg = f"  ✓ {game.get('date', '')} vs {opponent} (recap found)"
            else:
                # Create game summary WITHOUT recap data (score only)
                summary = GameSummary(
                    game_id=game_id,
                    date=game.get('date', ''),
                    opponent=opponent,
                    score=f"{team_score}-{opp_score}",
                    result=result,
                    goals_for=team_score,
                    goals_against=opp_score,
                    key_moments=[],  # No recap available
                    style_keywords=[]
                )
                log_msg = f"  ✓ {game.get('date', '')} vs {opponent} (score only)"

        except Exception as e:
            # Even if recap fetch fails, create summary with score data
            summary = GameSummary(
                game_id=game_id,
                date=game.get('date', ''),
                opponent=opponent,
                score=f"{team_score}-{opp_score}",
                result=result,
                goals_for=team_score,
                goals_against=opp_score,
                key_moments=[],
                style_keywords=[]
            )
            log_msg = f"  ✓ {game.get('date', '')} vs {opponent} (score only, error: {e})"

        return {
            'summary': summary,
            'recap_text': recap_text,
            'parsed_recap': parsed,
            'log_message': log_msg
        }

    # Use ThreadPoolExecutor to fetch in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        futures = [executor.submit(process_game, game) for game in team_games]

        # Print progress as tasks complete
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if res and res.get('log_message'):
                    click.echo(res['log_message'])
            except Exception as e:
                # This should be caught inside process_game, but safety net
                logger.error(f"Error processing game: {e}")

    # Collect results in original order
    for future in futures:
        try:
            res = future.result()
            if not res:
                continue

            game_summaries.append(res['summary'])
            if res.get('recap_text'):
                game_recaps.append(res['recap_text'])
            if res.get('parsed_recap'):
                parsed_recaps.append(res['parsed_recap'])
        except Exception:
            # Already handled/logged
            pass

    if not game_summaries:
        click.echo("\nError: No games found for this team", err=True)
        sys.exit(1)

    click.echo(f"\n✓ Analyzed {len(game_summaries)} game(s): {len(game_recaps)} with recaps, {len(game_summaries) - len(game_recaps)} score-only")
    click.echo()

    # Download and parse gamesheets
    click.echo("Downloading and parsing gamesheets...")
    logger.info(f"Starting gamesheet download for {len(team_games)} games")

    # Create scouting report directory
    team_name_safe = team_name.replace('/', '_').replace(' ', '_').replace('(', '').replace(')', '')
    team_id_str = team_identifier if team_identifier.isdigit() else 'unknown'
    report_dir = Path(f"scouting_reports/{team_id_str}_{team_name_safe}")
    gamesheet_dir = report_dir / "gamesheets"
    gamesheet_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Gamesheet directory: {gamesheet_dir}")

    gamesheet_count = 0
    parsed_gamesheet_count = 0
    failed_downloads = 0
    failed_parses = 0

    for idx, game in enumerate(team_games, 1):
        game_id = game.get('game_id')
        if not game_id:
            logger.warning(f"Game at index {idx} has no game_id, skipping")
            continue

        logger.debug(f"[{idx}/{len(team_games)}] Processing game {game_id}")

        try:
            # Download gamesheet PDF
            pdf_path = gamesheet_dir / f"game_{game_id}.pdf"

            if download_gamesheet(game_id, str(pdf_path)):
                gamesheet_count += 1
                click.echo(f"  ✓ Downloaded gamesheet for game {game_id}")
                logger.info(f"Downloaded gamesheet for game {game_id} to {pdf_path}")

                # Parse the gamesheet
                try:
                    gamesheet_data = parse_gamesheet_pdf(str(pdf_path))

                    # Save parsed data as JSON using the new export function
                    # This ensures consistent schema and proper error handling
                    try:
                        json_path = save_gamesheet_json(gamesheet_data, str(pdf_path))
                        logger.debug(f"Saved JSON for game {game_id} to {json_path}")
                    except GamesheetSerializationError as json_error:
                        click.echo(f"  ⚠ Warning: Could not save JSON for game {game_id}: {json_error}", err=True)
                        logger.error(f"Failed to save JSON for game {game_id}: {json_error}")
                        json_path = None

                    # Add to game object
                    game['gamesheet_data'] = gamesheet_data
                    game['gamesheet_pdf'] = str(pdf_path)
                    if json_path:
                        game['gamesheet_json'] = json_path

                    parsed_gamesheet_count += 1
                    logger.info(f"Successfully parsed gamesheet for game {game_id}")

                except Exception as parse_error:
                    failed_parses += 1
                    click.echo(f"  ⚠ Warning: Could not parse gamesheet for game {game_id}: {parse_error}", err=True)
                    logger.error(f"Failed to parse gamesheet {pdf_path} for game {game_id}: {parse_error}", exc_info=True)
                    game['gamesheet_pdf'] = str(pdf_path)
                    game['gamesheet_parse_error'] = str(parse_error)
            else:
                click.echo(f"  ⊘ No gamesheet available for game {game_id}")
                logger.info(f"No gamesheet available for game {game_id}")

        except Exception as e:
            failed_downloads += 1
            click.echo(f"  ⚠ Warning: Could not download gamesheet for game {game_id}: {e}", err=True)
            logger.error(f"Failed to download gamesheet for game {game_id}: {e}", exc_info=True)

    # Log summary
    summary_msg = (
        f"Gamesheet processing complete: {gamesheet_count} downloaded, "
        f"{parsed_gamesheet_count} parsed, {failed_downloads} download failures, "
        f"{failed_parses} parse failures"
    )
    logger.info(summary_msg)
    click.echo(f"\n✓ Downloaded {gamesheet_count} gamesheet(s), parsed {parsed_gamesheet_count}")
    if failed_downloads > 0 or failed_parses > 0:
        click.echo(f"  ⚠ {failed_downloads} download failure(s), {failed_parses} parse failure(s)")
    click.echo()

    # Analyze player performance
    click.echo("Analyzing player performance...")
    top_performers = identify_top_performers(game_recaps, team_name)

    # Analyze team tendencies
    click.echo("Analyzing team tendencies...")
    tendencies = analyze_team_tendencies(parsed_recaps)

    # Calculate statistics
    total_goals_for = sum(g.goals_for for g in game_summaries)
    total_goals_against = sum(g.goals_against for g in game_summaries)
    wins = sum(1 for g in game_summaries if g.result == 'W')
    losses = sum(1 for g in game_summaries if g.result == 'L')
    ties = sum(1 for g in game_summaries if g.result == 'T')

    avg_goals_for = total_goals_for / len(game_summaries) if game_summaries else 0
    avg_goals_against = total_goals_against / len(game_summaries) if game_summaries else 0

    # Try to get standings info
    standings_info = {}
    try:
        standings = fetch_standings(season_id, division_id)
        for team_standing in standings:
            if team_name.lower() in team_standing.get('team_name', '').lower():
                standings_info = team_standing
                break
    except:
        pass

    # Build scouting report data
    report_data = ScoutingReportData(
        team_name=team_name,
        division=division_id or "",
        games_analyzed=len(game_summaries),
        wins=wins,
        losses=losses,
        ties=ties,
        division_rank=standings_info.get('ranking'),
        total_points=standings_info.get('total_points'),
        avg_goals_for=avg_goals_for,
        avg_goals_against=avg_goals_against,
        total_goals_for=total_goals_for,
        total_goals_against=total_goals_against,
        recent_games=game_summaries,
        top_scorers=top_performers.get('top_scorers', []),
        goalies=top_performers.get('goalies', []),
        playmakers=top_performers.get('playmakers', []),
        key_players=top_performers.get('most_mentioned', [])[:5],
        play_style=generate_play_style_description(tendencies),
        common_keywords=[kw for kw, _ in tendencies.get('common_keywords', Counter()).most_common(5)],
        high_scoring_pct=tendencies.get('high_scoring_pct', 0),
        close_game_pct=tendencies.get('close_game_pct', 0),
        comeback_pct=tendencies.get('comeback_pct', 0),
        physical_pct=tendencies.get('physical_pct', 0),
        period_strengths=tendencies.get('period_strengths', {})
    )

    # Enhance report with gamesheet data (Requirements 10.3, 10.4, 10.5, 10.6, 10.8)
    gamesheet_data_list = [
        game.get('gamesheet_data')
        for game in team_games
        if game.get('gamesheet_data')
    ]

    if gamesheet_data_list:
        click.echo(f"Enhancing report with data from {len(gamesheet_data_list)} gamesheet(s)...")
        report_data = enhance_report_with_gamesheet_data(report_data, gamesheet_data_list)

    # Generate recommendations
    report_data.recommendations = generate_recommendations(report_data)

    # Generate the report
    click.echo("Generating scouting report...")
    report = generate_scouting_report(report_data)

    # Save comprehensive report to scouting_reports directory
    report_md_path = report_dir / "report.md"
    report_json_path = report_dir / "report_data.json"

    # Save markdown report
    with open(report_md_path, 'w') as f:
        # Add data coverage header
        coverage_header = f"""# Scouting Report Data Coverage
- **Games Analyzed:** {len(team_games)}
- **Games with Recaps:** {len(game_recaps)}
- **Games with Gamesheets:** {gamesheet_count}
- **Gamesheets Parsed:** {parsed_gamesheet_count}
- **Team ID:** {team_id_str}
- **Report Directory:** {report_dir}

---

"""
        f.write(coverage_header)
        f.write(report)

    # Save JSON data
    json_data = {
        'team_name': team_name,
        'team_id': team_id_str,
        'games_analyzed': len(team_games),
        'recaps_found': len(game_recaps),
        'gamesheets_downloaded': gamesheet_count,
        'gamesheets_parsed': parsed_gamesheet_count,
        'report_data': {
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'avg_goals_for': avg_goals_for,
            'avg_goals_against': avg_goals_against,
            'top_scorers': top_performers.get('top_scorers', []),
            'goalies': top_performers.get('goalies', []),
            'games': [
                {
                    'game_id': g.game_id,
                    'date': g.date,
                    'opponent': g.opponent,
                    'score': g.score,
                    'result': g.result
                } for g in game_summaries
            ]
        },
        # Gamesheet-derived statistics (Requirements 10.3, 10.4, 10.5, 10.6, 10.8)
        'gamesheet_stats': {
            'top_scorers': report_data.gamesheet_top_scorers,
            'most_penalized': report_data.gamesheet_most_penalized,
            'goalies': report_data.gamesheet_goalies,
            'gamesheets_analyzed': report_data.gamesheets_analyzed,
        },
        'gamesheet_files': [
            {
                'game_id': g.get('game_id'),
                'pdf_path': g.get('gamesheet_pdf'),
                'json_path': g.get('gamesheet_json'),
                'parse_error': g.get('gamesheet_parse_error')
            } for g in team_games if g.get('gamesheet_pdf')
        ]
    }

    with open(report_json_path, 'w') as f:
        json.dump(json_data, f, indent=2)

    click.echo(f"\n✓ Scouting report saved:")
    click.echo(f"  📄 Report: {report_md_path}")
    click.echo(f"  📊 Data: {report_json_path}")
    click.echo(f"  📁 Gamesheets: {gamesheet_dir} ({gamesheet_count} files)")

    # Output the report to custom path or stdout
    if output:
        with open(output, 'w') as f:
            f.write(report)
        click.echo(f"  📄 Also saved to: {output}")
    else:
        click.echo("\n" + "=" * 60)
        click.echo(report)
        click.echo("=" * 60)

    click.echo()


@click.command()
@click.option('--team-id', '-t', help='Team ID (default: from config.toml)')
@click.option('--rebuild', is_flag=True, help='Full rebuild instead of incremental update')
@click.option('--threshold', type=float, default=0.85, help='Fuzzy match threshold (0.0-1.0)')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
@click.option('--output', '-o', help='Custom output path for roster.json')
def generate_roster(team_id, rebuild, threshold, config_path, output):
    """Generate team roster from gamesheets with player statistics."""
    from mhl_scraper.analytics.roster_builder import RosterBuilder
    from pathlib import Path
    import json

    # Load config
    config = UserConfig(config_path)

    # Use team_id from argument or config
    if not team_id:
        team_id = config.get_team_id()
        if not team_id:
            click.echo("❌ Error: No team_id specified. Use --team-id or configure in config.toml")
            return

    team_name = config.get_team_name() or f"Team {team_id}"
    season_id = config.get_season_id()

    click.echo(f"\nGenerating roster for {team_name} (Team ID: {team_id})")
    click.echo("━" * 60)

    # Find scouting report directory
    scouting_dir = Path('scouting_reports')
    team_dirs = list(scouting_dir.glob(f'{team_id}_*'))

    if not team_dirs:
        click.echo(f"❌ Error: No scouting report directory found for team {team_id}")
        click.echo(f"   Run 'python mhl.py scout-opponent {team_id}' first to download gamesheets")
        return

    team_dir = team_dirs[0]

    # Extract actual team name from directory name
    # Directory format: {team_id}_{Team_Name_With_Underscores}
    dir_name = team_dir.name
    if '_' in dir_name:
        extracted_team_name = dir_name.split('_', 1)[1].replace('_', ' ')
        # Use extracted name for matching, but keep config name for display if available
        team_name_for_matching = extracted_team_name
    else:
        team_name_for_matching = team_name

    gamesheet_dir = team_dir / 'gamesheets'

    if not gamesheet_dir.exists():
        click.echo(f"❌ Error: No gamesheets directory found at {gamesheet_dir}")
        return

    # Find all extracted gamesheet files
    extracted_files = sorted(gamesheet_dir.glob('game_*_extracted.json'))

    if not extracted_files:
        click.echo(f"❌ Error: No extracted gamesheet files found in {gamesheet_dir}")
        click.echo(f"   Expected files matching pattern: game_*_extracted.json")
        return

    click.echo(f"\nFound {len(extracted_files)} gamesheet file(s)")

    # Determine output path
    if output:
        roster_path = Path(output)
    else:
        roster_path = team_dir / 'roster.json'

    # Create roster builder
    builder = RosterBuilder(team_id, team_name, season_id)

    # Load existing roster unless rebuild
    if not rebuild and roster_path.exists():
        if builder.load_existing_roster(roster_path):
            click.echo(f"✓ Loaded existing roster ({len(builder.players)} players)")
        else:
            click.echo("⚠ Could not load existing roster, starting fresh")
    else:
        if rebuild:
            click.echo("Performing full rebuild...")

    # Process each gamesheet
    click.echo("\nProcessing gamesheets...")

    for idx, gamesheet_file in enumerate(extracted_files, 1):
        try:
            with open(gamesheet_file, 'r') as f:
                game_data = json.load(f)

            game_id = game_data.get('game_id', gamesheet_file.stem)
            game_metadata = game_data.get('game_metadata', {})

            # Determine if our team is home or away
            home_team = game_metadata.get('home_team', '')
            away_team = game_metadata.get('away_team', '')

            # Check if team_name_for_matching appears in home or away
            if team_name_for_matching.lower() in home_team.lower():
                team_side = 'home'
            elif team_name_for_matching.lower() in away_team.lower():
                team_side = 'away'
            else:
                # Fallback: assume home (could be improved)
                team_side = 'home'

            # Add game data
            builder.add_game_data(game_data, team_side)

            click.echo(f"  [{idx}/{len(extracted_files)}] game_{game_id} ✓")

        except Exception as e:
            click.echo(f"  [{idx}/{len(extracted_files)}] {gamesheet_file.name} ✗ Error: {e}")

    # Aggregate stats
    click.echo("\nAggregating statistics...")
    builder.aggregate_stats()

    # Print matching summary
    click.echo("\nPlayer Matching Summary:")
    click.echo(f"  ✓ Exact matches: {builder.match_stats['exact_matches']}")
    click.echo(f"  ✓ Fuzzy matches: {builder.match_stats['fuzzy_matches']}", nl=False)

    if builder.match_stats['fuzzy_confidences']:
        avg_confidence = sum(builder.match_stats['fuzzy_confidences']) / len(builder.match_stats['fuzzy_confidences'])
        click.echo(f" (avg confidence: {avg_confidence:.2f})")
    else:
        click.echo()

    if builder.match_stats['number_changes'] > 0:
        click.echo(f"  ⚠ Number changes detected: {builder.match_stats['number_changes']}")

    click.echo(f"  ✓ New players: {builder.match_stats['new_players']}")

    # Get team summary
    summary = builder.get_team_summary()

    # Print top performers
    click.echo(f"\nRoster Statistics:")
    click.echo(f"  Total players: {summary['total_unique_players']}")
    click.echo(f"  Games analyzed: {builder.metadata['total_games_analyzed']}")

    if summary['top_scorers']:
        click.echo("\n  Top Scorers:")
        for idx, scorer in enumerate(summary['top_scorers'][:5], 1):
            click.echo(f"    {idx}. {scorer['name']} (#{scorer['number']}) - {scorer['goals']}G, {scorer['assists']}A, {scorer['points']}P")

    if summary['starting_goalie']:
        goalie = summary['starting_goalie']
        click.echo(f"\n  Starting Goalie:")
        click.echo(f"    {goalie['name']} (#{goalie['number']}) - {goalie['games']} games, {goalie['goals_allowed']} GA")

    # Save roster
    builder.save_roster(roster_path, create_backup=not rebuild)

    click.echo(f"\n✓ Roster saved: {roster_path}")

    if rebuild and (roster_path.parent / 'roster_backup.json').exists():
        click.echo(f"  Backup: {roster_path.parent / 'roster_backup.json'}")

    click.echo()

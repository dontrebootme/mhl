"""CLI command for USA Hockey Patch Awards detection."""

import json
import csv
import io
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import click

from mhl_scraper.config import UserConfig
from mhl_scraper.parsers.gamesheet_models import GamesheetData
from mhl_scraper.analytics.patch_awards import (
    AwardType,
    detect_all_awards,
    filter_awards_by_team,
    PatchAward,
)
from functions.firestore_config import COLS


def _load_manifest(directory):
    """Load manifest.json from the gamesheet directory, or return None."""
    manifest_path = Path(directory) / 'manifest.json'
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _missing_from_manifest(manifest, games_analyzed):
    """Return (total_games, missing_count) derived from the manifest.

    total_games  — how many completed games the team has played this season
    missing_count — games not included in analysis (total - analyzed)
    """
    total = manifest.get('summary', {}).get('total', 0)
    return total, max(0, total - games_analyzed)


def _missing_fallback(directory, games_analyzed):
    """Fallback when no manifest: count PDFs vs extracted JSONs."""
    d = Path(directory)
    pdf_count = len(list(d.glob('game_*.pdf')))
    return pdf_count, max(0, pdf_count - games_analyzed)


def _find_gamesheet_dir(team_id, explicit_dir=None):
    """Resolve the directory containing extracted gamesheet JSONs."""
    if explicit_dir:
        d = Path(explicit_dir)
        if d.exists():
            return d
        return None

    if not team_id:
        return None

    scouting_dir = Path('scouting_reports')
    team_dirs = list(scouting_dir.glob(f'{team_id}_*'))
    if not team_dirs:
        return None

    gamesheet_dir = team_dirs[0] / 'gamesheets'
    return gamesheet_dir if gamesheet_dir.exists() else None


def _load_gamesheets(directory):
    """Load all extracted gamesheet JSONs from a directory."""
    extracted_files = sorted(Path(directory).glob('game_*_extracted.json'))
    gamesheets = []
    for f in extracted_files:
        try:
            with open(f, 'r') as fh:
                data = json.load(fh)
            gamesheets.append(GamesheetData.from_dict(data))
        except Exception as e:
            click.echo(f"  Warning: Could not load {f.name}: {e}")
    return gamesheets


def _format_table(all_awards, games_analyzed, total_games=0, missing_gamesheets=0):
    """Format awards as a readable table."""
    lines = []

    by_type = {}
    for award in all_awards:
        by_type.setdefault(award.award_type, []).append(award)

    type_labels = {
        AwardType.HAT_TRICK: 'Hat Tricks (3+ goals)',
        AwardType.PLAYMAKER: 'Playmaker (3+ assists)',
        AwardType.SHUTOUT: 'Shutouts',
    }

    for award_type in AwardType:
        awards = by_type.get(award_type, [])
        if not awards:
            continue

        lines.append(f"\n  {type_labels.get(award_type, award_type)}")
        lines.append("  " + "─" * 56)

        for a in sorted(awards, key=lambda x: x.game_date or ''):
            num_str = f"#{a.player_number}" if a.player_number else ""
            lines.append(
                f"    {a.player_name} {num_str} — {a.details}"
                f"  (vs {a.opponent}, {a.game_date or 'unknown date'})"
            )

    if not all_awards:
        lines.append("\n  No awards detected.")

    if total_games:
        lines.append(f"\n  Total: {len(all_awards)} award(s) across {games_analyzed} of {total_games} game(s)")
    else:
        lines.append(f"\n  Total: {len(all_awards)} award(s) across {games_analyzed} game(s)")
    if missing_gamesheets:
        lines.append(
            f"  ⚠ Note: {missing_gamesheets} game(s) missing from analysis (gamesheet not found)"
        )
    return "\n".join(lines)


def _format_json(all_awards, team_name, team_id, season_id, games_analyzed,
                 total_games=0, missing_gamesheets=0):
    """Format awards as JSON."""
    return json.dumps({
        'team_name': team_name,
        'team_id': team_id,
        'season_id': season_id,
        'games_analyzed': games_analyzed,
        'total_games': total_games,
        'missing_gamesheets': missing_gamesheets,
        'awards': [asdict(a) for a in all_awards],
    }, indent=2)


def _format_csv(all_awards):
    """Format awards as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'award_type', 'player_name', 'player_number',
        'team_name', 'game_date', 'game_id', 'opponent', 'details',
    ])
    for a in all_awards:
        writer.writerow([
            a.award_type, a.player_name, a.player_number,
            a.team_name, a.game_date, a.game_id, a.opponent, a.details,
        ])
    return output.getvalue()


def _upload_to_firestore(all_awards, team_name, team_id, season_id, games_analyzed,
                         total_games=0, missing_gamesheets=0):
    """Upload awards to Firestore."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        click.echo("❌ firebase-admin package not installed. Run: pip install firebase-admin")
        return False

    # Initialize if needed
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    doc_id = f"{team_id}_{season_id}"
    collection_name = COLS.AWARDS

    doc_data = {
        'team_id': team_id,
        'team_name': team_name,
        'season_id': season_id,
        'games_analyzed': games_analyzed,
        'total_games': total_games,
        'missing_gamesheets': missing_gamesheets,
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'awards': [asdict(a) for a in all_awards],
    }

    db.collection(collection_name).document(doc_id).set(doc_data)
    return True


@click.command('patch-awards')
@click.option('--team', '-t', required=True, help='Team name filter (e.g., "O\'Connor")')
@click.option('--team-id', help='Team ID to find gamesheets in scouting_reports/')
@click.option('--dir', '-d', 'gamesheet_dir', help='Explicit directory of gamesheet JSONs')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'csv']),
              default='table', help='Output format')
@click.option('--upload', is_flag=True, help='Upload awards to Firestore')
@click.option('--season-id', '-s', help='Season ID (defaults from config.toml)')
@click.option('--all-teams', is_flag=True, help='Show awards for all teams, not just filtered')
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def patch_awards(team, team_id, gamesheet_dir, output_format, upload, season_id, all_teams, config_path):
    """Detect USA Hockey patch awards from gamesheets."""
    config = UserConfig(config_path)

    if not team_id:
        team_id = config.get_team_id()
    if not season_id:
        season_id = config.get_season_id()

    click.echo(f"\nUSA Hockey Patch Awards — {team}")
    click.echo("━" * 60)

    # Find gamesheet directory
    gs_dir = _find_gamesheet_dir(team_id, gamesheet_dir)
    if not gs_dir:
        click.echo("❌ No gamesheets found.")
        if not gamesheet_dir and not team_id:
            click.echo("   Provide --team-id or --dir, or set team_id in config.toml")
        elif team_id:
            click.echo(f"   Run: python mhl.py scout-opponent {team_id} --games 20")
        return

    click.echo(f"  Scanning: {gs_dir}")

    # Load gamesheets
    gamesheets = _load_gamesheets(gs_dir)
    if not gamesheets:
        click.echo("❌ No extracted gamesheet files found.")
        return

    games_analyzed = len(gamesheets)
    manifest = _load_manifest(gs_dir)
    if manifest:
        total_games, missing = _missing_from_manifest(manifest, games_analyzed)
    else:
        total_games, missing = _missing_fallback(gs_dir, games_analyzed)

    click.echo(f"  Loaded {games_analyzed} gamesheet(s)")
    if total_games:
        click.echo(f"  Total games played: {total_games}")
    if missing:
        click.echo(f"  ⚠ {missing} game(s) missing from analysis (gamesheet not found)")

    # Detect awards
    all_awards = []
    for gs in gamesheets:
        game_awards = detect_all_awards(gs)
        if not all_teams:
            game_awards = filter_awards_by_team(game_awards, team)
        all_awards.extend(game_awards.awards)

    # Output
    if output_format == 'json':
        click.echo(_format_json(all_awards, team, team_id, season_id,
                                games_analyzed, total_games, missing))
    elif output_format == 'csv':
        click.echo(_format_csv(all_awards))
    else:
        click.echo(_format_table(all_awards, games_analyzed, total_games, missing))

    # Upload
    if upload:
        if not team_id or not season_id:
            click.echo("\n❌ --upload requires --team-id and --season-id (or config.toml)")
            return

        click.echo(f"\n  Uploading to Firestore: mhl_scout_awards/{team_id}_{season_id}")
        if _upload_to_firestore(all_awards, team, team_id, season_id,
                                games_analyzed, total_games, missing):
            click.echo("  ✓ Upload complete")
        else:
            click.echo("  ✗ Upload failed")

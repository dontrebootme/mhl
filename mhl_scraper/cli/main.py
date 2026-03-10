import click
from typing import Optional

from mhl_scraper.cli.utils import setup_logging
from mhl_scraper.cli.config import config, show_config
from mhl_scraper.cli.list import (
    list_seasons, list_divisions, list_teams, list_scores, list_games,
    list_standings, list_locations, find_team
)
from mhl_scraper.cli.gamesheet import gamesheets, test_gamesheet_auth
from mhl_scraper.cli.analysis import scout_opponent, generate_roster, game_details
from mhl_scraper.cli.awards import patch_awards
from mhl_scraper.cli.cloud import cloud_usage

@click.group()
@click.version_option(version='1.0.0', prog_name='mhl-scraper')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging output')
@click.option('--log-file', type=click.Path(), help='Write logs to specified file')
@click.pass_context
def cli(ctx, verbose: bool, log_file: Optional[str]):
    """MHL Scout - Scrape and analyze Metropolitan Hockey League games."""
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['log_file'] = log_file

    # Setup logging
    setup_logging(verbose=verbose, log_file=log_file)
    pass

# Add commands
cli.add_command(config)
cli.add_command(show_config)
cli.add_command(list_seasons)
cli.add_command(list_divisions)
cli.add_command(list_teams)
cli.add_command(list_scores)
cli.add_command(list_games)
cli.add_command(list_standings)
cli.add_command(list_locations)
cli.add_command(find_team)
cli.add_command(gamesheets)
cli.add_command(test_gamesheet_auth)
cli.add_command(scout_opponent)
cli.add_command(generate_roster)
cli.add_command(game_details)
cli.add_command(cloud_usage)
cli.add_command(patch_awards)

if __name__ == '__main__':
    cli()

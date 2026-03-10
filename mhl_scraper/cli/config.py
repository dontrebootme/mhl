import sys
import click
from mhl_scraper.config import UserConfig
from mhl_scraper.utils import get_seasons, get_divisions, get_teams

@click.command()
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def config(config_path: str):
    """
    Generate or update configuration file interactively.

    This command will guide you through selecting:
    - Season
    - Division(s)
    - Team name (optional)
    """
    click.echo("\nMHL Scout Configuration")
    click.echo("-" * 50)

    # Load or create config
    user_config = UserConfig(config_path)

    # Step 1: Select Season
    click.echo("\nFetching seasons...")
    seasons = get_seasons()

    if not seasons:
        click.echo("Error: Could not fetch seasons", err=True)
        sys.exit(1)

    click.echo(f"\nSeasons ({len(seasons)}):")
    for i, season in enumerate(seasons, 1):
        click.echo(f"  {i}. {season['name']}")

    click.echo()

    # Get season selection
    while True:
        try:
            season_choice = click.prompt(
                "Select season number",
                type=int,
                default=1
            )

            if 1 <= season_choice <= len(seasons):
                selected_season = seasons[season_choice - 1]
                break
            else:
                click.echo(f"Please enter a number between 1 and {len(seasons)}")
        except (ValueError, click.Abort):
            click.echo("\nConfiguration cancelled.")
            sys.exit(0)

    user_config.set_season(selected_season['id'], selected_season['name'])
    click.echo(f"\n✓ Selected season: {selected_season['name']}")

    # Step 2: Select Division(s)
    click.echo("\nFetching available divisions...")
    divisions = get_divisions(selected_season['id'])

    if not divisions:
        click.echo("Error: Could not fetch divisions from MHL website", err=True)
        sys.exit(1)

    click.echo(f"\nFound {len(divisions)} division(s):")
    click.echo()

    for i, division in enumerate(divisions, 1):
        click.echo(f"  {i:2d}. {division['name']}")

    click.echo()
    click.echo("You can select multiple divisions (comma-separated, e.g., '1,3,5')")
    click.echo("Or enter 'all' to select all divisions")
    click.echo()

    # Get division selection
    while True:
        try:
            division_input = click.prompt(
                "Select division number(s)",
                type=str,
                default="all"
            ).strip()

            if division_input.lower() == 'all':
                selected_divisions = divisions
                break
            else:
                # Parse comma-separated numbers
                division_indices = [int(x.strip()) - 1 for x in division_input.split(',')]

                # Validate all indices
                if all(0 <= idx < len(divisions) for idx in division_indices):
                    selected_divisions = [divisions[idx] for idx in division_indices]
                    break
                else:
                    click.echo(f"Please enter numbers between 1 and {len(divisions)}")
        except (ValueError, click.Abort):
            click.echo("\nConfiguration cancelled.")
            sys.exit(0)

    division_ids = [d['id'] for d in selected_divisions]
    division_names = [d['name'] for d in selected_divisions]

    user_config.set_divisions(division_ids, division_names)
    click.echo(f"\n✓ Selected {len(selected_divisions)} division(s):")
    for name in division_names:
        click.echo(f"    - {name}")

    # Step 3: Team selection (optional)
    click.echo()
    if click.confirm("Would you like to set a default team?", default=False):
        click.echo("\nFetching available teams...")

        # If only one division selected, use it; otherwise ask which division to query
        team_division_id = None
        if len(selected_divisions) == 1:
            team_division_id = selected_divisions[0]['id']
            click.echo(f"Using division: {selected_divisions[0]['name']}")
        else:
            click.echo("\nSelect which division to query for teams:")
            for i, division in enumerate(selected_divisions, 1):
                click.echo(f"  {i}. {division['name']}")

            while True:
                try:
                    div_choice = click.prompt(
                        "Select division number",
                        type=int,
                        default=1
                    )
                    if 1 <= div_choice <= len(selected_divisions):
                        team_division_id = selected_divisions[div_choice - 1]['id']
                        break
                    else:
                        click.echo(f"Please enter a number between 1 and {len(selected_divisions)}")
                except (ValueError, click.Abort):
                    click.echo("\nTeam selection cancelled.")
                    team_division_id = None
                    break

        if team_division_id:
            teams = get_teams(selected_season['id'], team_division_id)

            if not teams:
                click.echo("Error: Could not fetch teams", err=True)
            else:
                click.echo(f"\nFound {len(teams)} team(s):")
                click.echo()

                for i, team in enumerate(teams, 1):
                    click.echo(f"  {i:2d}. {team['name']}")

                click.echo()

                # Get team selection
                while True:
                    try:
                        team_choice = click.prompt(
                            "Select team number",
                            type=int,
                            default=1
                        )

                        if 1 <= team_choice <= len(teams):
                            selected_team = teams[team_choice - 1]
                            user_config.set_team(selected_team['id'], selected_team['name'])
                            click.echo(f"✓ Set team: {selected_team['name']}")
                            break
                        else:
                            click.echo(f"Please enter a number between 1 and {len(teams)}")
                    except (ValueError, click.Abort):
                        click.echo("\nTeam selection cancelled.")
                        break

    # Step 4: API URL configuration (optional)
    click.echo()
    if click.confirm("Would you like to configure a custom API URL?", default=False):
        from mhl_scraper.config import ScraperConfig
        default_url = ScraperConfig.DEFAULT_API_URL

        click.echo(f"\nDefault API URL: {default_url}")
        click.echo("Press Enter to keep the default, or enter a custom URL.")
        click.echo()

        try:
            custom_url = click.prompt(
                "API URL",
                type=str,
                default=default_url
            ).strip()

            if custom_url:
                user_config.set_api_url(custom_url)
                if custom_url == default_url:
                    click.echo("✓ Using default API URL")
                else:
                    click.echo(f"✓ Set custom API URL: {custom_url}")
        except (ValueError, click.Abort):
            click.echo("\nAPI URL configuration cancelled.")

    # Save configuration
    click.echo()
    if user_config.save():
        click.echo("\nConfiguration Summary")
        click.echo("-" * 50)
        click.echo(f"Season:    {user_config.get_season_name()}")
        click.echo(f"\nDivisions: {len(user_config.get_division_names())} selected")
        for div in user_config.get_division_names():
            click.echo(f"  • {div}")
        if user_config.get_team_name():
            click.echo(f"\nTeam:      {user_config.get_team_name()}")
        click.echo(f"\nAPI URL:   {user_config.get_api_url()}")
        click.echo(f"\nConfig:    {config_path}")
        click.echo()
    else:
        click.echo("Error: Failed to save configuration", err=True)
        sys.exit(1)


@click.command()
@click.option('--config-path', '-c', default='config.toml', help='Path to config file')
def show_config(config_path: str):
    """Display current configuration."""
    user_config = UserConfig(config_path)

    if not user_config.is_configured():
        click.echo("No configuration found. Run 'mhl-scraper config' to create one.")
        sys.exit(1)

    click.echo("\nConfiguration")
    click.echo("-" * 50)
    click.echo(f"Season:    {user_config.get_season_name()}")
    click.echo(f"           (ID: {user_config.get_season_id()})")
    click.echo(f"\nDivisions: {len(user_config.get_division_ids())} selected")
    for name in user_config.get_division_names():
        click.echo(f"  • {name}")
    if user_config.get_team_name():
        click.echo(f"\nTeam:      {user_config.get_team_name()}")
        if user_config.get_team_id():
            click.echo(f"           (ID: {user_config.get_team_id()})")
    click.echo(f"\nAPI URL:   {user_config.get_api_url()}")
    click.echo(f"\nConfig:    {config_path}")
    click.echo()

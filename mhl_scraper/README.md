# MHL Scraper Core & CLI

The **MHL Scraper** is the python engine behind the MHL Scout platform. It provides both a command-line interface (CLI) for power users and a reusable python library for programmatic access to MHL data.

## 📦 Components

1.  **CLI Tool** (`mhl.py`): Interactive command-line tool for scraping, scouting, and analysis.
2.  **Core Library** (`mhl_scraper/`): Python package handling API communication, parsing, and business logic. Used by the CLI and Cloud Functions.

## 💻 CLI Usage

The CLI is the primary way to interact with the scraper locally. The entry point is `mhl.py` in the project root.

### Quick Start

```bash
# From the repository root
python mhl.py config
python mhl.py list-games
```

### Common Commands

| Command | Description |
| :--- | :--- |
| `list-games` | View schedule and results. |
| `list-standings` | View division standings. |
| `scout-opponent` | Generate an AI scouting report for a team. |
| `gamesheets` | Download and parse official PDF gamesheets. |
| `game-details` | View deep-dive stats for a specific game. |

**[See Full CLI Documentation](../docs/CLI_USAGE.md)**

---

## 🐍 Library Usage

You can use the `mhl_scraper` package in your own python scripts. This is how the **Cloud Functions** interact with the data.

### Basic Example

```python
from mhl_scraper.utils import get_games, get_standings
from mhl_scraper.config import ScraperConfig

# Initialize config (if needed)
config = ScraperConfig()

# Fetch games for a specific season and team
games = get_games(season_id="45165", team_id="723731")

for game in games:
    print(f"{game['date']}: {game['home_team']} vs {game['away_team']}")
```

### Advanced: Scouting Engine

```python
from mhl_scraper.services.scouting import generate_scouting_report

# Analyze an opponent
report = generate_scouting_report(
    team_name="Jr Kraken 10U (Navy)",
    season_id="45165",
    num_games=5
)

print(report.markdown)
```

---

## 🔧 Configuration

The scraper uses a `config.toml` file in the root directory.

```toml
season_id = "45165"
division_ids = ["244225"]
team_id = "723731"
```

**Security Note:** Never commit `config.toml` if it contains API keys. Use environment variables for sensitive credentials.

## 🧪 Testing

Run the test suite from the project root:

```bash
# Run all tests
pytest

# Run only scraper tests
pytest tests/
```

## 📚 Documentation Links

*   **[TeamLinkt API Reference](../docs/TEAMLINKT_API.md)**
*   **[Gamesheet API Reference](../docs/GAMESHEET_API.md)**
*   **[Deployment Guide](../deploy/README.md)** (Automated via GitHub Actions)

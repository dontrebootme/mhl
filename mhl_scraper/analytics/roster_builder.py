"""
Build and maintain team rosters from gamesheet data.

Handles player identity tracking, fuzzy matching, stat aggregation,
and incremental roster updates.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter, defaultdict

from .roster_matcher import match_player_by_number_and_name


class PlayerIdentity:
    """
    Represents a unique player with matching logic.

    Tracks name variants, jersey number history, and provides
    fuzzy matching capabilities.
    """

    def __init__(self, player_data: Dict):
        """
        Initialize player identity from dict.

        Args:
            player_data: Dict with player_id, primary_name, etc.
        """
        self.player_id = player_data.get('player_id')
        self.primary_name = player_data.get('primary_name')
        self.name_variants = player_data.get('name_variants', [])
        self.primary_number = player_data.get('primary_number')
        self.number_history = player_data.get('number_history', [])
        self.primary_position = player_data.get('primary_position')
        self.position_history = player_data.get('position_history', [])
        self.season_stats = player_data.get('season_stats', {})
        self.game_log = player_data.get('game_log', [])
        self.data_quality = player_data.get('data_quality', {})

    def to_dict(self) -> Dict:
        """Convert player identity to dictionary format."""
        return {
            'player_id': self.player_id,
            'primary_name': self.primary_name,
            'name_variants': self.name_variants,
            'primary_number': self.primary_number,
            'number_history': self.number_history,
            'primary_position': self.primary_position,
            'position_history': self.position_history,
            'season_stats': self.season_stats,
            'game_log': self.game_log,
            'data_quality': self.data_quality
        }

    def add_name_variant(self, name: str) -> None:
        """Add a name variant if not already present."""
        if name and name not in self.name_variants:
            self.name_variants.append(name)

    def add_number_entry(self, number: int, date: str) -> None:
        """Add or update number history entry."""
        if not number:
            return

        # Update existing entry or create new one
        for entry in self.number_history:
            if entry['number'] == number:
                entry['last_seen'] = date
                return

        # New number
        self.number_history.append({
            'number': number,
            'first_seen': date,
            'last_seen': date
        })

        # Update primary number to most recent
        self.primary_number = number

    def add_position(self, position: str) -> None:
        """Add position to history if not present."""
        if position and position not in self.position_history:
            self.position_history.append(position)

    def add_game_entry(self, game_data: Dict) -> None:
        """Add game log entry."""
        self.game_log.append(game_data)


class RosterBuilder:
    """
    Build and update team rosters from gamesheet data.

    Handles player matching, stat aggregation, and roster persistence.
    """

    def __init__(self, team_id: str, team_name: str, season_id: str = None):
        """
        Initialize roster builder.

        Args:
            team_id: Team identifier
            team_name: Team name
            season_id: Optional season identifier
        """
        self.team_id = team_id
        self.team_name = team_name
        self.season_id = season_id
        self.players: List[PlayerIdentity] = []
        self.metadata = {
            'team_id': team_id,
            'team_name': team_name,
            'season_id': season_id,
            'last_updated': None,
            'total_games_analyzed': 0,
            'generation_type': 'new'
        }
        self.match_stats = {
            'exact_matches': 0,
            'fuzzy_matches': 0,
            'fuzzy_confidences': [],
            'number_changes': 0,
            'new_players': 0
        }

    def load_existing_roster(self, roster_path: Path) -> bool:
        """
        Load existing roster from JSON file.

        Args:
            roster_path: Path to roster.json

        Returns:
            True if loaded successfully, False otherwise
        """
        if not roster_path.exists():
            return False

        try:
            with open(roster_path, 'r') as f:
                data = json.load(f)

            self.metadata = data.get('metadata', self.metadata)
            self.metadata['generation_type'] = 'incremental'

            # Load players
            for player_data in data.get('players', []):
                player = PlayerIdentity(player_data)
                self.players.append(player)

            return True

        except Exception as e:
            print(f"Error loading roster: {e}")
            return False

    def add_game_data(self, game_data: Dict, team_side: str = 'home') -> None:
        """
        Add players from a single game's gamesheet data.

        Args:
            game_data: Parsed gamesheet data (game_{id}_extracted.json format)
            team_side: 'home' or 'away' to indicate which roster to process
        """
        game_id = game_data.get('game_id')
        game_metadata = game_data.get('game_metadata', {})
        game_date = game_metadata.get('date', '')

        # Determine which roster to process
        roster_key = f'{team_side}_roster'
        roster = game_data.get(roster_key, [])

        # Determine opponent
        if team_side == 'home':
            opponent = game_metadata.get('away_team', '')
            team_score = game_metadata.get('final_score', {}).get('home', 0)
            opponent_score = game_metadata.get('final_score', {}).get('away', 0)
        else:
            opponent = game_metadata.get('home_team', '')
            team_score = game_metadata.get('final_score', {}).get('away', 0)
            opponent_score = game_metadata.get('final_score', {}).get('home', 0)

        # Build scoring lookup (player number -> goals count)
        scoring_plays = game_data.get('scoring_plays', [])
        goals_by_player = Counter()
        for play in scoring_plays:
            if play.get('team') == team_side:
                goals_by_player[play.get('scorer_number')] += 1

        # Build goalie stats lookup
        goalie_stats_lookup = {}
        for goalie_stat in game_data.get('goalie_stats', []):
            if goalie_stat.get('team') == team_side:
                goalie_stats_lookup[goalie_stat.get('number')] = goalie_stat

        # Process each player in roster
        for player_data in roster:
            name = player_data.get('name')
            number = player_data.get('number')
            position = player_data.get('position')

            # Match or create player
            player_id, confidence = self._match_player({
                'name': name,
                'number': number,
                'position': position
            })

            if player_id:
                # Found existing player
                player = self._get_player_by_id(player_id)

                # Track match stats
                if confidence == 1.0:
                    self.match_stats['exact_matches'] += 1
                elif confidence >= 0.85:
                    self.match_stats['fuzzy_matches'] += 1
                    self.match_stats['fuzzy_confidences'].append(confidence)

                if confidence == 0.7:  # Number change
                    self.match_stats['number_changes'] += 1

                # Update player info
                player.add_name_variant(name)
                player.add_number_entry(number, game_date)
                player.add_position(position)
            else:
                # Create new player
                player = self._create_new_player(name, number, position, game_date)
                self.players.append(player)
                self.match_stats['new_players'] += 1

            # Add game entry
            goals = goals_by_player.get(number, 0)
            goalie_stats = goalie_stats_lookup.get(number)

            game_entry = {
                'game_id': game_id,
                'date': game_date,
                'opponent': opponent,
                'number_worn': number,
                'position': position,
                'goals': goals,
                'assists': 0,  # Not available in extracted data yet
                'penalty_minutes': 0,  # Not available in extracted data yet
                'data_source': 'gamesheet'
            }

            # Add goalie-specific stats if applicable
            if goalie_stats:
                game_entry['goals_allowed'] = goalie_stats.get('goals_allowed')
                game_entry['shots_faced'] = goalie_stats.get('shots_faced')
                game_entry['saves'] = goalie_stats.get('saves')

            player.add_game_entry(game_entry)

        # Update metadata
        self.metadata['total_games_analyzed'] += 1

    def _match_player(self, candidate: Dict) -> Tuple[Optional[str], float]:
        """
        Match candidate against existing players.

        Args:
            candidate: Dict with name, number, position

        Returns:
            Tuple of (player_id or None, confidence)
        """
        if not self.players:
            return None, 0.0

        # Convert players to dict format for matcher
        existing_players = [p.to_dict() for p in self.players]

        return match_player_by_number_and_name(candidate, existing_players)

    def _get_player_by_id(self, player_id: str) -> Optional[PlayerIdentity]:
        """Get player by ID."""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def _create_new_player(
        self,
        name: str,
        number: Optional[int],
        position: str,
        first_seen_date: str
    ) -> PlayerIdentity:
        """
        Create a new player identity.

        Args:
            name: Player name
            number: Jersey number
            position: Position
            first_seen_date: Date first seen

        Returns:
            New PlayerIdentity instance
        """
        player_id = f"player_{len(self.players) + 1:03d}"

        player_data = {
            'player_id': player_id,
            'primary_name': name,
            'name_variants': [name],
            'primary_number': number,
            'number_history': [
                {'number': number, 'first_seen': first_seen_date, 'last_seen': first_seen_date}
            ] if number else [],
            'primary_position': position,
            'position_history': [position] if position else [],
            'season_stats': {},
            'game_log': [],
            'data_quality': {
                'gamesheet_appearances': 0,
                'recap_mentions': 0,
                'confidence_score': 1.0
            }
        }

        return PlayerIdentity(player_data)

    def aggregate_stats(self) -> None:
        """Calculate season_stats from game_log for all players."""
        for player in self.players:
            stats = {
                'games_played': len(player.game_log),
                'goals': 0,
                'assists': 0,
                'points': 0,
                'penalty_minutes': 0,
                'goals_allowed': 0,
                'games_as_goalie': 0,
                'shutouts': 0
            }

            for game in player.game_log:
                stats['goals'] += game.get('goals', 0)
                stats['assists'] += game.get('assists', 0)
                stats['penalty_minutes'] += game.get('penalty_minutes', 0)

                # Goalie stats
                if game.get('goals_allowed') is not None:
                    stats['goals_allowed'] += game.get('goals_allowed', 0)
                    stats['games_as_goalie'] += 1
                    if game.get('goals_allowed', 0) == 0:
                        stats['shutouts'] += 1

            stats['points'] = stats['goals'] + stats['assists']

            player.season_stats = stats
            player.data_quality['gamesheet_appearances'] = stats['games_played']

    def get_team_summary(self) -> Dict:
        """Generate team summary with top performers."""
        summary = {
            'total_unique_players': len(self.players),
            'top_scorers': [],
            'starting_goalie': None
        }

        # Find top scorers (non-goalies)
        scorers = []
        for player in self.players:
            goals = player.season_stats.get('goals', 0)
            assists = player.season_stats.get('assists', 0)
            if goals > 0 or assists > 0:
                scorers.append({
                    'player_id': player.player_id,
                    'name': player.primary_name,
                    'number': player.primary_number,
                    'goals': goals,
                    'assists': assists,
                    'points': goals + assists
                })

        scorers.sort(key=lambda x: x['points'], reverse=True)
        summary['top_scorers'] = scorers[:5]

        # Find starting goalie (most games)
        goalies = []
        for player in self.players:
            games_as_goalie = player.season_stats.get('games_as_goalie', 0)
            if games_as_goalie > 0:
                goalies.append({
                    'player_id': player.player_id,
                    'name': player.primary_name,
                    'number': player.primary_number,
                    'games': games_as_goalie,
                    'goals_allowed': player.season_stats.get('goals_allowed', 0)
                })

        if goalies:
            goalies.sort(key=lambda x: x['games'], reverse=True)
            summary['starting_goalie'] = goalies[0]

        return summary

    def save_roster(self, output_path: Path, create_backup: bool = True) -> None:
        """
        Save roster to JSON file.

        Args:
            output_path: Path to save roster.json
            create_backup: Whether to backup existing file
        """
        # Create backup if requested
        if create_backup and output_path.exists():
            backup_path = output_path.parent / 'roster_backup.json'
            with open(output_path, 'r') as f_in, open(backup_path, 'w') as f_out:
                f_out.write(f_in.read())

        # Update metadata
        self.metadata['last_updated'] = datetime.now().isoformat()

        # Build roster data
        roster_data = {
            'metadata': self.metadata,
            'players': [p.to_dict() for p in self.players],
            'team_summary': self.get_team_summary()
        }

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(roster_data, f, indent=2)


__all__ = ['PlayerIdentity', 'RosterBuilder']

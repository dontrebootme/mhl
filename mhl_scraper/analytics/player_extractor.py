"""
Extract and analyze player information from game recap text.
"""

import re
from typing import List, Dict, Any, Set, Optional
from collections import Counter, defaultdict


# Common hockey-related words that might look like names but aren't
STOP_WORDS = {
    'hockey', 'game', 'period', 'goal', 'goals', 'score', 'scored', 'team', 'teams',
    'player', 'players', 'goalie', 'goaltender', 'coach', 'offensive', 'defensive',
    'power', 'play', 'penalty', 'minute', 'minutes', 'second', 'third', 'first',
    'final', 'win', 'loss', 'victory', 'defeat', 'match', 'contest', 'battle',
    'strong', 'performance', 'end', 'start', 'middle', 'thanks', 'including',
    'against', 'between', 'totems', 'thunderbirds', 'kraken', 'red', 'blue',
    'navy', 'white', 'black', 'green', 'however', 'although', 'addition'
}


def extract_players_from_text(text: str) -> List[str]:
    """
    Extract potential player names from text using pattern matching.

    Args:
        text: Game recap text

    Returns:
        List of potential player names (First Last format)
    """
    # Pattern: Capitalized First and Last name
    # Matches: "John Smith", "Carter Long", "Alexander Him"
    # Avoids: "Period", "Goals", single words
    name_pattern = r'\b([A-Z][a-z]+(?:\'[A-Z][a-z]+)?)\s+([A-Z][a-z]+(?:\'[A-Z][a-z]+)?)\b'

    matches = re.findall(name_pattern, text)

    names = []
    for first, last in matches:
        # Skip if either part is a stop word
        if first.lower() in STOP_WORDS or last.lower() in STOP_WORDS:
            continue

        # Skip if it's likely a team name or location
        if first in ['Jr', 'Sno', 'SJHA'] or last in ['Totems', 'Thunderbirds', 'Kraken', 'Hawks']:
            continue

        full_name = f"{first} {last}"
        names.append(full_name)

    return names


def extract_players_with_context(text: str) -> List[Dict[str, Any]]:
    """
    Extract player names with their surrounding context (action, role).

    Args:
        text: Game recap text

    Returns:
        List of dicts with player name, context, and role hints
    """
    players_with_context = []

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        # Extract names from this sentence
        names = extract_players_from_text(sentence)

        for name in names:
            context = {
                'name': name,
                'sentence': sentence.strip(),
                'is_scorer': False,
                'is_goalie': False,
                'has_penalty': False,
                'has_assist': False
            }

            sentence_lower = sentence.lower()

            # Check for scoring context
            if re.search(r'\b(goal|scored|tallied|netted)\b', sentence_lower):
                context['is_scorer'] = True

            # Check for goalie context
            if re.search(r'\b(goalie|goaltender|netminder|saves?|stops?)\b', sentence_lower):
                context['is_goalie'] = True

            # Check for penalty context
            if re.search(r'\b(penalty|penalized|minor|major)\b', sentence_lower):
                context['has_penalty'] = True

            # Check for assist context
            if re.search(r'\b(assist|helper|set.?up|pass)\b', sentence_lower):
                context['has_assist'] = True

            players_with_context.append(context)

    return players_with_context


def identify_top_performers(recap_texts: List[str], team_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze multiple game recaps to identify top performers.

    Args:
        recap_texts: List of game recap texts
        team_name: Optional team name to filter for

    Returns:
        Dictionary with top scorers, goalies, and frequently mentioned players
    """
    # Track player mentions and contexts
    all_players = []
    player_mention_count = Counter()
    player_roles = defaultdict(lambda: {'scorer': 0, 'goalie': 0, 'penalty': 0, 'assist': 0})

    for recap in recap_texts:
        # Filter for team if specified
        if team_name:
            # Simple check: is team mentioned in this recap?
            if team_name.lower() not in recap.lower():
                continue

        # Extract players with context
        players_in_game = extract_players_with_context(recap)
        all_players.extend(players_in_game)

        # Count mentions
        for player_data in players_in_game:
            name = player_data['name']
            player_mention_count[name] += 1

            if player_data['is_scorer']:
                player_roles[name]['scorer'] += 1
            if player_data['is_goalie']:
                player_roles[name]['goalie'] += 1
            if player_data['has_penalty']:
                player_roles[name]['penalty'] += 1
            if player_data['has_assist']:
                player_roles[name]['assist'] += 1

    # Identify top performers by category
    top_performers = {
        'most_mentioned': [],
        'top_scorers': [],
        'goalies': [],
        'playmakers': [],
        'penalty_prone': []
    }

    # Most mentioned (appears in most games)
    for name, count in player_mention_count.most_common(10):
        top_performers['most_mentioned'].append({
            'name': name,
            'games_mentioned': count,
            'total_mentions': len([p for p in all_players if p['name'] == name])
        })

    # Top scorers
    scorer_list = [(name, roles['scorer']) for name, roles in player_roles.items() if roles['scorer'] > 0]
    scorer_list.sort(key=lambda x: x[1], reverse=True)

    for name, scorer_count in scorer_list[:5]:
        top_performers['top_scorers'].append({
            'name': name,
            'scoring_mentions': scorer_count,
            'games_mentioned': player_mention_count[name]
        })

    # Goalies
    goalie_list = [(name, roles['goalie']) for name, roles in player_roles.items() if roles['goalie'] > 0]
    goalie_list.sort(key=lambda x: x[1], reverse=True)

    for name, goalie_count in goalie_list[:3]:
        top_performers['goalies'].append({
            'name': name,
            'goalie_mentions': goalie_count,
            'games_mentioned': player_mention_count[name]
        })

    # Playmakers (assists without as many goals)
    playmaker_list = [(name, roles['assist']) for name, roles in player_roles.items()
                      if roles['assist'] > 0 and roles['scorer'] < roles['assist']]
    playmaker_list.sort(key=lambda x: x[1], reverse=True)

    for name, assist_count in playmaker_list[:5]:
        top_performers['playmakers'].append({
            'name': name,
            'assist_mentions': assist_count,
            'games_mentioned': player_mention_count[name]
        })

    # Penalty prone
    penalty_list = [(name, roles['penalty']) for name, roles in player_roles.items() if roles['penalty'] > 1]
    penalty_list.sort(key=lambda x: x[1], reverse=True)

    for name, penalty_count in penalty_list[:5]:
        top_performers['penalty_prone'].append({
            'name': name,
            'penalty_mentions': penalty_count,
            'games_mentioned': player_mention_count[name]
        })

    return top_performers


def analyze_team_tendencies(parsed_recaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze team tendencies across multiple parsed game recaps.

    Args:
        parsed_recaps: List of parsed recap dicts from parse_game_recap()

    Returns:
        Dictionary with team tendency analysis
    """
    tendencies = {
        'total_games': len(parsed_recaps),
        'play_styles': Counter(),
        'period_strengths': {'first': 0, 'second': 0, 'third': 0, 'overtime': 0},
        'common_keywords': Counter(),
        'high_scoring_games': 0,
        'close_games': 0,
        'comeback_games': 0,
        'physical_games': 0,
        'penalty_heavy_games': 0,
        'avg_goals_for': 0.0,
        'avg_goals_against': 0.0
    }

    total_goals_for = 0
    total_goals_against = 0
    goals_counted = 0

    for recap in parsed_recaps:
        style = recap.get('game_style', {})
        metadata = recap.get('metadata', {})

        # Count style characteristics
        if style.get('is_high_scoring'):
            tendencies['high_scoring_games'] += 1
        if style.get('is_close_game'):
            tendencies['close_games'] += 1
        if style.get('is_comeback'):
            tendencies['comeback_games'] += 1
        if style.get('is_physical'):
            tendencies['physical_games'] += 1

        # Count keywords
        for keyword in style.get('keywords', []):
            tendencies['common_keywords'][keyword] += 1

        # Track penalties
        if len(recap.get('penalty_mentions', [])) > 2:
            tendencies['penalty_heavy_games'] += 1

        # Period strengths (more mentions = more action)
        period_breakdown = recap.get('period_breakdown', {})
        for period, sentences in period_breakdown.items():
            tendencies['period_strengths'][period] += len(sentences)

        # Calculate scoring averages (need to know which team is which)
        if 'away_score' in metadata and 'home_score' in metadata:
            # For now, just track that we have score data
            # In actual usage, we'd need to know if this team was home or away
            goals_counted += 1

    # Calculate percentages
    if tendencies['total_games'] > 0:
        tendencies['high_scoring_pct'] = round(tendencies['high_scoring_games'] / tendencies['total_games'] * 100, 1)
        tendencies['close_game_pct'] = round(tendencies['close_games'] / tendencies['total_games'] * 100, 1)
        tendencies['comeback_pct'] = round(tendencies['comeback_games'] / tendencies['total_games'] * 100, 1)
        tendencies['physical_pct'] = round(tendencies['physical_games'] / tendencies['total_games'] * 100, 1)

    return tendencies


__all__ = ['extract_players_from_text', 'identify_top_performers', 'extract_players_with_context', 'analyze_team_tendencies']

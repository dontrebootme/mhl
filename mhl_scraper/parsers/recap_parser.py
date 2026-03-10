"""
Parser for extracting structured data from game recap text.
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime


def extract_recap_metadata(recap_text: str) -> Dict[str, Any]:
    """
    Extract metadata from game recap text (header section).

    Args:
        recap_text: Full game recap text including headers

    Returns:
        Dictionary with game_id, date, teams, score, level
    """
    metadata = {}

    lines = recap_text.strip().split('\n')

    for line in lines:
        line = line.strip()

        # Game ID: 2914741
        if line.startswith('Game ID:'):
            metadata['game_id'] = line.split(':', 1)[1].strip()

        # Date: Sat Oct 4, 2025
        elif line.startswith('Date:'):
            metadata['date'] = line.split(':', 1)[1].strip()

        # Teams: Team A @ Team B
        elif line.startswith('Teams:'):
            teams_str = line.split(':', 1)[1].strip()
            # Split on @ or vs
            if ' @ ' in teams_str:
                parts = teams_str.split(' @ ')
            elif ' vs ' in teams_str:
                parts = teams_str.split(' vs ')
            else:
                parts = [teams_str, '']

            metadata['away_team'] = parts[0].strip() if len(parts) > 0 else ''
            metadata['home_team'] = parts[1].strip() if len(parts) > 1 else ''
            metadata['teams'] = teams_str

        # Score: 8 - 7
        elif line.startswith('Score:'):
            score_str = line.split(':', 1)[1].strip()
            metadata['score_string'] = score_str

            # Parse score
            score_match = re.search(r'(\d+)\s*-\s*(\d+)', score_str)
            if score_match:
                metadata['away_score'] = int(score_match.group(1))
                metadata['home_score'] = int(score_match.group(2))

        # Level: 10U C
        elif line.startswith('Level:'):
            metadata['level'] = line.split(':', 1)[1].strip()

        # Title: ...
        elif line.startswith('Title:'):
            metadata['title'] = line.split(':', 1)[1].strip()

    return metadata


def extract_scoring_mentions(recap_text: str) -> List[str]:
    """
    Extract goal-scoring mentions from recap text.

    Returns:
        List of sentences mentioning goals/scoring
    """
    scoring_keywords = [
        r'\bgoal',
        r'\bscored',
        r'\bscoring',
        r'\btallied',
        r'\bnetted',
        r'back of the net',
        r'\bgoals?\b',
    ]

    pattern = '|'.join(scoring_keywords)

    sentences = re.split(r'[.!?]+', recap_text)
    scoring_sentences = []

    for sentence in sentences:
        if re.search(pattern, sentence, re.IGNORECASE):
            scoring_sentences.append(sentence.strip())

    return scoring_sentences


def extract_penalty_mentions(recap_text: str) -> List[str]:
    """
    Extract penalty mentions from recap text.

    Returns:
        List of sentences mentioning penalties
    """
    penalty_keywords = [
        r'\bpenalt(?:y|ies)',
        r'\bminor',
        r'\bmajor',
        r'\bmisconduct',
        r'penalty box',
        r'power play',
        r'short.?handed',
    ]

    pattern = '|'.join(penalty_keywords)

    sentences = re.split(r'[.!?]+', recap_text)
    penalty_sentences = []

    for sentence in sentences:
        if re.search(pattern, sentence, re.IGNORECASE):
            penalty_sentences.append(sentence.strip())

    return penalty_sentences


def extract_goalie_mentions(recap_text: str) -> List[str]:
    """
    Extract goalie/goaltender mentions from recap text.

    Returns:
        List of sentences mentioning goalies
    """
    goalie_keywords = [
        r'\bgoalie',
        r'\bgoaltender',
        r'\bgoalkeeper',
        r'\bnetminder',
        r'\bsaved?',
        r'\bstops?',
        r'in net',
        r'in goal',
        r'between the pipes',
    ]

    pattern = '|'.join(goalie_keywords)

    sentences = re.split(r'[.!?]+', recap_text)
    goalie_sentences = []

    for sentence in sentences:
        if re.search(pattern, sentence, re.IGNORECASE):
            goalie_sentences.append(sentence.strip())

    return goalie_sentences


def extract_period_mentions(recap_text: str) -> Dict[str, List[str]]:
    """
    Extract mentions by period from recap text.

    Returns:
        Dictionary with period numbers as keys and sentences as values
    """
    periods = {
        'first': [],
        'second': [],
        'third': [],
        'overtime': []
    }

    sentences = re.split(r'[.!?]+', recap_text)

    for sentence in sentences:
        sentence_lower = sentence.lower()

        if 'first period' in sentence_lower or 'opening period' in sentence_lower:
            periods['first'].append(sentence.strip())
        elif 'second period' in sentence_lower or 'middle period' in sentence_lower:
            periods['second'].append(sentence.strip())
        elif 'third period' in sentence_lower or 'final period' in sentence_lower:
            periods['third'].append(sentence.strip())
        elif 'overtime' in sentence_lower or 'ot' in sentence_lower:
            periods['overtime'].append(sentence.strip())

    return periods


def classify_game_style(recap_text: str, score_diff: Optional[int] = None) -> Dict[str, Any]:
    """
    Classify the game style based on recap keywords and score.

    Args:
        recap_text: Full game recap text
        score_diff: Absolute score difference (optional)

    Returns:
        Dictionary with style classifications
    """
    text_lower = recap_text.lower()

    style = {
        'is_high_scoring': False,
        'is_close_game': False,
        'is_physical': False,
        'is_fast_paced': False,
        'is_defensive': False,
        'is_comeback': False,
        'keywords': []
    }

    # High scoring indicators
    high_scoring_keywords = ['high-scoring', 'offensive', 'back-and-forth', 'shootout', 'goal fest']
    if any(kw in text_lower for kw in high_scoring_keywords):
        style['is_high_scoring'] = True
        style['keywords'].extend([kw for kw in high_scoring_keywords if kw in text_lower])

    # Close game indicators
    close_game_keywords = ['close', 'tight', 'nail-biter', 'thriller', 'decided late']
    if any(kw in text_lower for kw in close_game_keywords) or (score_diff is not None and score_diff <= 1):
        style['is_close_game'] = True
        style['keywords'].extend([kw for kw in close_game_keywords if kw in text_lower])

    # Physical game indicators
    physical_keywords = ['physical', 'hard-hitting', 'aggressive', 'chippy', 'tough']
    if any(kw in text_lower for kw in physical_keywords):
        style['is_physical'] = True
        style['keywords'].extend([kw for kw in physical_keywords if kw in text_lower])

    # Fast-paced indicators
    fast_paced_keywords = ['fast-paced', 'up-tempo', 'rapid', 'quick', 'high-tempo']
    if any(kw in text_lower for kw in fast_paced_keywords):
        style['is_fast_paced'] = True
        style['keywords'].extend([kw for kw in fast_paced_keywords if kw in text_lower])

    # Defensive game indicators
    defensive_keywords = ['defensive', 'low-scoring', 'defensive battle', 'stingy']
    if any(kw in text_lower for kw in defensive_keywords):
        style['is_defensive'] = True
        style['keywords'].extend([kw for kw in defensive_keywords if kw in text_lower])

    # Comeback indicators
    comeback_keywords = ['comeback', 'rallied', 'rally', 'battled back', 'overcame', 'erased']
    if any(kw in text_lower for kw in comeback_keywords):
        style['is_comeback'] = True
        style['keywords'].extend([kw for kw in comeback_keywords if kw in text_lower])

    return style


def parse_game_recap(recap_text: str) -> Dict[str, Any]:
    """
    Parse a complete game recap and extract all relevant data.

    Args:
        recap_text: Full game recap text

    Returns:
        Dictionary with all extracted data
    """
    metadata = extract_recap_metadata(recap_text)

    # Calculate score difference if scores are available
    score_diff = None
    if 'away_score' in metadata and 'home_score' in metadata:
        score_diff = abs(metadata['away_score'] - metadata['home_score'])

    parsed_data = {
        'metadata': metadata,
        'scoring_mentions': extract_scoring_mentions(recap_text),
        'penalty_mentions': extract_penalty_mentions(recap_text),
        'goalie_mentions': extract_goalie_mentions(recap_text),
        'period_breakdown': extract_period_mentions(recap_text),
        'game_style': classify_game_style(recap_text, score_diff),
        'raw_text': recap_text
    }

    return parsed_data

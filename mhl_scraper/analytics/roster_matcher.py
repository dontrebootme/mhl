"""
Fuzzy matching utilities for player identification across games.

Handles name variations, jersey number changes, and player identity matching
using difflib-based similarity scoring.
"""

from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


def normalize_name(name: str) -> str:
    """
    Normalize a player name for comparison.

    Removes periods, converts to lowercase, and trims excess whitespace.

    Args:
        name: Player name to normalize

    Returns:
        Normalized name string

    Examples:
        >>> normalize_name("Henry Mangrobang")
        'henry mangrobang'
        >>> normalize_name("H. Mangrobang")
        'h mangrobang'
        >>> normalize_name("  John   O'Connor  ")
        "john o'connor"
    """
    if not name:
        return ""

    # Remove periods, lowercase, collapse whitespace
    normalized = name.replace('.', '').lower()
    normalized = ' '.join(normalized.split())

    return normalized


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names using SequenceMatcher.

    Args:
        name1: First name to compare
        name2: Second name to compare

    Returns:
        Similarity score between 0.0 and 1.0

    Examples:
        >>> calculate_name_similarity("Henry Mangrobang", "H. Mangrobang")
        0.88  # High similarity
        >>> calculate_name_similarity("John Smith", "Jane Doe")
        0.22  # Low similarity
    """
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return 0.0

    # Exact match after normalization
    if norm1 == norm2:
        return 1.0

    # Use SequenceMatcher for fuzzy comparison
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    return round(similarity, 2)


def match_player_by_number_and_name(
    candidate: Dict,
    existing_players: List[Dict],
    threshold: float = 0.85
) -> Tuple[Optional[str], float]:
    """
    Match a candidate player against existing players using priority-based matching.

    Matching Priority:
        1. Exact Match (1.0): Same name AND same number
        2. Strong Match (0.9): Same number AND name >85% similar
        3. Name Match (0.8): Name >90% similar AND position matches
        4. Number Change (0.7): Exact name BUT different number
        5. Uncertain (<0.7): Low similarity, create new player

    Args:
        candidate: Dict with 'name', 'number', 'position' keys
        existing_players: List of player dicts with same keys plus 'player_id',
                         'primary_name', 'name_variants', 'primary_number'
        threshold: Minimum confidence score to accept match (default: 0.85)

    Returns:
        Tuple of (player_id or None, confidence_score)

    Examples:
        >>> candidate = {'name': 'H. Mangrobang', 'number': 13, 'position': 'G'}
        >>> existing = [{
        ...     'player_id': 'player_001',
        ...     'primary_name': 'Henry Mangrobang',
        ...     'name_variants': ['Henry Mangrobang'],
        ...     'primary_number': 13,
        ...     'primary_position': 'G'
        ... }]
        >>> match_player_by_number_and_name(candidate, existing)
        ('player_001', 0.9)  # Strong match: same number, high name similarity
    """
    candidate_name = candidate.get('name', '')
    candidate_number = candidate.get('number')
    candidate_position = candidate.get('position', '')

    if not candidate_name:
        return None, 0.0

    best_match = None
    best_confidence = 0.0

    for player in existing_players:
        player_id = player.get('player_id')
        primary_name = player.get('primary_name', '')
        name_variants = player.get('name_variants', [])
        primary_number = player.get('primary_number')
        primary_position = player.get('primary_position', '')

        # Check all name variants
        all_names = [primary_name] + name_variants

        for existing_name in all_names:
            name_similarity = calculate_name_similarity(candidate_name, existing_name)

            # Priority 1: Exact Match (1.0)
            if name_similarity == 1.0 and candidate_number == primary_number:
                return player_id, 1.0

            # Priority 2: Strong Match (0.9)
            # Same number AND high name similarity
            if candidate_number == primary_number and name_similarity >= 0.85:
                confidence = 0.9
                if confidence > best_confidence:
                    best_match = player_id
                    best_confidence = confidence

            # Priority 3: Name Match (0.8)
            # Very high name similarity AND position matches
            elif name_similarity >= 0.90 and candidate_position == primary_position:
                confidence = 0.8
                if confidence > best_confidence:
                    best_match = player_id
                    best_confidence = confidence

            # Priority 4: Number Change (0.7)
            # Exact name match BUT different number
            elif name_similarity == 1.0 and candidate_number != primary_number:
                confidence = 0.7
                if confidence > best_confidence:
                    best_match = player_id
                    best_confidence = confidence

    # Only return match if it meets threshold
    if best_confidence >= threshold:
        return best_match, best_confidence

    return None, best_confidence


__all__ = [
    'normalize_name',
    'calculate_name_similarity',
    'match_player_by_number_and_name'
]

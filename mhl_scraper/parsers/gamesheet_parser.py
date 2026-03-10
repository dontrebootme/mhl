"""
Parser for extracting structured data from TeamLinkt gamesheet PDFs.

TeamLinkt gamesheets use a text-based layout rather than structured tables.
Data is arranged in columns and must be parsed from raw text using regex patterns.

See .kiro/steering/gamesheet-pdf-format.md for detailed format documentation.
"""

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class GamesheetParsingError(Exception):
    """Base exception for gamesheet parsing errors."""
    pass


class GamesheetPDFError(GamesheetParsingError):
    """Raised when PDF is corrupted or unreadable."""
    pass


def parse_gamesheet_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extract all data from a gamesheet PDF.

    Args:
        pdf_path: Path to the gamesheet PDF file

    Returns:
        Dictionary with extracted game data including:
        - game_metadata: Basic game info (teams, score, date, location)
        - home_roster: List of home team players
        - away_roster: List of away team players
        - scoring_summary: List of goals with details
        - penalty_summary: List of penalties
        - goalie_stats: Goalie performance data
        - parsing_errors: List of any errors encountered during parsing

    Raises:
        GamesheetPDFError: If the PDF is corrupted or unreadable
    """
    logger.info(f"Parsing gamesheet PDF: {pdf_path}")

    result = {
        'game_metadata': {},
        'home_roster': [],
        'away_roster': [],
        'scoring_summary': [],
        'penalty_summary': [],
        'goalie_stats': [],
        'parsing_errors': []
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            full_text = ""
            page_texts = []

            for page in pdf.pages:
                page_text = page.extract_text() or ""
                page_texts.append(page_text)
                full_text += page_text + "\n"

            # Parse each section independently to allow partial success
            # Page 1 contains main game data
            page1_text = page_texts[0] if page_texts else ""

            # Page 2 contains game summary with location and date
            page2_text = page_texts[1] if len(page_texts) > 1 else ""

            # Extract metadata (uses both pages)
            try:
                result['game_metadata'] = extract_game_metadata(page1_text, page2_text)
                game_id = result['game_metadata'].get('game_id', 'unknown')
                logger.debug(f"Extracted metadata for game {game_id}")
            except Exception as e:
                logger.warning(f"Failed to extract game metadata from {pdf_path}: {e}")
                result['parsing_errors'].append({
                    'section': 'game_metadata',
                    'error': str(e),
                    'file': pdf_path
                })

            # Extract rosters
            try:
                home_roster, away_roster = extract_rosters(page1_text)
                result['home_roster'] = home_roster
                result['away_roster'] = away_roster
                logger.debug(f"Extracted rosters: {len(home_roster)} home players, {len(away_roster)} away players")
            except Exception as e:
                logger.warning(f"Failed to extract rosters from {pdf_path}: {e}")
                result['parsing_errors'].append({
                    'section': 'rosters',
                    'error': str(e),
                    'file': pdf_path
                })

            # Extract scoring summary
            try:
                result['scoring_summary'] = extract_scoring_summary(page1_text)
                logger.debug(f"Extracted {len(result['scoring_summary'])} goals")
            except Exception as e:
                logger.warning(f"Failed to extract scoring summary from {pdf_path}: {e}")
                result['parsing_errors'].append({
                    'section': 'scoring_summary',
                    'error': str(e),
                    'file': pdf_path
                })

            # Extract penalties
            try:
                result['penalty_summary'] = extract_penalty_summary(page1_text)
                logger.debug(f"Extracted {len(result['penalty_summary'])} penalties")
            except Exception as e:
                logger.warning(f"Failed to extract penalties from {pdf_path}: {e}")
                result['parsing_errors'].append({
                    'section': 'penalty_summary',
                    'error': str(e),
                    'file': pdf_path
                })

            # Extract goalie stats
            try:
                result['goalie_stats'] = extract_goalie_stats(
                    page1_text,
                    result['home_roster'],
                    result['away_roster']
                )
                logger.debug(f"Extracted {len(result['goalie_stats'])} goalie stat entries")
            except Exception as e:
                logger.warning(f"Failed to extract goalie stats from {pdf_path}: {e}")
                result['parsing_errors'].append({
                    'section': 'goalie_stats',
                    'error': str(e),
                    'file': pdf_path
                })

            # Associate goals and penalties with teams based on player numbers
            try:
                result['scoring_summary'] = associate_goals_with_teams(
                    result['scoring_summary'],
                    result['home_roster'],
                    result['away_roster']
                )
                logger.debug("Associated goals with teams")
            except Exception as e:
                logger.warning(f"Failed to associate goals with teams in {pdf_path}: {e}")

            try:
                result['penalty_summary'] = associate_penalties_with_teams(
                    result['penalty_summary'],
                    result['home_roster'],
                    result['away_roster']
                )
                logger.debug("Associated penalties with teams")
            except Exception as e:
                logger.warning(f"Failed to associate penalties with teams in {pdf_path}: {e}")

            # Apply final position logic:
            # - Players who appear in goalie_stats are "Goalie" (they actually played)
            # - All other players are "Skater"
            try:
                result['home_roster'], result['away_roster'] = apply_position_from_goalie_stats(
                    result['home_roster'],
                    result['away_roster'],
                    result['goalie_stats']
                )
                logger.debug("Applied goalie positions from stats")
            except Exception as e:
                logger.warning(f"Failed to apply goalie positions in {pdf_path}: {e}")

            # Log parsing summary
            errors_count = len(result['parsing_errors'])
            if errors_count > 0:
                logger.warning(
                    f"Gamesheet {pdf_path} parsed with {errors_count} error(s): "
                    f"{[e['section'] for e in result['parsing_errors']]}"
                )
            else:
                game_id = result['game_metadata'].get('game_id', 'unknown')
                logger.info(
                    f"Successfully parsed gamesheet {pdf_path} (game {game_id}): "
                    f"{len(result['home_roster'])} home players, "
                    f"{len(result['away_roster'])} away players, "
                    f"{len(result['scoring_summary'])} goals, "
                    f"{len(result['penalty_summary'])} penalties"
                )

            return result

    except PdfminerException as e:
        logger.error(f"PDF is corrupted or unreadable: {pdf_path} - {e}")
        raise GamesheetPDFError(f"PDF is corrupted or unreadable: {e}")
    except Exception as e:
        logger.error(f"Failed to open PDF {pdf_path}: {e}")
        raise GamesheetPDFError(f"Failed to open PDF: {e}")


def extract_game_metadata(page1_text: str, page2_text: str) -> Dict[str, Any]:
    """
    Extract game metadata from gamesheet text.

    Extracts all game information required by Requirements 7.1-7.7:
    - game_id: Unique identifier for the game (7.6)
    - date: Game date in YYYY-MM-DD format (7.1)
    - time: Game start time (7.2)
    - location: Rink/arena name (7.3)
    - home_team: Home team name (7.4)
    - away_team: Away team name (7.4)
    - home_score: Final score for home team (7.5)
    - away_score: Final score for away team (7.5)

    Args:
        page1_text: Text from page 1 (main gamesheet)
        page2_text: Text from page 2 (game summary)

    Returns:
        Dictionary with structured metadata object (7.7) containing:
        - game_id: str or None
        - date: str (YYYY-MM-DD format) or None
        - time: str (start time) or None
        - location: str or None
        - home_team: str or None
        - away_team: str or None
        - home_score: int or None
        - away_score: int or None
        - Additional fields: date_display, start_time, end_time, division, period_scores
    """
    metadata = {}
    lines = page1_text.split('\n') if page1_text else []

    # Line 1: Team names (home on left, away on right)
    # Format: "Jr Kraken 10U (Navy) Sno-King Jr. Thunderbirds 10U C (O'Connor)"
    # Teams are NOT separated by multiple spaces - need to find the boundary
    if lines:
        team_line = lines[0].strip()
        # Try to split on common team name patterns
        # Look for pattern where one team name ends and another begins
        # Usually there's a closing paren followed by a capital letter
        team_split = re.match(r'^(.+?\))\s+([A-Z].+)$', team_line)
        if team_split:
            metadata['home_team'] = team_split.group(1).strip()
            metadata['away_team'] = team_split.group(2).strip()
        else:
            # Fallback: try splitting on multiple spaces
            teams = re.split(r'\s{2,}', team_line)
            if len(teams) >= 2:
                metadata['home_team'] = teams[0].strip()
                metadata['away_team'] = teams[-1].strip()
            elif team_line:
                # Last resort: just store the whole line
                metadata['teams_raw'] = team_line

    # Line 2: Game info - Month Day Year GameID Division
    if len(lines) > 1:
        info_match = re.match(r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})\s+(\d+)\s+(\w+)', lines[1])
        if info_match:
            month, day, year, game_id, division = info_match.groups()
            metadata['game_id'] = game_id
            metadata['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            metadata['division'] = division

    # Extract location from page 1 (appears on its own line)
    # Common patterns: "KCI - Starbucks", "Sno-King Renton - Small"
    location_pattern = r'^([A-Z][A-Za-z\s\-]+(?:Rink|Arena|Ice|Center|Centre|Small|Large|Starbucks)[A-Za-z\s\-]*)$'
    for line in lines:
        line = line.strip()
        # Look for location-like lines (contain common rink keywords)
        if any(kw in line for kw in ['Rink', 'Arena', 'Ice', 'KCI', 'Sno-King', 'Center', 'Centre']):
            if not any(char.isdigit() for char in line[:10]):  # Avoid lines starting with numbers
                metadata['location'] = line
                break

    # Extract from page 2 if available (more reliable location/date info)
    if page2_text:
        p2_lines = page2_text.split('\n')
        if p2_lines:
            # First line is usually location
            metadata['location'] = p2_lines[0].strip()

        # Look for date/time line: "November 2, 2025 2:45PM - 3:45PM"
        date_pattern = r'(\w+\s+\d{1,2},\s+\d{4})\s+(\d{1,2}:\d{2}[AP]M)\s*-\s*(\d{1,2}:\d{2}[AP]M)'
        for line in p2_lines:
            date_match = re.search(date_pattern, line)
            if date_match:
                metadata['date_display'] = date_match.group(1)
                metadata['start_time'] = date_match.group(2)
                metadata['end_time'] = date_match.group(3)
                break

    # Extract period scores from page 1
    # Pattern: rows like "1 1 4 0 6" and "4 5 2 0 11"
    score_pattern = r'^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$'
    score_lines = []
    for line in lines:
        line = line.strip()
        match = re.match(score_pattern, line)
        if match:
            score_lines.append([int(x) for x in match.groups()])

    if len(score_lines) >= 2:
        # First score line is home, second is away
        metadata['home_score'] = score_lines[0][4]  # Total is last column
        metadata['away_score'] = score_lines[1][4]
        metadata['period_scores'] = {
            'home': {'p1': score_lines[0][0], 'p2': score_lines[0][1], 'p3': score_lines[0][2], 'ot': score_lines[0][3]},
            'away': {'p1': score_lines[1][0], 'p2': score_lines[1][1], 'p3': score_lines[1][2], 'ot': score_lines[1][3]}
        }

    # Set 'time' field to start_time for consistency with design document schema (Requirement 7.2)
    # The design document expects a 'time' field representing the game start time
    if 'start_time' in metadata:
        metadata['time'] = metadata['start_time']

    return metadata


def extract_rosters(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract player rosters for both teams from gamesheet text.

    The gamesheet format has home players on the left side of lines and away players
    on the right side. Names may be mixed case OR ALL CAPS depending on the gamesheet.

    Line format examples:
    - "10 Calvin Havens 10:35PM 11:35PM 11 SHINWOO LEE"
    - "G 13 Henry Mangrobang 1 15:02 #60 EV 1 11:13 #31 EV 13 CHRISTOPHER BAYHA"
    - "11 MILO LYONS 11:30AM 12:30PM 13 CHRISTOPHER BAYHA" (both ALL CAPS)

    Args:
        text: Full text from page 1 of gamesheet

    Returns:
        Tuple of (home_roster, away_roster) where each is a list of player dicts
        with 'number', 'name', and optional 'position' fields
    """
    home_roster = []
    away_roster = []

    lines = text.split('\n')

    for line in lines:
        line_stripped = line.strip()

        # Skip empty lines and lines that look like scores/stats
        if not line_stripped or re.match(r'^\d+\s+\d+\s+\d+\s+\d+\s+\d+$', line_stripped):
            continue

        # Skip staff lines (TV, TM, TR prefixes)
        if re.match(r'^(TV|TM|TR)\s+', line_stripped):
            # But check for away goalie at end: "TV Jason Koceja G 89 CALEB MARTORANA"
            away_goalie_match = re.search(r'G\s+(\d+)\s+([A-Z][A-Z\s\'\-]+)\s*$', line)
            if away_goalie_match:
                number, name = away_goalie_match.groups()
                away_roster.append({
                    'number': number,
                    'name': normalize_player_name(name),
                    'position': 'Goalie'
                })
            continue

        # Extract HOME player from start of line
        # Pattern: [Position] Number Name (mixed case or ALL CAPS)
        # Position codes: G, F, D, C, CF, LW, RW

        # Try mixed case first: "G 13 Henry Mangrobang"
        home_match = re.match(
            r'^(?:([GFDCLRW]{1,2})\s+)?(\d{1,3})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\'\-]+)+)',
            line_stripped
        )
        if home_match:
            position, number, name = home_match.groups()
            if ' ' in name:
                home_roster.append({
                    'number': number,
                    'name': name.strip(),
                    'position': classify_position(position)
                })
        else:
            # Try ALL CAPS: "11 MILO LYONS" or "G 23 PAYTON COOPER"
            home_caps_match = re.match(
                r'^(?:([GFDCLRW]{1,2})\s+)?(\d{1,3})\s+([A-Z][A-Z\'\-]+(?:\s+[A-Z][A-Z\'\-]+)+)',
                line_stripped
            )
            if home_caps_match:
                position, number, name = home_caps_match.groups()
                name = name.strip()
                # Make sure it's a real name (not goal entries like "1 00:00")
                if ' ' in name and not re.match(r'^\d', name) and len(name) > 4:
                    # Check it's not a time pattern
                    if not re.search(r'\d{1,2}:\d{2}', name):
                        home_roster.append({
                            'number': number,
                            'name': normalize_player_name(name),
                            'position': classify_position(position)
                        })

        # Extract AWAY player from end of line
        # Away players appear at the RIGHT side of lines, can be ALL CAPS or mixed case
        # Examples:
        #   "11 SHINWOO LEE 9:15AM 10:15AM 1 Marcus Mazal"  -> "1 Marcus Mazal"
        #   "G 80 ETHAN BABKIN 97 Ramiro Rogers Espinoza"  -> "97 Ramiro Rogers Espinoza"
        #   "13 CHRISTOPHER BAYHA 1 00:00 #31 EV G 17 Liam Allen" -> "G 17 Liam Allen"

        # First check for goalie pattern at end: "G 17 Liam Allen" or "G 80 ETHAN BABKIN"
        # Match both ALL CAPS and mixed case names
        away_goalie_match = re.search(r'G\s+(\d+)\s+([A-Z][A-Za-z\'\-]+(?:\s+[A-Za-z\'\-]+)+)\s*$', line)
        if away_goalie_match:
            number, name = away_goalie_match.groups()
            name = name.strip()
            if len(name) > 3 and ' ' in name:  # Must be a real name
                away_roster.append({
                    'number': number,
                    'name': normalize_player_name(name),
                    'position': 'Goalie'
                })
        else:
            # Regular away player at end of line - match both ALL CAPS and mixed case
            # Pattern: Number Name (where Name has at least first and last name)
            # Examples: "1 Marcus Mazal", "97 Ramiro Rogers Espinoza", "11 SHINWOO LEE"
            away_match = re.search(r'(\d{1,3})\s+([A-Z][A-Za-z\'\-]+(?:\s+[A-Za-z\'\-]+)+)\s*$', line)
            if away_match:
                number, name = away_match.groups()
                name = name.strip()
                # Verify this is a real name (at least 2 parts, not just "EV" or "PP")
                # Also exclude common non-name patterns and staff roles
                if (len(name) > 3 and ' ' in name and
                    name.upper() not in ('EV', 'PP', 'SH', 'EN') and
                    not re.match(r'^\d', name) and  # Doesn't start with digit
                    not re.search(r'\d{1,2}:\d{2}', name) and  # No time patterns
                    not re.search(r'\b[MTX]\s+[A-Z]', name)):  # No staff markers (M=Manager, T=Trainer, X=?)
                    away_roster.append({
                        'number': number,
                        'name': normalize_player_name(name),
                        'position': None
                    })

    # Deduplicate rosters (same number = same player)
    home_roster = deduplicate_roster(home_roster)
    away_roster = deduplicate_roster(away_roster)

    return home_roster, away_roster


def deduplicate_roster(roster: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate players based on jersey number."""
    seen_numbers = set()
    unique_roster = []
    for player in roster:
        if player['number'] not in seen_numbers:
            seen_numbers.add(player['number'])
            unique_roster.append(player)
    return unique_roster


def normalize_player_name(name: str) -> str:
    """
    Normalize player name to consistent "First Last" format.

    Handles:
    - "SMITH, JOHN" -> "John Smith"
    - "JOHN SMITH" -> "John Smith"
    - "john smith" -> "John Smith"
    - "Smith, J." -> "J. Smith"

    Args:
        name: Raw player name string

    Returns:
        Normalized name in "First Last" format
    """
    if not name or not name.strip():
        return ""

    name = name.strip()

    # Handle "LAST, FIRST" format
    if ',' in name:
        parts = name.split(',', 1)
        if len(parts) == 2:
            last = parts[0].strip()
            first = parts[1].strip()
            name = f"{first} {last}"

    # Title case each word
    words = name.split()
    normalized_words = []
    for word in words:
        if word:
            # Handle names with apostrophes (O'Connor) and hyphens (Zhang-Shen)
            if "'" in word:
                parts = word.split("'")
                word = "'".join(p.capitalize() for p in parts)
            elif "-" in word:
                parts = word.split("-")
                word = "-".join(p.capitalize() for p in parts)
            else:
                word = word.capitalize()
            normalized_words.append(word)

    return " ".join(normalized_words)


def classify_position(position_code: Optional[str]) -> Optional[str]:
    """
    Classify position code as 'Skater' or 'Goalie'.

    Args:
        position_code: Raw position code (G, F, D, CF, etc.)

    Returns:
        'Goalie' for goalies, 'Skater' for all other positions, None if unknown
    """
    if not position_code:
        return None

    position_code = position_code.upper().strip()

    if position_code == 'G':
        return 'Goalie'
    elif position_code in ('F', 'D', 'C', 'CF', 'LW', 'RW', 'LD', 'RD'):
        return 'Skater'

    return None


def apply_position_from_goalie_stats(
    home_roster: List[Dict[str, Any]],
    away_roster: List[Dict[str, Any]],
    goalie_stats: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Apply final position logic based on goalie stats.

    - Players who appear in goalie_stats AND actually played are marked as "Goalie"
    - A goalie "played" if they have goals_allowed > 0, OR saves > 0, OR shots_against > 0
    - If a goalie has all zeros, they were listed but didn't play (backup)
    - Exception: if only one goalie is listed for a team, they played (even with a shutout)
    - All other players are marked as "Skater"

    Args:
        home_roster: Home team roster
        away_roster: Away team roster
        goalie_stats: List of goalie statistics

    Returns:
        Tuple of (home_roster, away_roster) with updated positions
    """
    # Separate goalies by team
    home_goalies = [g for g in goalie_stats if g.get('team') == 'home']
    away_goalies = [g for g in goalie_stats if g.get('team') == 'away']

    def goalie_has_stats(goalie: Dict[str, Any]) -> bool:
        """Check if goalie has any non-zero stats indicating they played."""
        goals_allowed = goalie.get('goals_allowed', 0)
        saves = goalie.get('saves') or 0
        shots_against = goalie.get('shots_against') or 0
        goals_by_period = goalie.get('goals_by_period', {})
        period_total = sum(goals_by_period.values()) if goals_by_period else 0

        return goals_allowed > 0 or saves > 0 or shots_against > 0 or period_total > 0

    def get_playing_goalies(goalies: List[Dict[str, Any]]) -> set:
        """Determine which goalies actually played."""
        if not goalies:
            return set()

        # If only one goalie listed, they played (even with shutout/0 stats)
        if len(goalies) == 1:
            return {goalies[0].get('number')}

        # Multiple goalies: only include those with non-zero stats
        playing = {g.get('number') for g in goalies if goalie_has_stats(g)}

        # If no goalies have stats (rare - maybe a 0-0 game?), include the first one
        if not playing and goalies:
            playing.add(goalies[0].get('number'))

        return playing

    home_goalie_numbers = get_playing_goalies(home_goalies)
    away_goalie_numbers = get_playing_goalies(away_goalies)

    # Update home roster positions
    for player in home_roster:
        if player['number'] in home_goalie_numbers:
            player['position'] = 'Goalie'
        else:
            player['position'] = 'Skater'

    # Update away roster positions
    for player in away_roster:
        if player['number'] in away_goalie_numbers:
            player['position'] = 'Goalie'
        else:
            player['position'] = 'Skater'

    return home_roster, away_roster


def extract_scoring_summary(text: str) -> List[Dict[str, Any]]:
    """
    Extract all goals from gamesheet text.

    Args:
        text: Full text from page 1 of gamesheet

    Returns:
        List of goal dictionaries with:
        - period: int (1, 2, 3, or OT)
        - time: str (MM:SS format)
        - scorer_number: str (jersey number of scorer)
        - assist_numbers: List[str] (jersey numbers of assisters, 0-2 elements)
        - strength: str ('EV', 'PP', 'SH', 'EN')
        - team: str or None (will be populated by associate_goals_with_teams)
        - scorer: str or None (player name, populated after team association)
        - assists: List[str] (player names, populated after team association)

    Note:
        The scorer and assists fields are initially None/empty and are populated
        by associate_goals_with_teams() which maps jersey numbers to player names.
    """
    goals = []

    # Goal pattern: Period Time #Jersey [#Assist1] [#Assist2] Type [Notes]
    # Examples:
    #   1 15:02 #60 EV
    #   1 00:00 #40 #7 EV
    #   2 11:22 #7 EV
    #   3 04:23 #33 #7 #22 PP
    goal_pattern = r'(\d)\s+(\d{1,2}:\d{2})\s+#(\d+)(?:\s+#(\d+))?(?:\s+#(\d+))?\s+(EV|PP|SH|EN)'

    matches = re.findall(goal_pattern, text)

    for match in matches:
        period, time, scorer, assist1, assist2, strength = match

        assist_numbers = []
        if assist1:
            assist_numbers.append(assist1)
        if assist2:
            assist_numbers.append(assist2)

        goals.append({
            'period': int(period),
            'time': time,
            'scorer_number': scorer,
            'assist_numbers': assist_numbers,
            'strength': strength,
            'team': None,  # Will be determined by matching scorer to roster
            'scorer': None,  # Player name, populated after team association
            'assists': []  # Player names, populated after team association
        })

    return goals


def extract_penalty_summary(text: str) -> List[Dict[str, Any]]:
    """
    Extract all penalties from gamesheet text.

    Args:
        text: Full text from page 1 of gamesheet

    Returns:
        List of penalty dictionaries with:
        - period: int (1, 2, 3, or OT)
        - time: str (MM:SS format when penalty was called)
        - player_number: str (jersey number of penalized player)
        - player: str or None (player name, populated after team association)
        - infraction: str (type of penalty, e.g., "Interference", "Tripping")
        - duration: int (penalty duration in minutes)
        - penalty_type: str ('MIN', 'MAJ', 'MIS', 'GM')
        - team: str or None (will be populated by associate_penalties_with_teams)

    Note:
        The player and team fields are initially None and are populated
        by associate_penalties_with_teams() which maps jersey numbers to player names.
    """
    penalties = []

    # Penalty pattern: Period #Jersey Type-Infraction Duration Time Time Time
    # Examples:
    #   2 #93 MIN-Interference 2 00:00 00:00 14:00
    #   3 #22 MIN-Attempt to Injure 2 00:00 00:00 14:00
    #   1 #15 MAJ-Fighting 5 12:30 00:00 14:00
    #   2 #8 MIS-Misconduct 10 05:45 00:00 14:00
    #   3 #44 GM-Game Misconduct 10 00:00 00:00 14:00
    # The first time after duration is typically when the penalty was called
    penalty_pattern = r'(\d)\s+#(\d+)\s+(MIN|MAJ|MIS|GM)-([A-Za-z\s]+?)\s+(\d+)\s+(\d{1,2}:\d{2})'

    matches = re.findall(penalty_pattern, text)

    for match in matches:
        period, player_number, penalty_type, infraction, duration, time = match

        # Parse and validate duration
        duration_int = int(duration)

        # Enforce minimum durations based on penalty type
        # MIN (Minor) = 2 minutes
        # MAJ (Major) = 5 minutes
        # MIS (Misconduct) = 10 minutes
        # GM (Game Misconduct) = 10 minutes (player ejected)
        if penalty_type == 'MIN' and duration_int < 2:
            duration_int = 2
        elif penalty_type == 'MAJ' and duration_int < 5:
            duration_int = 5
        elif penalty_type in ('MIS', 'GM') and duration_int < 10:
            duration_int = 10

        # Cap duration at 10 minutes (game misconducts are the max)
        # Note: Some leagues may have different rules, but 10 is standard max
        if duration_int > 10:
            duration_int = 10

        penalties.append({
            'period': int(period),
            'time': time,
            'player_number': player_number,
            'player': None,  # Will be populated by associate_penalties_with_teams
            'infraction': infraction.strip(),
            'duration': duration_int,
            'penalty_type': penalty_type,
            'team': None  # Will be determined by matching player to roster
        })

    return penalties


def extract_goalie_stats(
    text: str,
    home_roster: List[Dict[str, Any]],
    away_roster: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract goalie statistics from gamesheet text.

    This function extracts goalie performance data including:
    - Jersey number and name (from roster matching)
    - Goals allowed (total and by period)
    - Shots against, saves, and save percentage (when available)

    The function handles multiple goalies per team and calculates save percentage
    when shots_against data is available.

    Args:
        text: Full text from page 1 of gamesheet
        home_roster: Home team roster (to identify goalies)
        away_roster: Away team roster (to identify goalies)

    Returns:
        List of goalie stat dictionaries with:
        - team: 'home' or 'away'
        - number: Jersey number (str)
        - name: Player name (str or None)
        - goals_allowed: Total goals allowed (int)
        - goals_by_period: Dict with p1, p2, p3, ot goals (int)
        - shots_against: Total shots faced (int or None)
        - saves: Total saves made (int or None)
        - save_percentage: Save percentage 0.0-1.0 (float or None)

    Note:
        Returns empty list if no goalie stats are found (Requirements 6.6).
        Handles multiple goalies per team (Requirements 6.4).
    """
    goalie_stats = []

    # Find goalies from rosters (players marked with 'G' position)
    home_goalies = [p for p in home_roster if p.get('position') == 'Goalie']
    away_goalies = [p for p in away_roster if p.get('position') == 'Goalie']

    # Primary pattern: Goalie stats row with jersey number prefix
    # Format: #Number P1_GA P2_GA P3_GA OT_GA Total_GA [additional stats...]
    # Example: #13 4 5 2 0 11 0 0 0 0 0
    # The additional 5 numbers after total may include shots/saves in some formats
    goalie_stat_pattern = r'#(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+))?'

    matches = re.findall(goalie_stat_pattern, text)

    for match in matches:
        # Unpack match - may have 6 or 11 groups depending on format
        number = match[0]
        p1 = int(match[1])
        p2 = int(match[2])
        p3 = int(match[3])
        ot = int(match[4])
        total_ga = int(match[5])

        # Additional stats (if present) - interpretation varies by format
        # Some formats may include: shots_against, saves, etc.
        additional_stats = [int(x) if x else None for x in match[6:11]]

        # Determine team and name by matching number to roster
        team, name = _find_goalie_in_rosters(
            number, home_goalies, away_goalies, home_roster, away_roster
        )

        # Extract shots_against and saves if available in additional stats
        # Common format: [shots_against, saves, ...] or all zeros if not tracked
        shots_against = None
        saves = None
        save_percentage = None

        if additional_stats and any(s is not None and s > 0 for s in additional_stats):
            # Try to interpret additional stats
            # If first additional stat is larger than goals_allowed, it might be shots_against
            if additional_stats[0] is not None and additional_stats[0] >= total_ga:
                shots_against = additional_stats[0]
                # Calculate saves: shots_against - goals_allowed
                saves = shots_against - total_ga
                # Calculate save percentage
                save_percentage = calculate_save_percentage(shots_against, saves)

        goalie_stats.append({
            'team': team,
            'number': number,
            'name': name,
            'goals_allowed': total_ga,
            'goals_by_period': {
                'p1': p1,
                'p2': p2,
                'p3': p3,
                'ot': ot
            },
            'shots_against': shots_against,
            'saves': saves,
            'save_percentage': save_percentage
        })

    # If no goalie stats found via pattern, try to identify goalies from roster
    # and create placeholder entries (they played but stats weren't in expected format)
    if not goalie_stats:
        goalie_stats = _create_goalie_entries_from_roster(
            home_goalies, away_goalies, text
        )

    return goalie_stats


def _find_goalie_in_rosters(
    number: str,
    home_goalies: List[Dict[str, Any]],
    away_goalies: List[Dict[str, Any]],
    home_roster: List[Dict[str, Any]],
    away_roster: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Find a goalie by jersey number in the rosters.

    Args:
        number: Jersey number to find
        home_goalies: List of home team goalies
        away_goalies: List of away team goalies
        home_roster: Full home team roster
        away_roster: Full away team roster

    Returns:
        Tuple of (team, name) where team is 'home' or 'away' (or None)
        and name is the player's name (or None)
    """
    # First check goalies specifically
    for goalie in home_goalies:
        if goalie['number'] == number:
            return 'home', goalie['name']

    for goalie in away_goalies:
        if goalie['number'] == number:
            return 'away', goalie['name']

    # If not found in goalie list, check all players
    for player in home_roster:
        if player['number'] == number:
            return 'home', player['name']

    for player in away_roster:
        if player['number'] == number:
            return 'away', player['name']

    return None, None


def _create_goalie_entries_from_roster(
    home_goalies: List[Dict[str, Any]],
    away_goalies: List[Dict[str, Any]],
    text: str
) -> List[Dict[str, Any]]:
    """
    Create goalie stat entries from roster when detailed stats aren't available.

    This is a fallback when the goalie stats row pattern isn't found in the text.
    We create entries for goalies identified in the roster with None for stats.

    Args:
        home_goalies: List of home team goalies from roster
        away_goalies: List of away team goalies from roster
        text: Full gamesheet text (for potential future parsing)

    Returns:
        List of goalie stat dictionaries with basic info (stats set to None)
    """
    goalie_stats = []

    for goalie in home_goalies:
        goalie_stats.append({
            'team': 'home',
            'number': goalie['number'],
            'name': goalie['name'],
            'goals_allowed': None,
            'goals_by_period': None,
            'shots_against': None,
            'saves': None,
            'save_percentage': None
        })

    for goalie in away_goalies:
        goalie_stats.append({
            'team': 'away',
            'number': goalie['number'],
            'name': goalie['name'],
            'goals_allowed': None,
            'goals_by_period': None,
            'shots_against': None,
            'saves': None,
            'save_percentage': None
        })

    return goalie_stats


def calculate_save_percentage(shots_against: Optional[int], saves: Optional[int]) -> Optional[float]:
    """
    Calculate goalie save percentage.

    Save percentage = saves / shots_against

    Args:
        shots_against: Total shots faced by goalie
        saves: Total saves made by goalie

    Returns:
        Save percentage as float between 0.0 and 1.0, or None if calculation
        is not possible (missing data or zero shots)

    Note:
        - Returns None if shots_against is None, 0, or negative
        - Returns None if saves is None or negative
        - Clamps result to [0.0, 1.0] range for validity
    """
    if shots_against is None or shots_against <= 0:
        return None

    if saves is None or saves < 0:
        return None

    # Calculate save percentage
    save_pct = saves / shots_against

    # Clamp to valid range [0.0, 1.0]
    # This handles edge cases where data might be inconsistent
    save_pct = max(0.0, min(1.0, save_pct))

    return save_pct


def associate_goals_with_teams(
    goals: List[Dict[str, Any]],
    home_roster: List[Dict[str, Any]],
    away_roster: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Associate each goal with the correct team based on scorer's jersey number.
    Also populates scorer name and assist names from the rosters.

    Args:
        goals: List of goal dictionaries with scorer_number and assist_numbers
        home_roster: Home team roster
        away_roster: Away team roster

    Returns:
        Goals list with 'team', 'scorer', and 'assists' fields populated.
        - team: 'home' or 'away' based on which roster contains the scorer
        - scorer: Player name from roster (or jersey number if not found)
        - assists: List of player names (or jersey numbers if not found)
    """
    # Build lookup dictionaries for jersey number -> player name
    home_players = {p['number']: p['name'] for p in home_roster}
    away_players = {p['number']: p['name'] for p in away_roster}

    home_numbers = set(home_players.keys())
    away_numbers = set(away_players.keys())

    for goal in goals:
        scorer_num = goal.get('scorer_number')
        assist_nums = goal.get('assist_numbers', [])

        # Determine team and get player lookup based on scorer
        if scorer_num in home_numbers:
            goal['team'] = 'home'
            player_lookup = home_players
        elif scorer_num in away_numbers:
            goal['team'] = 'away'
            player_lookup = away_players
        else:
            # Scorer not found in either roster - leave team as None
            # Use combined lookup for name resolution
            player_lookup = {**home_players, **away_players}

        # Populate scorer name
        goal['scorer'] = player_lookup.get(scorer_num, f"#{scorer_num}")

        # Populate assist names
        # Assists should be from the same team as the scorer
        assists = []
        for assist_num in assist_nums:
            assist_name = player_lookup.get(assist_num, f"#{assist_num}")
            assists.append(assist_name)
        goal['assists'] = assists

    return goals


def associate_penalties_with_teams(
    penalties: List[Dict[str, Any]],
    home_roster: List[Dict[str, Any]],
    away_roster: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Associate each penalty with the correct team based on player's jersey number.
    Also populates the player name from the roster.

    Args:
        penalties: List of penalty dictionaries with player_number
        home_roster: Home team roster
        away_roster: Away team roster

    Returns:
        Penalties list with 'team' and 'player' fields populated.
        - team: 'home' or 'away' based on which roster contains the player
        - player: Player name from roster (or jersey number if not found)
    """
    # Build lookup dictionaries for jersey number -> player name
    home_players = {p['number']: p['name'] for p in home_roster}
    away_players = {p['number']: p['name'] for p in away_roster}

    home_numbers = set(home_players.keys())
    away_numbers = set(away_players.keys())

    for penalty in penalties:
        player_num = penalty.get('player_number')

        # Determine team and get player lookup based on player number
        if player_num in home_numbers:
            penalty['team'] = 'home'
            penalty['player'] = home_players.get(player_num, f"#{player_num}")
        elif player_num in away_numbers:
            penalty['team'] = 'away'
            penalty['player'] = away_players.get(player_num, f"#{player_num}")
        else:
            # Player not found in either roster - leave team as None
            # Use combined lookup for name resolution
            combined_players = {**home_players, **away_players}
            penalty['player'] = combined_players.get(player_num, f"#{player_num}")

    return penalties


# =============================================================================
# JSON Export Functionality
# =============================================================================
# Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6

import json
from .gamesheet_models import GamesheetData, GameMetadata, Player, Goal, Penalty, GoalieStats


class GamesheetSerializationError(GamesheetParsingError):
    """Raised when JSON serialization fails."""
    pass


def save_gamesheet_json(
    parsed_data: Dict[str, Any],
    pdf_path: str,
    output_path: Optional[str] = None
) -> str:
    """
    Save parsed gamesheet data as JSON file.

    Saves the structured data extracted from a gamesheet PDF to a JSON file
    with a consistent schema. The JSON file is placed alongside the source PDF
    by default, with '_extracted.json' suffix.

    Args:
        parsed_data: Dictionary containing parsed gamesheet data from parse_gamesheet_pdf()
        pdf_path: Path to the source PDF file (used for generating output filename)
        output_path: Optional explicit output path. If None, generates path from pdf_path.

    Returns:
        Path to the saved JSON file

    Raises:
        GamesheetSerializationError: If JSON serialization fails

    Requirements:
        - 8.1: Save structured data as JSON file
        - 8.2: Include all extracted data (metadata, rosters, scoring, penalties, goalie stats)
        - 8.3: Use consistent schema across all gamesheets
        - 8.4: Include game ID in filename
        - 8.5: Place JSON file in same directory as source PDF
        - 8.6: Raise exception with details on serialization error
    """
    game_id = parsed_data.get('game_metadata', {}).get('game_id', 'unknown')
    logger.debug(f"Saving gamesheet JSON for game {game_id} from {pdf_path}")

    # Generate output path if not provided
    if output_path is None:
        output_path = generate_json_path(pdf_path, parsed_data)

    # Convert to GamesheetData model for consistent schema
    try:
        gamesheet_data = dict_to_gamesheet_data(parsed_data)
        json_dict = gamesheet_data.to_dict()
    except Exception as e:
        logger.error(f"Failed to convert parsed data to schema for {pdf_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to convert parsed data to consistent schema: {e}"
        )

    # Serialize to JSON
    try:
        json_str = json.dumps(json_dict, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize gamesheet data to JSON for {pdf_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to serialize gamesheet data to JSON: {e}"
        )

    # Write to file
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json_str, encoding='utf-8')
    except (IOError, OSError) as e:
        logger.error(f"Failed to write JSON file to {output_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to write JSON file to {output_path}: {e}"
        )

    logger.info(f"Saved gamesheet JSON to {output_path} (game {game_id})")
    return str(output_path)


def generate_json_path(pdf_path: str, parsed_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate JSON output path from PDF path.

    Creates a JSON filename based on the source PDF path, placing the JSON file
    in the same directory as the PDF. If game_id is available in parsed_data,
    it's included in the filename.

    Args:
        pdf_path: Path to the source PDF file
        parsed_data: Optional parsed data containing game_id in metadata

    Returns:
        Path for the JSON output file

    Requirements:
        - 8.4: Include game ID in filename for easy identification
        - 8.5: Place JSON file in same directory as source PDF
    """
    pdf_file = Path(pdf_path)

    # Try to get game_id from parsed data
    game_id = None
    if parsed_data:
        metadata = parsed_data.get('game_metadata', {})
        game_id = metadata.get('game_id')

    # Generate filename
    if game_id:
        # Use game_id in filename: game_{game_id}_extracted.json
        json_filename = f"game_{game_id}_extracted.json"
    else:
        # Fallback: use PDF filename with _extracted.json suffix
        json_filename = pdf_file.stem + "_extracted.json"

    # Place in same directory as PDF
    json_path = pdf_file.parent / json_filename

    return str(json_path)


def dict_to_gamesheet_data(parsed_data: Dict[str, Any]) -> GamesheetData:
    """
    Convert parsed dictionary data to GamesheetData model.

    Transforms the raw dictionary output from parse_gamesheet_pdf() into
    a structured GamesheetData object with proper dataclass instances.

    Args:
        parsed_data: Dictionary from parse_gamesheet_pdf()

    Returns:
        GamesheetData instance with all data properly structured

    Requirements:
        - 8.2: Include all extracted data
        - 8.3: Use consistent schema
    """
    # Convert game metadata
    metadata_dict = parsed_data.get('game_metadata', {})
    game_metadata = GameMetadata(
        game_id=metadata_dict.get('game_id'),
        date=metadata_dict.get('date'),
        time=metadata_dict.get('time') or metadata_dict.get('start_time'),
        location=metadata_dict.get('location'),
        home_team=metadata_dict.get('home_team'),
        away_team=metadata_dict.get('away_team'),
        home_score=metadata_dict.get('home_score'),
        away_score=metadata_dict.get('away_score'),
    )

    # Convert home roster
    home_roster = [
        Player(
            number=p.get('number', ''),
            name=p.get('name', ''),
            position=p.get('position'),
        )
        for p in parsed_data.get('home_roster', [])
    ]

    # Convert away roster
    away_roster = [
        Player(
            number=p.get('number', ''),
            name=p.get('name', ''),
            position=p.get('position'),
        )
        for p in parsed_data.get('away_roster', [])
    ]

    # Convert scoring summary
    scoring_summary = [
        Goal(
            period=g.get('period', 0),
            time=g.get('time', ''),
            team=g.get('team', ''),
            scorer=g.get('scorer', ''),
            assists=g.get('assists', []),
            strength=g.get('strength', 'EV'),
        )
        for g in parsed_data.get('scoring_summary', [])
    ]

    # Convert penalty summary
    penalty_summary = [
        Penalty(
            period=p.get('period', 0),
            time=p.get('time', ''),
            team=p.get('team', ''),
            player=p.get('player', ''),
            infraction=p.get('infraction', ''),
            duration=p.get('duration', 0),
        )
        for p in parsed_data.get('penalty_summary', [])
    ]

    # Convert goalie stats
    goalie_stats = [
        GoalieStats(
            team=g.get('team', ''),
            number=g.get('number', ''),
            name=g.get('name', ''),
            shots_against=g.get('shots_against'),
            saves=g.get('saves'),
            goals_allowed=g.get('goals_allowed'),
            save_percentage=g.get('save_percentage'),
        )
        for g in parsed_data.get('goalie_stats', [])
    ]

    return GamesheetData(
        game_metadata=game_metadata,
        home_roster=home_roster,
        away_roster=away_roster,
        scoring_summary=scoring_summary,
        penalty_summary=penalty_summary,
        goalie_stats=goalie_stats,
    )


def load_gamesheet_json(json_path: str) -> GamesheetData:
    """
    Load gamesheet data from JSON file.

    Reads a JSON file created by save_gamesheet_json() and returns
    a GamesheetData object.

    Args:
        json_path: Path to the JSON file

    Returns:
        GamesheetData instance loaded from the file

    Raises:
        GamesheetSerializationError: If loading or parsing fails
    """
    logger.debug(f"Loading gamesheet JSON from {json_path}")
    try:
        json_file = Path(json_path)
        json_str = json_file.read_text(encoding='utf-8')
        data = json.loads(json_str)
        result = GamesheetData.from_dict(data)
        logger.debug(f"Successfully loaded gamesheet JSON from {json_path}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {json_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to parse JSON from {json_path}: {e}"
        )
    except (IOError, OSError) as e:
        logger.error(f"Failed to read JSON file {json_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to read JSON file {json_path}: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to load gamesheet data from {json_path}: {e}")
        raise GamesheetSerializationError(
            f"Failed to load gamesheet data from {json_path}: {e}"
        )

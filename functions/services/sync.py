"""Sync service for data synchronization from TeamLinkt.

Handles scheduled data synchronization with smart scheduling logic
based on game day patterns and incremental updates.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from clients.teamlinkt import TeamLinktClient
from models.game import Game
from models.standing import Standing
from services.cache import CacheService, Season, Division, Team


logger = logging.getLogger(__name__)

# Pacific timezone for game day detection
PACIFIC_TZ = ZoneInfo('America/Los_Angeles')

# Metadata keys
LAST_SYNC_KEY = 'last_sync_timestamp'
ACTIVE_SEASON_KEY = 'active_season_id'


@dataclass
class SyncResult:
    """Result of a sync operation.

    Attributes:
        inserted: Number of new records inserted
        updated: Number of existing records updated
        unchanged: Number of records that were unchanged
        errors: List of error messages encountered
        skipped: True if sync was skipped due to timing
    """
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def total_processed(self) -> int:
        """Total number of records processed."""
        return self.inserted + self.updated + self.unchanged



class SyncService:
    """Service for synchronizing data from TeamLinkt to cache.

    Implements simple time-based scheduling to minimize Firestore reads:
    - Weekend (Sat/Sun) 8am-6pm PT: sync every trigger
    - Weekday (Mon-Fri): sync only at 8am PT

    This approach uses ZERO Firestore reads for scheduling decisions,
    eliminating the ~3,000 reads per trigger from the old smart scheduling.

    Attributes:
        cache: CacheService instance for data storage
        teamlinkt: TeamLinktClient instance for API calls
    """

    # Time-based scheduling constants
    WEEKEND_SYNC_START_HOUR = 8   # 8am PT
    WEEKEND_SYNC_END_HOUR = 22    # 10pm PT (exclusive)
    WEEKDAY_SYNC_HOUR = 8         # 8am PT
    WEEKDAY_SYNC_WINDOW_MINUTES = 30  # Allow 30 min window for scheduler variance

    def __init__(self, cache: CacheService, teamlinkt: TeamLinktClient):
        """Initialize the sync service.

        Args:
            cache: CacheService instance for data storage
            teamlinkt: TeamLinktClient instance for API calls
        """
        self.cache = cache
        self.teamlinkt = teamlinkt

    def should_sync(self, now: Optional[datetime] = None) -> bool:
        """Determine if sync should run based on time only.

        Simple time-based scheduling with ZERO Firestore reads.

        Schedule:
        - Weekends (Sat/Sun): Run every trigger from 8am-6pm PT
        - Weekdays (Mon-Fri): Run only at 8am PT (within 30 min window)

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5

        Args:
            now: Current datetime (defaults to now in Pacific time)

        Returns:
            True if sync should run based on time only
        """
        if now is None:
            now = datetime.now(tz=PACIFIC_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=PACIFIC_TZ)

        is_weekend = now.weekday() >= 5  # Sat=5, Sun=6
        hour = now.hour

        if is_weekend:
            # Weekends: sync every 30 min from 8am-6pm PT
            should_run = self.WEEKEND_SYNC_START_HOUR <= hour < self.WEEKEND_SYNC_END_HOUR
            if should_run:
                logger.info(f"[SYNC] Weekend {hour}:00 PT - within sync window (8am-6pm)")
            else:
                logger.info(f"[SYNC] Weekend {hour}:00 PT - outside sync window (8am-6pm)")
            return should_run
        else:
            # Weekdays: sync once at 8am PT
            # Scheduler triggers at 8am, so check we're in that window
            should_run = hour == self.WEEKDAY_SYNC_HOUR and now.minute < self.WEEKDAY_SYNC_WINDOW_MINUTES
            if should_run:
                logger.info(f"[SYNC] Weekday {hour}:{now.minute:02d} PT - within 8am sync window")
            else:
                logger.info(f"[SYNC] Weekday {hour}:{now.minute:02d} PT - outside 8am sync window")
            return should_run


    def detect_active_season(self, force_refresh: bool = False) -> Optional[str]:
        """Detect the active season, using cached value if available.

        This method checks for a cached active_season_id first (1 Firestore read).
        If cached, returns immediately without scanning seasons/divisions/games.
        If not cached, runs expensive detection and caches the result.

        Requirements: 3.1, 3.2, 3.3, 3.5

        Args:
            force_refresh: If True, bypass cache and run expensive detection

        Returns:
            Season ID of the active season, or None if no seasons found
        """
        # Check for cached active_season_id first (1 read)
        if not force_refresh:
            cached_result = self.cache.get_metadata(ACTIVE_SEASON_KEY)
            if cached_result.cache_hit and cached_result.data:
                logger.info(f"[SYNC] Using cached active_season_id: {cached_result.data}")
                return cached_result.data

        # Fall back to expensive detection
        logger.info("[SYNC] No cached active_season_id, detecting...")
        season_id = self._detect_active_season_expensive()

        # Cache for future runs (no TTL - updated when new season detected)
        if season_id:
            self.cache.set_metadata(ACTIVE_SEASON_KEY, season_id, ttl_hours=0)
            logger.info(f"[SYNC] Cached active_season_id: {season_id}")

        return season_id

    def _detect_active_season_expensive(self) -> Optional[str]:
        """Expensive detection of active season by scanning all games.

        This method scans all seasons, divisions, and games to find the
        active season. It should only be called when cache is empty.

        Returns:
            Season ID of the active season, or None if no seasons found
        """
        # First try to get seasons from cache
        seasons_result = self.cache.get_seasons()

        if not seasons_result.cache_hit or not seasons_result.data:
            # Try fetching from TeamLinkt
            try:
                seasons_data = self.teamlinkt.get_seasons()
                if not seasons_data:
                    return None
                # Return the first (most recent) season
                return str(seasons_data[0]['id'])
            except Exception as e:
                logger.error(f"Failed to fetch seasons: {e}")
                return None

        seasons = seasons_result.data
        if not seasons:
            return None

        now = datetime.now(tz=PACIFIC_TZ)
        today = now.date()

        # Check each season for games around current date
        best_season = None
        best_score = -1

        for season in seasons:
            # Get divisions for this season
            divisions_result = self.cache.get_divisions(season.id)
            if not divisions_result.cache_hit:
                continue

            season_has_recent_games = False
            season_has_future_games = False

            for division in divisions_result.data:
                games_result = self.cache.get_games(season.id, division.id)
                if not games_result.cache_hit:
                    continue

                for game in games_result.data:
                    try:
                        game_date = datetime.strptime(game.date, '%Y-%m-%d').date()
                        days_diff = (game_date - today).days

                        # Game within last 30 days
                        if -30 <= days_diff <= 0:
                            season_has_recent_games = True
                        # Game within next 60 days
                        if 0 <= days_diff <= 60:
                            season_has_future_games = True
                    except ValueError:
                        continue

            # Score the season based on game proximity
            score = 0
            if season_has_recent_games:
                score += 1
            if season_has_future_games:
                score += 2

            if score > best_score:
                best_score = score
                best_season = season.id

        # If no season found with games, return the first one
        if best_season is None and seasons:
            best_season = seasons[0].id

        return best_season

    def _fetch_teamlinkt_games(
        self,
        season_id: str,
        division_id: str,
        team_to_division: Optional[dict[str, str]] = None,
        team_name_to_id: Optional[dict[str, str]] = None
    ) -> list[Game]:
        """Fetch games and scores from TeamLinkt API and merge into Game objects.

        Fetches both scheduled games and completed games with scores from TeamLinkt,
        merges them (scores take precedence), and converts to Game objects.

        Requirements: 2.1

        Args:
            season_id: Season identifier
            division_id: Division identifier
            team_to_division: Optional mapping of team_name to child division_id
            team_name_to_id: Optional mapping of team_name to team_id

        Returns:
            List of Game objects from TeamLinkt
        """
        # Fetch scheduled games (FREE - external API)
        games_data = self.teamlinkt.get_games(
            season_id=season_id,
            division_id=division_id,
            team_id='all'
        )
        logger.info(f"[SYNC] TeamLinkt returned {len(games_data)} scheduled games")

        # Fetch completed games with scores (FREE - external API)
        scores_data = self.teamlinkt.get_scores(
            season_id=season_id,
            division_id=division_id,
            team_id='all'
        )
        logger.info(f"[SYNC] TeamLinkt returned {len(scores_data)} completed games")

        # Merge: scores_data takes precedence (has actual scores)
        games_by_id = {str(g.get('game_id')): g for g in games_data}
        for score in scores_data:
            game_id = str(score.get('game_id'))
            games_by_id[game_id] = score  # Overwrite with scored version

        all_games_data = list(games_by_id.values())
        logger.info(f"[SYNC] Total unique games after merge: {len(all_games_data)}")

        # Convert to Game objects
        games = []
        for game_data in all_games_data:
            try:
                game = self._convert_game_data(
                    game_data, season_id, division_id, team_to_division, team_name_to_id
                )
                games.append(game)
            except Exception as e:
                logger.error(f"[SYNC] Error converting game {game_data.get('game_id', 'unknown')}: {e}")

        return games

    def sync_division(
        self,
        season_id: str,
        division_id: str,
        force: bool = False
    ) -> SyncResult:
        """Sync games for a specific division using bulk compare strategy.

        Uses bulk compare strategy to minimize Firestore reads:
        1. Fetch all games from TeamLinkt (FREE - external API)
        2. Fetch all existing games from Firestore in ONE query
        3. Compare in memory using _game_changed() helper
        4. Batch write only changed games

        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.1, 4.2, 4.3, 4.4, 4.5

        Args:
            season_id: Season identifier
            division_id: Division identifier
            force: If True, skip the should_sync check

        Returns:
            SyncResult with counts of inserted, updated, unchanged records
        """
        import time
        import traceback

        result = SyncResult()
        start_time = time.time()

        # Requirement 4.1: Log start with context
        logger.info(
            f"[SYNC] Starting division sync (bulk compare): "
            f"season_id={season_id}, division_id={division_id}, force={force}"
        )

        # Check if sync should run
        if not force and not self.should_sync():
            result.skipped = True
            logger.info(f"[SYNC] Skipped division {division_id} due to time-based scheduling")
            return result

        try:
            # Build team-to-division mapping for proper division assignment
            team_to_division = self.build_team_division_mapping(season_id, division_id)

            # Build team name-to-id mapping to populate team IDs in games
            team_name_to_id = self.build_team_name_to_id_mapping(season_id, division_id)

            # Step 1: Fetch all games from TeamLinkt (FREE - external API)
            # Requirements 2.1: Fetch from TeamLinkt first, no Firestore reads
            teamlinkt_games = self._fetch_teamlinkt_games(
                season_id, division_id, team_to_division, team_name_to_id
            )
            logger.info(f"[SYNC] Fetched {len(teamlinkt_games)} games from TeamLinkt")

            if not teamlinkt_games:
                logger.warning(f"[SYNC] No games returned for division {division_id}")

            # Step 2: Fetch all existing games from Firestore by game_id
            # Requirements 2.2: Single bulk query instead of per-game lookups
            # Note: We query by game_id (not division_id) because games may be
            # stored under child division_ids different from the parent division
            # we're syncing. This ensures we find existing games regardless of
            # which division they were assigned to.
            game_ids = [g.game_id for g in teamlinkt_games]
            existing_result = self.cache.get_games_by_ids(game_ids)
            existing_by_id = {g.game_id: g for g in (existing_result.data or [])}
            logger.info(f"[SYNC] Fetched {len(existing_by_id)} existing games from Firestore (batch lookup)")

            # Step 3: Compare in memory (FREE - CPU only)
            # Requirements 2.3, 2.4, 2.5: Compare and collect changed games
            games_to_write = []
            for game in teamlinkt_games:
                existing = existing_by_id.get(game.game_id)
                if existing is None:
                    # New game - needs to be inserted
                    games_to_write.append(game)
                    result.inserted += 1
                    logger.info(
                        f"[SYNC] INSERT game {game.game_id}: "
                        f"{game.away_team} @ {game.home_team} ({game.date}) "
                        f"[division={game.division_id}]"
                    )
                elif self._game_changed(existing, game):
                    # Changed game - needs to be updated
                    games_to_write.append(game)
                    result.updated += 1
                    logger.info(
                        f"[SYNC] UPDATE game {game.game_id}: "
                        f"{game.away_team} @ {game.home_team} ({game.date}) "
                        f"[division={game.division_id}]"
                    )
                else:
                    # Unchanged game - skip
                    result.unchanged += 1
                    logger.debug(f"[SYNC] SKIP unchanged game {game.game_id}")

            logger.info(
                f"[SYNC] Comparison: {result.inserted} new, "
                f"{result.updated} changed, {result.unchanged} unchanged"
            )

            # Step 4: Batch write changes (N WRITES, batched)
            # Requirements 2.6: Use batch writes for efficiency
            if games_to_write:
                written = self._batch_write_games(games_to_write)
                logger.info(f"[SYNC] Batch wrote {written} games")

            # Update last sync timestamp
            self._update_last_sync()

            # Requirement 4.4: Log completion summary
            duration = time.time() - start_time
            logger.info(
                f"[SYNC] Division {division_id} complete: "
                f"inserted={result.inserted}, updated={result.updated}, "
                f"unchanged={result.unchanged}, errors={len(result.errors)}, "
                f"duration={duration:.2f}s"
            )

        except Exception as e:
            # Requirement 4.5: Log errors with full context
            error_msg = f"Failed to sync division {division_id}: {e}"
            logger.error(
                f"[SYNC] {error_msg}\n"
                f"Context: season_id={season_id}, division_id={division_id}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )
            result.errors.append(error_msg)

        return result


    def sync_standings(
        self,
        season_id: str,
        division_id: str,
        force: bool = False
    ) -> SyncResult:
        """Sync standings for a specific division using bulk compare.

        Fetches standings from TeamLinkt and compares with existing data,
        only writing standings that have actually changed.

        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5

        Args:
            season_id: Season identifier
            division_id: Division identifier
            force: If True, skip the should_sync check

        Returns:
            SyncResult with counts of updated records
        """
        import traceback

        result = SyncResult()

        logger.info(
            f"[SYNC] Starting standings sync: "
            f"season_id={season_id}, division_id={division_id}, force={force}"
        )

        # Check if sync should run
        if not force and not self.should_sync():
            result.skipped = True
            logger.info(f"[SYNC] Standings sync skipped for division {division_id}")
            return result

        try:
            # Fetch standings from TeamLinkt
            logger.info(
                f"[SYNC] Fetching standings from TeamLinkt: "
                f"season_id={season_id}, division_id={division_id}"
            )
            standings_data = self.teamlinkt.get_standings(
                season_id=season_id,
                division_id=division_id
            )
            logger.info(f"[SYNC] TeamLinkt returned standings for {len(standings_data)} teams")

            # Convert to Standing objects
            new_standings = []
            for idx, standing_data in enumerate(standings_data):
                try:
                    standing = self._convert_standing_data(standing_data, idx + 1)
                    new_standings.append(standing)
                except Exception as e:
                    error_msg = f"Error processing standing: {e}"
                    logger.error(
                        f"[SYNC] {error_msg}\n"
                        f"Context: standing_data={standing_data}\n"
                        f"Stack trace:\n{traceback.format_exc()}"
                    )
                    result.errors.append(error_msg)

            # Fetch existing standings for comparison
            existing_result = self.cache.get_standings(season_id, division_id)
            existing_by_team = {s.team_id: s for s in (existing_result.data or [])}

            # Compare and collect changed standings
            standings_to_write = []
            for standing in new_standings:
                existing = existing_by_team.get(standing.team_id)
                if existing is None:
                    standings_to_write.append(standing)
                    result.inserted += 1
                elif self._standing_changed(existing, standing):
                    standings_to_write.append(standing)
                    result.updated += 1
                else:
                    result.unchanged += 1

            logger.info(
                f"[SYNC] Standings comparison: {result.inserted} new, "
                f"{result.updated} changed, {result.unchanged} unchanged"
            )

            # Only write changed standings
            if standings_to_write:
                written_count = self.cache.upsert_standings(
                    season_id, division_id, standings_to_write
                )
                logger.info(f"[SYNC] Wrote {written_count} standings records")

            logger.info(
                f"[SYNC] Standings sync complete for division {division_id}: "
                f"updated={result.updated}, errors={len(result.errors)}"
            )

        except Exception as e:
            error_msg = f"Failed to sync standings for division {division_id}: {e}"
            logger.error(
                f"[SYNC] {error_msg}\n"
                f"Context: season_id={season_id}, division_id={division_id}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )
            result.errors.append(error_msg)

        return result

    def sync_seasons_and_divisions(self) -> SyncResult:
        """Sync seasons and divisions metadata.

        Fetches seasons and divisions from TeamLinkt and updates the cache.

        Requirements: 4.1, 4.2, 4.3, 4.4

        Returns:
            SyncResult with counts of updated records
        """
        import traceback

        result = SyncResult()
        seasons_count = 0
        divisions_count = 0

        logger.info("[SYNC] Starting seasons and divisions sync")

        try:
            # Fetch and cache seasons
            logger.info("[SYNC] Fetching seasons from TeamLinkt")
            seasons_data = self.teamlinkt.get_seasons()
            logger.info(f"[SYNC] TeamLinkt returned {len(seasons_data)} seasons")

            for season_data in seasons_data:
                season = Season(
                    id=str(season_data['id']),
                    name=str(season_data['name']),
                    last_updated=datetime.now()
                )
                self.cache.upsert_season(season)
                seasons_count += 1
                result.updated += 1
                logger.debug(f"[SYNC] Upserted season {season.id}: {season.name}")

            # Fetch and cache divisions for each season
            for season_data in seasons_data:
                season_id = str(season_data['id'])
                logger.info(f"[SYNC] Fetching divisions for season {season_id}")
                divisions_data = self.teamlinkt.get_divisions(season_id=season_id)
                logger.info(f"[SYNC] TeamLinkt returned {len(divisions_data)} divisions for season {season_id}")

                for division_data in divisions_data:
                    division = Division(
                        id=str(division_data['id']),
                        name=str(division_data['name']),
                        season_id=season_id,
                        last_updated=datetime.now()
                    )
                    self.cache.upsert_division(division)
                    divisions_count += 1
                    result.updated += 1
                    logger.debug(f"[SYNC] Upserted division {division.id}: {division.name}")

            logger.info(
                f"[SYNC] Seasons/divisions sync complete: "
                f"seasons={seasons_count}, divisions={divisions_count}"
            )

        except Exception as e:
            error_msg = f"Failed to sync seasons and divisions: {e}"
            logger.error(
                f"[SYNC] {error_msg}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )
            result.errors.append(error_msg)

        return result

    def sync_teams(self, season_id: str, division_id: str) -> SyncResult:
        """Sync teams for a specific division with count validation.

        Compares TeamLinkt team count with cached team count and logs
        discrepancies for investigation. Ensures all TeamLinkt teams
        are synced to the cache.

        Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            SyncResult with counts of updated records
        """
        import traceback

        result = SyncResult()

        logger.info(
            f"[SYNC] Starting teams sync: "
            f"season_id={season_id}, division_id={division_id}"
        )

        try:
            # Get existing cached teams for comparison (Requirements 3.1, 3.2)
            cached_teams_result = self.cache.get_teams(season_id, division_id)
            cached_teams = cached_teams_result.data if cached_teams_result.cache_hit else []
            cached_team_names = {team.name for team in cached_teams}
            cached_team_count = len(cached_teams)

            logger.info(
                f"[SYNC] Fetching teams from TeamLinkt: "
                f"season_id={season_id}, division_id={division_id}"
            )
            teams_data = self.teamlinkt.get_teams(
                season_id=season_id,
                division_id=division_id
            )
            teamlinkt_team_count = len(teams_data)
            teamlinkt_team_names = {str(team_data['name']) for team_data in teams_data}

            logger.info(f"[SYNC] TeamLinkt returned {teamlinkt_team_count} teams")

            # Validate team counts and log discrepancies (Requirements 3.1, 3.2)
            if cached_team_count > 0 and teamlinkt_team_count != cached_team_count:
                # Find missing teams in each direction
                missing_from_cache = teamlinkt_team_names - cached_team_names
                missing_from_teamlinkt = cached_team_names - teamlinkt_team_names

                logger.warning(
                    f"[SYNC] Team count discrepancy detected for division {division_id}: "
                    f"TeamLinkt={teamlinkt_team_count}, Cache={cached_team_count}"
                )

                if missing_from_cache:
                    logger.warning(
                        f"[SYNC] Teams in TeamLinkt but missing from cache: {missing_from_cache}"
                    )

                if missing_from_teamlinkt:
                    logger.warning(
                        f"[SYNC] Teams in cache but missing from TeamLinkt: {missing_from_teamlinkt}"
                    )

            # Sync all teams from TeamLinkt (source of truth) (Requirement 3.3)
            # Get all divisions to check for child divisions
            divisions_result = self.cache.get_divisions(season_id)
            division_names = {d.id: d.name for d in (divisions_result.data or [])}
            current_division_name = division_names.get(division_id, '')
            is_parent_division = '/' not in current_division_name

            # Batch fetch all existing teams to avoid N+1 queries
            existing_teams_map = {}
            if is_parent_division:
                team_ids = [str(td['id']) for td in teams_data]
                existing_result = self.cache.get_teams_by_ids(team_ids)
                if existing_result.cache_hit and existing_result.data:
                    existing_teams_map = existing_result.data

            for team_data in teams_data:
                team_id = str(team_data['id'])
                final_division_id = division_id

                # If syncing from parent division, check if team already has
                # a child division assignment (don't overwrite child with parent)
                # See docs/TEAMLINKT_API.md "Parent Division Includes Child Games"
                if is_parent_division and team_id in existing_teams_map:
                    existing_team = existing_teams_map[team_id]
                    existing_div_name = division_names.get(
                        existing_team.division_id, ''
                    )
                    if '/' in existing_div_name:
                        # Team already has child division, preserve it
                        final_division_id = existing_team.division_id
                        logger.debug(
                            f"[SYNC] Preserving child division for team {team_id}: "
                            f"{final_division_id}"
                        )

                team = Team(
                    id=team_id,
                    name=str(team_data['name']),
                    division_id=final_division_id,
                    season_id=season_id
                )
                self.cache.upsert_team(team)
                result.updated += 1
                logger.debug(f"[SYNC] Upserted team {team.id}: {team.name}")

            # Track inserted vs updated for accurate reporting
            new_teams = teamlinkt_team_names - cached_team_names
            if new_teams:
                result.inserted = len(new_teams)
                result.updated = result.updated - result.inserted
                logger.info(
                    f"[SYNC] Added {result.inserted} new teams to cache: {new_teams}"
                )

            logger.info(
                f"[SYNC] Teams sync complete for division {division_id}: "
                f"total={teamlinkt_team_count}, inserted={result.inserted}, updated={result.updated}"
            )

        except Exception as e:
            error_msg = f"Failed to sync teams for division {division_id}: {e}"
            logger.error(
                f"[SYNC] {error_msg}\n"
                f"Context: season_id={season_id}, division_id={division_id}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )
            result.errors.append(error_msg)

        return result

    def build_team_division_mapping(
        self,
        season_id: str,
        parent_division_id: str
    ) -> dict[str, str]:
        """Build a mapping of team_name to child division_id.

        This mapping is used to determine the correct division for games
        when teams belong to child divisions under a parent.

        Requirements: 3.1, 3.2

        Args:
            season_id: Season identifier
            parent_division_id: Parent division identifier

        Returns:
            Dictionary mapping team_name to division_id
        """
        team_to_division: dict[str, str] = {}

        # Get all divisions for the season
        divisions_result = self.cache.get_divisions(season_id)
        if not divisions_result.cache_hit or not divisions_result.data:
            return team_to_division

        # Find child divisions (divisions with "/" in name indicating parent/child)
        # e.g., "10U / Green" is a child of "10U"
        for division in divisions_result.data:
            # Check if this is a child division of the parent
            # Child divisions typically have format "Parent / Child" or similar
            if '/' in division.name:
                # Get teams for this child division
                teams_result = self.cache.get_teams(season_id, division.id)
                if teams_result.cache_hit and teams_result.data:
                    for team in teams_result.data:
                        team_to_division[team.name] = division.id

        logger.debug(
            f"[SYNC] Built team-division mapping for parent {parent_division_id}: "
            f"{len(team_to_division)} teams mapped"
        )

        return team_to_division

    def build_team_name_to_id_mapping(
        self,
        season_id: str,
        division_id: str
    ) -> dict[str, str]:
        """Build a mapping of team_name to team_id.

        This mapping is used to populate team IDs in games since the
        TeamLinkt games API doesn't return team IDs.

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            Dictionary mapping team_name to team_id
        """
        team_name_to_id: dict[str, str] = {}

        # Get all divisions for the season to find all teams
        divisions_result = self.cache.get_divisions(season_id)
        if not divisions_result.cache_hit or not divisions_result.data:
            return team_name_to_id

        # Get teams from all divisions (including child divisions)
        for division in divisions_result.data:
            teams_result = self.cache.get_teams(season_id, division.id)
            if teams_result.cache_hit and teams_result.data:
                for team in teams_result.data:
                    team_name_to_id[team.name] = team.id

        logger.debug(
            f"[SYNC] Built team name-to-id mapping: "
            f"{len(team_name_to_id)} teams mapped"
        )

        return team_name_to_id

    def determine_game_division(
        self,
        home_team: str,
        away_team: str,
        parent_division_id: str,
        team_to_division: dict[str, str]
    ) -> str:
        """Determine the correct division for a game based on team membership.

        Logic:
        - If both teams belong to the same child division → use child division
        - If teams belong to different child divisions → use parent division
        - If teams not found in mapping → use parent division

        Requirements: 3.1, 3.2

        Args:
            home_team: Home team name
            away_team: Away team name
            parent_division_id: Parent division identifier
            team_to_division: Mapping of team_name to division_id

        Returns:
            Division ID to use for the game
        """
        home_division = team_to_division.get(home_team)
        away_division = team_to_division.get(away_team)

        # If both teams are in the same child division, use that division
        if home_division and away_division and home_division == away_division:
            logger.debug(
                f"[SYNC] Game {home_team} vs {away_team}: "
                f"both in child division {home_division}"
            )
            return home_division

        # Otherwise (different divisions or not found), use parent division
        if home_division and away_division and home_division != away_division:
            logger.debug(
                f"[SYNC] Game {home_team} vs {away_team}: "
                f"cross-division game (home={home_division}, away={away_division}), "
                f"using parent {parent_division_id}"
            )
        else:
            logger.debug(
                f"[SYNC] Game {home_team} vs {away_team}: "
                f"team(s) not in mapping, using parent {parent_division_id}"
            )

        return parent_division_id

    def _convert_game_data(
        self,
        game_data: dict,
        season_id: str,
        division_id: str,
        team_to_division: Optional[dict[str, str]] = None,
        team_name_to_id: Optional[dict[str, str]] = None
    ) -> Game:
        """Convert TeamLinkt game data to Game model.

        Args:
            game_data: Raw game data from TeamLinkt
            season_id: Season identifier
            division_id: Division identifier (parent division from query)
            team_to_division: Optional mapping of team_name to child division_id
            team_name_to_id: Optional mapping of team_name to team_id

        Returns:
            Game instance
        """
        # Parse scores - empty string means not played
        home_score = game_data.get('home_score', '')
        away_score = game_data.get('away_score', '')

        home_score_int = int(home_score) if home_score not in ('', None) else None
        away_score_int = int(away_score) if away_score not in ('', None) else None

        # Determine status
        if home_score_int is not None and away_score_int is not None:
            status = 'completed'
        else:
            status = 'scheduled'

        # Determine correct division based on team membership
        home_team = str(game_data.get('home_team', ''))
        away_team = str(game_data.get('away_team', ''))

        if team_to_division:
            final_division_id = self.determine_game_division(
                home_team, away_team, division_id, team_to_division
            )
        else:
            final_division_id = division_id

        # Look up team IDs from team names (TeamLinkt API doesn't return team IDs in games)
        home_team_id = ''
        away_team_id = ''
        if team_name_to_id:
            home_team_id = team_name_to_id.get(home_team, '')
            away_team_id = team_name_to_id.get(away_team, '')

        # Fall back to game_data if available (for future API changes)
        if not home_team_id:
            home_team_id = str(game_data.get('home_team_id', ''))
        if not away_team_id:
            away_team_id = str(game_data.get('away_team_id', ''))

        return Game(
            game_id=str(game_data['game_id']),
            season_id=season_id,
            division_id=final_division_id,
            home_team=home_team,
            home_team_id=home_team_id,
            away_team=away_team,
            away_team_id=away_team_id,
            home_score=home_score_int,
            away_score=away_score_int,
            date=str(game_data.get('date', '')),
            time=str(game_data.get('time', '')),
            location=str(game_data.get('location', '')),
            status=status,
            recap_text=game_data.get('recap_text'),
            last_updated=datetime.now()
        )

    def _game_changed(self, existing: Game, new: Game) -> bool:
        """Compare two games to detect changes.

        Compares division_id, date, time, location, scores, status, and recap_text.
        Division_id comparison ensures games get assigned to the most specific
        (child) division. See docs/TEAMLINKT_API.md "Parent Division Includes Child Games".

        Requirements: 2.3

        Args:
            existing: Existing game from Firestore cache
            new: New game from TeamLinkt

        Returns:
            True if any field differs, False if games are identical
        """
        changes = []
        if existing.division_id != new.division_id:
            changes.append(f"division_id: '{existing.division_id}' -> '{new.division_id}'")
        if existing.date != new.date:
            changes.append(f"date: '{existing.date}' -> '{new.date}'")
        if existing.time != new.time:
            changes.append(f"time: '{existing.time}' -> '{new.time}'")
        if existing.location != new.location:
            changes.append(f"location: '{existing.location}' -> '{new.location}'")
        if existing.home_score != new.home_score:
            changes.append(f"home_score: {existing.home_score} -> {new.home_score}")
        if existing.away_score != new.away_score:
            changes.append(f"away_score: {existing.away_score} -> {new.away_score}")
        if existing.status != new.status:
            changes.append(f"status: '{existing.status}' -> '{new.status}'")
        if existing.recap_text != new.recap_text:
            changes.append(f"recap_text changed")

        if changes:
            logger.info(f"[SYNC] Game {new.game_id} changes: {', '.join(changes)}")
            return True
        return False

    def _standing_changed(self, existing: Standing, new: Standing) -> bool:
        """Compare two standings to detect changes.

        Compares all standing fields except team_id and team_name.

        Args:
            existing: Existing standing from Firestore cache
            new: New standing from TeamLinkt

        Returns:
            True if any field differs, False if standings are identical
        """
        return (
            existing.ranking != new.ranking or
            existing.games_played != new.games_played or
            existing.wins != new.wins or
            existing.losses != new.losses or
            existing.ties != new.ties or
            existing.points != new.points or
            existing.goals_for != new.goals_for or
            existing.goals_against != new.goals_against
        )

    def _batch_write_games(self, games: list[Game]) -> int:
        """Write games in batches of 500 using Firestore batch API.

        Requirements: 2.6

        Args:
            games: List of Game objects to write

        Returns:
            Number of games written
        """
        BATCH_SIZE = 500
        total_written = 0

        for i in range(0, len(games), BATCH_SIZE):
            batch_games = games[i:i + BATCH_SIZE]
            batch = self.cache.db.batch()

            for game in batch_games:
                # Ensure game has a timestamp
                if game.last_updated is None:
                    game = Game(
                        game_id=game.game_id,
                        season_id=game.season_id,
                        division_id=game.division_id,
                        home_team=game.home_team,
                        home_team_id=game.home_team_id,
                        away_team=game.away_team,
                        away_team_id=game.away_team_id,
                        home_score=game.home_score,
                        away_score=game.away_score,
                        date=game.date,
                        time=game.time,
                        location=game.location,
                        status=game.status,
                        recap_text=game.recap_text,
                        last_updated=datetime.now(),
                    )

                doc_ref = self.cache.db.collection(self.cache.GAMES_COLLECTION).document(game.game_id)
                batch.set(doc_ref, game.to_dict(), merge=True)

            batch.commit()
            total_written += len(batch_games)
            logger.info(f"[SYNC] Batch wrote {len(batch_games)} games (total: {total_written})")

        return total_written

    def _convert_standing_data(self, standing_data: dict, ranking: int) -> Standing:
        """Convert TeamLinkt standing data to Standing model.

        Args:
            standing_data: Raw standing data from TeamLinkt
            ranking: Team ranking position

        Returns:
            Standing instance
        """
        return Standing(
            team_id=str(standing_data.get('team_id', '')),
            team_name=str(standing_data.get('team_name', '')),
            ranking=ranking,
            games_played=int(standing_data.get('games_played', 0)),
            wins=int(standing_data.get('total_wins', 0)),
            losses=int(standing_data.get('total_losses', 0)),
            ties=int(standing_data.get('total_ties', 0)),
            points=int(standing_data.get('total_points', 0)),
            goals_for=int(standing_data.get('score_for', 0)),
            goals_against=int(standing_data.get('score_against', 0))
        )

    def _update_last_sync(self) -> None:
        """Update the last sync timestamp in metadata."""
        now = datetime.now(tz=PACIFIC_TZ)
        self.cache.set_metadata(LAST_SYNC_KEY, now.isoformat(), ttl_hours=0)

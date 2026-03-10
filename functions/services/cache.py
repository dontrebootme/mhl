"""Cache service for Firestore-based data storage.

Provides an abstraction layer over Firestore operations for caching
game data, standings, and metadata with TTL support.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol
import logging

from models.game import Game
from models.standing import Standing
from firestore_config import COLS


logger = logging.getLogger(__name__)


class FirestoreClient(Protocol):
    """Protocol for Firestore client interface."""

    def collection(self, collection_id: str) -> Any:
        """Get a collection reference."""
        ...


@dataclass
class CacheResult:
    """Result of a cache operation with hit/miss tracking.

    Attributes:
        data: The cached data (None if cache miss)
        cache_hit: True if data was found in cache
        timestamp: When the cache was checked
    """
    data: Any
    cache_hit: bool
    timestamp: datetime


@dataclass
class Season:
    """Represents a season."""
    id: str
    name: str
    last_updated: datetime

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'last_updated': self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Season':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()
        return cls(
            id=str(data['id']),
            name=str(data['name']),
            last_updated=last_updated,
        )


@dataclass
class Division:
    """Represents a division."""
    id: str
    name: str
    season_id: str
    last_updated: datetime

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'season_id': self.season_id,
            'last_updated': self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Division':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()
        return cls(
            id=str(data['id']),
            name=str(data['name']),
            season_id=str(data['season_id']),
            last_updated=last_updated,
        )


@dataclass
class Team:
    """Represents a team."""
    id: str
    name: str
    division_id: str
    season_id: str

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'division_id': self.division_id,
            'season_id': self.season_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Team':
        return cls(
            id=str(data['id']),
            name=str(data['name']),
            division_id=str(data['division_id']),
            season_id=str(data['season_id']),
        )



class CacheService:
    """Abstraction layer over Firestore operations for caching hockey data.

    Provides methods for reading and writing games, standings, seasons,
    divisions, teams, and metadata with TTL support.

    Attributes:
        db: Firestore client instance
    """

    # Collection names
    GAMES_COLLECTION = COLS.GAMES
    STANDINGS_COLLECTION = COLS.STANDINGS
    SEASONS_COLLECTION = COLS.SEASONS
    DIVISIONS_COLLECTION = COLS.DIVISIONS
    TEAMS_COLLECTION = COLS.TEAMS
    METADATA_COLLECTION = COLS.METADATA

    def __init__(self, db: FirestoreClient):
        """Initialize the cache service.

        Args:
            db: Firestore client instance
        """
        self.db = db

    # ==================== Game Operations ====================

    def get_games(
        self,
        season_id: str,
        division_id: str,
        team_id: Optional[str] = None
    ) -> CacheResult:
        """Get games from cache filtered by season, division, and optionally team.

        Args:
            season_id: Season identifier
            division_id: Division identifier
            team_id: Optional team identifier to filter by (home or away)

        Returns:
            CacheResult with list of Game objects and cache hit status
        """
        now = datetime.now()
        collection = self.db.collection(self.GAMES_COLLECTION)

        # Build query
        query = collection.where('season_id', '==', season_id)
        query = query.where('division_id', '==', division_id)

        # Execute query
        docs = list(query.stream())

        if not docs:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        games = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                game = Game.from_dict(data)
                # Filter by team if specified
                if team_id is None or game.home_team_id == team_id or game.away_team_id == team_id:
                    games.append(game)

        hit = len(games) > 0
        logger.info(
            f"[CACHE] Operation: get_games, Hit: {hit}, "
            f"Args: season_id={season_id}, division_id={division_id}, team_id={team_id}"
        )
        return CacheResult(data=games, cache_hit=hit, timestamp=now)

    def get_game_by_id(self, game_id: str) -> CacheResult:
        """Get a single game by its ID.

        Args:
            game_id: Unique game identifier

        Returns:
            CacheResult with Game object or None
        """
        now = datetime.now()
        doc_ref = self.db.collection(self.GAMES_COLLECTION).document(game_id)
        doc = doc_ref.get()

        if not doc.exists:
            logger.info(f"[CACHE] Operation: get_game_by_id, Hit: False, Args: game_id={game_id}")
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        data = doc.to_dict()
        if data is None:
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        game = Game.from_dict(data)
        logger.info(f"[CACHE] Operation: get_game_by_id, Hit: True, Args: game_id={game_id}")
        return CacheResult(data=game, cache_hit=True, timestamp=now)

    def get_games_by_ids(self, game_ids: list[str]) -> CacheResult:
        """Get multiple games by their IDs using batch lookup.

        Uses Firestore's get_all for efficient batch retrieval.
        This is more efficient than querying by division_id when games
        may be stored under different division_ids than queried.

        Args:
            game_ids: List of game identifiers to fetch

        Returns:
            CacheResult with list of Game objects and cache hit status
        """
        now = datetime.now()

        if not game_ids:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        # Create document references for all game_ids
        doc_refs = [
            self.db.collection(self.GAMES_COLLECTION).document(gid)
            for gid in game_ids
        ]

        # Batch fetch all documents
        docs = self.db.get_all(doc_refs)

        games = []
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                if data:
                    game = Game.from_dict(data)
                    games.append(game)

        hit = len(games) > 0
        logger.info(
            f"[CACHE] Operation: get_games_by_ids, Hit: {hit}, "
            f"Args: count={len(game_ids)}"
        )
        return CacheResult(data=games, cache_hit=hit, timestamp=now)

    def get_games_by_team(
        self,
        team_id: str,
        season_id: Optional[str] = None
    ) -> CacheResult:
        """Get all games for a team (as home or away).

        Queries games where home_team_id or away_team_id matches the given team_id.

        Args:
            team_id: Team identifier
            season_id: Optional season identifier to filter by

        Returns:
            CacheResult with list of Game objects and cache hit status
        """
        now = datetime.now()
        collection = self.db.collection(self.GAMES_COLLECTION)

        # Query for home games
        home_query = collection.where('home_team_id', '==', team_id)
        if season_id:
            home_query = home_query.where('season_id', '==', season_id)
        home_docs = list(home_query.stream())

        # Query for away games
        away_query = collection.where('away_team_id', '==', team_id)
        if season_id:
            away_query = away_query.where('season_id', '==', season_id)
        away_docs = list(away_query.stream())

        # Combine and deduplicate
        games_dict = {}
        for doc in home_docs + away_docs:
            data = doc.to_dict()
            if data:
                game = Game.from_dict(data)
                games_dict[game.game_id] = game

        games = list(games_dict.values())
        hit = len(games) > 0
        logger.info(
            f"[CACHE] Operation: get_games_by_team, Hit: {hit}, "
            f"Args: team_id={team_id}, season_id={season_id}"
        )
        return CacheResult(data=games, cache_hit=hit, timestamp=now)


    def upsert_game(self, game: Game) -> bool:
        """Insert or update a game in the cache.

        Compares the game against existing cached data and only writes
        if there are changes. Always ensures last_updated timestamp is set.

        Args:
            game: Game object to upsert

        Returns:
            True if the game was inserted or updated, False if unchanged
        """
        doc_ref = self.db.collection(self.GAMES_COLLECTION).document(game.game_id)
        existing_doc = doc_ref.get()

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

        if not existing_doc.exists:
            # Insert new game
            doc_ref.set(game.to_dict())
            return True

        # Compare with existing data
        existing_data = existing_doc.to_dict()
        if existing_data is None:
            doc_ref.set(game.to_dict())
            return True

        # Check if any relevant fields changed
        # Note: division_id IS compared because TeamLinkt returns games from
        # child divisions when querying parent divisions. We want the most
        # specific division_id (the one from the child division query).
        fields_to_compare = [
            'division_id', 'date', 'time', 'location', 'home_score', 'away_score',
            'status', 'recap_text'
        ]

        game_dict = game.to_dict()
        changed = False
        for field in fields_to_compare:
            if existing_data.get(field) != game_dict.get(field):
                changed = True
                break

        if changed:
            # Update with new timestamp
            game_dict['last_updated'] = datetime.now().isoformat()
            doc_ref.set(game_dict, merge=True)
            return True

        return False

    # ==================== Standings Operations ====================

    def get_standings(self, season_id: str, division_id: str) -> CacheResult:
        """Get standings from cache for a season and division.

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            CacheResult with list of Standing objects and cache hit status
        """
        now = datetime.now()
        standings_key = f"{season_id}_{division_id}"
        collection = self.db.collection(self.STANDINGS_COLLECTION).document(standings_key).collection('teams')

        docs = list(collection.stream())

        if not docs:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        standings = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                standings.append(Standing.from_dict(data))

        # Sort by ranking
        standings.sort(key=lambda s: s.ranking)

        hit = len(standings) > 0
        logger.info(
            f"[CACHE] Operation: get_standings, Hit: {hit}, "
            f"Args: season_id={season_id}, division_id={division_id}"
        )
        return CacheResult(data=standings, cache_hit=hit, timestamp=now)


    def upsert_standings(
        self,
        season_id: str,
        division_id: str,
        standings: list[Standing]
    ) -> int:
        """Insert or update standings for a season and division.

        Args:
            season_id: Season identifier
            division_id: Division identifier
            standings: List of Standing objects

        Returns:
            Number of standings records updated
        """
        standings_key = f"{season_id}_{division_id}"
        parent_doc = self.db.collection(self.STANDINGS_COLLECTION).document(standings_key)
        teams_collection = parent_doc.collection('teams')

        # Update metadata on parent document
        parent_doc.set({
            'season_id': season_id,
            'division_id': division_id,
            'last_updated': datetime.now().isoformat(),
        }, merge=True)

        updated_count = 0
        for standing in standings:
            doc_ref = teams_collection.document(standing.team_id)
            doc_ref.set(standing.to_dict())
            updated_count += 1

        return updated_count

    # ==================== Season Operations ====================

    def get_seasons(self) -> CacheResult:
        """Get all seasons from cache.

        Returns:
            CacheResult with list of Season objects and cache hit status
        """
        now = datetime.now()
        collection = self.db.collection(self.SEASONS_COLLECTION)
        docs = list(collection.stream())

        if not docs:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        seasons = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                seasons.append(Season.from_dict(data))

        hit = len(seasons) > 0
        logger.info(f"[CACHE] Operation: get_seasons, Hit: {hit}")
        return CacheResult(data=seasons, cache_hit=hit, timestamp=now)

    def upsert_season(self, season: Season) -> bool:
        """Insert or update a season in the cache.

        Args:
            season: Season object to upsert

        Returns:
            True if the season was inserted or updated
        """
        doc_ref = self.db.collection(self.SEASONS_COLLECTION).document(season.id)
        doc_ref.set(season.to_dict(), merge=True)
        return True

    # ==================== Division Operations ====================

    def get_divisions(self, season_id: str) -> CacheResult:
        """Get divisions from cache for a season.

        Args:
            season_id: Season identifier

        Returns:
            CacheResult with list of Division objects and cache hit status
        """
        now = datetime.now()
        collection = self.db.collection(self.DIVISIONS_COLLECTION)
        query = collection.where('season_id', '==', season_id)
        docs = list(query.stream())

        if not docs:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        divisions = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                divisions.append(Division.from_dict(data))

        hit = len(divisions) > 0
        logger.info(
            f"[CACHE] Operation: get_divisions, Hit: {hit}, "
            f"Args: season_id={season_id}"
        )
        return CacheResult(data=divisions, cache_hit=hit, timestamp=now)

    def upsert_division(self, division: Division) -> bool:
        """Insert or update a division in the cache.

        Args:
            division: Division object to upsert

        Returns:
            True if the division was inserted or updated
        """
        doc_ref = self.db.collection(self.DIVISIONS_COLLECTION).document(division.id)
        doc_ref.set(division.to_dict(), merge=True)
        return True


    # ==================== Team Operations ====================

    def get_teams(self, season_id: str, division_id: str) -> CacheResult:
        """Get teams from cache for a season and division.

        Args:
            season_id: Season identifier
            division_id: Division identifier

        Returns:
            CacheResult with list of Team objects and cache hit status
        """
        now = datetime.now()
        collection = self.db.collection(self.TEAMS_COLLECTION)
        query = collection.where('season_id', '==', season_id)
        query = query.where('division_id', '==', division_id)
        docs = list(query.stream())

        if not docs:
            return CacheResult(data=[], cache_hit=False, timestamp=now)

        teams = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                teams.append(Team.from_dict(data))

        hit = len(teams) > 0
        logger.info(
            f"[CACHE] Operation: get_teams, Hit: {hit}, "
            f"Args: season_id={season_id}, division_id={division_id}"
        )
        return CacheResult(data=teams, cache_hit=hit, timestamp=now)

    def get_team_by_id(self, team_id: str) -> CacheResult:
        """Get a single team by its ID.

        Args:
            team_id: Unique team identifier

        Returns:
            CacheResult with Team object or None if not found
        """
        now = datetime.now()
        doc_ref = self.db.collection(self.TEAMS_COLLECTION).document(team_id)
        doc = doc_ref.get()

        if not doc.exists:
            logger.info(f"[CACHE] Operation: get_team_by_id, Hit: False, Args: team_id={team_id}")
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        data = doc.to_dict()
        if data is None:
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        team = Team.from_dict(data)
        logger.info(f"[CACHE] Operation: get_team_by_id, Hit: True, Args: team_id={team_id}")
        return CacheResult(data=team, cache_hit=True, timestamp=now)

    def get_teams_by_ids(self, team_ids: list[str]) -> CacheResult:
        """Get multiple teams by their IDs using batch lookup.

        Uses Firestore's get_all for efficient batch retrieval.
        This is more efficient than individual get_team_by_id calls in a loop.

        Args:
            team_ids: List of team identifiers to fetch

        Returns:
            CacheResult with dict mapping team_id to Team object
        """
        now = datetime.now()

        if not team_ids:
            return CacheResult(data={}, cache_hit=False, timestamp=now)

        # Create document references for all team_ids
        doc_refs = [
            self.db.collection(self.TEAMS_COLLECTION).document(tid)
            for tid in team_ids
        ]

        # Batch fetch all documents
        docs = self.db.get_all(doc_refs)

        teams_map = {}
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                if data:
                    team = Team.from_dict(data)
                    teams_map[team.id] = team

        hit = len(teams_map) > 0
        logger.info(
            f"[CACHE] Operation: get_teams_by_ids, Hit: {hit}, "
            f"Args: requested={len(team_ids)}, found={len(teams_map)}"
        )
        return CacheResult(data=teams_map, cache_hit=hit, timestamp=now)

    def upsert_team(self, team: Team) -> bool:
        """Insert or update a team in the cache.

        Args:
            team: Team object to upsert

        Returns:
            True if the team was inserted or updated
        """
        doc_ref = self.db.collection(self.TEAMS_COLLECTION).document(team.id)
        doc_ref.set(team.to_dict(), merge=True)
        return True

    # ==================== Metadata Operations ====================

    def get_metadata(self, key: str) -> CacheResult:
        """Get metadata value from cache.

        Checks TTL expiration and returns cache miss if expired.

        Args:
            key: Metadata key

        Returns:
            CacheResult with metadata value or None if not found/expired
        """
        now = datetime.now()
        doc_ref = self.db.collection(self.METADATA_COLLECTION).document(key)
        doc = doc_ref.get()

        if not doc.exists:
            logger.info(f"[CACHE] Operation: get_metadata, Hit: False (not found), Args: key={key}")
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        data = doc.to_dict()
        if data is None:
            return CacheResult(data=None, cache_hit=False, timestamp=now)

        # Check TTL expiration
        expires_at = data.get('expires_at')
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at < now:
                # Expired - treat as cache miss
                logger.info(f"[CACHE] Operation: get_metadata, Hit: False (expired), Args: key={key}")
                return CacheResult(data=None, cache_hit=False, timestamp=now)

        logger.info(f"[CACHE] Operation: get_metadata, Hit: True, Args: key={key}")
        return CacheResult(data=data.get('value'), cache_hit=True, timestamp=now)

    def set_metadata(self, key: str, value: Any, ttl_hours: int = 0) -> None:
        """Set metadata value in cache with optional TTL.

        Args:
            key: Metadata key
            value: Value to store
            ttl_hours: Time-to-live in hours (0 = no expiration)
        """
        now = datetime.now()
        doc_ref = self.db.collection(self.METADATA_COLLECTION).document(key)

        data = {
            'value': value,
            'last_updated': now.isoformat(),
        }

        if ttl_hours > 0:
            data['expires_at'] = (now + timedelta(hours=ttl_hours)).isoformat()
        else:
            data['expires_at'] = None

        doc_ref.set(data)

    def delete_metadata(self, key: str) -> None:
        """Delete metadata from cache.

        Args:
            key: Metadata key to delete
        """
        doc_ref = self.db.collection(self.METADATA_COLLECTION).document(key)
        doc_ref.delete()

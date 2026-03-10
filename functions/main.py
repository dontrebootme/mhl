"""Sync Cloud Function entry point.

Flask-based mhlv2_sync function triggered by Cloud Scheduler.
Syncs TeamLinkt data into Firestore under the mhlv2_ collection prefix.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_functions import https_fn

from clients.teamlinkt import TeamLinktClient
from services.cache import CacheService
from services.sync import SyncService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PACIFIC_TZ = ZoneInfo('America/Los_Angeles')


def get_firestore_client():
    """Get or initialize Firestore client."""
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


@https_fn.on_request(
    memory=512,
    timeout_sec=540,
    min_instances=0,
    max_instances=2,
)
def mhlv2_sync(req: https_fn.Request) -> https_fn.Response:
    """Sync function entry point for scheduled data synchronization.

    Triggered by Cloud Scheduler. Accepts optional JSON body:
      { "force": true, "season_id": "...", "division_ids": [...] }
    """
    logger.info(f"Sync triggered at {datetime.now(tz=PACIFIC_TZ).isoformat()}")

    force = False
    season_id = None
    division_ids = None

    if req.is_json:
        data = req.get_json(silent=True) or {}
        force = data.get('force', False)
        season_id = data.get('season_id')
        division_ids = data.get('division_ids')

    try:
        db = get_firestore_client()
        cache = CacheService(db)
        teamlinkt = TeamLinktClient()
        sync_service = SyncService(cache, teamlinkt)

        stats = _run_sync(sync_service, season_id, division_ids, force)

        response = {
            'status': 'skipped' if stats.get('skipped') else 'completed',
            'timestamp': datetime.now(tz=PACIFIC_TZ).isoformat(),
            'stats': stats,
        }

        return https_fn.Response(
            response=json.dumps(response),
            status=200 if not stats.get('errors') else 207,
            headers={'Content-Type': 'application/json'},
        )

    except Exception as e:
        logger.error(f"Sync function failed: {e}", exc_info=True)
        return https_fn.Response(
            response=json.dumps({
                'status': 'error',
                'timestamp': datetime.now(tz=PACIFIC_TZ).isoformat(),
                'error': str(e),
            }),
            status=500,
            headers={'Content-Type': 'application/json'},
        )


def _run_sync(
    sync_service: SyncService,
    season_id: Optional[str] = None,
    division_ids: Optional[list] = None,
    force: bool = False,
) -> dict:
    """Run the sync process and return stats."""
    stats = {
        'divisions_synced': 0,
        'games_inserted': 0,
        'games_updated': 0,
        'games_unchanged': 0,
        'standings_updated': 0,
        'metadata_synced': 0,
        'errors': [],
        'skipped': False,
        'duration_seconds': 0.0,
    }
    start_time = time.time()

    if not force and not sync_service.should_sync():
        stats['skipped'] = True
        logger.info("Sync skipped due to smart scheduling")
        return stats

    try:
        if not season_id:
            season_id = sync_service.detect_active_season()
            if not season_id:
                logger.warning("No active season detected")
                stats['errors'].append("No active season detected")
                return stats

        logger.info(f"Starting sync for season {season_id}")

        metadata_result = sync_service.sync_seasons_and_divisions()
        stats['metadata_synced'] += metadata_result.updated + metadata_result.inserted

        if not division_ids:
            divisions_result = sync_service.cache.get_divisions(season_id)
            if divisions_result.cache_hit:
                # Sort children (with "/") before parents so child division_id
                # assignment wins when games appear in both parent and child.
                divisions = divisions_result.data
                divisions.sort(key=lambda d: (0 if '/' in d.name else 1, d.name))
                division_ids = [d.id for d in divisions]
                logger.info(f"[SYNC] Division order: {[d.name for d in divisions]}")
            else:
                logger.warning(f"No divisions found for season {season_id}")
                stats['errors'].append(f"No divisions found for season {season_id}")
                return stats

        for division_id in division_ids:
            logger.info(f"Syncing division {division_id}")

            teams_result = sync_service.sync_teams(season_id, division_id)
            stats['metadata_synced'] += teams_result.updated + teams_result.inserted

            try:
                games_result = sync_service.sync_division(season_id, division_id, force=True)
                stats['games_inserted'] += games_result.inserted
                stats['games_updated'] += games_result.updated
                stats['games_unchanged'] += games_result.unchanged
                stats['divisions_synced'] += 1
            except Exception as e:
                error_msg = f"Failed to sync games for division {division_id}: {e}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)

            try:
                standings_result = sync_service.sync_standings(season_id, division_id, force=True)
                stats['standings_updated'] += standings_result.updated + standings_result.inserted
            except Exception as e:
                error_msg = f"Failed to sync standings for division {division_id}: {e}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)

    except Exception as e:
        error_msg = f"Sync failed: {e}"
        logger.error(error_msg, exc_info=True)
        stats['errors'].append(error_msg)

    stats['duration_seconds'] = round(time.time() - start_time, 2)
    logger.info(
        f"Sync complete: divisions={stats['divisions_synced']}, "
        f"games_inserted={stats['games_inserted']}, games_updated={stats['games_updated']}, "
        f"games_unchanged={stats['games_unchanged']}, "
        f"standings_updated={stats['standings_updated']}, "
        f"metadata_synced={stats['metadata_synced']}, "
        f"errors={len(stats['errors'])}, duration={stats['duration_seconds']}s"
    )

    return stats

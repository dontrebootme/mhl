/**
 * Firestore Service Layer
 *
 * Provides direct access to Firestore collections.
 * Mirrors the backend's CacheService functionality.
 */

import {
  collection,
  doc,
  getDoc,
  getDocs,
  query,
  where,
} from 'firebase/firestore';
import { db, COLLECTIONS, isFirebaseConfigured } from './config';

export class FirestoreError extends Error {
  constructor(message, code = 'FIRESTORE_ERROR') {
    super(message);
    this.name = 'FirestoreError';
    this.code = code;
  }
}

const ensureFirestore = () => {
  if (!isFirebaseConfigured() || !db) {
    throw new FirestoreError(
      'Firebase is not configured. Please set environment variables.',
      'NOT_CONFIGURED'
    );
  }
};

export async function getSeasons() {
  ensureFirestore();
  const snapshot = await getDocs(collection(db, COLLECTIONS.SEASONS));
  return snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
}

export async function getDivisions(seasonId) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');

  const q = query(collection(db, COLLECTIONS.DIVISIONS), where('season_id', '==', seasonId));
  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
}

export async function getTeams(seasonId, divisionId) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');
  if (!divisionId) throw new FirestoreError('divisionId is required', 'INVALID_PARAMS');

  const q = query(
    collection(db, COLLECTIONS.TEAMS),
    where('season_id', '==', seasonId),
    where('division_id', '==', divisionId)
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
}

export async function getGames(seasonId, divisionId, teamId = null) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');
  if (!divisionId && !teamId) throw new FirestoreError('divisionId or teamId is required', 'INVALID_PARAMS');

  const gamesRef = collection(db, COLLECTIONS.GAMES);

  if (!divisionId) {
    // Two queries for home and away when only teamId provided
    const homeQuery = query(gamesRef, where('season_id', '==', seasonId), where('home_team_id', '==', teamId));
    const awayQuery = query(gamesRef, where('season_id', '==', seasonId), where('away_team_id', '==', teamId));
    const [homeSnap, awaySnap] = await Promise.all([getDocs(homeQuery), getDocs(awayQuery)]);

    const gamesMap = new Map();
    homeSnap.docs.forEach((doc) => gamesMap.set(doc.id, { id: doc.id, ...doc.data() }));
    awaySnap.docs.forEach((doc) => gamesMap.set(doc.id, { id: doc.id, ...doc.data() }));
    return Array.from(gamesMap.values());
  }

  const q = query(gamesRef, where('season_id', '==', seasonId), where('division_id', '==', divisionId));
  const snapshot = await getDocs(q);
  let games = snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));

  if (teamId) {
    games = games.filter((g) => g.home_team_id === teamId || g.away_team_id === teamId);
  }

  return games;
}

export async function getGameById(gameId) {
  ensureFirestore();
  if (!gameId) throw new FirestoreError('gameId is required', 'INVALID_PARAMS');

  const docSnap = await getDoc(doc(db, COLLECTIONS.GAMES, gameId));
  if (!docSnap.exists()) return null;
  return { id: docSnap.id, ...docSnap.data() };
}

export async function getStandings(seasonId, divisionId) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');
  if (!divisionId) throw new FirestoreError('divisionId is required', 'INVALID_PARAMS');

  const standingsKey = `${seasonId}_${divisionId}`;
  const teamsRef = collection(db, COLLECTIONS.STANDINGS, standingsKey, 'teams');
  const snapshot = await getDocs(teamsRef);

  const standings = snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
  standings.sort((a, b) => (a.ranking || 0) - (b.ranking || 0));
  return standings;
}

export async function getScores(seasonId, divisionId, teamId = null) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');
  if (!divisionId) throw new FirestoreError('divisionId is required', 'INVALID_PARAMS');

  const games = await getGames(seasonId, divisionId, teamId);
  return games.filter((game) => {
    const status = (game.status || '').toLowerCase();
    return status === 'completed' || status === 'final';
  });
}

export async function getRecentScores(seasonId, maxResults = 10) {
  ensureFirestore();
  if (!seasonId) throw new FirestoreError('seasonId is required', 'INVALID_PARAMS');

  const q = query(collection(db, COLLECTIONS.GAMES), where('season_id', '==', seasonId));
  const snapshot = await getDocs(q);
  const games = snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));

  const completed = games.filter((game) => {
    const status = (game.status || '').toLowerCase();
    return ['final', 'completed', 'forfeit'].includes(status);
  });

  completed.sort((a, b) => {
    const timeA = a.date ? new Date(a.date).getTime() : 0;
    const timeB = b.date ? new Date(b.date).getTime() : 0;
    return (timeB || 0) - (timeA || 0);
  });

  return completed.slice(0, maxResults);
}

export default {
  getSeasons,
  getDivisions,
  getTeams,
  getGames,
  getGameById,
  getStandings,
  getScores,
  getRecentScores,
  FirestoreError,
};

/**
 * Data Service
 *
 * Single interface for fetching data from Firestore.
 * Handles snake_case → camelCase transformation and status normalization.
 */

import * as firestoreService from '../firebase/firestore';

/**
 * Normalize game status to frontend format
 */
const normalizeStatus = (status) => {
  if (!status) return 'scheduled';
  const s = status.toLowerCase();
  if (s === 'in progress') return 'live';
  if (s === 'final' || s === 'completed') return 'final';
  if (s === 'scheduled') return 'scheduled';
  return s;
};

/**
 * Transform game from Firestore snake_case to frontend camelCase
 */
export const transformGame = (game) => ({
  gameId: game.game_id || game.id,
  homeTeam: game.home_team,
  awayTeam: game.away_team,
  homeScore: game.home_score,
  awayScore: game.away_score,
  date: game.date,
  time: game.time,
  location: game.location,
  status: normalizeStatus(game.status),
  homeRecord: null,
  awayRecord: null,
});

const transformStanding = (standing) => ({
  teamId: standing.team_id || standing.id,
  teamName: standing.team_name,
  rank: standing.ranking,
  gamesPlayed: standing.games_played,
  wins: standing.wins,
  losses: standing.losses,
  ties: standing.ties,
  points: standing.points,
  goalsFor: standing.goals_for,
  goalsAgainst: standing.goals_against,
  streak: null,
});

const transformSeason = (season) => ({
  value: season.id,
  label: season.name,
});

const transformDivision = (division) => ({
  value: division.id,
  label: division.name,
  seasonId: division.season_id,
});

export async function fetchGames(seasonId, divisionId = null, teamId = null) {
  const games = await firestoreService.getGames(seasonId, divisionId, teamId);
  return games.map(transformGame);
}

export async function fetchStandings(seasonId, divisionId) {
  const standings = await firestoreService.getStandings(seasonId, divisionId);
  return standings.map(transformStanding);
}

export async function fetchSeasons() {
  const seasons = await firestoreService.getSeasons();
  return seasons.map(transformSeason);
}

export async function fetchDivisions(seasonId) {
  const divisions = await firestoreService.getDivisions(seasonId);
  return divisions.map(transformDivision);
}

export async function fetchGameById(gameId) {
  try {
    const game = await firestoreService.getGameById(gameId);
    return game ? transformGame(game) : null;
  } catch (error) {
    console.warn('Failed to fetch game:', error);
    return null;
  }
}

export async function fetchScores(seasonId, divisionId, teamId = null) {
  const scores = await firestoreService.getScores(seasonId, divisionId, teamId);
  return scores.map(transformGame);
}

export async function fetchRecentScores(seasonId, maxResults = 10) {
  const scores = await firestoreService.getRecentScores(seasonId, maxResults);
  return scores.map(transformGame);
}

export default {
  fetchGames,
  fetchStandings,
  fetchSeasons,
  fetchDivisions,
  fetchGameById,
  fetchScores,
  fetchRecentScores,
};

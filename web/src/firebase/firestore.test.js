import { describe, it, expect, vi, beforeEach } from 'vitest';
import { collection, doc, getDoc, getDocs, query, where } from 'firebase/firestore';

vi.mock('./config', () => ({
  db: { mocked: true },
  COLLECTIONS: {
    GAMES: 'mhlv2_games',
    STANDINGS: 'mhlv2_standings',
    SEASONS: 'mhlv2_seasons',
    DIVISIONS: 'mhlv2_divisions',
    TEAMS: 'mhlv2_teams',
    METADATA: 'mhlv2_metadata',
  },
  isFirebaseConfigured: vi.fn(() => true),
}));

import {
  getSeasons,
  getDivisions,
  getTeams,
  getGames,
  getGameById,
  getStandings,
  getRecentScores,
  FirestoreError,
} from './firestore';
import { isFirebaseConfigured } from './config';

describe('Firestore Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isFirebaseConfigured).mockReturnValue(true);
  });

  describe('FirestoreError', () => {
    it('creates error with message and code', () => {
      const error = new FirestoreError('Test error', 'TEST_CODE');
      expect(error.message).toBe('Test error');
      expect(error.code).toBe('TEST_CODE');
      expect(error.name).toBe('FirestoreError');
    });

    it('uses default code when none provided', () => {
      const error = new FirestoreError('Test error');
      expect(error.code).toBe('FIRESTORE_ERROR');
    });
  });

  describe('getSeasons', () => {
    it('throws when Firebase is not configured', async () => {
      vi.mocked(isFirebaseConfigured).mockReturnValue(false);
      await expect(getSeasons()).rejects.toThrow('Firebase is not configured');
    });

    it('returns seasons from Firestore', async () => {
      const mockDocs = [
        { id: '1', data: () => ({ name: '2024-25 Season' }) },
        { id: '2', data: () => ({ name: '2023-24 Season' }) },
      ];
      vi.mocked(collection).mockReturnValue('seasons-collection');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const seasons = await getSeasons();

      expect(collection).toHaveBeenCalledWith({ mocked: true }, 'mhlv2_seasons');
      expect(seasons).toHaveLength(2);
      expect(seasons[0]).toEqual({ id: '1', name: '2024-25 Season' });
    });
  });

  describe('getDivisions', () => {
    it('throws when seasonId is missing', async () => {
      await expect(getDivisions('')).rejects.toThrow('seasonId is required');
    });

    it('returns divisions filtered by seasonId', async () => {
      const mockDocs = [
        { id: '1', data: () => ({ name: '10U AA', season_id: '1' }) },
      ];
      vi.mocked(collection).mockReturnValue('divisions-collection');
      vi.mocked(where).mockReturnValue('where-clause');
      vi.mocked(query).mockReturnValue('query');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const divisions = await getDivisions('1');

      expect(collection).toHaveBeenCalledWith({ mocked: true }, 'mhlv2_divisions');
      expect(where).toHaveBeenCalledWith('season_id', '==', '1');
      expect(divisions).toHaveLength(1);
      expect(divisions[0]).toEqual({ id: '1', name: '10U AA', season_id: '1' });
    });
  });

  describe('getTeams', () => {
    it('throws when seasonId is missing', async () => {
      await expect(getTeams('', '1')).rejects.toThrow('seasonId is required');
    });

    it('throws when divisionId is missing', async () => {
      await expect(getTeams('1', '')).rejects.toThrow('divisionId is required');
    });

    it('returns teams filtered by season and division', async () => {
      const mockDocs = [
        { id: '1', data: () => ({ name: 'Blue Devils', season_id: '1', division_id: '2' }) },
      ];
      vi.mocked(collection).mockReturnValue('teams-collection');
      vi.mocked(where).mockReturnValue('where-clause');
      vi.mocked(query).mockReturnValue('query');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const teams = await getTeams('1', '2');

      expect(collection).toHaveBeenCalledWith({ mocked: true }, 'mhlv2_teams');
      expect(teams).toHaveLength(1);
      expect(teams[0].name).toBe('Blue Devils');
    });
  });

  describe('getGames', () => {
    it('throws when seasonId is missing', async () => {
      await expect(getGames('', '1')).rejects.toThrow('seasonId is required');
    });

    it('throws when neither divisionId nor teamId is provided', async () => {
      await expect(getGames('1', null, null)).rejects.toThrow('divisionId or teamId is required');
    });

    it('returns games filtered by season and division', async () => {
      const mockDocs = [
        { id: '123', data: () => ({ game_id: '123', home_team: 'Team A', away_team: 'Team B', status: 'Final' }) },
      ];
      vi.mocked(collection).mockReturnValue('games-collection');
      vi.mocked(where).mockReturnValue('where-clause');
      vi.mocked(query).mockReturnValue('query');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const games = await getGames('1', '2');

      expect(collection).toHaveBeenCalledWith({ mocked: true }, 'mhlv2_games');
      expect(games).toHaveLength(1);
      expect(games[0].home_team).toBe('Team A');
    });
  });

  describe('getGameById', () => {
    it('throws when gameId is missing', async () => {
      await expect(getGameById('')).rejects.toThrow('gameId is required');
    });

    it('returns null when game does not exist', async () => {
      vi.mocked(doc).mockReturnValue('doc-ref');
      vi.mocked(getDoc).mockResolvedValue({ exists: () => false });

      const game = await getGameById('123');
      expect(game).toBeNull();
    });

    it('returns game when it exists', async () => {
      vi.mocked(doc).mockReturnValue('doc-ref');
      vi.mocked(getDoc).mockResolvedValue({
        exists: () => true,
        id: '123',
        data: () => ({ home_team: 'Team A', away_team: 'Team B' }),
      });

      const game = await getGameById('123');
      expect(game).toEqual({ id: '123', home_team: 'Team A', away_team: 'Team B' });
    });
  });

  describe('getStandings', () => {
    it('throws when seasonId is missing', async () => {
      await expect(getStandings('', '1')).rejects.toThrow('seasonId is required');
    });

    it('throws when divisionId is missing', async () => {
      await expect(getStandings('1', '')).rejects.toThrow('divisionId is required');
    });

    it('returns standings sorted by ranking', async () => {
      const mockDocs = [
        { id: '2', data: () => ({ team_name: 'Team B', ranking: 2 }) },
        { id: '1', data: () => ({ team_name: 'Team A', ranking: 1 }) },
        { id: '3', data: () => ({ team_name: 'Team C', ranking: 3 }) },
      ];
      vi.mocked(collection).mockReturnValue('standings-collection');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const standings = await getStandings('1', '2');

      expect(standings).toHaveLength(3);
      expect(standings[0].ranking).toBe(1);
      expect(standings[1].ranking).toBe(2);
      expect(standings[2].ranking).toBe(3);
    });
  });

  describe('getRecentScores', () => {
    it('throws when seasonId is missing', async () => {
      await expect(getRecentScores('')).rejects.toThrow('seasonId is required');
    });

    it('filters completed games and sorts by date descending', async () => {
      const mockDocs = [
        { id: '1', data: () => ({ status: 'Final', date: '2024-01-10' }) },
        { id: '2', data: () => ({ status: 'Completed', date: '2024-01-09' }) },
        { id: '3', data: () => ({ status: 'Scheduled', date: '2024-01-11' }) }, // excluded
        { id: '4', data: () => ({ status: 'final', date: '2024-01-08' }) },
      ];
      vi.mocked(collection).mockReturnValue('games-collection');
      vi.mocked(where).mockReturnValue('where-clause');
      vi.mocked(query).mockReturnValue('query');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const scores = await getRecentScores('1', 2);

      expect(where).toHaveBeenCalledWith('season_id', '==', '1');
      expect(scores).toHaveLength(2);
      expect(scores[0].id).toBe('1');
      expect(scores[1].id).toBe('2');
    });

    it('handles missing or invalid dates without crashing', async () => {
      const mockDocs = [
        { id: '1', data: () => ({ status: 'Final', date: '2024-01-10' }) },
        { id: '2', data: () => ({ status: 'Final', date: null }) },
        { id: '3', data: () => ({ status: 'Final', date: 'invalid' }) },
        { id: '4', data: () => ({ status: 'Final', date: '2024-01-09' }) },
      ];
      vi.mocked(collection).mockReturnValue('games-collection');
      vi.mocked(where).mockReturnValue('where-clause');
      vi.mocked(query).mockReturnValue('query');
      vi.mocked(getDocs).mockResolvedValue({ docs: mockDocs });

      const scores = await getRecentScores('1', 4);

      expect(scores).toHaveLength(4);
      expect(scores[0].id).toBe('1');
      expect(scores[1].id).toBe('4');
    });
  });
});

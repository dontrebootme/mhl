import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../firebase/config', () => ({
  isFirebaseConfigured: vi.fn(() => true),
  db: { mocked: true },
  COLLECTIONS: {
    GAMES: 'mhlv2_games',
    STANDINGS: 'mhlv2_standings',
    SEASONS: 'mhlv2_seasons',
    DIVISIONS: 'mhlv2_divisions',
    TEAMS: 'mhlv2_teams',
    METADATA: 'mhlv2_metadata',
  },
}));

vi.mock('../firebase/firestore', () => ({
  getSeasons: vi.fn(),
  getDivisions: vi.fn(),
  getTeams: vi.fn(),
  getGames: vi.fn(),
  getGameById: vi.fn(),
  getStandings: vi.fn(),
  getScores: vi.fn(),
  getRecentScores: vi.fn(),
}));

import {
  fetchGames,
  fetchStandings,
  fetchSeasons,
  fetchDivisions,
  fetchGameById,
  fetchScores,
  fetchRecentScores,
  transformGame,
} from './data';
import * as firestoreService from '../firebase/firestore';

describe('Data Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('transformGame', () => {
    it('converts snake_case fields to camelCase', () => {
      const raw = {
        game_id: '123',
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 3,
        away_score: 2,
        date: '2024-02-15',
        time: '7:00 PM',
        location: 'Ice Arena',
        status: 'Final',
      };
      const game = transformGame(raw);
      expect(game.gameId).toBe('123');
      expect(game.homeTeam).toBe('Team A');
      expect(game.awayTeam).toBe('Team B');
      expect(game.homeScore).toBe(3);
      expect(game.awayScore).toBe(2);
    });

    it('normalizes status: Final → final', () => {
      expect(transformGame({ status: 'Final' }).status).toBe('final');
    });

    it('normalizes status: Completed → final', () => {
      expect(transformGame({ status: 'Completed' }).status).toBe('final');
    });

    it('normalizes status: In Progress → live', () => {
      expect(transformGame({ status: 'In Progress' }).status).toBe('live');
    });

    it('normalizes status: Scheduled → scheduled', () => {
      expect(transformGame({ status: 'Scheduled' }).status).toBe('scheduled');
    });

    it('defaults missing status to scheduled', () => {
      expect(transformGame({}).status).toBe('scheduled');
    });

    it('uses game.id as fallback for gameId', () => {
      expect(transformGame({ id: 'abc' }).gameId).toBe('abc');
    });
  });

  describe('fetchSeasons', () => {
    it('fetches from Firestore and transforms to {value, label}', async () => {
      vi.mocked(firestoreService.getSeasons).mockResolvedValue([
        { id: '1', name: '2024-25 Season' },
        { id: '2', name: '2023-24 Season' },
      ]);

      const seasons = await fetchSeasons();

      expect(firestoreService.getSeasons).toHaveBeenCalled();
      expect(seasons).toHaveLength(2);
      expect(seasons[0]).toEqual({ value: '1', label: '2024-25 Season' });
    });

    it('propagates errors', async () => {
      vi.mocked(firestoreService.getSeasons).mockRejectedValue(new Error('Firestore error'));
      await expect(fetchSeasons()).rejects.toThrow('Firestore error');
    });
  });

  describe('fetchDivisions', () => {
    it('fetches and transforms to {value, label, seasonId}', async () => {
      vi.mocked(firestoreService.getDivisions).mockResolvedValue([
        { id: '1', name: '10U AA', season_id: '5' },
      ]);

      const divisions = await fetchDivisions('5');

      expect(firestoreService.getDivisions).toHaveBeenCalledWith('5');
      expect(divisions[0]).toEqual({ value: '1', label: '10U AA', seasonId: '5' });
    });
  });

  describe('fetchGames', () => {
    it('fetches games and transforms to camelCase', async () => {
      vi.mocked(firestoreService.getGames).mockResolvedValue([
        {
          game_id: '123',
          home_team: 'Team A',
          away_team: 'Team B',
          home_score: 3,
          away_score: 2,
          date: '2024-02-15',
          time: '7:00 PM',
          location: 'Ice Arena',
          status: 'Final',
        },
      ]);

      const games = await fetchGames('1', '2');

      expect(firestoreService.getGames).toHaveBeenCalledWith('1', '2', null);
      expect(games[0]).toMatchObject({
        gameId: '123',
        homeTeam: 'Team A',
        awayTeam: 'Team B',
        homeScore: 3,
        awayScore: 2,
        status: 'final',
      });
    });
  });

  describe('fetchStandings', () => {
    it('fetches standings and transforms to camelCase', async () => {
      vi.mocked(firestoreService.getStandings).mockResolvedValue([
        {
          team_id: '1',
          team_name: 'Blue Devils',
          ranking: 1,
          games_played: 20,
          wins: 15,
          losses: 3,
          ties: 2,
          points: 32,
          goals_for: 65,
          goals_against: 28,
        },
      ]);

      const standings = await fetchStandings('1', '2');

      expect(firestoreService.getStandings).toHaveBeenCalledWith('1', '2');
      expect(standings[0]).toMatchObject({
        teamId: '1',
        teamName: 'Blue Devils',
        rank: 1,
        gamesPlayed: 20,
        wins: 15,
        losses: 3,
        ties: 2,
        points: 32,
        goalsFor: 65,
        goalsAgainst: 28,
      });
    });
  });

  describe('fetchGameById', () => {
    it('returns null when game not found', async () => {
      vi.mocked(firestoreService.getGameById).mockResolvedValue(null);
      const game = await fetchGameById('999');
      expect(game).toBeNull();
    });

    it('transforms game when found', async () => {
      vi.mocked(firestoreService.getGameById).mockResolvedValue({
        game_id: '42',
        home_team: 'A',
        away_team: 'B',
        status: 'final',
        date: '',
        time: '',
        location: '',
      });

      const game = await fetchGameById('42');
      expect(game.gameId).toBe('42');
      expect(game.homeTeam).toBe('A');
    });

    it('returns null on error without throwing', async () => {
      vi.mocked(firestoreService.getGameById).mockRejectedValue(new Error('fail'));
      const game = await fetchGameById('bad-id');
      expect(game).toBeNull();
    });
  });

  describe('fetchRecentScores', () => {
    it('fetches and transforms recent completed games', async () => {
      vi.mocked(firestoreService.getRecentScores).mockResolvedValue([
        { game_id: '1', home_team: 'A', away_team: 'B', status: 'final', date: '2024-01-10', time: '', location: '' },
        { game_id: '2', home_team: 'C', away_team: 'D', status: 'final', date: '2024-01-09', time: '', location: '' },
      ]);

      const scores = await fetchRecentScores('season1');

      expect(firestoreService.getRecentScores).toHaveBeenCalledWith('season1', 10);
      expect(scores).toHaveLength(2);
      expect(scores[0].status).toBe('final');
    });
  });
});

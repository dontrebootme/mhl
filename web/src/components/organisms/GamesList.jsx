import { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import GameCard from '../molecules/GameCard';
import Select from '../atoms/Select';
import Button from '../atoms/Button';

/**
 * Parse time string (e.g., "7:00 PM") to minutes since midnight for comparison
 */
const parseTimeToMinutes = (timeStr) => {
  if (!timeStr) return 0;

  const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
  if (!match) return 0;

  let hours = parseInt(match[1], 10);
  const minutes = parseInt(match[2], 10);
  const period = match[3]?.toUpperCase();

  // Convert to 24-hour format if AM/PM is present
  if (period === 'PM' && hours !== 12) {
    hours += 12;
  } else if (period === 'AM' && hours === 12) {
    hours = 0;
  }

  return hours * 60 + minutes;
};

/**
 * Create a sortable datetime value from date and time strings
 */
const getGameDateTime = (game) => {
  const dateValue = game.date ? new Date(game.date).getTime() : 0;
  const timeValue = parseTimeToMinutes(game.time);
  return dateValue + timeValue * 60 * 1000; // Add time as milliseconds
};

/**
 * GamesList - Filterable/sortable list of games
 */
const GamesList = ({
  games = [],
  onGameClick = null,
  showFilters = true
}) => {
  const [statusFilter, setStatusFilter] = useState('all');
  const [teamFilter, setTeamFilter] = useState('all');
  const [sortOrder, setSortOrder] = useState('date-desc');

  const filteredGames = useMemo(() => {
    let result = [...games];

    // Apply filters
    if (statusFilter !== 'all') {
      result = result.filter(game => game.status === statusFilter);
    }

    if (teamFilter !== 'all') {
      result = result.filter(game =>
        game.homeTeam === teamFilter || game.awayTeam === teamFilter
      );
    }

    // Apply sorting
    result.sort((a, b) => {
      const dateTimeA = getGameDateTime(a);
      const dateTimeB = getGameDateTime(b);

      if (sortOrder === 'date-asc') {
        return dateTimeA - dateTimeB;
      } else {
        // date-desc (default): newest first
        return dateTimeB - dateTimeA;
      }
    });

    return result;
  }, [games, statusFilter, teamFilter, sortOrder]);

  // Get unique teams for filter
  const uniqueTeams = [...new Set(games.flatMap(g => [g.homeTeam, g.awayTeam]))].sort();

  const statusOptions = [
    { value: 'all', label: 'All Games' },
    { value: 'scheduled', label: 'Scheduled' },
    { value: 'live', label: 'Live' },
    { value: 'final', label: 'Final' }
  ];

  const teamOptions = [
    { value: 'all', label: 'All Teams' },
    ...uniqueTeams.map(team => ({ value: team, label: team }))
  ];

  const sortOptions = [
    { value: 'date-desc', label: 'Newest First' },
    { value: 'date-asc', label: 'Oldest First' }
  ];

  return (
    <div className="space-y-4">
      {showFilters && (
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between bg-gray-50 p-4 rounded-lg">
          <div className="flex flex-col sm:flex-row gap-3 flex-1">
            <div className="flex-1">
              <Select
                id="status-filter"
                label="Status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={statusOptions}
              />
            </div>
            <div className="flex-1">
              <Select
                id="team-filter"
                label="Team"
                value={teamFilter}
                onChange={(e) => setTeamFilter(e.target.value)}
                options={teamOptions}
              />
            </div>
            <div className="flex-1">
              <Select
                id="sort-order"
                label="Sort By"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                options={sortOptions}
              />
            </div>
          </div>
          {(statusFilter !== 'all' || teamFilter !== 'all') && (
            <Button
              variant="secondary"
              size="small"
              onClick={() => {
                setStatusFilter('all');
                setTeamFilter('all');
              }}
            >
              Clear Filters
            </Button>
          )}
        </div>
      )}

      {filteredGames.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <div className="text-4xl mb-3">🏒</div>
          {games.length === 0 ? (
            <>
              <p className="text-gray-600 mb-2">No games scheduled yet</p>
              <p className="text-sm text-gray-500">Check back later for upcoming games!</p>
            </>
          ) : (
            <>
              <p className="text-gray-600 mb-2">No games found</p>
              <p className="text-sm text-gray-500">Try changing your filters</p>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredGames.map((game) => (
            <GameCard
              key={game.gameId}
              homeTeam={game.homeTeam}
              awayTeam={game.awayTeam}
              homeScore={game.homeScore}
              awayScore={game.awayScore}
              date={game.date}
              time={game.time}
              location={game.location}
              status={game.status}
              homeRecord={game.homeRecord}
              awayRecord={game.awayRecord}
              onClick={onGameClick ? () => onGameClick(game) : null}
            />
          ))}
        </div>
      )}

      {filteredGames.length > 0 && (
        <div className="text-center text-sm text-gray-600">
          Showing {filteredGames.length} of {games.length} games
        </div>
      )}
    </div>
  );
};

GamesList.propTypes = {
  games: PropTypes.arrayOf(
    PropTypes.shape({
      gameId: PropTypes.string.isRequired,
      homeTeam: PropTypes.string.isRequired,
      awayTeam: PropTypes.string.isRequired,
      homeScore: PropTypes.number,
      awayScore: PropTypes.number,
      date: PropTypes.string.isRequired,
      time: PropTypes.string.isRequired,
      location: PropTypes.string.isRequired,
      status: PropTypes.string.isRequired,
      homeRecord: PropTypes.object,
      awayRecord: PropTypes.object
    })
  ).isRequired,
  onGameClick: PropTypes.func,
  showFilters: PropTypes.bool
};

export default GamesList;

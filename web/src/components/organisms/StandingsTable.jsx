import { useState } from 'react';
import PropTypes from 'prop-types';
import Card from '../atoms/Card';
import StandingCard from '../molecules/StandingCard';
import StandingRow from '../molecules/StandingRow';

/**
 * SortIcon - Displays sort direction indicator
 */
const SortIcon = ({ column, sortBy, sortDir }) => {
  if (sortBy !== column) {
    return <span className="text-ice-700 opacity-60">↕</span>;
  }
  return <span className="text-ice-300">{sortDir === 'asc' ? '↑' : '↓'}</span>;
};

SortIcon.propTypes = {
  column: PropTypes.string.isRequired,
  sortBy: PropTypes.string.isRequired,
  sortDir: PropTypes.string.isRequired,
};

const headerCellClass = 'py-3 px-4 text-xs font-display font-bold text-ice-300 uppercase tracking-widest cursor-pointer hover:text-white transition-colors select-none';

/**
 * StandingsTable - Complete division standings with sorting
 */
const StandingsTable = ({
  standings = [],
  currentTeamId = null,
  onTeamClick = null
}) => {
  const [sortBy, setSortBy] = useState('rank');
  const [sortDir, setSortDir] = useState('asc');

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const getGoalDiffColor = (diff) => diff > 0 ? 'text-win' : diff < 0 ? 'text-loss' : 'text-gray-600';

  const getSortedStandings = () => {
    return [...standings]
      .map((s) => {
        const goalDiff = s.goalsFor - s.goalsAgainst;
        return { ...s, goalDiff, goalDiffColor: getGoalDiffColor(goalDiff) };
      })
      .sort((a, b) => {
        let aVal = a[sortBy];
        let bVal = b[sortBy];

        if (sortBy === 'teamName') {
          return sortDir === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal);
        }

        if (sortDir === 'asc') {
          return aVal - bVal;
        }
        return bVal - aVal;
      });
  };

  const sortedStandings = getSortedStandings();

  return (
    <>
      {/* Mobile Card View */}
      <div className="md:hidden space-y-2">
        {sortedStandings.map((standing) => (
          <StandingCard
            key={standing.teamId}
            rank={standing.rank}
            teamName={standing.teamName}
            gamesPlayed={standing.gamesPlayed}
            wins={standing.wins}
            losses={standing.losses}
            ties={standing.ties}
            points={standing.points}
            goalDiff={standing.goalDiff}
            goalDiffColor={standing.goalDiffColor}
            isCurrentTeam={standing.teamId === currentTeamId}
            onClick={onTeamClick ? () => onTeamClick(standing) : null}
          />
        ))}
      </div>

      {/* Desktop Table View */}
      <Card padding={false} className="overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-ice-900 sticky top-0">
              <tr>
                <th
                  className={`${headerCellClass} text-left`}
                  onClick={() => handleSort('rank')}
                >
                  <div className="flex items-center gap-1">
                    Rank <SortIcon column="rank" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-left`}
                  onClick={() => handleSort('teamName')}
                >
                  <div className="flex items-center gap-1">
                    Team <SortIcon column="teamName" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('gamesPlayed')}
                >
                  <div className="flex items-center justify-center gap-1">
                    GP <SortIcon column="gamesPlayed" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('wins')}
                >
                  <div className="flex items-center justify-center gap-1">
                    W <SortIcon column="wins" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('losses')}
                >
                  <div className="flex items-center justify-center gap-1">
                    L <SortIcon column="losses" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('ties')}
                >
                  <div className="flex items-center justify-center gap-1">
                    T <SortIcon column="ties" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('points')}
                >
                  <div className="flex items-center justify-center gap-1">
                    PTS <SortIcon column="points" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('goalsFor')}
                >
                  <div className="flex items-center justify-center gap-1">
                    GF <SortIcon column="goalsFor" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th
                  className={`${headerCellClass} text-center`}
                  onClick={() => handleSort('goalsAgainst')}
                >
                  <div className="flex items-center justify-center gap-1">
                    GA <SortIcon column="goalsAgainst" sortBy={sortBy} sortDir={sortDir} />
                  </div>
                </th>
                <th className={`${headerCellClass} text-center cursor-default`}>
                  +/−
                </th>
                <th className={`${headerCellClass} text-center cursor-default`}>
                  Streak
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {sortedStandings.map((standing) => (
                <StandingRow
                  key={standing.teamId}
                  rank={standing.rank}
                  teamName={standing.teamName}
                  gamesPlayed={standing.gamesPlayed}
                  wins={standing.wins}
                  losses={standing.losses}
                  ties={standing.ties}
                  points={standing.points}
                  goalsFor={standing.goalsFor}
                  goalsAgainst={standing.goalsAgainst}
                  goalDiff={standing.goalDiff}
                  goalDiffColor={standing.goalDiffColor}
                  streak={standing.streak}
                  isCurrentTeam={standing.teamId === currentTeamId}
                  onClick={onTeamClick ? () => onTeamClick(standing) : null}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
};

StandingsTable.propTypes = {
  standings: PropTypes.arrayOf(
    PropTypes.shape({
      teamId: PropTypes.string.isRequired,
      teamName: PropTypes.string.isRequired,
      rank: PropTypes.number.isRequired,
      gamesPlayed: PropTypes.number.isRequired,
      wins: PropTypes.number.isRequired,
      losses: PropTypes.number.isRequired,
      ties: PropTypes.number.isRequired,
      points: PropTypes.number.isRequired,
      goalsFor: PropTypes.number.isRequired,
      goalsAgainst: PropTypes.number.isRequired,
      streak: PropTypes.string
    })
  ).isRequired,
  currentTeamId: PropTypes.string,
  onTeamClick: PropTypes.func
};

export default StandingsTable;

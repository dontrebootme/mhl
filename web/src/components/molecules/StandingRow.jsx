import PropTypes from 'prop-types';
import RankBadge from '../atoms/RankBadge';

const rankBorderClass = (rank) => {
  if (rank === 1) return 'border-l-4 border-yellow-400';
  if (rank === 2) return 'border-l-4 border-gray-400';
  if (rank === 3) return 'border-l-4 border-orange-400';
  return 'border-l-4 border-transparent';
};

/**
 * StandingRow - Single row in standings table
 */
const StandingRow = ({
  rank,
  teamName,
  gamesPlayed,
  wins,
  losses,
  ties,
  points,
  goalsFor,
  goalsAgainst,
  goalDiff,
  goalDiffColor,
  streak = null,
  isCurrentTeam = false,
  onClick = null
}) => {
  return (
    <tr
      className={`
        hover:bg-ice-50 transition-colors even:bg-gray-50/40
        ${rankBorderClass(rank)}
        ${isCurrentTeam ? 'bg-ice-50' : ''}
        ${onClick ? 'cursor-pointer' : ''}
      `}
      onClick={onClick}
    >
      <td className="py-3 px-4">
        <RankBadge rank={rank} size="small" />
      </td>
      <td className={`py-3 px-4 ${isCurrentTeam ? 'font-semibold text-ice-700' : 'font-medium text-gray-900'}`}>
        {teamName}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-600">
        {gamesPlayed}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
        {wins}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
        {losses}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
        {ties}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm font-bold text-gray-900">
        {points}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-600">
        {goalsFor}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-600">
        {goalsAgainst}
      </td>
      <td className={`py-3 px-4 text-center font-mono text-sm font-semibold ${goalDiffColor}`}>
        {goalDiff > 0 ? '+' : ''}{goalDiff}
      </td>
      <td className="py-3 px-4 text-center">
        <span className="text-xs font-medium text-gray-600">
          {streak || '-'}
        </span>
      </td>
    </tr>
  );
};

StandingRow.propTypes = {
  rank: PropTypes.number.isRequired,
  teamName: PropTypes.string.isRequired,
  gamesPlayed: PropTypes.number.isRequired,
  wins: PropTypes.number.isRequired,
  losses: PropTypes.number.isRequired,
  ties: PropTypes.number.isRequired,
  points: PropTypes.number.isRequired,
  goalsFor: PropTypes.number.isRequired,
  goalsAgainst: PropTypes.number.isRequired,
  goalDiff: PropTypes.number.isRequired,
  goalDiffColor: PropTypes.string.isRequired,
  streak: PropTypes.string,
  isCurrentTeam: PropTypes.bool,
  onClick: PropTypes.func
};

export default StandingRow;

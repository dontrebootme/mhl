import PropTypes from 'prop-types';
import RankBadge from '../atoms/RankBadge';

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
        border-b border-gray-200 last:border-0
        hover:bg-ice-50 transition-colors
        ${isCurrentTeam ? 'bg-ice-100 border-l-4 border-ice-500' : ''}
        ${onClick ? 'cursor-pointer' : ''}
      `}
      onClick={onClick}
    >
      <td className="py-3 px-4">
        <RankBadge rank={rank} size="small" />
      </td>
      <td className={`py-3 px-4 ${isCurrentTeam ? 'font-semibold' : 'font-medium'} text-gray-900`}>
        {teamName}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
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
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
        {goalsFor}
      </td>
      <td className="py-3 px-4 text-center font-mono text-sm text-gray-700">
        {goalsAgainst}
      </td>
      <td className={`py-3 px-4 text-center font-mono text-sm font-medium ${goalDiffColor}`}>
        {goalDiff > 0 ? '+' : ''}{goalDiff}
      </td>
      <td className="py-3 px-4 text-center">
        <span className="text-xs font-medium text-gray-700">
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

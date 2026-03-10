import PropTypes from 'prop-types';
import RankBadge from '../atoms/RankBadge';

/**
 * StandingCard - Mobile-friendly standing display card
 */
const StandingCard = ({
  rank,
  teamName,
  gamesPlayed,
  wins,
  losses,
  ties,
  points,
  goalDiff,
  goalDiffColor,
  isCurrentTeam = false,
  onClick = null
}) => {
  return (
    <div
      className={`bg-white rounded-lg border shadow-sm p-3 ${isCurrentTeam ? 'border-ice-500 bg-ice-50' : 'border-gray-200'} ${onClick ? 'cursor-pointer active:bg-gray-50' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <RankBadge rank={rank} size="small" />
          <span className={`font-medium text-gray-900 truncate ${isCurrentTeam ? 'font-semibold' : ''}`}>
            {teamName}
          </span>
        </div>
        <span className="font-bold text-gray-900 text-lg ml-2 shrink-0">
          {points} <span className="text-xs font-normal text-gray-500">PTS</span>
        </span>
      </div>
      <div className="flex items-center justify-between mt-2 text-sm text-gray-600">
        <span className="font-mono">
          {wins}-{losses}-{ties}
        </span>
        <div className="flex items-center gap-3">
          <span className="text-gray-500">{gamesPlayed} GP</span>
          <span className={`font-mono font-medium ${goalDiffColor}`}>
            {goalDiff > 0 ? '+' : ''}{goalDiff}
          </span>
        </div>
      </div>
    </div>
  );
};

StandingCard.propTypes = {
  rank: PropTypes.number.isRequired,
  teamName: PropTypes.string.isRequired,
  gamesPlayed: PropTypes.number.isRequired,
  wins: PropTypes.number.isRequired,
  losses: PropTypes.number.isRequired,
  ties: PropTypes.number.isRequired,
  points: PropTypes.number.isRequired,
  goalDiff: PropTypes.number.isRequired,
  goalDiffColor: PropTypes.string.isRequired,
  isCurrentTeam: PropTypes.bool,
  onClick: PropTypes.func
};

export default StandingCard;

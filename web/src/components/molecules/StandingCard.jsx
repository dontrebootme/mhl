import PropTypes from 'prop-types';
import RankBadge from '../atoms/RankBadge';

const rankTopBarClass = (rank) => {
  if (rank === 1) return 'bg-yellow-400';
  if (rank === 2) return 'bg-gray-400';
  if (rank === 3) return 'bg-orange-400';
  return null;
};

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
  const topBar = rankTopBarClass(rank);

  return (
    <div
      className={`bg-white rounded-xl border shadow-sm overflow-hidden ${isCurrentTeam ? 'border-ice-400 ring-1 ring-ice-400/30' : 'border-gray-200'} ${onClick ? 'cursor-pointer active:bg-gray-50' : ''}`}
      onClick={onClick}
    >
      {/* Medal accent bar for top 3 */}
      {topBar && <div className={`h-1 ${topBar}`} />}

      <div className="p-3">
        <div className="flex items-center gap-3">
          <RankBadge rank={rank} size="small" />
          <span className={`font-display font-bold text-base uppercase truncate flex-1 min-w-0 ${isCurrentTeam ? 'text-ice-700' : 'text-gray-900'}`}>
            {teamName}
          </span>
          <div className="shrink-0 text-right">
            <span className="font-mono font-black text-xl text-gray-900 leading-none">{points}</span>
            <span className="text-[10px] font-bold text-gray-400 tracking-wider ml-0.5">PTS</span>
          </div>
        </div>
        <div className="flex items-center justify-between mt-2 pl-9">
          <span className="font-mono text-sm text-gray-600">
            {wins}–{losses}–{ties}
          </span>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span>{gamesPlayed} GP</span>
            <span className={`font-mono font-semibold ${goalDiffColor}`}>
              {goalDiff > 0 ? '+' : ''}{goalDiff}
            </span>
          </div>
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

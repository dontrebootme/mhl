import PropTypes from 'prop-types';
import DateBadge from '../atoms/DateBadge';
import StatusBadge from '../atoms/StatusBadge';
import LocationPin from '../atoms/LocationPin';
import RecordDisplay from '../atoms/RecordDisplay';

/**
 * GameCard - Horizontal scoreboard layout with VS split
 */
const GameCard = ({
  homeTeam,
  awayTeam,
  homeScore = null,
  awayScore = null,
  date,
  time,
  location,
  status = 'scheduled',
  homeRecord = null,
  awayRecord = null,
  onClick = null
}) => {
  const isCompleted = status === 'final';
  const isLive = status === 'live';
  const hasScore = isCompleted || isLive;
  const homeWon = isCompleted && homeScore > awayScore;
  const awayWon = isCompleted && awayScore > homeScore;

  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden hover:shadow-md transition-all duration-200 ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      {/* Top accent line */}
      {isCompleted && (
        <div className="h-0.5 bg-gradient-to-r from-ice-700 to-ice-500" />
      )}
      {isLive && (
        <div className="h-0.5 bg-team-red-500" />
      )}

      <div className="p-4">
        {/* Date & Status row */}
        <div className="flex items-center justify-between mb-4">
          <DateBadge date={date} variant="compact" />
          <StatusBadge status={status} />
        </div>

        {/* VS layout: home | score | away */}
        <div className="flex items-center gap-3">
          {/* Home team */}
          <div className="flex-1 min-w-0 text-left">
            <div className={`font-display font-bold text-xl uppercase leading-tight truncate ${isCompleted && !homeWon ? 'text-gray-400' : 'text-gray-900'}`}>
              {homeTeam}
            </div>
            {homeRecord && (
              <RecordDisplay
                wins={homeRecord.wins}
                losses={homeRecord.losses}
                ties={homeRecord.ties}
                className="text-gray-500"
              />
            )}
          </div>

          {/* Score / VS center */}
          <div className="shrink-0 text-center">
            {hasScore ? (
              <div className="flex items-center gap-1 tabular-nums">
                <span className={`font-mono font-black text-4xl leading-none ${isCompleted && !homeWon ? 'text-gray-300' : 'text-gray-900'}`}>
                  {homeScore}
                </span>
                <span className="text-gray-200 text-2xl font-light mx-0.5">–</span>
                <span className={`font-mono font-black text-4xl leading-none ${isCompleted && !awayWon ? 'text-gray-300' : 'text-gray-900'}`}>
                  {awayScore}
                </span>
              </div>
            ) : (
              <span className="font-display font-bold text-2xl text-gray-300 tracking-widest">VS</span>
            )}
          </div>

          {/* Away team */}
          <div className="flex-1 min-w-0 text-right">
            <div className={`font-display font-bold text-xl uppercase leading-tight truncate ${isCompleted && !awayWon ? 'text-gray-400' : 'text-gray-900'}`}>
              {awayTeam}
            </div>
            {awayRecord && (
              <RecordDisplay
                wins={awayRecord.wins}
                losses={awayRecord.losses}
                ties={awayRecord.ties}
                className="text-gray-500"
              />
            )}
          </div>
        </div>

        {/* Footer: time & location */}
        <div className="flex items-center justify-center gap-2 mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500">
          <span className="font-medium">{time}</span>
          <span className="text-gray-200">·</span>
          <LocationPin location={location} compact />
        </div>
      </div>
    </div>
  );
};

GameCard.propTypes = {
  homeTeam: PropTypes.string.isRequired,
  awayTeam: PropTypes.string.isRequired,
  homeScore: PropTypes.number,
  awayScore: PropTypes.number,
  date: PropTypes.string.isRequired,
  time: PropTypes.string.isRequired,
  location: PropTypes.string.isRequired,
  status: PropTypes.oneOf(['scheduled', 'live', 'final', 'cancelled', 'postponed']),
  homeRecord: PropTypes.shape({
    wins: PropTypes.number,
    losses: PropTypes.number,
    ties: PropTypes.number
  }),
  awayRecord: PropTypes.shape({
    wins: PropTypes.number,
    losses: PropTypes.number,
    ties: PropTypes.number
  }),
  onClick: PropTypes.func
};

export default GameCard;

import PropTypes from 'prop-types';
import Card from '../atoms/Card';
import Badge from '../atoms/Badge';
import StatusBadge from '../atoms/StatusBadge';
import DateBadge from '../atoms/DateBadge';
import LocationPin from '../atoms/LocationPin';
import RecordDisplay from '../atoms/RecordDisplay';

/**
 * GameCard - Compact game display for lists
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
  const homeWon = isCompleted && homeScore > awayScore;
  const awayWon = isCompleted && awayScore > homeScore;
  const isTie = isCompleted && homeScore === awayScore;

  return (
    <Card
      className={`hover:shadow-lg transition-all duration-200 ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
      padding={false}
    >
      <div className="p-4">
        {/* Header with Date and Status */}
        <div className="flex items-center justify-between mb-3">
          <DateBadge date={date} variant="compact" />
          <StatusBadge status={status} />
        </div>

        {/* Teams and Score */}
        <div className="space-y-2">
          {/* Home Team */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="font-semibold text-gray-900 truncate">
                {homeTeam}
              </span>
              {homeRecord && (
                <RecordDisplay
                  wins={homeRecord.wins}
                  losses={homeRecord.losses}
                  ties={homeRecord.ties}
                  className="text-gray-600"
                />
              )}
            </div>
            <div className="flex items-center gap-2">
              {isCompleted && homeWon && <Badge variant="win">W</Badge>}
              {isCompleted && isTie && <Badge variant="tie">T</Badge>}
              {(isCompleted || isLive) && (
                <span className="font-mono text-2xl font-bold text-gray-900 w-8 text-right">
                  {homeScore}
                </span>
              )}
            </div>
          </div>

          {/* Away Team */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="font-semibold text-gray-900 truncate">
                {awayTeam}
              </span>
              {awayRecord && (
                <RecordDisplay
                  wins={awayRecord.wins}
                  losses={awayRecord.losses}
                  ties={awayRecord.ties}
                  className="text-gray-600"
                />
              )}
            </div>
            <div className="flex items-center gap-2">
              {isCompleted && awayWon && <Badge variant="win">W</Badge>}
              {isCompleted && isTie && <Badge variant="tie">T</Badge>}
              {(isCompleted || isLive) && (
                <span className="font-mono text-2xl font-bold text-gray-900 w-8 text-right">
                  {awayScore}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Footer with Time and Location */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
          <span className="text-sm text-gray-600">{time}</span>
          <LocationPin location={location} compact />
        </div>
      </div>
    </Card>
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

import PropTypes from 'prop-types';
import Card from '../atoms/Card';
import RecordDisplay from '../atoms/RecordDisplay';
import RankBadge from '../atoms/RankBadge';

/**
 * TeamCard - Team overview card with stats
 */
const TeamCard = ({
  teamName,
  division = '',
  rank = null,
  wins,
  losses,
  ties,
  points = null,
  goalsFor = null,
  goalsAgainst = null,
  streak = null,
  onClick = null
}) => {
  const goalDiff = goalsFor !== null && goalsAgainst !== null ? goalsFor - goalsAgainst : null;

  return (
    <Card
      className={`hover:shadow-lg transition-shadow duration-200 ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-xl font-bold text-gray-900 truncate mb-1">
            {teamName}
          </h3>
          {division && (
            <p className="text-sm text-gray-600">
              {division}
            </p>
          )}
        </div>
        {rank && <RankBadge rank={rank} size="large" />}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs text-gray-600 uppercase tracking-wide mb-1">Record</p>
          <RecordDisplay wins={wins} losses={losses} ties={ties} className="text-lg font-bold" />
        </div>
        {points !== null && (
          <div className="text-right">
            <p className="text-xs text-gray-600 uppercase tracking-wide mb-1">Points</p>
            <p className="text-lg font-bold font-mono text-gray-900">{points}</p>
          </div>
        )}
      </div>

      {(goalsFor !== null || streak) && (
        <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
          {goalsFor !== null && (
            <div className="flex gap-4 text-sm">
              <div>
                <span className="text-gray-600">GF:</span>{' '}
                <span className="font-mono font-medium">{goalsFor}</span>
              </div>
              <div>
                <span className="text-gray-600">GA:</span>{' '}
                <span className="font-mono font-medium">{goalsAgainst}</span>
              </div>
              {goalDiff !== null && (
                <div>
                  <span className="text-gray-600">Diff:</span>{' '}
                  <span className={`font-mono font-medium ${
                    goalDiff > 0 ? 'text-win' : goalDiff < 0 ? 'text-loss' : 'text-gray-600'
                  }`}>
                    {goalDiff > 0 ? '+' : ''}{goalDiff}
                  </span>
                </div>
              )}
            </div>
          )}
          {streak && (
            <div className="text-right">
              <span className="text-xs text-gray-600 uppercase tracking-wide">Streak: </span>
              <span className="text-sm font-medium text-gray-900">{streak}</span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

TeamCard.propTypes = {
  teamName: PropTypes.string.isRequired,
  division: PropTypes.string,
  rank: PropTypes.number,
  wins: PropTypes.number.isRequired,
  losses: PropTypes.number.isRequired,
  ties: PropTypes.number.isRequired,
  points: PropTypes.number,
  goalsFor: PropTypes.number,
  goalsAgainst: PropTypes.number,
  streak: PropTypes.string,
  onClick: PropTypes.func
};

export default TeamCard;

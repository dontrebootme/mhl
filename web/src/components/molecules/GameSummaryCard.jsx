import PropTypes from 'prop-types';
import Card from '../atoms/Card';
import Badge from '../atoms/Badge';

/**
 * GameSummaryCard - Past game summary for scouting reports
 * TODO: Add compact variant if needed for condensed views (e.g., sidebar, mobile)
 */
const GameSummaryCard = ({
  date,
  opponent,
  score,
  result, // 'W', 'L', or 'T'
  goalsFor,
  goalsAgainst,
  keyMoments = []
}) => {
  const getResultBadge = () => {
    if (result === 'W') return <Badge variant="win">W</Badge>;
    if (result === 'L') return <Badge variant="loss">L</Badge>;
    return <Badge variant="tie">T</Badge>;
  };

  const getResultStyles = () => {
    if (result === 'W') return 'border-l-4 border-win bg-green-50/30';
    if (result === 'L') return 'border-l-4 border-loss bg-red-50/30';
    return 'border-l-4 border-tie bg-yellow-50/30';
  };

  const goalDiff = goalsFor - goalsAgainst;
  const goalDiffText = goalDiff > 0 ? `+${goalDiff}` : goalDiff.toString();

  return (
    <Card className={`hover:shadow-md transition-shadow duration-200 ${getResultStyles()}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {getResultBadge()}
          <div>
            <p className="text-lg font-semibold text-gray-900">vs {opponent}</p>
            <p className="text-sm text-gray-600">{date}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-mono text-4xl font-bold text-gray-900 leading-none mb-2">{score}</p>
          <div className="flex items-center gap-3 justify-end">
            <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-xs">
              <span className="text-gray-500 text-right">GF:</span>
              <span className="font-semibold text-gray-900">{goalsFor}</span>
              <span className="text-gray-500 text-right">GA:</span>
              <span className="font-semibold text-gray-900">{goalsAgainst}</span>
            </div>
            <div className={`px-2 py-1 rounded-md font-bold text-sm ${goalDiff > 0
              ? 'bg-green-100 text-green-700'
              : goalDiff < 0
                ? 'bg-red-100 text-red-700'
                : 'bg-gray-100 text-gray-700'
              }`}>
              {goalDiffText}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
          {keyMoments && keyMoments.length > 0 ? 'Key Moments' : 'Summary'}
        </p>
        {keyMoments && keyMoments.length > 0 ? (
          <ul className="space-y-1">
            {keyMoments.map((moment, idx) => (
              <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                <span className="text-ice-500 mt-0.5">•</span>
                <span>{moment}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500 italic">
            {result === 'W'
              ? `Won ${goalDiff > 1 ? 'convincingly' : 'narrowly'} against ${opponent}`
              : result === 'L'
                ? `Lost by ${Math.abs(goalDiff)} goal${Math.abs(goalDiff) !== 1 ? 's' : ''} to ${opponent}`
                : `Tied game with ${opponent}`
            }
          </p>
        )}
      </div>
    </Card>
  );
};

GameSummaryCard.propTypes = {
  date: PropTypes.string.isRequired,
  opponent: PropTypes.string.isRequired,
  score: PropTypes.string.isRequired,
  result: PropTypes.oneOf(['W', 'L', 'T']).isRequired,
  goalsFor: PropTypes.number.isRequired,
  goalsAgainst: PropTypes.number.isRequired,
  keyMoments: PropTypes.arrayOf(PropTypes.string)
};

export default GameSummaryCard;

import PropTypes from 'prop-types';
import Badge from '../atoms/Badge';

/**
 * StreakDisplay - Visual W/L/T streak display
 */
const StreakDisplay = ({ streak, maxGames = 10, variant = 'dots' }) => {
  // streak is an array of 'W', 'L', or 'T'
  const results = Array.isArray(streak) ? streak.slice(-maxGames) : [];

  if (variant === 'dots') {
    return (
      <div className="flex items-center gap-1">
        {results.map((result, idx) => {
          const colorClass =
            result === 'W' ? 'bg-win' :
            result === 'L' ? 'bg-loss' :
            'bg-tie';

          return (
            <div
              key={idx}
              className={`w-2 h-2 rounded-full ${colorClass}`}
              title={result === 'W' ? 'Win' : result === 'L' ? 'Loss' : 'Tie'}
            />
          );
        })}
      </div>
    );
  }

  if (variant === 'badges') {
    return (
      <div className="flex items-center gap-1 flex-wrap">
        {results.map((result, idx) => {
          const badgeVariant =
            result === 'W' ? 'win' :
            result === 'L' ? 'loss' :
            'tie';

          return (
            <Badge key={idx} variant={badgeVariant}>
              {result}
            </Badge>
          );
        })}
      </div>
    );
  }

  // Compact text variant
  return (
    <span className="font-mono text-sm">
      {results.map((result, idx) => {
        const colorClass =
          result === 'W' ? 'text-win' :
          result === 'L' ? 'text-loss' :
          'text-tie';

        return (
          <span key={idx} className={`${colorClass} font-bold`}>
            {result}
          </span>
        );
      }).reduce((prev, curr, idx) => [prev, <span key={`sep-${idx}`} className="text-gray-400">-</span>, curr])}
    </span>
  );
};

StreakDisplay.propTypes = {
  streak: PropTypes.arrayOf(PropTypes.oneOf(['W', 'L', 'T'])).isRequired,
  maxGames: PropTypes.number,
  variant: PropTypes.oneOf(['dots', 'badges', 'text'])
};

export default StreakDisplay;

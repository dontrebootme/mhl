import PropTypes from 'prop-types';

/**
 * RankBadge - Circular rank badge with color coding
 */
const RankBadge = ({ rank, size = 'medium', className = '' }) => {
  const sizeClasses = {
    small: 'w-6 h-6 text-xs',
    medium: 'w-8 h-8 text-sm',
    large: 'w-10 h-10 text-base'
  };

  // Color based on rank (top 3 get special colors)
  const getRankColor = (rank) => {
    if (rank === 1) return 'bg-yellow-400 text-yellow-900 ring-2 ring-yellow-500'; // Gold
    if (rank === 2) return 'bg-gray-300 text-gray-800 ring-2 ring-gray-400'; // Silver
    if (rank === 3) return 'bg-orange-400 text-orange-900 ring-2 ring-orange-500'; // Bronze
    return 'bg-ice-100 text-ice-800'; // Default
  };

  return (
    <div className={`${sizeClasses[size]} ${getRankColor(rank)} rounded-full flex items-center justify-center font-bold font-mono ${className}`}>
      {rank}
    </div>
  );
};

RankBadge.propTypes = {
  rank: PropTypes.number.isRequired,
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  className: PropTypes.string
};

export default RankBadge;

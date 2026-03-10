import PropTypes from 'prop-types';

/**
 * RankBadge - Circular rank badge with gold/silver/bronze medal treatment for top 3
 */
const RankBadge = ({ rank, size = 'medium', className = '' }) => {
  const sizeClasses = {
    small: 'w-6 h-6 text-xs',
    medium: 'w-8 h-8 text-sm',
    large: 'w-10 h-10 text-base'
  };

  const getRankStyle = (rank) => {
    if (rank === 1) return 'bg-gradient-to-br from-yellow-300 to-yellow-500 text-yellow-900 ring-1 ring-yellow-400 shadow-sm shadow-yellow-200';
    if (rank === 2) return 'bg-gradient-to-br from-gray-200 to-gray-400 text-gray-800 ring-1 ring-gray-300 shadow-sm';
    if (rank === 3) return 'bg-gradient-to-br from-orange-300 to-orange-500 text-orange-900 ring-1 ring-orange-400 shadow-sm shadow-orange-100';
    return 'bg-ice-100 text-ice-800';
  };

  return (
    <div className={`${sizeClasses[size]} ${getRankStyle(rank)} rounded-full flex items-center justify-center font-bold font-mono ${className}`}>
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

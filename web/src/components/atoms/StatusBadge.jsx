import PropTypes from 'prop-types';

/**
 * StatusBadge - Game status indicator
 */
const StatusBadge = ({ status, className = '' }) => {
  const statusConfig = {
    scheduled: {
      text: 'Scheduled',
      classes: 'bg-gray-100 text-gray-700'
    },
    live: {
      text: 'Live',
      classes: 'bg-red-600 text-white',
      withPulse: true
    },
    final: {
      text: 'Final',
      classes: 'bg-gray-900 text-white font-semibold'
    },
    cancelled: {
      text: 'Cancelled',
      classes: 'bg-gray-300 text-gray-600 line-through'
    },
    postponed: {
      text: 'Postponed',
      classes: 'bg-yellow-100 text-yellow-800'
    }
  };

  const config = statusConfig[status] || statusConfig.scheduled;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium uppercase tracking-wide ${config.classes} ${className}`}>
      {config.withPulse && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-200"></span>
        </span>
      )}
      {config.text}
    </span>
  );
};

StatusBadge.propTypes = {
  status: PropTypes.oneOf(['scheduled', 'live', 'final', 'cancelled', 'postponed']).isRequired,
  className: PropTypes.string
};

export default StatusBadge;

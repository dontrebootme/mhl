import PropTypes from 'prop-types';

/**
 * LocationPin - Rink/arena display with icon
 */
const LocationPin = ({ location, compact = false, className = '' }) => {
  return (
    <div className={`inline-flex items-center gap-1.5 ${compact ? 'text-xs' : 'text-sm'} text-gray-600 ${className}`}>
      <svg
        className={`${compact ? 'w-3 h-3' : 'w-4 h-4'} flex-shrink-0`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
        />
      </svg>
      <span className="truncate">{location}</span>
    </div>
  );
};

LocationPin.propTypes = {
  location: PropTypes.string.isRequired,
  compact: PropTypes.bool,
  className: PropTypes.string
};

export default LocationPin;

import PropTypes from 'prop-types';

/**
 * DateBadge - Formatted date display
 */
const DateBadge = ({ date, variant = 'default', className = '' }) => {
  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    const month = d.toLocaleDateString('en-US', { month: 'short' });
    const day = d.getDate();
    return { month, day };
  };

  const { month, day } = formatDate(date);

  const variantClasses = {
    default: 'bg-gray-100 text-gray-700',
    compact: 'bg-gray-50 text-gray-600 text-xs'
  };

  return (
    <div className={`inline-flex flex-col items-center justify-center px-2 py-1 rounded ${variantClasses[variant]} ${className}`}>
      <span className="text-xs uppercase font-medium leading-none">{month}</span>
      <span className="text-lg font-bold leading-none mt-0.5">{day}</span>
    </div>
  );
};

DateBadge.propTypes = {
  date: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(['default', 'compact']),
  className: PropTypes.string
};

export default DateBadge;

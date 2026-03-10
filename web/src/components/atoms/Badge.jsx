import PropTypes from 'prop-types';

/**
 * Badge component for status indicators (wins, losses, ties, etc.)
 */
const Badge = ({
  children,
  variant = 'info',
  className = ''
}) => {
  const baseClasses = 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium';

  const variantClasses = {
    win: 'bg-win text-white',
    loss: 'bg-loss text-white',
    tie: 'bg-tie text-gray-900',
    info: 'bg-gray-200 text-gray-800'
  };

  return (
    <span className={`${baseClasses} ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

Badge.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['win', 'loss', 'tie', 'info']),
  className: PropTypes.string
};

export default Badge;

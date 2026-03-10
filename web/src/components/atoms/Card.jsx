import PropTypes from 'prop-types';

/**
 * Card component - container for content with shadow and border
 */
const Card = ({
  children,
  className = '',
  padding = true,
  border = true
}) => {
  const baseClasses = 'bg-white rounded-lg shadow-md';
  const paddingClass = padding ? 'p-6' : '';
  const borderClass = border ? 'border border-gray-200' : '';

  return (
    <div className={`${baseClasses} ${paddingClass} ${borderClass} ${className}`}>
      {children}
    </div>
  );
};

Card.propTypes = {
  children: PropTypes.node.isRequired,
  className: PropTypes.string,
  padding: PropTypes.bool,
  border: PropTypes.bool
};

export default Card;

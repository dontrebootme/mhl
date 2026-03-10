import PropTypes from 'prop-types';

/**
 * Input component for form fields
 */
const Input = ({
  type = 'text',
  value,
  onChange,
  placeholder = '',
  disabled = false,
  required = false,
  className = ''
}) => {
  const baseClasses = 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-ice-500 focus:border-ice-500 hover:border-ice-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-50';

  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      required={required}
      className={`${baseClasses} ${className}`}
    />
  );
};

Input.propTypes = {
  type: PropTypes.oneOf(['text', 'number', 'email', 'password', 'date', 'time']),
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  required: PropTypes.bool,
  className: PropTypes.string
};

export default Input;

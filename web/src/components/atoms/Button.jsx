import PropTypes from 'prop-types';
import Spinner from './Spinner';

/**
 * Button component with multiple variants following the hockey-themed design system
 */
const Button = ({
  children,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  isLoading = false,
  onClick,
  type = 'button',
  className = '',
  ...props
}) => {
  const baseClasses = 'relative font-medium rounded-md transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2';

  const variantClasses = {
    primary: 'bg-ice-500 hover:bg-ice-600 active:bg-ice-700 text-white focus:ring-ice-500 disabled:opacity-50 disabled:cursor-not-allowed',
    secondary: 'bg-white hover:bg-gray-50 active:bg-gray-100 text-ice-600 border-2 border-ice-500 focus:ring-ice-500 disabled:opacity-50 disabled:cursor-not-allowed',
    danger: 'bg-team-red-500 hover:bg-team-red-700 active:bg-team-red-700 text-white focus:ring-team-red-500 disabled:opacity-50 disabled:cursor-not-allowed'
  };

  const sizeClasses = {
    small: 'px-3 py-1.5 text-sm',
    medium: 'px-4 py-2 text-base',
    large: 'px-6 py-3 text-lg'
  };

  const spinnerColor = variant === 'secondary' ? 'text-ice-600' : 'text-white';

  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      <span className={`flex items-center justify-center ${isLoading ? 'invisible' : ''}`}>
        {children}
      </span>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner size="small" color={spinnerColor} />
        </div>
      )}
    </button>
  );
};

Button.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['primary', 'secondary', 'danger']),
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  disabled: PropTypes.bool,
  isLoading: PropTypes.bool,
  onClick: PropTypes.func,
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
  className: PropTypes.string
};

export default Button;

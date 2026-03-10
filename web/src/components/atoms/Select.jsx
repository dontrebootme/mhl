import { useId } from 'react';
import PropTypes from 'prop-types';

/**
 * Select dropdown component with proper styling and accessibility
 */
const Select = ({
  value,
  onChange,
  options = [],
  placeholder = 'Select an option',
  disabled = false,
  className = '',
  label = '',
  id = ''
}) => {
  // Generate a unique ID if not provided (for label association)
  const generatedId = useId();
  const selectId = id || generatedId;


  const baseClasses = `
    w-full px-3 py-2 pr-10
    border border-gray-300 rounded-md
    focus:outline-none focus:ring-2 focus:ring-ice-500 focus:border-ice-500
    hover:border-ice-500 transition-colors
    disabled:opacity-50 disabled:cursor-not-allowed
    bg-white text-gray-900
    appearance-none cursor-pointer
  `.trim().replace(/\s+/g, ' ');

  return (
    <div className="relative">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-xs font-medium text-gray-700 mb-1"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          value={value}
          onChange={onChange}
          disabled={disabled}
          aria-label={label || placeholder}
          className={`${baseClasses} ${className}`}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {/* Dropdown chevron icon */}
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
          <svg
            className="h-4 w-4 text-gray-500"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      </div>
    </div>
  );
};

Select.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      label: PropTypes.string.isRequired
    })
  ).isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string,
  label: PropTypes.string,
  id: PropTypes.string
};

export default Select;

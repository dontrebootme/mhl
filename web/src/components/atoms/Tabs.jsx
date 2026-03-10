import PropTypes from 'prop-types';
import React from 'react';

/**
 * Tabs container component for managing tab state and rendering tab list
 */
const Tabs = ({
  children,
  activeTab,
  onTabChange,
  className = ''
}) => {
  // Ensure children is always an array to handle single child case
  const childArray = React.Children.toArray(children);

  return (
    <div className={className}>
      <div
        className="flex border-b border-gray-200"
        role="tablist"
        aria-label="Award categories"
      >
        {childArray.map((child) => {
          const isActive = child.props.id === activeTab;
          return (
            <button
              key={child.props.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${child.props.id}`}
              id={`tab-${child.props.id}`}
              tabIndex={isActive ? 0 : -1}
              className={`
                flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors
                border-b-2 -mb-px cursor-pointer
                ${isActive
                  ? 'border-ice-600 text-ice-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
                ${child.props.disabled ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              onClick={() => !child.props.disabled && onTabChange(child.props.id)}
              disabled={child.props.disabled}
            >
              {child.props.icon && <span className="text-base">{child.props.icon}</span>}
              <span>{child.props.label}</span>
              {child.props.count !== undefined && (
                <span className={`
                  text-xs px-2 py-0.5 rounded-full font-bold
                  ${isActive ? 'bg-ice-100 text-ice-700' : 'bg-gray-100 text-gray-600'}
                `}>
                  {child.props.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

Tabs.propTypes = {
  children: PropTypes.node.isRequired,
  activeTab: PropTypes.string.isRequired,
  onTabChange: PropTypes.func.isRequired,
  className: PropTypes.string,
};

export default Tabs;

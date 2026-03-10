import PropTypes from 'prop-types';

/**
 * Tab component - represents a single tab's content
 * Used as a child of Tabs component
 */
const Tab = ({
    id,
    children,
    className = ''
}) => {
    return (
        <div
            id={`tabpanel-${id}`}
            role="tabpanel"
            aria-labelledby={`tab-${id}`}
            className={className}
        >
            {children}
        </div>
    );
};

Tab.propTypes = {
    /** Unique identifier for the tab */
    id: PropTypes.string.isRequired,
    /** Tab label (used by parent Tabs component) */
    label: PropTypes.string.isRequired,
    /** Optional icon emoji or element */
    icon: PropTypes.node,
    /** Optional count badge */
    count: PropTypes.number,
    /** Whether tab is disabled */
    disabled: PropTypes.bool,
    /** Tab panel content */
    children: PropTypes.node,
    /** Additional classes for tab panel */
    className: PropTypes.string,
};

export default Tab;

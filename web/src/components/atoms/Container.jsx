import PropTypes from 'prop-types';

/**
 * Container - consistent max-width wrapper with horizontal padding
 * Used for page sections and content areas
 */
const Container = ({ children, className = '', as: Component = 'div' }) => {
    return (
        <Component className={`max-w-7xl mx-auto px-4 ${className}`}>
            {children}
        </Component>
    );
};

Container.propTypes = {
    children: PropTypes.node.isRequired,
    className: PropTypes.string,
    as: PropTypes.elementType
};

export default Container;

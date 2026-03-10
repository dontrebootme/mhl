import PropTypes from 'prop-types';
import { Container } from '../atoms';

/**
 * PageLayout - App shell wrapper that creates unified layout
 * Uses flexbox for sticky footer pattern (footer pushes to bottom on short content)
 */
const PageLayout = ({ header, children, footer }) => {
    return (
        <div className="min-h-screen flex flex-col bg-gray-50">
            {/* Header section */}
            {header}

            {/* Main content - flex-1 fills available space, white background connects header to footer */}
            <main className="flex-1 bg-white shadow-sm">
                <Container className="py-6">
                    {children}
                </Container>
            </main>

            {/* Footer - naturally pushed to bottom */}
            {footer}
        </div>
    );
};

PageLayout.propTypes = {
    header: PropTypes.node.isRequired,
    children: PropTypes.node.isRequired,
    footer: PropTypes.node.isRequired
};

export default PageLayout;

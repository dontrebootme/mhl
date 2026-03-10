import PropTypes from 'prop-types';

/**
 * RecordDisplay - Compact W-L-T record format
 */
const RecordDisplay = ({ wins, losses, ties, className = '' }) => {
  return (
    <span className={`font-mono text-sm ${className}`}>
      {wins}-{losses}-{ties}
    </span>
  );
};

RecordDisplay.propTypes = {
  wins: PropTypes.number.isRequired,
  losses: PropTypes.number.isRequired,
  ties: PropTypes.number.isRequired,
  className: PropTypes.string
};

export default RecordDisplay;

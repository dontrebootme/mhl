import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import StandingsTable from './StandingsTable';
import { fetchStandings, fetchDivisions } from '../../services/data';
import { Card, Select } from '../atoms';

const StandingsView = ({ seasonId }) => {
  const [standings, setStandings] = useState([]);
  const [divisions, setDivisions] = useState([]);
  const [selectedDivision, setSelectedDivision] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load divisions when seasonId changes
  useEffect(() => {
    let mounted = true;

    const loadDivisions = async () => {
      try {
        const data = await fetchDivisions(seasonId);
        if (mounted) {
          setDivisions(data);
          if (data.length > 0) {
            const preferred = data.find((d) => /10u.*green/i.test(d.label));
            setSelectedDivision((preferred ?? data[0]).value);
          }
        }
      } catch (err) {
        console.error('Failed to load divisions:', err);
      }
    };

    // Reset selection when seasonId changes
    setSelectedDivision('');
    loadDivisions();

    return () => {
      mounted = false;
    };
  }, [seasonId]);

  // Load standings when division changes
  useEffect(() => {
    if (!selectedDivision) {
      setStandings([]);
      setLoading(false);
      return;
    }

    let mounted = true;

    const loadStandings = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchStandings(seasonId, selectedDivision);
        if (mounted) {
          setStandings(data);
        }
      } catch (err) {
        if (mounted) {
          setError('Failed to load standings. Please try again later.');
          console.error(err);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadStandings();

    return () => {
      mounted = false;
    };
  }, [seasonId, selectedDivision]);

  const handleDivisionChange = (e) => {
    setSelectedDivision(e.target.value);
  };

  if (loading && !divisions.length) {
    return (
      <div className="space-y-6">
        <Card>
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-ice-600"></div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Standings</h2>
          {divisions.length > 0 && (
            <div className="w-full sm:w-56">
              <Select
                id="standings-division-select"
                value={selectedDivision}
                onChange={handleDivisionChange}
                options={divisions.map((d) => ({
                  value: d.value,
                  label: d.label,
                }))}
                placeholder="Select Division"
              />
            </div>
          )}
        </div>

        {error && (
          <div className="text-center py-12 text-red-600">
            <p>{error}</p>
          </div>
        )}

        {loading && (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-ice-600"></div>
          </div>
        )}

        {!loading && !error && standings.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <p>No standings available for this division.</p>
          </div>
        )}

        {!loading && !error && standings.length > 0 && (
          <StandingsTable standings={standings} />
        )}
      </Card>
    </div>
  );
};

StandingsView.propTypes = {
  seasonId: PropTypes.string.isRequired,
};

export default StandingsView;

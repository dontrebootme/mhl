import { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Select } from './components/atoms';
import { PageLayout } from './components/organisms';
import { fetchSeasons } from './services/data';
import './App.css';

function App() {
  const [selectedSeason, setSelectedSeason] = useState('');
  const [seasonOptions, setSeasonOptions] = useState([]);

  useEffect(() => {
    let mounted = true;

    const loadSeasons = async () => {
      try {
        const seasons = await fetchSeasons();
        if (mounted && seasons.length > 0) {
          const sortedSeasons = [...seasons].sort((a, b) => b.label.localeCompare(a.label));
          setSeasonOptions(sortedSeasons);
          setSelectedSeason(sortedSeasons[0].value);
        }
      } catch (err) {
        console.error('Failed to load seasons:', err);
      }
    };

    loadSeasons();
    return () => { mounted = false; };
  }, []);

  const tabs = [
    { to: '/', label: 'Dashboard', icon: '📊' },
    { to: '/games', label: 'Games', icon: '🏒' },
    { to: '/standings', label: 'Standings', icon: '🏆' },
  ];

  const header = (
    <header className="bg-gradient-to-r from-ice-600 to-ice-800 text-white shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="text-3xl">🏒</div>
            <div>
              <h1 className="text-2xl font-bold">MHL</h1>
              <p className="text-ice-200 text-sm">Metropolitan Hockey League</p>
            </div>
          </div>
          <div className="w-full sm:w-56">
            <label htmlFor="season-select" className="sr-only">Select Season</label>
            <Select
              id="season-select"
              value={selectedSeason}
              onChange={(e) => setSelectedSeason(e.target.value)}
              options={seasonOptions}
              placeholder={seasonOptions.length === 0 ? 'Loading seasons...' : 'Select Season'}
              disabled={seasonOptions.length === 0}
              className="bg-white text-gray-900 font-medium shadow-sm"
            />
          </div>
        </div>

        <nav className="mt-4 border-t border-ice-500 pt-2">
          <div className="flex gap-2 overflow-x-auto">
            {tabs.map(tab => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.to === '/'}
                className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-all
                  ${isActive
                    ? 'bg-white text-ice-700 shadow-md'
                    : 'text-ice-100 hover:bg-ice-500/50'
                  }`
                }
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </div>
    </header>
  );

  const footer = (
    <footer className="bg-gray-800 text-gray-300">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🏒</span>
            <span className="font-semibold">MHL</span>
          </div>
          <p className="text-sm text-gray-400">Metropolitan Hockey League Schedule & Standings</p>
        </div>
      </div>
    </footer>
  );

  return (
    <PageLayout header={header} footer={footer}>
      <Outlet context={{ seasonId: selectedSeason }} />
    </PageLayout>
  );
}

export default App;

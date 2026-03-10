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
    { to: '/', label: 'Dashboard' },
    { to: '/games', label: 'Games' },
    { to: '/standings', label: 'Standings' },
  ];

  const header = (
    <header className="bg-ice-900 text-white sticky top-0 z-50 shadow-2xl">
      {/* Accent stripe */}
      <div className="h-0.5 bg-gradient-to-r from-ice-400 via-ice-300 to-team-red-500" />

      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between py-3 gap-4">
          {/* Wordmark */}
          <div className="flex flex-col items-start shrink-0">
            <span className="font-display font-black text-4xl leading-none tracking-tight text-white uppercase">
              MHL
            </span>
            <span className="text-ice-400 text-[10px] font-semibold tracking-[0.2em] uppercase leading-none mt-0.5 hidden sm:block">
              Metropolitan Hockey League
            </span>
          </div>

          {/* Season selector */}
          <div className="w-full sm:w-48">
            <label htmlFor="season-select" className="sr-only">Select Season</label>
            <Select
              id="season-select"
              value={selectedSeason}
              onChange={(e) => setSelectedSeason(e.target.value)}
              options={seasonOptions}
              placeholder={seasonOptions.length === 0 ? 'Loading seasons...' : 'Select Season'}
              disabled={seasonOptions.length === 0}
              className="bg-ice-800 text-ice-100 border-ice-700 text-sm"
            />
          </div>
        </div>

        {/* Nav */}
        <nav className="border-t border-ice-800/80" aria-label="Main navigation">
          <div className="flex gap-0 overflow-x-auto">
            {tabs.map(tab => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.to === '/'}
                className={({ isActive }) =>
                  `px-5 py-3 font-display font-bold text-sm uppercase tracking-widest transition-colors whitespace-nowrap border-b-2
                  ${isActive
                    ? 'text-white border-ice-400'
                    : 'text-ice-400 hover:text-ice-200 border-transparent'
                  }`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </div>
    </header>
  );

  const footer = (
    <footer className="bg-ice-900 text-ice-500 border-t border-ice-800">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-2">
          <span className="font-display font-black text-xl tracking-tight text-white uppercase">MHL</span>
          <p className="text-xs tracking-wider uppercase">Metropolitan Hockey League · Schedule &amp; Standings</p>
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

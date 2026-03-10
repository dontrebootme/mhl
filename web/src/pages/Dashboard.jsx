import { useState, useEffect } from 'react';
import { useOutletContext, Link } from 'react-router-dom';
import { Card, Spinner, Button } from '../components/atoms';
import { GamesList } from '../components/organisms';
import { fetchRecentScores } from '../services/data';

const Dashboard = () => {
    const { seasonId } = useOutletContext();
    const [recentGames, setRecentGames] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const loadDashboardData = async () => {
            setLoading(true);
            try {
                const scores = await fetchRecentScores(seasonId);
                setRecentGames(scores);
                setError(null);
            } catch (err) {
                console.error('Failed to load dashboard data:', err);
                setError('Failed to load recent scores. Please try again later.');
            } finally {
                setLoading(false);
            }
        };

        if (seasonId) {
            loadDashboardData();
        } else {
            setLoading(false);
        }
    }, [seasonId]);

    if (loading) {
        return (
            <div className="flex justify-center items-center h-64">
                <Spinner size="large" />
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Hero */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-ice-900 via-ice-800 to-ice-900 text-white">
                {/* Diagonal stripe texture */}
                <div
                    className="absolute inset-0 opacity-[0.06]"
                    style={{
                        backgroundImage: 'repeating-linear-gradient(-45deg, white 0, white 1px, transparent 0, transparent 12px)',
                        backgroundSize: '17px 17px'
                    }}
                />
                {/* Bottom accent line */}
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-ice-400 via-ice-300 to-team-red-500" />
                <div className="relative px-8 py-10 md:py-12">
                    <p className="text-ice-400 text-[10px] font-bold tracking-[0.35em] uppercase mb-2">
                        Official League Hub
                    </p>
                    <h1 className="font-display font-black text-5xl md:text-6xl uppercase leading-none text-white">
                        Metropolitan<br />Hockey League
                    </h1>
                    <p className="text-ice-300 text-sm mt-4 max-w-sm leading-relaxed">
                        Schedule, scores, and standings for the Metropolitan Hockey League.
                    </p>
                </div>
            </div>

            {/* Recent Scores */}
            <section>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="font-display font-bold text-2xl uppercase tracking-wide text-gray-900">
                        Recent Scores
                    </h2>
                    <Link to="/games">
                        <Button variant="secondary" size="small">
                            View All Games
                        </Button>
                    </Link>
                </div>

                {error ? (
                    <div className="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">
                        {error}
                    </div>
                ) : recentGames.length > 0 ? (
                    <GamesList games={recentGames} showFilters={false} />
                ) : (
                    <Card>
                        <p className="text-gray-500 text-center py-8">
                            No recent games found for this season. Check back later!
                        </p>
                    </Card>
                )}
            </section>

            {/* Quick-nav cards */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Link to="/standings" className="block group">
                    <div className="h-full rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden group-hover:-translate-y-0.5 transform">
                        <div className="h-1.5 bg-gradient-to-r from-ice-600 to-ice-400" />
                        <div className="p-6">
                            <div className="flex items-center gap-3 mb-2">
                                <div className="w-10 h-10 bg-ice-50 rounded-lg flex items-center justify-center font-display font-black text-xl text-ice-600">
                                    S
                                </div>
                                <h3 className="font-display font-bold text-xl uppercase tracking-wide text-gray-900 group-hover:text-ice-600 transition-colors">
                                    Standings
                                </h3>
                            </div>
                            <p className="text-sm text-gray-600">
                                Current league standings, points, and division rankings.
                            </p>
                        </div>
                    </div>
                </Link>

                <Link to="/games" className="block group">
                    <div className="h-full rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden group-hover:-translate-y-0.5 transform">
                        <div className="h-1.5 bg-gradient-to-r from-team-red-500 to-team-red-700" />
                        <div className="p-6">
                            <div className="flex items-center gap-3 mb-2">
                                <div className="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center font-display font-black text-xl text-team-red-500">
                                    G
                                </div>
                                <h3 className="font-display font-bold text-xl uppercase tracking-wide text-gray-900 group-hover:text-team-red-500 transition-colors">
                                    Schedule
                                </h3>
                            </div>
                            <p className="text-sm text-gray-600">
                                Upcoming games, locations, and past results.
                            </p>
                        </div>
                    </div>
                </Link>
            </section>
        </div>
    );
};

export default Dashboard;

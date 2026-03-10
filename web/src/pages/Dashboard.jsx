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
            <div className="bg-white p-6 rounded-lg shadow-sm border border-ice-100">
                <h1 className="text-2xl font-bold text-ice-800 mb-2">Metropolitan Hockey League</h1>
                <p className="text-gray-600">
                    Schedule, scores, and standings for the Metropolitan Hockey League.
                </p>
            </div>

            <section>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold text-gray-900">Recent Scores</h2>
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

            <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Link to="/standings" className="block group">
                    <Card className="h-full hover:shadow-md transition-shadow border-t-4 border-ice-500">
                        <div className="flex items-center gap-3 mb-3">
                            <span className="text-3xl">🏆</span>
                            <h3 className="text-lg font-bold text-gray-900 group-hover:text-ice-600 transition-colors">
                                Standings
                            </h3>
                        </div>
                        <p className="text-sm text-gray-600">
                            Current league standings, points, and division rankings.
                        </p>
                    </Card>
                </Link>

                <Link to="/games" className="block group">
                    <Card className="h-full hover:shadow-md transition-shadow border-t-4 border-team-red-500">
                        <div className="flex items-center gap-3 mb-3">
                            <span className="text-3xl">🏒</span>
                            <h3 className="text-lg font-bold text-gray-900 group-hover:text-team-red-500 transition-colors">
                                Schedule
                            </h3>
                        </div>
                        <p className="text-sm text-gray-600">
                            Upcoming games, locations, and past results.
                        </p>
                    </Card>
                </Link>
            </section>
        </div>
    );
};

export default Dashboard;

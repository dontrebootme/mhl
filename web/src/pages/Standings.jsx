import { useOutletContext } from 'react-router-dom';
import { StandingsView } from '../components/organisms';

const Standings = () => {
    const { seasonId } = useOutletContext();
    return <StandingsView seasonId={seasonId} />;
};

export default Standings;

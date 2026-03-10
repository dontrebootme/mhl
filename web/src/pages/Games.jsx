import { useOutletContext } from 'react-router-dom';
import { GamesView } from '../components/organisms';

const Games = () => {
    const { seasonId } = useOutletContext();
    return <GamesView seasonId={seasonId} />;
};

export default Games;

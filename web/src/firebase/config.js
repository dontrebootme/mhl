/**
 * Firebase Configuration
 *
 * Initializes Firebase app and exports Firestore instance.
 * Configuration is read from environment variables.
 */

import { initializeApp } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const isFirebaseConfigured = () => {
  return !!(
    firebaseConfig.apiKey &&
    firebaseConfig.projectId &&
    firebaseConfig.apiKey !== 'your-api-key'
  );
};

let app = null;
let db = null;

if (isFirebaseConfigured()) {
  app = initializeApp(firebaseConfig);
  db = getFirestore(app);
}

// Collection names with mhlv2_ prefix (matches backend firestore_config.py)
export const COLLECTIONS = {
  DIVISIONS: 'mhlv2_divisions',
  GAMES: 'mhlv2_games',
  METADATA: 'mhlv2_metadata',
  SEASONS: 'mhlv2_seasons',
  STANDINGS: 'mhlv2_standings',
  TEAMS: 'mhlv2_teams',
};

export { app, db, isFirebaseConfigured };

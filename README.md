# MHL

Metropolitan Hockey League schedule, scores, and standings.

Live at **[mhl.spof.io](https://mhl.spof.io)**

## Stack

- **Frontend**: React 19 + Vite + Tailwind CSS, deployed to Firebase Hosting
- **Data sync**: Python 3.12 Cloud Function (`mhlv2_sync`) — scrapes TeamLinkt, writes to Firestore
- **Database**: Firestore (collections prefixed `mhlv2_`)
- **CI/CD**: GitHub Actions → Firebase (staging on every merge to `main`)

## Project Structure

```
mhl/
├── functions/          # mhlv2_sync Cloud Function (Python)
│   ├── main.py         # Function entry point
│   ├── clients/        # TeamLinkt API client
│   ├── services/       # Sync + cache logic
│   ├── models/         # Game, Standing dataclasses
│   └── requirements.txt
├── mhl_scraper/        # TeamLinkt scraping library
├── web/                # React frontend
│   └── src/
│       ├── firebase/   # Firestore client + collection config
│       ├── services/   # data.js — all data fetching + transforms
│       ├── components/ # atoms / molecules / organisms
│       └── pages/      # Dashboard, Games, Standings
├── firebase.json       # Hosting targets: staging + production
├── .firebaserc         # staging → mhl-v2-spof-io, production → mhl-spof-io
├── firestore.rules
└── firestore.indexes.json
```

## Local Development

```bash
# Web
cp .env.example web/.env.local   # fill in Firebase config
cd web && npm install && npm run dev

# Run tests
cd web && npm test
```

## Deployment

Merging to `main` automatically:
1. Runs web tests
2. Builds the frontend
3. Deploys `mhlv2_sync` function + staging hosting + Firestore rules

### Required GitHub Secrets

| Secret | Source |
|--------|--------|
| `FIREBASE_SERVICE_ACCOUNT_SPOF_IO` | GCP service account key |
| `VITE_FIREBASE_API_KEY` | Firebase Console → Project Settings → Apps |
| `VITE_FIREBASE_AUTH_DOMAIN` | " |
| `VITE_FIREBASE_PROJECT_ID` | " |
| `VITE_FIREBASE_STORAGE_BUCKET` | " |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | " |
| `VITE_FIREBASE_APP_ID` | " |
| `SYNC_SECRET` | Random hex — `python3 -c "import secrets; print(secrets.token_hex(32))"` |

`SYNC_SECRET` must also be set as the `X-Sync-Secret` header on each Cloud Scheduler job.

## Data Sync

`mhlv2_sync` is triggered by Cloud Scheduler:

| Job | Schedule | Timezone |
|-----|----------|----------|
| `mhlv2-sync-weekend` | `*/30 8-21 * * 6,0` | America/Los_Angeles |
| `mhlv2-sync-weekday` | `0 8 * * 1-5` | America/Los_Angeles |

Trigger a manual sync (requires `SYNC_SECRET`):
```bash
curl -X POST <function_url> \
  -H "X-Sync-Secret: <secret>" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

## Cutover to mhl.spof.io

When staging is validated, update `.firebaserc` so the `production` target points to `mhl-spof-io` and redeploy hosting only:

```bash
firebase deploy --only hosting:production --project spof-io
```

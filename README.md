# VideoFlow

Plateforme serverless de **traitement vidéo automatique** — projet universitaire démontrant l'architecture event-driven, l'auto-scaling, le pay-per-use et le temps réel.

## Problème

Les plateformes multimédia subissent des charges très variables et nécessitent beaucoup de puissance de calcul. Maintenir des serveurs actifs en permanence coûte cher et complique la gestion de l'infrastructure.

## Solution

Le serverless permet de traiter dynamiquement les vidéos uniquement lorsqu'un événement se produit (upload). Chaque étape du pipeline est une fonction indépendante, scalée automatiquement par le cloud.

## Architecture complète

```
Utilisateur
    ↓
Frontend React (upload + WebSocket)
    ↓
API Gateway REST → Lambda (jobs, URLs présignées)
    ↓
S3 Upload Bucket
    ↓
EventBridge (Video Uploaded)
    ↓
Lambda processVideo (FFmpeg : 720p, 1080p, thumbnail, métadonnées)
    ↓
S3 Processed Bucket + DynamoDB + SNS + WebSocket
```

### Concepts serverless démontrés

| Concept | Implémentation |
|---------|----------------|
| Event-driven | Upload → EventBridge → pipeline automatique |
| Auto-scaling | 1 upload = 1 Lambda, 10 000 uploads = 10 000 Lambdas |
| Pay-per-use | DynamoDB on-demand, Lambda à l'invocation |
| Microservices | Lambdas séparées : upload, traitement, WebSocket |
| Temps réel | WebSocket API push des mises à jour de statut |

## Démarrage rapide

### Option A — Mock (sans installation)

```bash
cd frontend
echo "VITE_MOCK_API=true" > .env.local
npm install && npm run dev
```

### Option B — FFmpeg local (recommandé pour la démo)

Prérequis : FFmpeg installé (`sudo apt install ffmpeg`)

```bash
# Terminal 1 — backend local (simule Lambda + EventBridge + WebSocket)
cd backend/local-server
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
cp .env.example .env.local   # pointe vers localhost:8000
npm install && npm run dev
```

Uploadez une vidéo → transcodage réel en 720p/1080p + miniature.

### Option C — AWS (production)

Prérequis : AWS CLI, SAM CLI, Python 3.12

```bash
cd infrastructure
sam build
sam deploy --guided
```

Configurer le frontend avec les outputs `ApiUrl` et `WebSocketUrl` :

```bash
cd frontend
cat > .env.local <<EOF
VITE_API_URL=https://xxx.execute-api.ca-central-1.amazonaws.com/dev
VITE_WS_URL=wss://yyy.execute-api.ca-central-1.amazonaws.com/dev
VITE_MOCK_API=false
EOF
npm run dev
```

## API REST

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/jobs` | Crée un job + URL présignée S3 |
| `PUT` | `{uploadUrl}` | Upload direct vers S3 |
| `POST` | `/jobs/{id}/confirm` | Confirme l'upload, déclenche EventBridge |
| `GET` | `/jobs` | Liste les jobs |
| `GET` | `/jobs/{id}` | Détail + URLs de téléchargement |

## WebSocket

Connexion : `wss://.../dev` (ou `ws://localhost:8000/ws`)

```json
{ "action": "subscribe", "jobId": "uuid-du-job" }
```

Réception :

```json
{ "type": "job_update", "job": { "status": "COMPLETED", ... } }
```

## Pipeline de traitement (Partie 2)

1. EventBridge reçoit `Video Uploaded`
2. Lambda `processVideo` :
   - Statut → `PROCESSING` + notification WebSocket
   - Télécharge la vidéo depuis S3
   - FFprobe : durée, résolution, codec
   - FFmpeg : transcodage 720p et 1080p
   - Génère une miniature JPG
   - Upload vers S3 Processed Bucket
   - Statut → `COMPLETED` + SNS + WebSocket

## Structure du dépôt

```
VideoFlow/
├── frontend/                 # React + Vite + WebSocket
├── backend/
│   ├── shared/               # utils.py, video_processor.py (FFmpeg)
│   ├── upload-api/           # Lambdas Partie 1
│   ├── processing/           # Lambda processVideo
│   ├── websocket/            # connect, disconnect, subscribe
│   └── local-server/         # Démo locale complète
├── infrastructure/
│   ├── template.yaml         # AWS SAM (toute l'infra)
│   └── Makefile
└── docs/REPARTITION.md       # Répartition binôme
```

## Technologies

- **Frontend** : React 18, TypeScript, Vite
- **Backend** : AWS Lambda (Python 3.12), FFmpeg
- **Infra** : S3, DynamoDB, API Gateway (REST + WebSocket), EventBridge, SNS
- **IaC** : AWS SAM

## Répartition binôme

Voir [docs/REPARTITION.md](docs/REPARTITION.md) — les deux parties sont implémentées ; le document reste utile pour la présentation orale.

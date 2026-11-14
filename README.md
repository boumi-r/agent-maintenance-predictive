# MaintenanceAI

Maintenance prédictive des moteurs électriques industriels (asynchrones triphasés) pour PME.

- **Règles normatives** déterministes (ISO 20816-3, NEMA MG-1, EN 50160, IEC 60085, heuristiques
  explicitement marquées) : ce sont elles qui fixent le niveau de risque
  `normal | surveillance | eleve | critique | indetermine`.
- **Agent Claude** : explique le diagnostic au technicien, consulte l'historique, rédige l'alerte.
  Il n'invente aucun chiffre et cite la source de chaque valeur.
- **Alertes email** (SendGrid ou Resend) vers des destinataires configurés côté serveur.
- **Retours techniciens** (défaut confirmé / fausse alerte) stockés pour réentraîner les modèles ML
  (phases 3-4).

Les seuils et leur source sont dans [`backend/app/services/regles_constantes.py`](backend/app/services/regles_constantes.py).
Le prototype d'origine (jour1 à jour5) est conservé dans [`legacy/`](legacy/).

## Arborescence

```
backend/app/
  api/            endpoints FastAPI (/api/v1)
  core/           configuration, sécurité (JWT, clés API), rate limiting
  db/ models/     SQLAlchemy 2 (Organisation → Site → Moteur → Mesure → Analyse → Alerte → RetourTechnicien)
  schemas/        Pydantic v2
  services/       règles, calculs électriques, alertes, email, accès multi-organisation
  agent/          boucle d'outils Claude
  static/app.html interface provisoire (servie sur /app)
backend/alembic/  migrations
backend/tests/    pytest
scripts/          bootstrap.py, test_email.py
ml/ models/       entraînement et artefacts (phases suivantes)
```

## Installation (Mac M1, conda)

```bash
conda create -n maintenance python=3.12
conda activate maintenance
pip install -e '.[dev]'
cp .env.example .env      # puis remplir les valeurs
```

## Variables d'environnement

Toutes sont décrites dans [`.env.example`](.env.example).

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | PostgreSQL (`postgresql+psycopg://...`). `postgres://` (Railway) est converti automatiquement |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Clé et modèle de l'agent (défaut `claude-sonnet-5-5`) |
| `ANTHROPIC_MAX_TOKENS`, `AGENT_MAX_ITERATIONS` | Limites de l'agent |
| `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` | Jetons des utilisateurs de l'interface |
| `API_KEY_SALT` | Sel HMAC des clés API machine (le changer invalide toutes les clés) |
| `CORS_ORIGINS` | Domaines du frontend, séparés par des virgules (`*` refusé) |
| `RATE_LIMIT_ANALYSE`, `RATE_LIMIT_STORAGE_URI` | Limite par organisation sur `/analyser-moteur` (ex. `10/minute`, `memory://` ou `redis://...`) |
| `EMAIL_PROVIDER` | `sendgrid`, `resend` ou `console` (journalise sans envoyer) |
| `EMAIL_FROM`, `EMAIL_FROM_NAME` | Expéditeur (doit être vérifié chez le provider) |
| `SENDGRID_API_KEY` / `RESEND_API_KEY` | Clé du provider choisi |

Générer les secrets : `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Base de données

Les **tests** utilisent SQLite en mémoire : rien à installer. L'**application** utilise PostgreSQL.
Deux options en local :

**Option A — Docker Desktop** (recommandé)
1. Installer Docker Desktop pour Mac (Apple Silicon) : https://www.docker.com/products/docker-desktop/
2. Le lancer (icône de baleine dans la barre de menu), puis `docker info` doit répondre.
3. `docker compose up --build` démarre PostgreSQL et l'API (voir plus bas).

**Option B — PostgreSQL via Homebrew**
```bash
brew install postgresql@16
brew services start postgresql@16
"$(brew --prefix postgresql@16)/bin/createuser" -s maintenance
"$(brew --prefix postgresql@16)/bin/psql" -d postgres -c "ALTER USER maintenance PASSWORD 'maintenance';"
"$(brew --prefix postgresql@16)/bin/createdb" -O maintenance maintenance
# dans .env :
# DATABASE_URL=postgresql+psycopg://maintenance:maintenance@localhost:5432/maintenance
```

## Lancement

### Avec Docker
```bash
docker compose up --build                     # API sur http://localhost:8000, migrations appliquées
docker compose exec api python /srv/scripts/bootstrap.py --org "Usine Demo" \
    --admin admin@demo.be --destinataire maintenance@demo.be
```

### Sans Docker (PostgreSQL Homebrew)
```bash
conda activate maintenance
cd backend && alembic upgrade head && cd ..
python scripts/bootstrap.py --org "Usine Demo" --admin admin@demo.be --destinataire maintenance@demo.be
uvicorn app.main:app --app-dir backend --reload
```

`bootstrap.py` demande le mot de passe admin (12 caractères minimum, ou `BOOTSTRAP_ADMIN_PASSWORD`)
et affiche **une seule fois** la clé API machine.

- Documentation interactive : http://localhost:8000/docs
- Interface : http://localhost:8000/app

### Exemple d'utilisation
```bash
# 1. Connexion (JWT)
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.be","mot_de_passe":"<mot de passe>"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2. Créer un moteur (admin) — site_id renvoyé par GET /api/v1/sites
curl -s localhost:8000/api/v1/moteurs -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{
  "site_id": 1, "code": "moteur-A1", "puissance_kw": 75, "courant_nominal_a": 140,
  "classe_isolation": "F", "groupe_iso20816": "groupe_2", "type_fondation": "rigide"}'

# 3. Analyse depuis un automate (clé API machine)
curl -s localhost:8000/api/v1/analyser-moteur -H "X-API-Key: mai_xxx" -H 'Content-Type: application/json' -d '{
  "moteur_code": "moteur-A1",
  "tension_ph1_v": 400, "tension_ph2_v": 402, "tension_ph3_v": 398,
  "courant_ph1_a": 120, "courant_ph2_a": 121, "courant_ph3_a": 119,
  "vibration_rms_mm_s": 3.1, "temperature_roulements_c": 72, "temperature_bobinage_c": 110,
  "observations": "léger bruit côté accouplement"}'
```

### Authentification
- **Machines** (automates, passerelles IoT) : en-tête `X-API-Key`. Clés créées par un admin
  (`POST /api/v1/cles-api`), stockées hachées, révocables. Accès : ingestion, analyse, lecture.
- **Utilisateurs** : `POST /api/v1/auth/login` puis `Authorization: Bearer <jwt>`. Rôles `admin`
  (gestion) et `technicien` (consultation, alertes, retours).
- Une organisation ne voit jamais les données d'une autre (404).

## Tests et qualité

```bash
conda activate maintenance
ruff check . && ruff format --check .
mypy
pytest --cov=app.services --cov=app.ml_inference --cov-report=term-missing
```

L'API Anthropic est simulée dans les tests (aucun appel réseau, aucune clé nécessaire).
Pour lancer la suite sur PostgreSQL : `TEST_DATABASE_URL=postgresql+psycopg://.../base_vide pytest`
(la base est vidée à chaque test). La CI GitHub Actions lance lint + mypy + tests SQLite, la suite
complète sur PostgreSQL avec un aller-retour de migration, et le build Docker.

## Déploiement Railway

1. Dans le projet Railway : **New → Database → PostgreSQL** (plugin Postgres).
2. Service API (ce dépôt) : Railway détecte le `Dockerfile` et l'utilise. La commande de démarrage
   applique les migrations puis lance uvicorn sur `$PORT`.
3. Variables du service API :
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (référence de variable Railway)
   - `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
   - `JWT_SECRET`, `API_KEY_SALT` (générés, différents de ceux de dev)
   - `CORS_ORIGINS` = l'URL publique du frontend
   - `EMAIL_PROVIDER`, `EMAIL_FROM`, `EMAIL_FROM_NAME`, `SENDGRID_API_KEY` ou `RESEND_API_KEY`
   - `ENV=prod`
4. Créer la première organisation : `railway run python scripts/bootstrap.py --org ... --admin ...`
   (ou depuis le shell du service).
5. Vérifier l'email : `railway run python scripts/test_email.py --to vous@exemple.be`.

> Le déploiement actuel part de `main`. Fusionner cette branche change l'API (préfixe `/api/v1`,
> authentification obligatoire, nouveau schéma de base) : les anciennes pages HTML et les clients
> existants doivent être mis à jour en même temps.

Le `Procfile` reste disponible pour un déploiement sans Docker (Nixpacks/Railpack).

## Dépannage des emails

```bash
python scripts/test_email.py --to vous@exemple.be
```
Le script affiche le provider, l'expéditeur, le **status code** et le **body** complet de la réponse,
et sort avec un code non nul en cas d'échec. Les échecs d'envoi d'alerte sont aussi visibles dans
l'alerte elle-même (`envoi_statut`, `envoi_erreur`) et dans les logs ; `POST /api/v1/alertes/{id}/renvoyer`
permet de réessayer.

**Erreur d'authentification SendGrid (401/403) : les 3 causes probables**
1. **La clé API n'a pas la permission « Mail Send »** : SendGrid → Settings → API Keys → créer une
   clé « Restricted Access » avec *Mail Send* = Full Access (ou Full Access).
2. **L'expéditeur n'est pas vérifié** (Sender Identity) : `EMAIL_FROM` doit être une *Single Sender*
   vérifiée ou appartenir à un domaine authentifié (Settings → Sender Authentication).
3. **Variables absentes sur Railway** : `SENDGRID_API_KEY`, `EMAIL_FROM` ou `EMAIL_PROVIDER=sendgrid`
   manquantes ou mal orthographiées dans les variables *du service API* (pas seulement du projet) ;
   redéployer après modification.

## Limites connues (phase 1)

- Pas encore de modèles ML : le niveau de risque vient uniquement des règles.
- Les seuils marqués `heuristique` sont à recaler avec les retours techniciens ; les valeurs
  normatives sont à vérifier sur le texte des normes avant usage commercial.
- `app.html` est une interface provisoire en attendant le frontend Next.js.

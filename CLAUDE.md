# CLAUDE.md — MaintenanceAI

> À placer à la racine du repo `agent-maintenance-predictive`. Claude Code le lit à chaque session.

## Le produit
Plateforme de maintenance prédictive pour moteurs électriques industriels (surtout asynchrones triphasés), destinée aux PME industrielles belges. Elle combine :
- des **modèles ML entraînés** (diagnostic vibration, diagnostic électrique, durée de vie restante, anomalie thermique, détection d'anomalie par moteur) ;
- une **couche de règles normatives** (zones de vibration ISO 20816, déséquilibre de tension, seuils thermiques par classe d'isolation) ;
- un **agent Claude** qui orchestre ces outils, explique le diagnostic à un technicien et déclenche les alertes.

Principe non négociable : **l'agent n'invente jamais un chiffre**. Chaque probabilité, durée de vie ou niveau de risque vient d'un modèle ou d'une règle, et l'agent cite sa source.

## Stack
- Backend : Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL (SQLite seulement en tests), Pydantic v2
- ML : numpy, scipy, pandas, scikit-learn, LightGBM, PyTorch (entraînement), ONNX Runtime ou joblib (inférence), MLflow en local pour le suivi des essais
- Agent : SDK Anthropic, modèle configurable via `ANTHROPIC_MODEL` (par défaut `claude-sonnet-5-5`)
- Frontend : Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts
- Déploiement : Railway (API + Postgres + frontend). L'entraînement se fait **hors Railway** (machine locale ou GPU cloud) ; seuls les artefacts de modèles sont déployés.

## Arborescence cible
```
backend/app/{api,core,db,models,schemas,services,agent,ml_inference}
ml/{data,features,training,evaluation,registry}   # entraînement, jamais importé par l'API
ml/data/raw/  ml/data/processed/                  # dans .gitignore
models/                                           # artefacts versionnés (petits) + model cards
frontend/
docs/{DATASETS.md,ARCHITECTURE.md,model_cards/}
legacy/                                           # anciens jour1..jour5.py
```

## Règles ML (impératives)
1. **Pas de fuite de données.** Découpage train/test **par roulement / par moteur physique**, jamais par segment ni par condition de charge. Toutes les fenêtres d'un même roulement vont dans la même partition.
2. Toujours une évaluation **inter-datasets** (entraîner sur A+B, tester sur C jamais vu) en plus de l'évaluation intra-dataset.
3. Métriques : F1 macro, AUROC macro, matrice de confusion, calibration (ECE) pour la classification ; RMSE, MAE et score PHM 2012 pour la RUL. L'accuracy seule est interdite comme métrique principale.
4. Intervalles de confiance (bootstrap ou plusieurs splits). On rapporte le chiffre réel, **même s'il déçoit**. Jamais de chiffre inventé, arrondi à la hausse ou sélectionné sur le jeu de test.
5. Chaque modèle sort une probabilité calibrée et peut répondre « incertain » sous un seuil de confiance.
6. Chaque modèle a une model card dans `docs/model_cards/` : données, licence, protocole, résultats, limites connues.
7. Les données brutes ne sont jamais commitées. Les scripts de téléchargement vérifient la taille et le checksum, et demandent confirmation au-delà de 5 Go.
8. Respecter les licences de `docs/DATASETS.md`. Un modèle entraîné sur des données NC (non commerciales) est marqué `research_only=True` dans le registre et ne doit pas être servi en production sans autorisation.

## Règles de code
- Typage complet, `ruff` + `mypy`, tests `pytest` (cible ≥ 80 % sur `backend/app/services` et `ml_inference`).
- Aucun secret dans le code ; tout passe par les variables d'environnement documentées dans `.env.example`.
- Aucun état global mutable partagé entre requêtes.
- Commits petits et explicites, en français ou en anglais mais cohérents.
- Avant de dire qu'une tâche est finie : lancer les tests et le lint, et montrer le résultat.

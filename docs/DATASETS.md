# Catalogue des jeux de données — MaintenanceAI

> À placer dans `docs/DATASETS.md` du repo. Claude Code s'en sert comme référence pour la phase 2.
> Les licences marquées **À VÉRIFIER** doivent être lues sur la page officielle avant tout usage commercial.
> Je ne suis pas juriste : pour un produit vendu, faire valider l'usage des données par écrit.

## 1. Diagnostic par vibration (roulements)

| Dataset | Contenu | Pourquoi il compte | Licence |
|---|---|---|---|
| **Paderborn KAt (PU)** | 32 roulements 6203 : 6 sains, 12 défauts artificiels, 14 défauts **réels** (vieillissement accéléré). Vibration + **2 courants moteur** synchronisés, + vitesse, couple, effort radial, température. 4 conditions de fonctionnement, 20 mesures de 4 s par réglage, 64 kHz. | Le seul gros jeu avec des défauts réels **et** du courant moteur. Référence n°1. | **CC BY-NC 4.0** — usage commercial : contacter l'université |
| **Ottawa UORED-VAFCLS** | 20 roulements (bague int., ext., bille, cage, 5 de chaque), chacun en 3 états : sain → défaut en développement → défaillant. Vibration + acoustique + température, 42 kHz, 10 s. | Contient l'état **naissant** du défaut, exactement ce qu'on veut détecter tôt. Deux fabricants de roulements. | Mendeley — **À VÉRIFIER** (version spectrogrammes : CC BY 4.0) |
| **CWRU** | Défauts usinés, 4 charges (0–3 hp), 12/48 kHz. | Le benchmark le plus cité, mais **un seul roulement sain** et des fuites de données quasi systématiques dans la littérature. À utiliser en complément, jamais seul. | **À VÉRIFIER** |
| **MaFaulDa** | 1951 séries multivariées sur simulateur SpectraQuest : sain, balourd, désalignement horizontal / vertical, défauts roulement. | Couvre les défauts **mécaniques** non-roulement (balourd, désalignement), très fréquents en PME. | **À VÉRIFIER** |
| **MFPT** | Roulements sains, bague ext. et int. à plusieurs charges + **3 défauts réels industriels**. | Petits mais réels ; bons pour un test hors distribution. | **À VÉRIFIER** |

## 2. Diagnostic électrique (moteurs asynchrones triphasés)

| Dataset | Contenu | Pourquoi il compte | Licence |
|---|---|---|---|
| **Treml et al., IEEE DataPort — barres rotoriques cassées** | Moteur asynchrone triphasé WEG 1 cv. Tensions et courants **triphasés** + 5 signaux de vibration. Charge de 12,5 % à 100 %, rotor sain puis 1 à 4 barres cassées. | Correspond exactement aux entrées de ton app (3 tensions, 3 courants). | Selon les CGU d'IEEE DataPort : CC BY 3.0 US — **À VÉRIFIER** |
| **AMPERE (Laboratoire Ampère / UBFC)** | Asynchrone 5,5 kW **alimenté par onduleur** : 3 tensions, 3 courants, vitesse, 3 accéléromètres. États : sain, 1 / 3 / 4 barres cassées, roulement dégradé. | Configuration industrielle réaliste (variateur). | **À VÉRIFIER** |

## 3. Pronostic — durée de vie restante (RUL)

| Dataset | Contenu | Licence |
|---|---|---|
| **XJTU-SY** | 15 roulements suivis jusqu'à la panne, 3 conditions (vitesse/charge), 25,6 kHz, 1,28 s par minute, défauts variés (bague int./ext., cage). | **CC BY 4.0** |
| **FEMTO / PRONOSTIA (IEEE PHM 2012)** | 17 essais jusqu'à la panne, 3 conditions, vibration 25,6 kHz + température 10 Hz. | **À VÉRIFIER** |
| **IMS / NASA** | 3 expériences jusqu'à la panne, 4 roulements par expérience. | **À VÉRIFIER** |
| **Paderborn — conditions variables (2024)** | Essais jusqu'à la panne avec vitesse et charge **qui varient dans le temps**, plus proches du terrain. Vibration + température. | **À VÉRIFIER** |

## 4. Thermique

| Dataset | Contenu | Licence |
|---|---|---|
| **Electric Motor Temperature (Kaggle, LEA Paderborn)** | 185 h à 2 Hz sur un PMSM 52 kW : courants id/iq, tensions, vitesse, couple, ambiante, liquide de refroidissement, températures **bobinage**, dent et culasse stator, aimant. | **À VÉRIFIER** |

Usage : apprendre la température « attendue » du bobinage selon la charge ; l'écart mesuré − attendu devient un indicateur d'anomalie thermique. Attention, c'est un PMSM automobile et non un asynchrone industriel : ça sert à valider la méthode, puis il faudra recaler sur les données du client.

## 5. Optionnel — acoustique

| Dataset | Contenu | Licence |
|---|---|---|
| **MIMII / MIMII DUE (Hitachi)** | Sons de machines industrielles (pompes, ventilateurs, vannes, réducteurs…) normaux et anormaux, avec bruit d'usine réel. | **CC BY-NC-SA 4.0** — R&D uniquement |

## 6. Ce qu'aucun dataset public ne remplacera

Les moteurs de tes futurs clients. La vraie précision viendra :
1. d'une **ligne de base par moteur** (apprise sur ses premières semaines saines) ;
2. du **retour des techniciens** (« défaut confirmé / fausse alerte ») stocké et réutilisé pour réentraîner ;
3. si possible d'un banc d'essai à l'UMons pour produire tes propres données sur asynchrones industriels.

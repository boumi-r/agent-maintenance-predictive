"""Envoie un email de test avec le provider configuré et affiche l'erreur complète en cas d'échec.

Usage :
    python scripts/test_email.py --to vous@exemple.be

Sur Railway :
    railway run python scripts/test_email.py --to vous@exemple.be
"""

from __future__ import annotations

import argparse
import sys

from app.core.config import get_settings
from app.services.email.factory import get_email_provider
from app.services.email.templates import rendre_alerte

CAUSES_SENDGRID = """
Causes probables d'une erreur d'authentification SendGrid (401/403) :
  1. La clé API n'a pas la permission « Mail Send » (Settings > API Keys > Restricted Access).
  2. L'expéditeur EMAIL_FROM n'est pas vérifié (Settings > Sender Authentication > Single Sender
     ou domaine authentifié).
  3. Les variables SENDGRID_API_KEY / EMAIL_FROM / EMAIL_PROVIDER sont absentes ou mal
     orthographiées dans l'environnement (ex. service Railway sans les variables).
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--to", required=True, help="Adresse destinataire du test")
    args = parser.parse_args()

    settings = get_settings()
    provider = get_email_provider(settings)
    print(f"Provider : {provider.nom}")
    print(f"Expéditeur : {settings.email_from_name} <{settings.email_from}>")
    print(f"Destinataire : {args.to}")

    email = rendre_alerte(
        moteur_code="TEST",
        site_nom="Test d'envoi",
        niveau="surveillance",
        message="Email de test MaintenanceAI. Aucune action requise.",
        regles=["Aucune — ceci est un test de configuration"],
    )
    resultat = provider.send([args.to], email.sujet, email.html, email.texte)

    print(f"Status code : {resultat.status_code}")
    print(f"Body : {resultat.body}")
    if resultat.ok:
        print(f"OK — message_id={resultat.message_id}")
        return 0
    print("ÉCHEC de l'envoi.", file=sys.stderr)
    if provider.nom == "sendgrid" and (resultat.status_code in (401, 403) or resultat.status_code is None):
        print(CAUSES_SENDGRID, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

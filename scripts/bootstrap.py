"""Crée une organisation, son site principal, un admin et une clé API machine.

Usage :
    python scripts/bootstrap.py --org "Usine Demo" --admin admin@demo.be [--destinataire maintenance@demo.be]

Le mot de passe admin est demandé interactivement (ou lu dans BOOTSTRAP_ADMIN_PASSWORD).
La clé API est affichée UNE SEULE FOIS.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.core.config import get_settings
from app.db.session import creer_engine, creer_session_factory
from app.services.bootstrap import creer_organisation


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--org", required=True, help="Nom de l'organisation")
    parser.add_argument("--admin", required=True, help="Email de l'administrateur")
    parser.add_argument("--site", default="Site principal", help="Nom du premier site")
    parser.add_argument("--destinataire", help="Email destinataire des alertes (toute l'organisation)")
    args = parser.parse_args()

    mot_de_passe = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Mot de passe admin : ")
    if len(mot_de_passe) < 12:
        print("Mot de passe trop court (12 caractères minimum).", file=sys.stderr)
        return 1

    settings = get_settings()
    factory = creer_session_factory(creer_engine(settings.database_url))
    with factory() as session:
        creee = creer_organisation(
            session,
            settings,
            nom=args.org,
            admin_email=args.admin,
            admin_mot_de_passe=mot_de_passe,
            site_nom=args.site,
            destinataire_email=args.destinataire,
        )
    print(f"Organisation #{creee.organisation_id}, site #{creee.site_id}, admin #{creee.admin_id} créés.")
    print("Clé API machine (affichée une seule fois, à conserver) :")
    print(f"  {creee.cle_api}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

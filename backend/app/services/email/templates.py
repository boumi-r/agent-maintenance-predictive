"""Gabarit de l'email d'alerte. Tout contenu variable est échappé (pas d'injection HTML)."""

from __future__ import annotations

import html
from dataclasses import dataclass

COULEURS = {"critique": "#c0392b", "eleve": "#d35400", "surveillance": "#b7950b"}


@dataclass(frozen=True)
class EmailRendu:
    sujet: str
    html: str
    texte: str


def _ligne(valeur: str) -> str:
    """Un sujet d'email ne doit contenir ni retour à la ligne ni caractère de contrôle."""
    return " ".join(valeur.split())[:200]


def rendre_alerte(
    *, moteur_code: str, site_nom: str, niveau: str, message: str, regles: list[str]
) -> EmailRendu:
    e = html.escape
    couleur = COULEURS.get(niveau, "#555555")
    items = "".join(f"<li>{e(r)}</li>" for r in regles)
    corps_html = f"""<div style="font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5;">
  <div style="background: {couleur}; color: white; padding: 15px; border-radius: 8px;">
    <h2 style="margin: 0;">ALERTE MAINTENANCE — niveau {e(niveau.upper())}</h2>
  </div>
  <div style="background: white; padding: 20px; border-radius: 8px; margin-top: 12px;">
    <p><strong>Moteur :</strong> {e(moteur_code)} — <strong>Site :</strong> {e(site_nom)}</p>
    <h3>Problème détecté</h3>
    <p style="white-space: pre-wrap;">{e(message)}</p>
    <h3>Règles franchies</h3>
    <ul>{items}</ul>
    <p style="color: #888; font-size: 12px;">
      Généré par MaintenanceAI. Niveau déterminé par des règles normatives.
    </p>
  </div>
</div>"""
    texte = (
        f"ALERTE MAINTENANCE — niveau {niveau.upper()}\n"
        f"Moteur : {moteur_code} — Site : {site_nom}\n\n{message}\n\nRègles franchies :\n"
        + "\n".join(f"- {r}" for r in regles)
    )
    sujet = _ligne(f"[MaintenanceAI] {niveau.upper()} — moteur {moteur_code} ({site_nom})")
    return EmailRendu(sujet, corps_html, texte)

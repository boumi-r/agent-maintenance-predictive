"""Schémas des mesures, analyses, alertes et retours techniciens."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import NiveauRisque, StatutAlerte, StatutAnalyse, StatutEnvoi


class Entree(BaseModel):
    # extra="forbid" : un ancien client envoyant email_maintenance ou une vibration texte reçoit un 422
    model_config = ConfigDict(extra="forbid")


class Sortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ValeursMesureIn(Entree):
    tension_ph1_v: float = Field(ge=0, le=100_000, description="Tension composée L1-L2 (V)")
    tension_ph2_v: float = Field(ge=0, le=100_000, description="Tension composée L2-L3 (V)")
    tension_ph3_v: float = Field(ge=0, le=100_000, description="Tension composée L3-L1 (V)")
    courant_ph1_a: float = Field(ge=0, le=100_000)
    courant_ph2_a: float = Field(ge=0, le=100_000)
    courant_ph3_a: float = Field(ge=0, le=100_000)
    vibration_rms_mm_s: float = Field(ge=0, le=1000, description="Vitesse vibratoire efficace (mm/s RMS)")
    temperature_roulements_c: float = Field(ge=-50, le=400)
    temperature_bobinage_c: float = Field(ge=-50, le=400)
    observations: str | None = Field(default=None, max_length=2000, description="Observations libres")
    mesure_le: AwareDatetime | None = Field(
        default=None, description="Horodatage avec fuseau ; défaut = maintenant"
    )


class MesureIn(ValeursMesureIn):
    """Identifie le moteur par son id ou par son code (unique dans l'organisation sinon 409)."""

    moteur_id: int | None = None
    moteur_code: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _un_seul_identifiant(self) -> Self:
        if (self.moteur_id is None) == (self.moteur_code is None):
            raise ValueError("Fournir exactement un de moteur_id ou moteur_code")
        return self


class MesureOut(Sortie):
    id: int
    moteur_id: int
    mesure_le: datetime
    tension_ph1_v: float
    tension_ph2_v: float
    tension_ph3_v: float
    courant_ph1_a: float
    courant_ph2_a: float
    courant_ph3_a: float
    vibration_rms_mm_s: float
    temperature_roulements_c: float
    temperature_bobinage_c: float
    observations: str | None
    desequilibre_tension_pct: float | None
    desequilibre_courant_pct: float | None


class AlerteOut(Sortie):
    id: int
    analyse_id: int
    moteur_id: int
    cree_le: datetime
    niveau: NiveauRisque
    message: str
    declenchee_par: str
    statut: StatutAlerte
    acquittee_le: datetime | None
    resolue_le: datetime | None
    envoi_statut: StatutEnvoi
    envoi_erreur: str | None
    envoi_destinataires: list[Any]
    envoye_le: datetime | None


class AnalyseOut(Sortie):
    id: int
    mesure_id: int
    moteur_id: int
    cree_le: datetime
    niveau_risque: NiveauRisque
    diagnostic: str | None
    resultats_regles: list[Any]
    sources: list[Any]
    version_regles: str
    versions_modeles: dict[str, Any]
    modele_llm: str | None
    statut: StatutAnalyse
    erreur: str | None


class ResultatAnalyseOut(BaseModel):
    analyse_id: int
    moteur_id: int
    moteur_code: str
    niveau_risque: NiveauRisque
    diagnostic: str | None
    statut: StatutAnalyse
    erreur: str | None
    regles: dict[str, Any]
    mesure: MesureOut
    alerte: AlerteOut | None
    historique_consulte: bool


class LigneHistorique(BaseModel):
    mesure: MesureOut
    niveau_risque: NiveauRisque | None
    analyse_id: int | None


class HistoriqueOut(BaseModel):
    moteur_id: int
    moteur_code: str
    nombre_mesures: int
    mesures: list[LigneHistorique]


class AlertePatch(Entree):
    statut: StatutAlerte


class RetourIn(Entree):
    defaut_confirme: bool | None = Field(
        description="true = défaut confirmé, false = pas de défaut, null = ne sait pas"
    )
    type_defaut: str | None = Field(default=None, max_length=100, examples=["roulement_bague_externe"])
    commentaire: str | None = Field(default=None, max_length=5000)
    intervention_le: AwareDatetime | None = None


class RetourOut(Sortie):
    id: int
    moteur_id: int
    analyse_id: int | None
    alerte_id: int | None
    utilisateur_id: int | None
    cree_le: datetime
    defaut_confirme: bool | None
    type_defaut: str | None
    commentaire: str | None
    intervention_le: datetime | None

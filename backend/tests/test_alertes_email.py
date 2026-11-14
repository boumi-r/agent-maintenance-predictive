from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Analyse, DestinataireAlerte, Mesure, Site
from app.models.enums import NiveauRisque, SourceMesure, StatutAlerte, StatutEnvoi
from app.services import alertes
from app.services.email.base import EmailResult
from app.services.email.console import ConsoleProvider
from app.services.email.factory import get_email_provider
from app.services.email.resend import ResendProvider
from app.services.email.sendgrid import SendGridProvider
from app.services.email.templates import rendre_alerte
from tests.conftest import Org

INJECTION = '<script>alert("x")</script><img src=x onerror=alert(1)>'


# --- Échappement -------------------------------------------------------------


def test_email_echappe_tout_contenu_variable() -> None:
    rendu = rendre_alerte(
        moteur_code=INJECTION, site_nom=INJECTION, niveau="critique", message=INJECTION, regles=[INJECTION]
    )
    assert "<script>" not in rendu.html
    assert "<img" not in rendu.html
    assert "&lt;script&gt;" in rendu.html
    assert "\n" not in rendu.sujet


def test_sujet_sans_retour_ligne() -> None:
    rendu = rendre_alerte(
        moteur_code="M1\r\nBcc: pirate@x.com", site_nom="S", niveau="eleve", message="m", regles=[]
    )
    assert "\r" not in rendu.sujet and "\n" not in rendu.sujet


# --- Providers ---------------------------------------------------------------


def _client(status: int, body: str, capture: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        capture.append(request)
        return httpx.Response(status, text=body, headers={"X-Message-Id": "sg-123"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sendgrid_succes() -> None:
    reqs: list[httpx.Request] = []
    p = SendGridProvider("SG.key", "from@x.be", "MAI", _client(202, "", reqs))
    r = p.send(["a@x.be"], "s", "<p>h</p>", "t")
    assert r.ok and r.message_id == "sg-123"
    corps = json.loads(reqs[0].content)
    assert corps["personalizations"][0]["to"] == [{"email": "a@x.be"}]
    assert reqs[0].headers["Authorization"] == "Bearer SG.key"


def test_sendgrid_echec_renvoie_status_et_body() -> None:
    body = '{"errors":[{"message":"The provided authorization grant is invalid, expired, or revoked"}]}'
    r = SendGridProvider("SG.bad", "f@x.be", "MAI", _client(401, body, [])).send(["a@x.be"], "s", "h", "t")
    assert not r.ok
    assert r.status_code == 401
    assert r.body == body
    assert "401" in r.resume_erreur()


def test_sendgrid_sans_cle() -> None:
    r = SendGridProvider("", "f@x.be", "MAI", _client(202, "", [])).send(["a@x.be"], "s", "h", "t")
    assert not r.ok and r.body is not None and "SENDGRID_API_KEY" in r.body


def test_sendgrid_erreur_reseau() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    r = SendGridProvider("k", "f@x.be", "MAI", client).send(["a@x.be"], "s", "h", "t")
    assert not r.ok and r.status_code is None and "ConnectError" in (r.body or "")


def test_resend_succes_et_echec() -> None:
    reqs: list[httpx.Request] = []
    ok = ResendProvider("re_k", "f@x.be", "MAI", _client(200, '{"id":"re-1"}', reqs)).send(
        ["a@x.be"], "s", "h", "t"
    )
    assert ok.ok and ok.message_id == "re-1"
    assert json.loads(reqs[0].content)["from"] == "MAI <f@x.be>"

    ko = ResendProvider("re_k", "f@x.be", "MAI", _client(403, '{"message":"domain not verified"}', [])).send(
        ["a@x.be"], "s", "h", "t"
    )
    assert not ko.ok and ko.status_code == 403 and "domain" in (ko.body or "")


def test_resend_sans_cle_et_erreur_reseau() -> None:
    assert not ResendProvider("", "f", "n", _client(200, "{}", [])).send(["a"], "s", "h", "t").ok

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lent")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert "ReadTimeout" in (ResendProvider("k", "f", "n", client).send(["a"], "s", "h", "t").body or "")


@pytest.mark.parametrize(
    ("nom", "classe"),
    [("sendgrid", SendGridProvider), ("resend", ResendProvider), ("console", ConsoleProvider)],
)
def test_factory(settings: Settings, nom: str, classe: type) -> None:
    s = settings.model_copy(update={"email_provider": nom, "sendgrid_api_key": SecretStr("k")})
    assert isinstance(get_email_provider(s, httpx.Client()), classe)


# --- Service d'alertes -------------------------------------------------------


class FauxProvider:
    nom = "faux"

    def __init__(self, resultat: EmailResult) -> None:
        self.resultat = resultat
        self.envois: list[tuple[list[str], str, str, str]] = []

    def send(self, to: list[str], subject: str, html: str, text: str) -> EmailResult:
        self.envois.append((to, subject, html, text))
        return self.resultat


def _analyse(session: Session, org: Org) -> Analyse:
    mesure = Mesure(
        moteur_id=org.moteur_id,
        source=SourceMesure.API_KEY,
        tension_ph1_v=400,
        tension_ph2_v=400,
        tension_ph3_v=400,
        courant_ph1_a=100,
        courant_ph2_a=100,
        courant_ph3_a=100,
        vibration_rms_mm_s=6,
        temperature_roulements_c=60,
        temperature_bobinage_c=90,
    )
    session.add(mesure)
    session.flush()
    analyse = Analyse(
        mesure_id=mesure.id,
        moteur_id=org.moteur_id,
        niveau_risque=NiveauRisque.CRITIQUE,
        version_regles="t",
        resultats_regles=[
            {
                "libelle": "Vibration",
                "valeur": 6,
                "unite": "mm/s",
                "niveau": "critique",
                "seuil": "> 4.5",
                "source": "ISO",
            },
            {
                "libelle": "Roulements",
                "valeur": 60,
                "unite": "°C",
                "niveau": "normal",
                "seuil": "",
                "source": "",
            },
        ],
    )
    session.add(analyse)
    session.flush()
    return analyse


def test_envoi_aux_destinataires_serveur(session: Session, org_a: Org, org_b: Org) -> None:
    session.add(
        DestinataireAlerte(organisation_id=org_a.organisation_id, site_id=org_a.site_id, email="site@a.be")
    )
    autre_site = Site(organisation_id=org_a.organisation_id, nom="Autre")
    session.add(autre_site)
    session.flush()
    session.add(
        DestinataireAlerte(organisation_id=org_a.organisation_id, site_id=autre_site.id, email="no@a.be")
    )
    alerte = alertes.creer_alerte(
        session, _analyse(session, org_a), NiveauRisque.CRITIQUE, "Roulement", "regles"
    )
    provider = FauxProvider(EmailResult(True, "faux", 202))

    alertes.envoyer_alerte(session, alerte, provider)

    assert provider.envois[0][0] == ["maintenance@alpha.be", "site@a.be"]  # ni autre site, ni org B
    assert alerte.envoi_statut is StatutEnvoi.ENVOYE
    assert alerte.envoye_le is not None
    texte = provider.envois[0][3]
    assert "Vibration" in texte and "Roulements" not in texte  # seules les règles franchies


def test_echec_envoi_visible_sur_alerte(session: Session, org_a: Org) -> None:
    alerte = alertes.creer_alerte(session, _analyse(session, org_a), NiveauRisque.CRITIQUE, "m", "regles")
    provider = FauxProvider(EmailResult(False, "sendgrid", 403, '{"errors":"sender not verified"}'))
    alertes.envoyer_alerte(session, alerte, provider)
    assert alerte.envoi_statut is StatutEnvoi.ECHEC
    assert alerte.envoi_erreur is not None
    assert "403" in alerte.envoi_erreur and "sender not verified" in alerte.envoi_erreur


def test_aucun_destinataire(session: Session, org_a: Org) -> None:
    for d in session.query(DestinataireAlerte).all():
        d.actif = False
    alerte = alertes.creer_alerte(session, _analyse(session, org_a), NiveauRisque.ELEVE, "m", "regles")
    provider = FauxProvider(EmailResult(True, "faux"))
    alertes.envoyer_alerte(session, alerte, provider)
    assert alerte.envoi_statut is StatutEnvoi.AUCUN_DESTINATAIRE
    assert provider.envois == []


def test_transitions_de_statut(session: Session, org_a: Org) -> None:
    alerte = alertes.creer_alerte(session, _analyse(session, org_a), NiveauRisque.ELEVE, "m", "regles")
    alertes.changer_statut(alerte, StatutAlerte.ACQUITTEE, 1)
    assert alerte.acquittee_le is not None and alerte.acquittee_par_id == 1
    alertes.changer_statut(alerte, StatutAlerte.ACQUITTEE, 1)  # idempotent
    alertes.changer_statut(alerte, StatutAlerte.FAUSSE_ALERTE, 1)
    assert alerte.resolue_le is not None
    with pytest.raises(alertes.TransitionInvalideError):
        alertes.changer_statut(alerte, StatutAlerte.OUVERTE, 1)

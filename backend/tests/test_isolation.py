"""Une organisation ne voit, ne lit et ne modifie jamais les ressources d'une autre."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import Org

V1 = "/api/v1"


def test_liste_moteurs_isolee(client: TestClient, org_a: Org, org_b: Org) -> None:
    for org, autre in ((org_a, org_b), (org_b, org_a)):
        for headers in (org.jwt, org.machine):
            ids = {m["id"] for m in client.get(f"{V1}/moteurs", headers=headers).json()}
            assert ids == {org.moteur_id}
            assert autre.moteur_id not in ids


def test_lecture_moteur_autre_org_404(client: TestClient, org_a: Org, org_b: Org) -> None:
    assert client.get(f"{V1}/moteurs/{org_b.moteur_id}", headers=org_a.jwt).status_code == 404
    assert client.get(f"{V1}/moteurs/{org_b.moteur_id}", headers=org_a.machine).status_code == 404
    assert client.get(f"{V1}/moteurs/{org_a.moteur_id}", headers=org_a.jwt).status_code == 200


def test_modification_moteur_autre_org_404(client: TestClient, org_a: Org, org_b: Org) -> None:
    r = client.patch(f"{V1}/moteurs/{org_b.moteur_id}", json={"puissance_kw": 1}, headers=org_a.jwt)
    assert r.status_code == 404
    assert client.get(f"{V1}/moteurs/{org_b.moteur_id}", headers=org_b.jwt).json()["puissance_kw"] == 75


def test_creation_moteur_sur_site_autre_org_404(client: TestClient, org_a: Org, org_b: Org) -> None:
    r = client.post(f"{V1}/moteurs", json={"site_id": org_b.site_id, "code": "intrus"}, headers=org_a.jwt)
    assert r.status_code == 404


def test_sites_et_destinataires_isoles(client: TestClient, org_a: Org, org_b: Org) -> None:
    sites = client.get(f"{V1}/sites", headers=org_a.jwt).json()
    assert [s["id"] for s in sites] == [org_a.site_id]

    dests_a = client.get(f"{V1}/destinataires", headers=org_a.jwt).json()
    assert [d["email"] for d in dests_a] == ["maintenance@alpha.be"]

    r = client.post(f"{V1}/sites/{org_b.site_id}/destinataires", json={"email": "x@a.be"}, headers=org_a.jwt)
    assert r.status_code == 404

    dest_b = client.get(f"{V1}/destinataires", headers=org_b.jwt).json()[0]["id"]
    assert client.delete(f"{V1}/destinataires/{dest_b}", headers=org_a.jwt).status_code == 404


def test_cles_api_isolees(client: TestClient, org_a: Org, org_b: Org) -> None:
    cles_b = client.get(f"{V1}/cles-api", headers=org_b.jwt).json()
    assert client.delete(f"{V1}/cles-api/{cles_b[0]['id']}", headers=org_a.jwt).status_code == 404
    assert client.get(f"{V1}/moteurs", headers=org_b.machine).status_code == 200


def test_utilisateurs_isoles(client: TestClient, org_a: Org, org_b: Org) -> None:
    emails = {u["email"] for u in client.get(f"{V1}/utilisateurs", headers=org_a.jwt).json()}
    assert emails == {org_a.email}


def test_meme_code_moteur_dans_deux_orgs(client: TestClient, org_a: Org, org_b: Org) -> None:
    # Les deux organisations ont un « moteur-A1 » ; chacune ne voit que le sien
    a = client.get(f"{V1}/moteurs", headers=org_a.jwt).json()
    b = client.get(f"{V1}/moteurs", headers=org_b.jwt).json()
    assert a[0]["code"] == b[0]["code"] == "moteur-A1"
    assert a[0]["id"] != b[0]["id"]

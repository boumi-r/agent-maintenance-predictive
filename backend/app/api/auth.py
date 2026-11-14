"""Connexion des utilisateurs (JWT) et gestion des comptes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminDep, SessionDep, SettingsDep, UtilisateurDep
from app.core.security import creer_jwt, hacher_mot_de_passe, verifier_mot_de_passe
from app.models import Utilisateur
from app.schemas.gestion import LoginIn, TokenOut, UtilisateurIn, UtilisateurOut

router = APIRouter(tags=["auth"])

# Hash factice : vérifié quand l'email est inconnu, pour ne pas révéler son existence par le temps de réponse.
_HASH_FACTICE = hacher_mot_de_passe("mot-de-passe-factice-pour-timing")


@router.post("/auth/login", response_model=TokenOut)
def login(donnees: LoginIn, session: SessionDep, settings: SettingsDep) -> TokenOut:
    utilisateur = session.scalar(select(Utilisateur).where(Utilisateur.email == donnees.email.lower()))
    hash_ = utilisateur.mot_de_passe_hash if utilisateur else _HASH_FACTICE
    valide = verifier_mot_de_passe(donnees.mot_de_passe, hash_)
    if utilisateur is None or not valide or not utilisateur.actif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect")
    token = creer_jwt(settings, utilisateur.id, utilisateur.organisation_id, utilisateur.role)
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/auth/me", response_model=UtilisateurOut)
def moi(principal: UtilisateurDep, session: SessionDep) -> Utilisateur:
    utilisateur = session.get(Utilisateur, principal.utilisateur_id)
    if utilisateur is None:  # supprimé entre-temps
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable")
    return utilisateur


@router.get("/utilisateurs", response_model=list[UtilisateurOut])
def lister_utilisateurs(principal: AdminDep, session: SessionDep) -> list[Utilisateur]:
    return list(
        session.scalars(select(Utilisateur).where(Utilisateur.organisation_id == principal.organisation_id))
    )


@router.post("/utilisateurs", response_model=UtilisateurOut, status_code=status.HTTP_201_CREATED)
def creer_utilisateur(donnees: UtilisateurIn, principal: AdminDep, session: SessionDep) -> Utilisateur:
    utilisateur = Utilisateur(
        organisation_id=principal.organisation_id,
        email=donnees.email.lower(),
        nom=donnees.nom,
        mot_de_passe_hash=hacher_mot_de_passe(donnees.mot_de_passe),
        role=donnees.role,
    )
    session.add(utilisateur)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email déjà utilisé") from exc
    return utilisateur

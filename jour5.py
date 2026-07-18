from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import declarative_base, Session
import anthropic
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from fastapi.responses import HTMLResponse

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

engine = create_engine("sqlite:///maintenance.db")
Base = declarative_base()

class HistoriqueMoteur(Base):
    __tablename__ = "historique"
    id = Column(Integer, primary_key=True)
    moteur_id = Column(String)
    temperature = Column(Float)
    vibration = Column(String)
    intensite_ecart = Column(Float)
    diagnostic = Column(String)
    niveau_risque = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

app = FastAPI()

class DonneesMoteur(BaseModel):
    moteur_id: str
    temperature: float
    vibration: str
    intensite_ecart: float
    email_maintenance: str

tools = [
    {
        "name": "predire_panne",
        "description": "Analyse les symptômes et prédit les pannes futures probables du moteur",
        "input_schema": {
            "type": "object",
            "properties": {
                "symptome": {"type": "string", "description": "Symptôme constaté sur le moteur"},
                "cause": {"type": "string", "description": "Cause probable identifiée"},
                "niveau_risque": {"type": "string", "description": "Niveau de risque: normal, elevated, critique"}
            },
            "required": ["symptome", "cause", "niveau_risque"]
        }
    },
    {
        "name": "alert_immediate",
        "description": "Envoie une alerte immédiate au service de maintenance en cas de risque élevé ou critique",
        "input_schema": {
            "type": "object",
            "properties": {
                "probleme": {"type": "string", "description": "Description du problème détecté"},
                "email_service_maintenance": {"type": "string", "description": "Email du service de maintenance"}
            },
            "required": ["probleme", "email_service_maintenance"]
        }
    }
]

niveau_risque_detecte = {"valeur": "normal"}

def predire_panne(symptome, cause, niveau_risque):
    niveau_risque_detecte["valeur"] = niveau_risque
    predictions = {
        "critique": ["Grippage total des roulements sous 24-48h", "Court-circuit des bobinages"],
        "elevated": ["Dégradation accélérée des roulements", "Surchauffe progressive"],
        "normal": ["Usure normale à long terme"]
    }
    return {
        "pannes_probables": predictions.get(niveau_risque, ["Surveillance requise"]),
        "delai_intervention": "IMMEDIAT" if niveau_risque == "critique" else "48-72h"
    }

def alert_immediate(probleme, email_service_maintenance):
    return {
        "status": "alerte_envoyee",
        "destinataire": email_service_maintenance,
        "probleme": probleme
    }

outils_disponibles = {
    "predire_panne": predire_panne,
    "alert_immediate": alert_immediate
}

@app.post("/analyser-moteur")
async def analyser_moteur(donnees: DonneesMoteur):

    with Session(engine) as session:
        historique = session.query(HistoriqueMoteur)\
            .filter(HistoriqueMoteur.moteur_id == donnees.moteur_id)\
            .order_by(HistoriqueMoteur.timestamp.desc())\
            .limit(5)\
            .all()

    contexte_historique = ""
    if historique:
        contexte_historique = "\nHistorique des 5 dernières mesures:\n"
        for h in historique:
            contexte_historique += f"- {h.timestamp}: temp={h.temperature}°C, vibration={h.vibration}, risque={h.niveau_risque}\n"

    message = f"""
    Moteur ID: {donnees.moteur_id}
    Mesures actuelles:
    - Température roulements: {donnees.temperature}°C
    - Vibrations: {donnees.vibration}
    - Écart intensité: {donnees.intensite_ecart}%
    - Email maintenance: {donnees.email_maintenance}
    {contexte_historique}
    """

    messages = [{"role": "user", "content": message}]
    diagnostic_final = ""
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system="Tu es un ingénieur expert en maintenance électrique industrielle. Tiens compte de l'historique pour détecter les tendances.",
                tools=tools,
                messages=messages
            )
        except Exception as e:
            return {"erreur": f"API Anthropic indisponible: {str(e)}", "moteur_id": donnees.moteur_id}

        if response.stop_reason == "end_turn":
            diagnostic_final = response.content[0].text
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name not in outils_disponibles:
                        return {"erreur": f"Outil inconnu: {block.name}", "moteur_id": donnees.moteur_id}
                    fonction = outils_disponibles[block.name]
                    resultat = fonction(**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(resultat)
                    })
            messages.append({"role": "user", "content": tool_results})

        else:
            return {"erreur": f"Réponse inattendue: {response.stop_reason}", "moteur_id": donnees.moteur_id}

    if iteration >= max_iterations:
        return {"erreur": "Agent bloqué en boucle", "moteur_id": donnees.moteur_id}

    with Session(engine) as session:
        nouvelle_mesure = HistoriqueMoteur(
            moteur_id=donnees.moteur_id,
            temperature=donnees.temperature,
            vibration=donnees.vibration,
            intensite_ecart=donnees.intensite_ecart,
            diagnostic=diagnostic_final,
            niveau_risque=niveau_risque_detecte["valeur"]
        )
        session.add(nouvelle_mesure)
        session.commit()

    return {
        "moteur_id": donnees.moteur_id,
        "diagnostic": diagnostic_final,
        "niveau_risque": niveau_risque_detecte["valeur"],
        "historique_consulte": len(historique) > 0
    }

@app.get("/historique/{moteur_id}")
async def voir_historique(moteur_id: str):
    with Session(engine) as session:
        historique = session.query(HistoriqueMoteur)\
            .filter(HistoriqueMoteur.moteur_id == moteur_id)\
            .order_by(HistoriqueMoteur.timestamp.desc())\
            .all()

    return {
        "moteur_id": moteur_id,
        "nombre_mesures": len(historique),
        "mesures": [
            {
                "timestamp": h.timestamp,
                "temperature": h.temperature,
                "vibration": h.vibration,
                "niveau_risque": h.niveau_risque
            }
            for h in historique
        ]
    }
@app.get("/interface", response_class=HTMLResponse)
async def interface():
    with open("interface.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/")
async def root():
    return {"message": "API Maintenance Prédictive avec mémoire persistante"}
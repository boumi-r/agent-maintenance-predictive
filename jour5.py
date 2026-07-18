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
import sendgrid
from sendgrid.helpers.mail import Mail

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
    # Électrique
    tension_ph1: float
    tension_ph2: float
    tension_ph3: float
    courant_ph1: float
    courant_ph2: float
    courant_ph3: float
    # Mécanique
    vibration: str
    # Thermique
    temperature_roulements: float
    temperature_bobinages: float
    # Contact
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
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        
        message = Mail(
            from_email=os.getenv("SENDGRID_FROM_EMAIL"),
            to_emails=email_service_maintenance,
            subject="🚨 ALERTE MAINTENANCE — Intervention requise",
            html_content=f"""
            <div style="font-family: Arial; padding: 20px; background: #f5f5f5;">
                <div style="background: #e94560; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h2>🚨 ALERTE MAINTENANCE PRÉDICTIVE</h2>
                </div>
                <div style="background: white; padding: 20px; border-radius: 8px;">
                    <h3>Problème détecté :</h3>
                    <p>{probleme}</p>
                    <hr>
                    <p><strong>Action requise :</strong> Intervention immédiate</p>
                    <p style="color: #888; font-size: 12px;">Généré par MaintenanceAI</p>
                </div>
            </div>
            """
        )
        
        sg.send(message)
        
        return {
            "status": "alerte_envoyee",
            "destinataire": email_service_maintenance,
            "probleme": probleme
        }
        
    except Exception as e:
        return {
            "status": "erreur_envoi",
            "erreur": str(e),
            "destinataire": email_service_maintenance
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

    Paramètres électriques:
    - Tension phase 1: {donnees.tension_ph1} V
    - Tension phase 2: {donnees.tension_ph2} V
    - Tension phase 3: {donnees.tension_ph3} V
    - Courant phase 1: {donnees.courant_ph1} A
    - Courant phase 2: {donnees.courant_ph2} A
    - Courant phase 3: {donnees.courant_ph3} A

    Paramètres mécaniques:
    - Vibrations: {donnees.vibration}

    Paramètres thermiques:
    - Température roulements: {donnees.temperature_roulements}°C
    - Température bobinages: {donnees.temperature_bobinages}°C

    Email maintenance: {donnees.email_maintenance}
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
            temperature=donnees.temperature_roulements,
            vibration=donnees.vibration,
            intensite_ecart=round(
                max(
                    abs(donnees.tension_ph1 - donnees.tension_ph2),
                    abs(donnees.tension_ph2 - donnees.tension_ph3),
                    abs(donnees.tension_ph1 - donnees.tension_ph3)
                ) / max(donnees.tension_ph1, donnees.tension_ph2, donnees.tension_ph3) * 100, 2
            ),
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
    
@app.get("/app", response_class=HTMLResponse)
async def application():
    with open("app.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/")
async def root():
    return {"message": "API Maintenance Prédictive avec mémoire persistante"}
from fastapi import FastAPI
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv
import os
import json

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

app = FastAPI()

# Structure des données que l'API va recevoir
class DonneesMoteur(BaseModel):
    temperature: float
    vibration: str
    intensite_ecart: float
    email_maintenance: str

# Tes outils
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

# Fonctions Python
def predire_panne(symptome, cause, niveau_risque):
    predictions = {
        "critique": ["Grippage total des roulements sous 24-48h", "Court-circuit des bobinages"],
        "elevated": ["Dégradation accélérée des roulements", "Surchauffe progressive"],
        "normal": ["Usure normale à long terme"]
    }
    return {
        "pannes_probables": predictions.get(niveau_risque, ["Surveillance requise"]),
        "delai_intervention": "IMMÉDIAT" if niveau_risque == "critique" else "48-72h"
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

# Endpoint principal
@app.post("/analyser-moteur")
async def analyser_moteur(donnees: DonneesMoteur):
    
    message = f"""
    Analyse ce moteur:
    - Température roulements: {donnees.temperature}°C
    - Vibrations: {donnees.vibration}
    - Écart intensité: {donnees.intensite_ecart}%
    - Email maintenance: {donnees.email_maintenance}
    """
    
    messages = [{"role": "user", "content": message}]
    
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="Tu es un ingénieur expert en maintenance électrique industrielle.",
            tools=tools,
            messages=messages
        )
        
        if response.stop_reason == "end_turn":
            return {"diagnostic": response.content[0].text}
        
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    fonction = outils_disponibles[block.name]
                    resultat = fonction(**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(resultat)
                    })
            
            messages.append({"role": "user", "content": tool_results})

# Route de test
@app.get("/")
async def root():
    return {"message": "API Maintenance Prédictive opérationnelle"}
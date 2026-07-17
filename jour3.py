import anthropic
from dotenv import load_dotenv
import os
import json

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Définition des 3 outils
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
                "email_service_maintenance": {"type": "string", "description": "Email du service de maintenance à alerter"}
            },
            "required": ["probleme", "email_service_maintenance"]
        }
    },
    {
        "name": "contact_prestataire",
        "description": "Contacte le prestataire de maintenance externe pour une intervention",
        "input_schema": {
            "type": "object",
            "properties": {
                "symptome": {"type": "string", "description": "Symptôme constaté"},
                "cause": {"type": "string", "description": "Cause probable"},
                "niveau_risque": {"type": "string", "description": "Niveau de risque"},
                "action_recommandee": {"type": "string", "description": "Action recommandée pour l'intervention"},
                "risque_si_inaction": {"type": "string", "description": "Conséquences si aucune action n'est prise"}
            },
            "required": ["symptome", "cause", "niveau_risque", "action_recommandee", "risque_si_inaction"]
        }
    }
]

# Fonctions Python réelles
def predire_panne(symptome, cause, niveau_risque):
    predictions = {
        "critique": ["Grippage total des roulements sous 24-48h", "Court-circuit des bobinages", "Incendie moteur"],
        "elevated": ["Dégradation accélérée des roulements", "Surchauffe progressive", "Surcharge prolongée"],
        "normal": ["Usure normale à long terme"]
    }
    return {
        "symptome": symptome,
        "cause": cause,
        "pannes_probables": predictions.get(niveau_risque, ["Surveillance requise"]),
        "delai_intervention": "IMMÉDIAT" if niveau_risque == "critique" else "48-72h" if niveau_risque == "elevated" else "Prochaine maintenance"
    }

def alert_immediate(probleme, email_service_maintenance):
    print(f"\n📧 ALERTE ENVOYÉE à {email_service_maintenance}")
    print(f"   Problème: {probleme}")
    print(f"   Action requise: ARRÊT IMMÉDIAT DU MOTEUR\n")
    return {"status": "alerte_envoyee", "destinataire": email_service_maintenance}

def contact_prestataire(symptome, cause, niveau_risque, action_recommandee, risque_si_inaction):
    print(f"\n📞 PRESTATAIRE CONTACTÉ")
    print(f"   Symptôme: {symptome}")
    print(f"   Cause: {cause}")
    print(f"   Action: {action_recommandee}")
    print(f"   Risque si inaction: {risque_si_inaction}\n")
    return {"status": "prestataire_contacte", "niveau_risque": niveau_risque}

# Mapping nom outil → fonction Python
outils_disponibles = {
    "predire_panne": predire_panne,
    "alert_immediate": alert_immediate,
    "contact_prestataire": contact_prestataire
}

# Agent complet
def executer_agent(message_utilisateur):
    print(f"\nMessage reçu: {message_utilisateur}\n")
    
    messages = [{"role": "user", "content": message_utilisateur}]
    
    # Boucle agent
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="Tu es un ingénieur expert en maintenance électrique industrielle. Analyse les paramètres fournis, prédit les pannes, et déclenche les alertes nécessaires.",
            tools=tools,
            messages=messages
        )
        
        # Si Claude a fini
        if response.stop_reason == "end_turn":
            print("\nDiagnostic final:")
            print(response.content[0].text)
            break
        
        # Si Claude veut utiliser un outil
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"→ Claude utilise: {block.name}")
                    
                    # Exécuter la fonction correspondante
                    fonction = outils_disponibles[block.name]
                    resultat = fonction(**block.input)
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(resultat)
                    })
            
            messages.append({"role": "user", "content": tool_results})

# Test
executer_agent("Moteur 75kW: température roulements 95°C, vibrations anormales, intensité +10% nominal. Email maintenance: maintenance@usine.be")
import anthropic
from dotenv import load_dotenv
import os
import json

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

tools = [
    {
        "name": "analyser_moteur",
        "description": "Analyse les paramètres d'un moteur électrique et retourne un diagnostic",
        "input_schema": {
            "type": "object",
            "properties": {
                "temperature": {"type": "number", "description": "Température des roulements en °C"},
                "vibration": {"type": "string", "description": "Niveau de vibration: normale, anormale, critique"},
                "intensite_ecart": {"type": "number", "description": "Écart d'intensité en % par rapport au nominal"}
            },
            "required": ["temperature", "vibration", "intensite_ecart"]
        }
    }
]

def analyser_moteur(temperature, vibration, intensite_ecart):
    risque = "normal"
    if temperature > 90 or intensite_ecart > 15:
        risque = "critique"
    elif temperature > 75 or intensite_ecart > 8:
        risque = "elevated"
    
    return {
        "risque": risque,
        "temperature_status": "HORS LIMITE" if temperature > 80 else "OK",
        "vibration_status": vibration,
        "action": "ARRÊT IMMÉDIAT" if risque == "critique" else "SURVEILLANCE RENFORCÉE" if risque == "elevated" else "RAS"
    }

# Étape 1 — premier appel
messages = [
    {"role": "user", "content": "Moteur 75kW: température roulements 95°C, vibrations anormales, intensité +10% nominal"}
]

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=messages
)

# Étape 2 — traiter le tool_use
for block in response.content:
    if block.type == "tool_use":
        tool_result = analyser_moteur(**block.input)
        
        # Étape 3 — renvoyer le résultat à Claude
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(tool_result)
                }
            ]
        })

# Étape 4 — deuxième appel pour la réponse finale
final_response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=messages
)

print(final_response.content[0].text)
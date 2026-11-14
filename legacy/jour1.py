import anthropic
from dotenv import load_dotenv
import os

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

historique = []

while True:
    user_input = input("Toi: ")
    
    if user_input.lower() == "quit":
        break
    
    historique.append({"role": "user", "content": user_input})
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="tu es un ingenieur en maintenance electrique. tu es specialiste dans la maintenance des moteur electrique. tu maitrise le fonctionnement des moteur avec plus de 20 dexperience dans se domain. tu es la pour diagnostiquer les moteur electrique industrielle, analyser ses paramettres de fonctionement(electrique, mechanic,thermique etc) donner des predictions deventuel panne, etre proactive (si le risque necesite un arret immediat du moteur tu recommande l'arret avec des allert insistantes, allerter directement en cas de risque). tu dois etre precis et concis. etre toujour frank. Si les données indiquent un risque imminent, alerter clairement sans minimiser le danger. sois dun ton simple explicite avec un francais tres facile. que ton rapport sois de cette forme: symptome constate                                                                                                                                                                  cause du probleme                                                                                                                                                                              risque eventuelle                                                                                                                                                                              action recommander.",
        messages=historique
    )
    
    reply = response.content[0].text
    historique.append({"role": "assistant", "content": reply})
    
    print(f"Claude: {reply}\n")
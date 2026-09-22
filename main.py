# main.py
import json
import asyncio
import requests
from playwright.async_api import async_playwright
from config import URL_WEBHOOK_DISCORD, URL_JEU_1WIN, CIBLE_WS
from database import initialiser_structure_bdd, traiter_resultat_et_predire

def push_discord(texte):
    """Transmet le rapport prédictif au salon Discord."""
    payload = {"content": texte}
    try:
        requests.post(URL_WEBHOOK_DISCORD, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Échec de communication Discord : {e}")

async def gestionnaire_websocket(ws):
    """Écouteur réseau pour capturer et décoder les trames Centrifugo."""
    print("🛰️ [OK] Liaison réseau établie avec le module Centrifugo de 1win.")
    
    async def intercept_frame(payload):
        try:
            data = json.loads(payload)
            
            # Analyse des flux liés à l'état du jeu
            if "pub" in data.get("push", {}):
                pub_data = data["push"]["pub"]
                game_data = pub_data.get("data", {})
                stage = game_data.get("stage")
                
                if stage == "start":
                    print("🟢 [FLUX] Le jeu commence : Les choix sont ouverts.")
                    
                elif stage == "waiting":
                    print("⏳ [FLUX] Le jeu tourne : Calcul du résultat en cours...")
                    
                elif stage == "ending":
                    outcome = game_data.get("outcome")
                    if outcome:
                        print(f"🔴 [FLUX] Partie terminée. Résultat = {outcome.upper()}")
                        
                        # Traitement binaire immédiat en fin de manche
                        alerte = traiter_resultat_et_predire(outcome)
                        if alerte:
                            print("🚀 Tendance statistique trouvée. Envoi de l'alerte...")
                            push_discord(alerte)
        except Exception:
            pass

    ws.on("framereceived", intercept_frame)

async def executer_bot():
    """Initialise le navigateur invisible et maintient l'écoute active."""
    initialiser_structure_bdd()
    
    async with async_playwright() as p:
        print("🤖 Initialisation du moteur d'exécution en mode production...")
        
        # Mode headless=True requis pour FadeHost (Pas d'affichage graphique sur le serveur cloud)
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context()
        page = await context.new_page()
        
        # Filtre les sockets pour ne capturer que le serveur Centrifugo ciblé
        page.on("websocket", lambda ws: asyncio.create_task(gestionnaire_websocket(ws)) if CIBLE_WS in ws.url else None)
        
        print(f"🔗 Connexion au serveur de jeu via {URL_JEU_1WIN}...")
        await page.goto(URL_JEU_1WIN)
        
        # Maintien de l'instance ouverte indéfiniment (24h/24)
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(executer_bot())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt manuel du Bot Expert appliqué.")

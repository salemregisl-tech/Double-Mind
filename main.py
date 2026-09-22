# main.py
import json
import os
import asyncio
import discord
from discord.ui import Button, View
from playwright.async_api import async_playwright
from config import BOT_TOKEN, URL_JEU_1WIN, CIBLE_WS
from database import initialiser_structure_bdd, enregistrer_tirage, generer_analyse_profonde

# Configuration des Intentions du Bot Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

class BoutonPredictionView(View):
    """Crée l'interface graphique du bouton interactif sous le message."""
    def __init__(self):
        super().__init__(timeout=None) # Pas de limite de temps pour le bouton

    @discord.ui.button(label="Obtenir la prédiction en direct", style=discord.ButtonStyle.primary, custom_id="btn_predict", emoji="🔮")
    async def bouton_callback(self, interaction: discord.Interaction):
        # Indique à Discord que le bot calcule (évite l'erreur "L'interaction a échoué")
        await interaction.response.defer(ephemeral=True)
        
        # Lancement de l'analyse mathématique profonde
        rapport = generer_analyse_profonde()
        
        # Envoi de la réponse uniquement à la personne qui a cliqué (mode éphémère)
        await interaction.followup.send(content=rapport, ephemeral=True)

@client.event
async def on_ready():
    print(f"🤖 Bot Discord connecté sous le nom : {client.user}")
    # Envoi du panneau d'accès au bouton lors du démarrage
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                # Nettoyer le salon et envoyer le bouton d'accès unique
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND**\nCliquez sur le bouton ci-dessous à tout moment pour analyser le flux du jeu.", view=BoutonPredictionView())
                break
        break

async def gestionnaire_websocket(ws):
    print("🛰️ [OK] Liaison réseau établie avec le module Centrifugo de 1win.")
    
    async def intercept_frame(payload):
        try:
            data = json.loads(payload)
            if "pub" in data.get("push", {}):
                pub_data = data["push"]["pub"]
                game_data = pub_data.get("data", {})
                
                if game_data.get("stage") == "ending":
                    outcome = game_data.get("outcome")
                    if outcome:
                        print(f"🔴 [FLUX] Partie terminée. Enregistrement en BDD : {outcome.upper()}")
                        # Le bot travaille en silence et stocke le résultat pour enrichir ses futurs calculs
                        enregistrer_tirage(outcome)
        except Exception:
            pass

    ws.on("framereceived", intercept_frame)

async def executer_flux():
    initialiser_structure_bdd()
    print("🌐 Vérification et installation des binaires de navigation...")
    os.system("python -m playwright install chromium")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context()
        page = await context.new_page()
        
        page.on("websocket", lambda ws: asyncio.create_task(gestionnaire_websocket(ws)) if CIBLE_WS in ws.url else None)
        await page.goto(URL_JEU_1WIN)
        await asyncio.Event().wait()

async def main():
    # Lancement simultané du Bot Discord et de l'intercepteur de flux de casino
    await asyncio.gather(
        client.start(BOT_TOKEN),
        executer_flux()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système Double-Mind.")

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
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Obtenir la prédiction en direct", style=discord.ButtonStyle.primary, custom_id="btn_predict", emoji="🔮")
    async def bouton_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        rapport = generer_analyse_profonde()
        await interaction.followup.send(content=rapport, ephemeral=True)

@client.event
async def on_ready():
    print(f"🤖 Bot Discord connecté sous le nom : {client.user}")
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND**\nCliquez sur le bouton ci-dessous à tout moment pour obtenir une prédiction.", view=BoutonPredictionView())
                break
        break

async def gestionnaire_websocket(ws):
    print("🛰️ [OK] Interception réussie du flux Centrifugo sécurisé.")
    
    async def intercept_frame(payload):
        try:
            data = json.loads(payload)
            if "pub" in data.get("push", {}):
                pub_data = data["push"]["pub"]
                game_data = pub_data.get("data", {})
                
                if game_data.get("stage") == "ending":
                    outcome = game_data.get("outcome")
                    if outcome:
                        print(f"🔴 [FLUX] Fin de manche. Résultat enregistré : {outcome.upper()}")
                        enregistrer_tirage(outcome)
        except Exception:
            pass

    ws.on("framereceived", intercept_frame)

async def executer_flux():
    """Initialise un Chromium ultra-léger sans aucune dépendance graphique Linux."""
    initialiser_structure_bdd()
    print("🌐 Préparation du moteur Chromium autonome...")
    
    # Force le téléchargement si absent sur FadeHost
    os.system("python -m playwright install chromium")
    
    async with async_playwright() as p:
        # 🛠️ ARGUMENTS EXPERTS : Coupe tout composant graphique, audio ou GPU 
        # Cela évite le plantage lié aux librairies système Linux manquantes sur FadeHost
        arguments_serveur = [
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--headless",
            "--mute-audio"
        ]
        
        browser = await p.chromium.launch(
            headless=True,
            args=arguments_serveur
        ) 
        context = await browser.new_context()
        page = await context.new_page()
        
        # Filtre le trafic réseau pour cibler le flux Centrifugo
        page.on("websocket", lambda ws: asyncio.create_task(gestionnaire_websocket(ws)) if CIBLE_WS in ws.url else None)
        
        print(f"🔗 Navigation vers la plateforme...")
        await page.goto(URL_JEU_1WIN)
        await asyncio.Event().wait()

async def main():
    await asyncio.gather(
        client.start(BOT_TOKEN),
        executer_flux()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système.")

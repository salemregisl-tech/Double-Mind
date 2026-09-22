# main.py
import json
import asyncio
import discord
from aiohttp import web
from discord.ui import Button, View
from config import BOT_TOKEN
from database import initialiser_structure_bdd, enregistrer_tirage, generer_analyse_profonde

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

class PanneauPredictionView(View):
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
    initialiser_structure_bdd()
    
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND AUTOMATIQUE**\nCliquez sur le bouton ci-dessous pour obtenir l'analyse en direct.", view=BoutonPredictionView())
                break
        break

# ==========================================
# 🛰️ SERVEUR API DE RÉCEPTION (FADEHOST)
# ==========================================
async def handle_api_post(request):
    """ Reçoit les données envoyées par votre capteur local """
    try:
        data = await request.json()
        outcome = data.get("outcome")
        
        if outcome in ["red", "blue", "green"]:
            print(f"📡 [API] Nouveau résultat reçu du capteur : {outcome.upper()}")
            # Sauvegarde automatique dans la base SQLite de FadeHost
            enregistrer_tirage(outcome)
            return web.json_response({"status": "success"})
            
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)
    return web.json_response({"status": "invalid_data"}, status=400)

async def demarrer_serveur_api():
    app = web.Application()
    app.router.add_post('/api/resultat', handle_api_post)
    runner = web.AppRunner(app)
    await runner.setup()
    # Utilise le port assigné par FadeHost ou 8080 par défaut
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🚀 Serveur API d'écoute actif sur le port 8080.")

async def main():
    # Lance le bot Discord et le serveur d'API en même temps
    await asyncio.gather(
        client.start(BOT_TOKEN),
        demarrer_serveur_api()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système.")

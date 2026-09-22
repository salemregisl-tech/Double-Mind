# main.py
import json
import asyncio
import discord
import websockets
from discord.ui import Button, View
from config import BOT_TOKEN, CIBLE_WS
from database import initialiser_structure_bdd, enregistrer_tirage, generer_analyse_profonde

# Configuration des Intentions du Bot Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# URL d'accès direct au WebSocket Centrifugo
WS_ENDPOINT = f"wss://{CIBLE_WS}/connection/websocket"

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
                # Envoyer le bouton d'accès unique
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND**\nCliquez sur le bouton ci-dessous à tout moment pour obtenir une analyse du marché basée sur le flux de données réel.", view=BoutonPredictionView())
                break
        break

async def ecouter_flux_jeu():
    """Se connecte en direct au serveur Centrifugo pour écouter les tirages 24h/24."""
    initialiser_structure_bdd()
    print("🛰️ Tentative de connexion directe au serveur de flux Centrifugo...")
    
    while True:
        try:
            async with websockets.connect(WS_ENDPOINT, ping_interval=20, ping_timeout=20) as ws:
                print("✅ [FLUX] Connecté en direct à l'infrastructure réseau du casino.")
                
                # Format d'initialisation de protocole Centrifugo si nécessaire
                init_frame = {"id": 1, "method": "connect", "params": {}}
                await ws.send(json.dumps(init_frame))
                
                async for message_brut in ws:
                    try:
                        data = json.loads(message_brut)
                        
                        # Extraction et lecture des paquets de données du jeu
                        if "pub" in data.get("push", {}):
                            pub_data = data["push"]["pub"]
                            game_data = pub_data.get("data", {})
                            
                            if game_data.get("stage") == "ending":
                                outcome = game_data.get("outcome")
                                if outcome:
                                    print(f"🔴 [FLUX] Fin de manche détectée. Résultat enregistré : {outcome.upper()}")
                                    # Sauvegarde discrète dans la base SQLite locale sur FadeHost
                                    enregistrer_tirage(outcome)
                    except json.JSONDecodeError:
                        pass
        except (websockets.ConnectionClosed, Exception) as e:
            print(f"⚠️ Déconnexion du flux ({e}). Nouvelle tentative dans 5 secondes...")
            await asyncio.sleep(5)

async def main():
    # Lancement simultané du Bot Discord et de la connexion réseau directe au casino
    await asyncio.gather(
        client.start(BOT_TOKEN),
        ecouter_flux_jeu()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système Double-Mind.")

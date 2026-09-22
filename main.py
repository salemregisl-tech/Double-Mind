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

# URL d'accès direct au flux du jeu
WS_ENDPOINT = f"wss://{CIBLE_WS}/connection/websocket"

class BoutonPredictionView(View):
    """Interface graphique du bouton sous le message Discord."""
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
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND**\nCliquez sur le bouton ci-dessous à tout moment pour analyser le flux du jeu.", view=BoutonPredictionView())
                break
        break

async def ecouter_flux_jeu():
    """Se connecte en direct au serveur du jeu et gère le protocole de communication."""
    initialiser_structure_bdd()
    print("🛰️ Connexion directe au serveur de flux...")
    
    # En-têtes essentiels pour simuler un accès conforme
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://1win.pro"
    }
    
    while True:
        try:
            async with websockets.connect(WS_ENDPOINT, extra_headers=headers, ping_interval=20, ping_timeout=20) as ws:
                print("✅ [FLUX] Connecté en direct à l'infrastructure réseau.")
                
                # Envoi du message de connexion au format JSON standard pour initialiser l'écoute
                init_frame = {"id": 1, "method": "connect", "params": {}}
                await ws.send(json.dumps(init_frame))
                
                async for message_brut in ws:
                    try:
                        data = json.loads(message_brut)
                        
                        # Interception et décodage des résultats de fin de manche
                        if "pub" in data.get("push", {}):
                            pub_data = data["push"]["pub"]
                            game_data = pub_data.get("data", {})
                            
                            if game_data.get("stage") == "ending":
                                outcome = game_data.get("outcome")
                                if outcome:
                                    print(f"🔴 [FLUX] Partie terminée. Résultat enregistré : {outcome.upper()}")
                                    enregistrer_tirage(outcome)
                    except json.JSONDecodeError:
                        pass
        except (websockets.ConnectionClosed, Exception) as e:
            print(f"⚠️ Flux temporairement indisponible ({e}). Nouvelle tentative dans 5 secondes...")
            await asyncio.sleep(5)

async def main():
    # Exécution simultanée de l'application Discord et de la capture réseau
    await asyncio.gather(
        client.start(BOT_TOKEN),
        ecouter_flux_jeu()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système.")

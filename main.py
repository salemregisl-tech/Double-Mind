# main.py
import json
import asyncio
import discord
import websockets
from discord.ui import Button, View
from config import BOT_TOKEN, CIBLE_WS
from database import initialiser_structure_bdd, enregistrer_tirage, generer_analyse_profonde

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Point d'accès standardisé de la connexion brute
WS_ENDPOINT = f"wss://{CIBLE_WS}/connection/websocket"

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
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND**\nCliquez sur le bouton ci-dessous à tout moment pour obtenir une analyse du marché basée sur le flux de données réel.", view=BoutonPredictionView())
                break
        break

async def ecouter_flux_jeu():
    """Se connecte au protocole Centrifugo en transmettant la commande d'autorisation initiale."""
    initialiser_structure_bdd()
    print("🛰️ Tentative de connexion réseau au serveur de flux Centrifugo...")
    
    fake_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://1win.pro"
    }
    
    while True:
        try:
            async with websockets.connect(WS_ENDPOINT, extra_headers=fake_headers, ping_interval=20, ping_timeout=20) as ws:
                print("✅ [FLUX] Établissement de la connexion. Envoi du paquet d'initialisation...")
                
                # 🛠️ CORRECTION RESEAU : Envoi de la commande de liaison obligatoire exigée par Centrifugo
                # Cette commande simule l'autorisation initiale de la page web pour démarrer les publications
                init_frame = {"id": 1, "method": "connect", "params": {}}
                await ws.send(json.dumps(init_frame))
                
                async for message_brut in ws:
                    try:
                        data = json.loads(message_brut)
                        
                        # Traitement des données si la liaison est validée
                        if "pub" in data.get("push", {}):
                            pub_data = data["push"]["pub"]
                            game_data = pub_data.get("data", {})
                            
                            if game_data.get("stage") == "ending":
                                outcome = game_data.get("outcome")
                                if outcome:
                                    print(f"🔴 [FLUX] Partie terminée. Résultat stocké : {outcome.upper()}")
                                    enregistrer_tirage(outcome)
                                    
                        # Gestion de la réponse de connexion initiale
                        elif "result" in data and "client" in data["result"]:
                            print("🔥 [FLUX] Authentification réseau réussie ! Écoute en continu activée.")
                            
                    except json.JSONDecodeError:
                        pass
        except (websockets.ConnectionClosed, Exception) as e:
            print(f"⚠️ Flux temporairement indisponible ({e}). Nouvelle tentative dans 5 secondes...")
            await asyncio.sleep(5)

async def main():
    await asyncio.gather(
        client.start(BOT_TOKEN),
        ecouter_flux_jeu()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système Double-Mind.")

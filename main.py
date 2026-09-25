# main.py
import os
import json
import asyncio
import discord
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("DoubleMind-Oracle")

BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
# L'adresse officielle du serveur de flux interceptée dans l'onglet F12 Network
URL_FLUX_1WIN = "wss://centrifugo-ws-mse.live.gamedev-tech.cc/connection/websocket"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

historique_tours = []

def analyser_strategies_oracle(g, c, d):
    """ Application stricte de vos deux stratégies mathématiques """
    global historique_tours
    
    # On mémorise le tirage complet
    historique_tours.append({"g": g, "c": c, "d": d})
    if len(historique_tours) > 5:
        historique_tours.pop(0)
        
    if len(historique_tours) < 3:
        return None

    # Extraction des manches pour l'analyse des cycles
    t_moins_2 = historique_tours[-3]
    t_moins_1 = historique_tours[-2]
    t_actuel  = historique_tours[-1]
    
    # 🔒 CONDITION DE SÉCURITÉ : Les deux tours précédents n'ont AUCUN 0 (nombres positifs uniquement)
    preparation_valide = (
        t_moins_2["g"] != 0 and t_moins_2["c"] != 0 and t_moins_2["d"] != 0 and
        t_moins_1["g"] != 0 and t_moins_1["c"] != 0 and t_moins_1["d"] != 0
    )
    
    if not preparation_valide:
        return None

    # 🔮 STRATÉGIE 1 : Le 0 apparaît au milieu (ex: 2 - 0 - 2)
    if t_actuel["c"] == 0 and t_actuel["g"] is not None and t_actuel["d"] is not None and t_actuel["g"] == t_actuel["d"]:
        # Note : Dans le flux, la couleur est liée à la valeur ou la position (Vert standard pour le 0)
        return f"🎯 **STRATÉGIE 1 ACTIONNÉE**\n\nSérie positive validée + Zéro au milieu : `{t_actuel['g']} - 0 - {t_actuel['d']}`\n\n🔮 **PROCHAIN TOUR : MISEZ SUR LA COULEUR DE CE 0 !**"

    # 🔮 STRATÉGIE 2 : Le chiffre au milieu est entouré de deux 0 (ex: 0 - 4 - 0)
    if t_actuel["g"] == 0 and t_actuel["d"] == 0 and t_actuel["c"] is not None and t_actuel["c"] != 0:
        return f"🎯 **STRATÉGIE 2 ACTIONNÉE**\n\nSérie positive validée + Chiffre entouré de zéros : `0 - {t_actuel['c']} - 0`\n\n🔮 **PROCHAIN TOUR : MISEZ SUR LA COULEUR DU CHIFFRE CENTRAL ({t_actuel['c']}) !**"

    return None

async def diffuser_signal_discord(texte_prediction):
    """ Envoie le flash d'alerte dans votre salon Discord textuel """
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🔮 ALERTE ORACLE - INSTANT DOUBLE",
                    description=texte_prediction,
                    color=discord.Color.gold()
                )
                await channel.send(embed=embed)
                break
        break

async def ecouter_flux_1win_f12():
    """ Se connecte au flux réseau F12 de 1win à distance depuis FadeHost """
    logger.info("🛰️ Connexion au serveur de flux Centrifugo de 1win...")
    while True:
        try:
            async with websockets.connect(URL_FLUX_1WIN) as ws:
                logger.info("✅ Connecté au flux temps réel du casino ! Analyse en cours...")
                
                async for message_brut in ws:
                    data = json.loads(message_brut)
                    
                    # Extraction chirurgicale des cartes au moment exact de la fin du tour
                    if "push" in data and "pub" in data["push"] and "data" in data["push"]["pub"]:
                        game_event = data["push"]["pub"]["data"]
                        
                        # Le serveur envoie "ending" quand les cartes s'immobilisent
                        if game_event.get("stage") == "ending" and "outcome" in game_event:
                            # Exemple de structure reçue : {"outcome":}
                            cartes = game_event["outcome"]
                            if len(cartes) == 3:
                                g, c, d = cartes[0], cartes[1], cartes[2]
                                logger.info(f"🎲 Tour décodé via le réseau : {g} - {c} - {d}")
                                
                                # Lancement immédiat de vos stratégies
                                prediction = analyser_strategies_oracle(g, c, d)
                                if prediction:
                                    await diffuser_signal_discord(prediction)
                                    
        except Exception as e:
            logger.error(f"⚠️ Déconnexion du flux 1win ({e}). Reconnexion automatique...")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    logger.info(f"🤖 Bot Oracle connecté sur Discord : {client.user}")
    asyncio.create_task(ecouter_flux_1win_f12())

if __name__ == "__main__":
    if BOT_TOKEN:
        client.run(BOT_TOKEN)
    else:
        logger.error("❌ Erreur : DISCORD_TOKEN manquant sur FadeHost.")

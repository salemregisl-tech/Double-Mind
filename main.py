# main.py
import os
import json
import asyncio
import discord
import websockets
import logging

# Configuration des logs du serveur
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("DoubleMind-Oracle")

# Récupération des clés secrètes configurées sur FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# L'adresse officielle du serveur de flux interceptée dans l'onglet F12 (Network > WS)
URL_FLUX_1WIN = "wss://centrifugo-ws-mse.live.gamedev-tech.cc/connection/websocket"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Historique en mémoire vive pour analyser la suite des tirages
historique_tours = []

def verifier_couleur_chiffre(valeur, type_couleur_brute):
    """ Associe le chiffre à sa vraie couleur d'après les règles du jeu """
    if valeur == 0:
        return "VERT"
    
    # Traduction des données de couleurs brutes renvoyées par le flux 1win
    if type_couleur_brute in ["red", "R", "rouge"]:
        return "ROUGE"
    if type_couleur_brute in ["blue", "B", "bleu", "black"]:
        return "BLEU"
    
    # Règle mathématique de secours si la couleur textuelle est absente du paquet réseau
    return "ROUGE" if valeur % 2 != 0 else "BLEU"

def analyser_strategies_oracle(g, c, d, cg, cc, cd):
    """ Application stricte de vos deux stratégies mathématiques d'interception """
    global historique_tours
    
    # Enregistrement du tirage réel dans l'historique
    historique_tours.append({
        "g": g, "c": c, "d": d,
        "cg": cg, "cc": cc, "cd": cd
    })
    
    # On conserve les 5 derniers tours maximum pour économiser la RAM de FadeHost
    if len(historique_tours) > 5:
        historique_tours.pop(0)
        
    # Il faut au moins 3 tours complets en mémoire pour analyser l'enchaînement
    if len(historique_tours) < 3:
        return None

    # Extraction des 3 manches consécutives
    t_moins_2 = historique_tours[-3] # Avant-avant-dernier tour
    t_moins_1 = historique_tours[-2] # Tour précédent
    t_actuel  = historique_tours[-1] # Tour qui vient de se terminer

    # 🔒 CONDITION DE SÉCURITÉ ABSOLUE : Les deux tours précédents n'ont AUCUN 0 (Nombres positifs uniquement)
    preparation_pure_sans_zero = (
        t_moins_2["g"] != 0 and t_moins_2["c"] != 0 and t_moins_2["d"] != 0 and
        t_moins_1["g"] != 0 and t_moins_1["c"] != 0 and t_moins_1["d"] != 0
    )
    
    if not preparation_pure_sans_zero:
        logger.info("ℹ️ Séquence ignorée : Présence d'un 0 dans les tours de préparation.")
        return None

    # 🔮 STRATÉGIE 1 : Le 0 apparaît au milieu (Configuration X - 0 - X)
    if t_actuel["c"] == 0 and t_actuel["g"] is not None and t_actuel["d"] is not None and t_actuel["g"] == t_actuel["d"]:
        couleur_du_zero = t_actuel["cc"]
        return (
            f"🎯 **STRATÉGIE 1 DÉTECTÉE (ZÉRO AU MILIEU)**\n\n"
            f"Série de préparation positive validée ✅\n"
            f"Motif capturé : `{t_actuel['g']} - 0 - {t_actuel['d']}`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LE {couleur_du_zero} !**"
        )

    # 🔮 STRATÉGIE 2 : Le chiffre au milieu est entouré de deux 0 (Configuration 0 - X - 0)
    if t_actuel["g"] == 0 and t_actuel["d"] == 0 and t_actuel["c"] is not None and t_actuel["c"] != 0:
        couleur_du_chiffre_central = t_actuel["cc"]
        return (
            f"🎯 **STRATÉGIE 2 DÉTECTÉE (CHIFFRE ENTOURÉ DE ZÉROS)**\n\n"
            f"Série de préparation positive validée ✅\n"
            f"Motif capturé : `0 - {t_actuel['c']} - 0`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LE {couleur_du_chiffre_central} !**"
        )

    return None

async def diffuser_signal_discord(texte_signal):
    """ Envoie la notification d'alerte instantanée dans le salon Discord textuel """
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🔮 SIGNAL ORACLE - INSTANT DOUBLE 1WIN",
                    description=texte_signal,
                    color=discord.Color.green()
                )
                embed.set_footer(text="Système DoubleMind Cloud • Analyse F12 Direct")
                await channel.send(embed=embed)
                break
        break

async def ecouter_flux_reseau_1win():
    """ Connexion persistante par WebSockets au serveur de flux de 1win """
    logger.info("🛰️ Initialisation de la connexion avec le serveur Centrifugo de 1win...")
    while True:
        try:
            async with websockets.connect(URL_FLUX_1WIN) as ws:
                logger.info("✅ Connecté en direct au flux F12 du casino ! Analyse algorithmique active...")
                
                async for message_brut in ws:
                    data = json.loads(message_brut)
                    
                    # Interception de l'événement de fin de partie envoyé par le serveur 1win
                    if "push" in data and "pub" in data["push"] and "data" in data["push"]["pub"]:
                        game_event = data["push"]["pub"]["data"]
                        
                        # Le mot 'ending' est l'indicateur officiel de l'arrêt des cartes envoyé par le jeu
                        if game_event.get("stage") == "ending" and "outcome" in game_event:
                            # Extraction de la liste des 3 cartes réelles
                            cartes_brutes = game_event["outcome"] 
                            
                            if len(cartes_brutes) == 3:
                                # Extraction des valeurs numériques pures
                                g = int(cartes_brutes[0].get("value", cartes_brutes[0]))
                                c = int(cartes_brutes[1].get("value", cartes_brutes[1]))
                                d = int(cartes_brutes[2].get("value", cartes_brutes[2]))
                                
                                # Déduction et filtrage des vraies couleurs associées
                                cg = verifier_couleur_chiffre(g, cartes_brutes[0].get("color", ""))
                                cc = verifier_couleur_chiffre(c, cartes_brutes[1].get("color", ""))
                                cd = verifier_couleur_chiffre(d, cartes_brutes[2].get("color", ""))
                                
                                logger.info(f"🎲 Tirage capturé -> G:[{cg} {g}] C:[{cc} {c}] D:[{cd} {d}]")
                                
                                # Traitement par vos 2 règles de trading
                                signal_oracle = analyser_strategies_oracle(g, c, d, cg, cc, cd)
                                if signal_oracle:
                                    logger.info("🚀 Stratégie validée ! Envoi du signal sur Discord.")
                                    await diffuser_signal_discord(signal_oracle)
                                    
        except Exception as e:
            logger.error(f"⚠️ Déconnexion ou micro-coupure du flux du casino ({e}). Reconnexion en cours...")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    logger.info(f"🤖 Bot Discord connecté sous le nom de : {client.user}")
    # Déclenchement de la boucle d'écoute du réseau en tâche de fond sur FadeHost
    asyncio.create_task(ecouter_flux_reseau_1win())

if __name__ == "__main__":
    if BOT_TOKEN:
        client.run(BOT_TOKEN)
    else:
        logger.error("❌ Impossible de démarrer : La variable DISCORD_TOKEN est absente sur FadeHost.")

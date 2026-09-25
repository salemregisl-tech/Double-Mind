# main.py
import os
import json
import asyncio
import discord
import websockets
import logging

# Configuration des logs professionnels pour la console FadeHost
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("DoubleMind-Oracle")

# Récupération sécurisée de votre Token Discord configuré sur FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# L'adresse officielle du serveur de flux interceptée dans l'onglet F12 (Network > WS)
URL_FLUX_1WIN = "wss://centrifugo-ws-mse.live.gamedev-tech.cc/connection/websocket"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Structure de mémoire vive pour stocker l'historique des manches
historique_tours = []

def verifier_couleur_chiffre(valeur, type_couleur_brute):
    """ Associe de manière stricte le chiffre lu à sa vraie couleur de table """
    if valeur == 0:
        return "VERT"
    
    couleur_nettoye = str(type_couleur_brute).lower().strip()
    if couleur_nettoye in ["red", "r", "rouge"]:
        return "ROUGE"
    if couleur_nettoye in ["blue", "b", "bleu", "black", "noir"]:
        return "BLEU"
    
    # Règle mathématique de secours d'après les algorithmes standards d'Instant Double
    return "ROUGE" if valeur % 2 != 0 else "BLEU"

def analyser_strategies_oracle(g, c, d, cg, cc, cd):
    """ Application chirurgicale de vos deux stratégies d'interception avec sécurité """
    global historique_tours
    
    # Enregistrement du tirage brut dans l'historique de session
    historique_tours.append({
        "g": g, "c": c, "d": d,
        "cg": cg, "cc": cc, "cd": cd
    })
    
    # Conservation des 5 dernières manches pour optimiser la mémoire du serveur
    if len(historique_tours) > 5:
        historique_tours.pop(0)
        
    # Le bot a besoin d'au moins 3 tours complets pour valider les enchaînements
    if len(historique_tours) < 3:
        return None

    # Isolement des 3 manches consécutives (T-2, T-1, et Tour Actuel)
    t_moins_2 = historique_tours[-3]
    t_moins_1 = historique_tours[-2]
    t_actuel  = historique_tours[-1]

    # 🔒 CONDITION DE SÉCURITÉ ABSOLUE : Les deux tours précédents n'ont AUCUN 0 (nombres positifs uniquement)
    preparation_pure_sans_zero = (
        t_moins_2["g"] != 0 and t_moins_2["c"] != 0 and t_moins_2["d"] != 0 and
        t_moins_1["g"] != 0 and t_moins_1["c"] != 0 and t_moins_1["d"] != 0
    )
    
    if not preparation_pure_sans_zero:
        logger.info("ℹ️ Analyse : Série non valide (présence d'un 0 dans les 2 tours précédents).")
        return None

    # 🔮 STRATÉGIE 1 : Le 0 apparaît au milieu (Configuration X - 0 - X)
    if t_actuel["c"] == 0 and t_actuel["g"] is not None and t_actuel["d"] is not None and t_actuel["g"] == t_actuel["d"]:
        couleur_du_zero = t_actuel["cc"]
        return (
            f"🎯 **STRATÉGIE 1 VALIDÉE (ZÉRO AU MILIEU)**\n\n"
            f"Série de préparation positive confirmée ✅\n"
            f"Motif intercepté : `{t_actuel['g']} - 0 - {t_actuel['d']}`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LE {couleur_du_zero} !**"
        )

    # 🔮 STRATÉGIE 2 : Le chiffre au milieu est entouré de deux 0 (Configuration 0 - X - 0)
    if t_actuel["g"] == 0 and t_actuel["d"] == 0 and t_actuel["c"] is not None and t_actuel["c"] != 0:
        couleur_du_chiffre_central = t_actuel["cc"]
        return (
            f"🎯 **STRATÉGIE 2 VALIDÉE (CHIFFRE ENTOURÉ DE ZÉROS)**\n\n"
            f"Série de préparation positive confirmée ✅\n"
            f"Motif intercepté : `0 - {t_actuel['c']} - 0`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LE {couleur_du_chiffre_central} !**"
        )

    return None

async def diffuser_signal_discord(texte_signal):
    """ Diffuse l'alerte sous forme d'encadré visuel dans votre salon Discord """
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🔮 ALERTE EXCLUSIVE ORACLE - INSTANT DOUBLE",
                    description=texte_signal,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="DoubleMind Cloud Engine • Flux Réseau Synchrone")
                await channel.send(embed=embed)
                break
        break

async def ecouter_flux_reseau_1win():
    """ Écoute active et permanente du serveur de flux de 1win avec protocole Keep-Alive """
    logger.info("🛰️ Connexion au serveur de flux Centrifugo de 1win...")
    while True:
        try:
            # Fixation des intervalles de ping pour tuer l'erreur de déconnexion 3502 stale
            async with websockets.connect(
                URL_FLUX_1WIN,
                ping_interval=10,
                ping_timeout=5,
                extra_headers={"User-Agent": "Mozilla/5.0"}
            ) as ws:
                logger.info("✅ Connecté au flux temps réel du casino ! Analyse en cours...")
                
                # Envoi du jeton de présence initial exigé par Centrifugo pour stabiliser le canal
                init_handshake = {"connect": {}, "id": 1}
                await ws.send(json.dumps(init_handshake))

                async for message_brut in ws:
                    if message_brut == "{}" or not message_brut:
                        continue
                        
                    data = json.loads(message_brut)
                    
                    # Décodage des événements de publication envoyés par 1win
                    if "push" in data and "pub" in data["push"] and "data" in data["push"]["pub"]:
                        game_event = data["push"]["pub"]["data"]
                        
                        # Vérification de l'étape de fin de manche 'ending' (Arrêt des cartes)
                        if game_event.get("stage") == "ending" and "outcome" in game_event:
                            cartes_brutes = game_event["outcome"]
                            
                            # Sécurité de format : On s'assure de recevoir la liste des 3 cartes
                            if isinstance(cartes_brutes, list) and len(cartes_brutes) == 3:
                                try:
                                    # Extraction chirurgicale des nombres réels
                                    g = int(cartes_brutes[0].get("value", cartes_brutes[0]))
                                    c = int(cartes_brutes[1].get("value", cartes_brutes[1]))
                                    d = int(cartes_brutes[2].get("value", cartes_brutes[2]))
                                    
                                    # Extraction et vérification des couleurs réelles associées
                                    cg = verifier_couleur_chiffre(g, cartes_brutes[0].get("color", ""))
                                    cc = verifier_couleur_chiffre(c, cartes_brutes[1].get("color", ""))
                                    cd = verifier_couleur_chiffre(d, cartes_brutes[2].get("color", ""))
                                    
                                    logger.info(f"🎲 Manches capturée -> G:[{cg} {g}] C:[{cc} {c}] D:[{cd} {d}]")
                                    
                                    # Lancement de l'analyse décisionnelle de vos stratégies
                                    prediction = analyser_strategies_oracle(g, c, d, cg, cc, cd)
                                    if prediction:
                                        logger.info("🚀 Tendance validée ! Envoi immédiat de la prédiction sur Discord.")
                                        await diffuser_signal_discord(prediction)
                                except (KeyError, IndexError, ValueError) as err:
                                    logger.debug(f"Analyse des paquets de transition ignorée : {err}")
                                    
        except Exception as e:
            logger.error(f"⚠️ Reconnexion au flux du casino suite à un rafraîchissement ({e})...")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    logger.info(f"🤖 Bot Oracle connecté sur Discord : {client.user}")
    # Injection du scanner réseau dans la boucle d'exécution asynchrone de FadeHost
    asyncio.create_task(ecouter_flux_reseau_1win())

if __name__ == "__main__":
    if BOT_TOKEN:
        client.run(BOT_TOKEN)
    else:
        logger.error("❌ Erreur critique : La variable DISCORD_TOKEN est absente du serveur FadeHost.")

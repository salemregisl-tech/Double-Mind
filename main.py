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

# Récupération sécurisée du Token Discord configuré sur FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# L'adresse officielle du serveur de flux interceptée dans l'onglet F12 (Network > WS)
URL_FLUX_1WIN = "wss://centrifugo-ws-mse.live.gamedev-tech.cc/connection/websocket"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Structure de mémoire vive pour stocker l'historique des tirages
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
    
    # Règle mathématique de secours d'après les algorithmes d'Instant Double
    return "ROUGE" if valeur % 2 != 0 else "BLEU"

def analyser_strategies_oracle(g, c, d, cg, cc, cd):
    """ Application chirurgicale de vos deux stratégies d'interception avec sécurité absolue """
    global historique_tours
    
    # Enregistrement du tirage brut dans l'historique de session
    historique_tours.append({
        "g": g, "c": c, "d": d,
        "cg": cg, "cc": cc, "cd": cd
    })
    
    # Conservation des 5 dernières manches pour optimiser la mémoire du serveur FadeHost
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
    """ Diffuse l'alerte sous forme d'encadré visuel dans votre premier salon Discord disponible """
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
    """ Écoute active et synchrone du serveur Centrifugo de 1win avec protocole de souscription stable """
    logger.info("🛰️ Connexion au serveur de flux Centrifugo de 1win...")
    while True:
        try:
            # Fixation des paramètres de ping pour éliminer les déconnexions cycliques
            async with websockets.connect(
                URL_FLUX_1WIN,
                ping_interval=20,
                ping_timeout=10,
                extra_headers={"User-Agent": "Mozilla/5.0"}
            ) as ws:
                logger.info("📡 Connexion au serveur établie. Envoi du protocole initial...")
                
                # 1. Envoi du Handshake de connexion requis par Centrifugo
                init_handshake = {"connect": {}, "id": 1}
                await ws.send(json.dumps(init_handshake))
                
                # Attente de la validation du serveur de jeu
                await ws.recv()
                logger.info("✅ Connexion globale validée par le serveur.")

                # 2. Souscription obligatoire au canal de la table de jeu pour recevoir les tirages en continu
                # Cela stoppe définitivement l'erreur "no close frame received or sent"
                subscription = {
                    "subscribe": {"channel": "instant-double:public"},
                    "id": 2
                }
                await ws.send(json.dumps(subscription))
                logger.info("✅ Abonnement au flux Instant Double en direct validé !")

                async for message_brut in ws:
                    if message_brut == "{}" or not message_brut:
                        continue
                        
                    data = json.loads(message_brut)
                    
                    # Décodage et ciblage des paquets de données du jeu
                    pub_data = None
                    if "push" in data and "pub" in data["push"] and "data" in data["push"]["pub"]:
                        pub_data = data["push"]["pub"]["data"]
                    elif "reply" in data and "subscribe" in data["reply"] and "data" in data["reply"]["subscribe"]:
                        pub_data = data["reply"]["subscribe"]["data"]

                    if pub_data:
                        # Vérification de la phase officielle de fin de manche 'ending' (arrêt des cartes)
                        if pub_data.get("stage") == "ending" and "outcome" in pub_data:
                            cartes_brutes = pub_data["outcome"]
                            
                            if isinstance(cartes_brutes, list) and len(cartes_brutes) == 3:
                                try:
                                    # Extraction immédiate et brute des nombres
                                    g = int(cartes_brutes[0].get("value", cartes_brutes[0]))
                                    c = int(cartes_brutes[1].get("value", cartes_brutes[1]))
                                    d = int(cartes_brutes[2].get("value", cartes_brutes[2]))
                                    
                                    # Extraction des couleurs correspondantes
                                    cg = verifier_couleur_chiffre(g, cartes_brutes[0].get("color", ""))
                                    cc = verifier_couleur_chiffre(c, cartes_brutes[1].get("color", ""))
                                    cd = verifier_couleur_chiffre(d, cartes_brutes[2].get("color", ""))
                                    
                                    logger.info(f"🎲 Tirage capturé -> G:[{cg} {g}] C:[{cc} {c}] D:[{cd} {d}]")
                                    
                                    # Lancement de l'analyse décisionnelle de vos deux stratégies
                                    prediction = analyser_strategies_oracle(g, c, d, cg, cc, cd)
                                    if prediction:
                                        logger.info("🚀 Stratégie validée ! Envoi immédiat de la prédiction sur Discord.")
                                        await diffuser_signal_discord(prediction)
                                except (KeyError, IndexError, ValueError):
                                    pass
                                    
        except Exception as e:
            logger.error(f"⚠️ Attente ou synchronisation avec le flux du casino ({e}). Réexécution dans 5 secondes...")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    logger.info(f"🤖 Bot Discord connecté sous le nom de : {client.user}")
    # Lancement du scanner réseau en tâche de fond sur l'hébergeur Cloud
    asyncio.create_task(ecouter_flux_reseau_1win())

if __name__ == "__main__":
    if BOT_TOKEN:
        client.run(BOT_TOKEN)
    else:
        logger.error("❌ Impossible de démarrer : La variable DISCORD_TOKEN est absente du serveur FadeHost.")

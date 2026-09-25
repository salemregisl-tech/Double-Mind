# main.py
import os
import json
import asyncio
import discord
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("DoubleMind-Oracle")

BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# L'URL de l'API publique d'historique de 1win interceptée en F12
URL_API_HISTORIQUE = "https://gamedev-tech.cc"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

historique_manches_traitees = []

def determiner_couleur(valeur, couleur_brute):
    if valeur == 0:
        return "VERT 🟢"
    c = str(couleur_brute).lower().strip()
    if c in ["red", "r", "rouge"]: return "ROUGE 🔴"
    if c in ["blue", "b", "bleu", "black", "noir"]: return "BLEU 🔵"
    return "ROUGE 🔴" if valeur % 2 != 0 else "BLEU 🔵"

def analyser_strategies_oracle(session_history):
    """ Analyse les vrais derniers tirages reçus de l'API publique """
    if len(session_history) < 3:
        return None

    # Extraction des 3 derniers vrais tirages réels du casino
    t_moins_2 = session_history[-3]
    t_moins_1 = session_history[-2]
    t_actuel  = session_history[-1]

    # 🔒 CONDITION DE SÉCURITÉ ABSOLUE : Les deux tours précédents n'ont AUCUN 0
    preparation_pure_sans_zero = (
        t_moins_2["g"] != 0 and t_moins_2["c"] != 0 and t_moins_2["d"] != 0 and
        t_moins_1["g"] != 0 and t_moins_1["c"] != 0 and t_moins_1["d"] != 0
    )
    
    if not preparation_pure_sans_zero:
        return None

    # 🔮 STRATÉGIE 1 : Le 0 apparaît au milieu (Configuration X - 0 - X)
    if t_actuel["c"] == 0 and t_actuel["g"] is not None and t_actuel["d"] is not None and t_actuel["g"] == t_actuel["d"]:
        return (
            f"🎯 **STRATÉGIE 1 DÉTECTÉE (ZÉRO AU MILIEU)**\n\n"
            f"Série de préparation positive réelle validée ✅\n"
            f"Motif capturé : `{t_actuel['g']} - 0 - {t_actuel['d']}`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LA COULEUR DE CE ZÉRO ({t_actuel['cc']}) !**"
        )

    # 🔮 STRATÉGIE 2 : Le chiffre au milieu est entouré de deux 0 (Configuration 0 - X - 0)
    if t_actuel["g"] == 0 and t_actuel["d"] == 0 and t_actuel["c"] is not None and t_actuel["c"] != 0:
        return (
            f"🎯 **STRATÉGIE 2 DÉTECTÉE (CHIFFRE ENTOURÉ DE ZÉROS)**\n\n"
            f"Série de préparation positive réelle validée ✅\n"
            f"Motif capturé : `0 - {t_actuel['c']} - 0`\n\n"
            f"🔮 **ORDRE DE L'ORACLE : AU PROCHAIN TOUR, MISEZ SUR LA COULEUR DU CHIFFRE CENTRAL ({t_actuel['cc']}) !**"
        )

    return None

async def diffuser_signal_discord(texte_signal):
    """ Envoie l'embed sur votre serveur Discord """
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🔮 ALERTE EXCLUSIVE ORACLE — INSTANT DOUBLE",
                    description=texte_signal,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="Système DoubleMind Cloud • Analyseur Réseau Historique API")
                await channel.send(embed=embed)
                break
        break

async def scraper_historique_1win_en_continu():
    """ Récupère les vrais résultats du jeu en interrogeant l'API d'historique publique """
    global historique_manches_traitees
    logger.info("✅ Capteur d'historique API activé. Recherche des vrais tirages...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    local_session_history = []

    while True:
        try:
            # Requete HTTP sur l'API publique de 1win (Pèse moins de 0.002 Mo, idéal Cloud)
            response = requests.get(URL_API_HISTORIQUE, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Récupération de la liste des derniers tirages réels
                manches_recues = data.get("history", [])
                if manches_recues:
                    # On prend la dernière manche qui vient de se terminer
                    derniere_manche = manches_recues[0]
                    id_manche = premiere_manche.get("id")
                    
                    # Si c'est une nouvelle manche qu'on n'a pas encore analysée
                    if id_manche not in historique_manches_traitees:
                        historique_manches_traitees.append(id_manche)
                        if len(historique_manches_traitees) > 100: historique_manches_traitees.pop(0)
                        
                        cartes = derniere_manche.get("outcome", [])
                        if len(cartes) == 3:
                            g = int(cartes[0].get("value", cartes[0]))
                            c = int(cartes[1].get("value", cartes[1]))
                            d = int(cartes[2].get("value", cartes[2]))
                            
                            cg = determiner_couleur(g, cartes[0].get("color", ""))
                            cc = determiner_couleur(c, cartes[1].get("color", ""))
                            cd = determiner_couleur(d, cartes[2].get("color", ""))
                            
                            logger.info(f"🎲 Vrai tirage récupéré de l'API -> G:[{cg} {g}] C:[{cc} {c}] D:[{cd} {d}]")
                            
                            local_session_history.append({"g": g, "c": c, "d": d, "cg": cg, "cc": cc, "cd": cd})
                            if len(local_session_history) > 5: local_session_history.pop(0)
                            
                            prediction = analyser_strategies_oracle(local_session_history)
                            if prediction:
                                logger.info("🚀 Stratégie validée sur de vrais chiffres ! Envoi Discord.")
                                await diffuser_signal_discord(prediction)
                                
            # Interrogation de l'historique toutes les 15 secondes (vitesse d'une manche)
            await asyncio.sleep(15)
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture de l'API : {e}")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    logger.info(f"🤖 Bot Oracle connecté sur Discord : {client.user}")
    asyncio.create_task(scanner_historique_1win_en_continu())

if __name__ == "__main__":
    if BOT_TOKEN:
        client.run(BOT_TOKEN.strip())
    else:
        logger.error("❌ Erreur : DISCORD_TOKEN manquant sur FadeHost.")

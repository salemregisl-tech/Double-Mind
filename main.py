#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 BOT SENTINELLE MEMPOOL - Détection Insiders / Rug Pulls / Gros Achats
 Hébergement cible : FadeHost (Linux, 256 Mo RAM, Python 3.11)
 Flux temps réel   : Alchemy WSS (alchemyPendingTransactions)
================================================================================
"""

import os
import re
import sys
import gc
import json
import asyncio
import logging

import discord
from discord.ext import commands
import websockets


# ==============================================================================
# ⚙️  ZONE DE CONFIGURATION — C'EST ICI QUE TU REMPLIS TES INFOS
# ==============================================================================
#
# Remplis les valeurs ci-dessous directement entre les guillemets.
# ⚠️ Si ton dépôt GitHub est PUBLIC, ne laisse jamais tes vraies clés ici :
#    utilise plutôt les variables d'environnement du panel FadeHost, qui
#    resteront prioritaires sur ce qui est écrit ci-dessous (voir plus bas).
#
# ------------------------------------------------------------------------------

# Ton token de bot Discord (Discord Developer Portal -> Bot -> Reset Token)
DISCORD_TOKEN_CONFIG = "MTU1MTk1MjEzNDU3MDc3NDU3OA.GUGw8d.rmKZkD9ekpV7WXjssJAEsMdNkCs8VBcaORMNas"

# L'URL WebSocket Alchemy pour Ethereum Mainnet (commence par "wss://", PAS "https://")
# Exemple : wss://eth-mainnet.g.alchemy.com/v2/TA_CLE_ALCHEMY
WSS_NODE_URL_CONFIG = "wss://eth-mainnet.g.alchemy.com/v2/alch_2B4IRipwhijWk6icES02Z"

# L'ID du salon Discord où envoyer les alertes (clic droit sur le salon -> Copier l'ID
# ; il faut activer le Mode Développeur dans Discord : Réglages -> Avancés)
DISCORD_CHANNEL_ID_CONFIG = "1551939043397468190"

# (Optionnel) Adresses de wallets "insiders" à surveiller, séparées par des virgules
INSIDER_WALLETS_CONFIG = ""

# (Optionnel) Seuil en ETH à partir duquel un achat est considéré comme "gros achat"
SEUIL_GROS_ACHAT_ETH_CONFIG = "5"

# ==============================================================================
# FIN DE LA ZONE DE CONFIGURATION — ne modifie rien en dessous de cette ligne
# sauf si tu sais ce que tu fais.
# ==============================================================================


# ------------------------------------------------------------------------------
# 1. LOGGING
# ------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sentinelle_mempool")


# ------------------------------------------------------------------------------
# 2. LECTURE DE LA CONFIG : variable d'environnement en priorité,
#    sinon on retombe sur la valeur écrite dans la zone de configuration.
# ------------------------------------------------------------------------------

def nettoyer_valeur(valeur: str) -> str:
    """Supprime espaces classiques, espaces invisibles et guillemets parasites."""
    if valeur is None:
        return ""
    valeur = valeur.strip()
    valeur = re.sub(r"[\u200b\u200c\u200d\ufeff\u00a0\u2028\u2029]", "", valeur)
    valeur = valeur.strip("'\"")
    return valeur.strip()


def get_env_robuste(nom_cible: str) -> str:
    """
    Cherche une variable d'environnement en ignorant la casse et les
    caractères invisibles, en scannant tout os.environ.
    """
    cible_normalisee = nom_cible.strip().upper()
    for cle, valeur in os.environ.items():
        if cle.strip().upper() == cible_normalisee:
            valeur_propre = nettoyer_valeur(valeur)
            if valeur_propre:
                return valeur_propre
    return ""


def charger_config(nom_env: str, valeur_config: str, alias: list[str] | None = None) -> str:
    """
    Renvoie, dans l'ordre de priorité :
      1) la variable d'environnement (si elle existe sur le panel FadeHost),
      2) sinon la valeur écrite en dur dans la zone de configuration du fichier.
    """
    valeur = get_env_robuste(nom_env)
    if valeur:
        return valeur
    for autre_nom in (alias or []):
        valeur = get_env_robuste(autre_nom)
        if valeur:
            return valeur
    return nettoyer_valeur(valeur_config)


def corriger_url_wss(url: str) -> str:
    """Corrige les erreurs de copier-coller classiques dans une URL WSS."""
    if not url:
        return url
    url = re.sub(r"^wss:/+:*/*", "wss://", url)
    url = re.sub(r"^(wss://)/+", r"\1", url)
    return url


def debug_environnement() -> None:
    """Liste les variables d'environnement au démarrage, secrets masqués."""
    logger.info("=" * 70)
    logger.info("DÉBOGAGE DES VARIABLES D'ENVIRONNEMENT (panel FadeHost)")
    logger.info(f"({len(os.environ)} variable(s) détectée(s) au total dans ce processus)")
    logger.info("=" * 70)
    mots_sensibles = ("TOKEN", "KEY", "WSS", "SECRET", "URL", "PASS")
    for cle in sorted(os.environ.keys()):
        valeur_brute = os.environ[cle]
        valeur_propre = nettoyer_valeur(valeur_brute)
        if any(mot in cle.upper() for mot in mots_sensibles):
            apercu = f"{valeur_propre[:6]}...{valeur_propre[-4:]}" if len(valeur_propre) > 12 else "***"
            logger.info(f"  {cle:<25} -> [{len(valeur_propre)} car.] {apercu}")
        else:
            logger.info(f"  {cle:<25} -> {valeur_brute}")
    logger.info("=" * 70)


# --- Chargement effectif de la config (env var prioritaire, sinon zone config) ---

DISCORD_TOKEN = charger_config("DISCORD_TOKEN", DISCORD_TOKEN_CONFIG)

WSS_NODE_URL = corriger_url_wss(charger_config(
    "WSS_NODE_URL", WSS_NODE_URL_CONFIG,
    alias=["WSS_URL", "ALCHEMY_WSS_URL", "ALCHEMY_WS_URL", "RPC_WSS_URL"],
))

DISCORD_CHANNEL_ID = charger_config("DISCORD_CHANNEL_ID", DISCORD_CHANNEL_ID_CONFIG)

INSIDER_WALLETS = [
    w.strip().lower()
    for w in charger_config("INSIDER_WALLETS", INSIDER_WALLETS_CONFIG).split(",")
    if w.strip()
]

SEUIL_GROS_ACHAT_ETH = float(
    charger_config("SEUIL_GROS_ACHAT_ETH", SEUIL_GROS_ACHAT_ETH_CONFIG) or "5"
)


def verifier_configuration() -> None:
    """Arrête proprement le bot si la config essentielle manque, avec un message clair."""
    erreurs = []
    if not DISCORD_TOKEN:
        erreurs.append(
            "DISCORD_TOKEN manquant : remplis DISCORD_TOKEN_CONFIG en haut du fichier, "
            "ou définis DISCORD_TOKEN dans les variables d'environnement FadeHost."
        )
    if not WSS_NODE_URL or not WSS_NODE_URL.startswith("wss://"):
        erreurs.append(
            "WSS_NODE_URL manquant ou invalide : remplis WSS_NODE_URL_CONFIG en haut du "
            "fichier avec une URL commençant par 'wss://' (pas 'https://'), ou définis "
            "WSS_NODE_URL dans les variables d'environnement FadeHost."
        )
    if erreurs:
        for e in erreurs:
            logger.error(f"❌ {e}")
        logger.error("⛔ Configuration invalide -> arrêt.")
        sys.exit(1)


# ------------------------------------------------------------------------------
# 3. DÉTECTION ON-CHAIN (routeurs DEX connus + sélecteurs de fonctions)
# ------------------------------------------------------------------------------

ADRESSES_ROUTEURS_DEX = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488": "Uniswap V2 Router",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",
}

SELECTEURS_ACHAT = {
    "0x7ff36ab5": "swapExactETHForTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
}

SELECTEURS_RETRAIT_LIQUIDITE = {
    "0x02751cad": "removeLiquidityETH",
    "0xaf2979eb": "removeLiquidityETHSupportingFeeOnTransferTokens",
    "0xbaa2abde": "removeLiquidity",
    "0xded9382a": "removeLiquidityETHWithPermit",
}


def decoder_adresse_param(data_hex: str, index_mot: int) -> str | None:
    """Extrait une adresse (32 octets, alignée à droite) à la position 'index_mot' du calldata."""
    try:
        debut = 10 + index_mot * 64
        morceau = data_hex[debut:debut + 64]
        return "0x" + morceau[-40:]
    except (IndexError, ValueError):
        return None


def decoder_token_depuis_swap(data_hex: str) -> str | None:
    """Décode l'adresse du token acheté (dernier élément du tableau 'path' du calldata)."""
    try:
        offset_hex = data_hex[10 + 64:10 + 128]
        offset_octets = int(offset_hex, 16)
        position = 10 + offset_octets * 2
        longueur = int(data_hex[position:position + 64], 16)
        dernier_index = longueur - 1
        debut_dernier = position + 64 + dernier_index * 64
        morceau = data_hex[debut_dernier:debut_dernier + 64]
        return "0x" + morceau[-40:]
    except (IndexError, ValueError):
        return None


def analyser_transaction(tx: dict) -> dict | None:
    """Analyse une transaction en attente et retourne une alerte si pertinente."""
    try:
        vers = (tx.get("to") or "").lower()
        de = (tx.get("from") or "").lower()
        data = tx.get("input") or "0x"
        selecteur = data[:10] if len(data) >= 10 else ""
        valeur_wei = int(tx.get("value", "0x0"), 16)
        valeur_eth = valeur_wei / 10**18

        if de in INSIDER_WALLETS:
            return {
                "type": "insider",
                "titre": "🕵️ Wallet Insider Détecté !",
                "couleur": 0xF1C40F,
                "hash": tx.get("hash"),
                "wallet": de,
                "cible": vers,
                "valeur_eth": valeur_eth,
                "token": None,
            }

        if selecteur in SELECTEURS_RETRAIT_LIQUIDITE and vers in ADRESSES_ROUTEURS_DEX:
            return {
                "type": "rug_pull",
                "titre": "🚨 ALERTE RUG PULL POTENTIEL 🚨",
                "couleur": 0xE74C3C,
                "hash": tx.get("hash"),
                "wallet": de,
                "cible": vers,
                "methode": SELECTEURS_RETRAIT_LIQUIDITE[selecteur],
                "valeur_eth": valeur_eth,
                "token": decoder_adresse_param(data, 0),
            }

        if selecteur in SELECTEURS_ACHAT and vers in ADRESSES_ROUTEURS_DEX and valeur_eth >= SEUIL_GROS_ACHAT_ETH:
            return {
                "type": "gros_achat",
                "titre": "💰 Gros Achat Détecté !",
                "couleur": 0x2ECC71,
                "hash": tx.get("hash"),
                "wallet": de,
                "cible": vers,
                "valeur_eth": valeur_eth,
                "token": decoder_token_depuis_swap(data),
            }

    except (ValueError, TypeError, KeyError) as erreur:
        logger.debug(f"Transaction ignorée (parsing) : {erreur}")

    return None


# ------------------------------------------------------------------------------
# 4. ÉCOUTE MEMPOOL EN DIRECT (tâche de fond asyncio, non bloquante)
# ------------------------------------------------------------------------------

async def ecouter_mempool(file_alertes: asyncio.Queue) -> None:
    """
    Se connecte en boucle infinie au flux WSS d'Alchemy et analyse chaque
    transaction en attente. Reconnexion automatique avec backoff exponentiel.
    """
    delai_reconnexion = 5

    while True:
        try:
            logger.info("🔌 Connexion au flux WSS Alchemy...")
            async with websockets.connect(
                WSS_NODE_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
                max_size=2**20,  # 1 Mo max par message -> protège les 256 Mo de RAM
            ) as ws:
                logger.info("✅ Connecté en direct à la Mempool Ethereum (Alchemy).")
                delai_reconnexion = 5

                abonnement = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["alchemyPendingTransactions", {"hashesOnly": False}],
                }
                await ws.send(json.dumps(abonnement))

                async for message in ws:
                    try:
                        donnees = json.loads(message)
                        tx = donnees.get("params", {}).get("result")
                        if not tx:
                            continue
                        alerte = analyser_transaction(tx)
                        if alerte:
                            if file_alertes.full():
                                file_alertes.get_nowait()
                            await file_alertes.put(alerte)
                    except json.JSONDecodeError:
                        continue

        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as erreur:
            logger.warning(f"⚠️ Connexion WSS perdue ({erreur}). Reconnexion dans {delai_reconnexion}s...")
        except Exception as erreur:
            logger.error(f"❌ Erreur inattendue dans l'écoute mempool : {erreur}")

        await asyncio.sleep(delai_reconnexion)
        delai_reconnexion = min(delai_reconnexion * 2, 60)


async def nettoyage_memoire_periodique() -> None:
    """Libère la mémoire toutes les 10 minutes (utile sur les 256 Mo de RAM de FadeHost)."""
    while True:
        await asyncio.sleep(600)
        objets_liberes = gc.collect()
        logger.debug(f"🧹 Nettoyage mémoire : {objets_liberes} objets libérés.")


# ------------------------------------------------------------------------------
# 5. EMBEDS DISCORD + BOUTON LIEN DEXSCREENER
# ------------------------------------------------------------------------------

def construire_embed_alerte(alerte: dict) -> tuple[discord.Embed, discord.ui.View]:
    """Construit un embed soigné + un bouton lien direct vers DexScreener."""
    embed = discord.Embed(
        title=alerte["titre"],
        color=alerte["couleur"],
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="💼 Wallet", value=f"`{alerte['wallet']}`", inline=False)
    if alerte.get("token"):
        embed.add_field(name="🪙 Token ciblé", value=f"`{alerte['token']}`", inline=False)
    embed.add_field(name="💎 Valeur", value=f"{alerte['valeur_eth']:.4f} ETH", inline=True)
    if alerte.get("methode"):
        embed.add_field(name="⚙️ Méthode", value=f"`{alerte['methode']}`", inline=True)
    embed.add_field(
        name="🔗 Transaction",
        value=f"[Voir sur Etherscan](https://etherscan.io/tx/{alerte['hash']})",
        inline=False,
    )
    embed.set_footer(text="Bot Sentinelle Mempool • Flux Alchemy en direct")

    token_pour_lien = alerte.get("token") or alerte.get("cible")
    url_dexscreener = f"https://dexscreener.com/ethereum/{token_pour_lien}"

    vue = discord.ui.View()
    vue.add_item(discord.ui.Button(
        label="📈 Trader sur DexScreener",
        style=discord.ButtonStyle.link,
        url=url_dexscreener,
    ))
    return embed, vue


async def expediteur_alertes(bot: "BotTradingMemecoins") -> None:
    """Consomme la file d'alertes et envoie l'embed correspondant sur Discord."""
    await bot.wait_until_ready()
    while True:
        alerte = await bot.file_alertes.get()
        try:
            if bot.canal_alertes is None:
                logger.warning("⚠️ Alerte reçue mais DISCORD_CHANNEL_ID n'est pas configuré/valide.")
                continue
            embed, vue = construire_embed_alerte(alerte)
            await bot.canal_alertes.send(embed=embed, view=vue)
        except discord.HTTPException as erreur:
            logger.error(f"❌ Échec de l'envoi de l'embed Discord : {erreur}")
        finally:
            bot.file_alertes.task_done()


# ------------------------------------------------------------------------------
# 6. BOT DISCORD (discord.py v2)
# ------------------------------------------------------------------------------

intents = discord.Intents.none()
intents.guilds = True

class BotTradingMemecoins(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            max_messages=50,
        )
        self.file_alertes: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.canal_alertes: discord.TextChannel | None = None

    async def setup_hook(self) -> None:
        """
        Point d'entrée officiel de discord.py v2 pour lancer des tâches de fond
        AVANT la connexion à la gateway. On ne touche jamais à asyncio.run() ici :
        c'est justement ce qui fait planter les scripts sur FadeHost.
        """
        self.loop.create_task(ecouter_mempool(self.file_alertes))
        self.loop.create_task(expediteur_alertes(self))
        self.loop.create_task(nettoyage_memoire_periodique())
        logger.info("🚀 Tâches de fond lancées (écoute mempool + expéditeur + nettoyage RAM).")

    async def on_ready(self) -> None:
        logger.info(f"✅ Connecté à Discord en tant que {self.user} (ID: {self.user.id})")
        if DISCORD_CHANNEL_ID:
            try:
                self.canal_alertes = await self.fetch_channel(int(DISCORD_CHANNEL_ID))
                logger.info(f"📡 Canal d'alertes configuré : #{self.canal_alertes}")
            except (discord.NotFound, discord.Forbidden, ValueError) as erreur:
                logger.error(f"❌ Impossible de récupérer le canal {DISCORD_CHANNEL_ID} : {erreur}")
        else:
            logger.warning("⚠️ DISCORD_CHANNEL_ID non défini : aucune alerte ne pourra être envoyée.")


# ------------------------------------------------------------------------------
# 7. POINT D'ENTRÉE
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    debug_environnement()
    verifier_configuration()
    logger.info(f"🌐 URL WSS utilisée (nettoyée) : {WSS_NODE_URL[:25]}...")
    logger.info(f"🕵️ {len(INSIDER_WALLETS)} wallet(s) insider(s) surveillé(s).")
    logger.info(f"💰 Seuil de gros achat : {SEUIL_GROS_ACHAT_ETH} ETH")

    bot = BotTradingMemecoins()

    # IMPORTANT : bot.run() est BLOQUANT et gère sa propre boucle asyncio en
    # interne. Ne JAMAIS l'entourer d'asyncio.run() -> c'est ce qui coupe le
    # script sur FadeHost. Les tâches de fond démarrent via setup_hook().
    try:
        bot.run(DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logger.error("❌ DISCORD_TOKEN invalide : vérifie DISCORD_TOKEN_CONFIG ou la variable FadeHost.")
        sys.exit(1)

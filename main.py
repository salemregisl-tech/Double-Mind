#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 BOT SENTINELLE MEMPOOL - Détection Insiders / Rug Pulls / Gros Achats
 Hébergement cible : FadeHost (Linux, 256 Mo RAM, Python 3.11)
 Flux temps réel   : Alchemy WSS (alchemyPendingTransactions)
================================================================================

Architecture :
  - discord.py v2 avec bot.run() (bloquant, stable) -> AUCUN asyncio.run().
  - La tâche WSS est lancée dans setup_hook(), le point d'entrée officiel
    de discord.py v2 pour démarrer des tâches de fond AVANT la connexion
    à la gateway Discord, sans jamais créer une 2e boucle asyncio.
  - Communication entre la tâche WSS et Discord via une asyncio.Queue
    (même event loop -> pas de threads, RAM minimale).
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
# 1. CONFIGURATION DU LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sentinelle_mempool")


# ==============================================================================
# 2. LECTURE ULTRA-ROBUSTE DES VARIABLES D'ENVIRONNEMENT
#    (corrige le bug FadeHost : casse différente, espaces/caractères invisibles)
# ==============================================================================

def nettoyer_valeur(valeur: str) -> str:
    """Supprime espaces classiques, espaces invisibles et guillemets parasites."""
    if valeur is None:
        return ""
    valeur = valeur.strip()
    # Caractères invisibles fréquents lors d'un copier-coller depuis un panel web :
    # espace insécable (U+00A0), zero-width space/joiners, BOM UTF-8.
    valeur = re.sub(r"[\u200b\u200c\u200d\ufeff\u00a0\u2028\u2029]", "", valeur)
    valeur = valeur.strip("'\"")  # guillemets copiés par erreur
    return valeur.strip()


def get_env_robuste(nom_cible: str, defaut: str = "") -> str:
    """
    Recherche une variable d'environnement en ignorant la casse et les
    caractères invisibles, en scannant TOUT os.environ plutôt que de faire
    un simple os.environ.get(). C'est ce qui répare le bug : certains panels
    (dont FadeHost) peuvent stocker/afficher les clés avec une casse ou des
    espaces légèrement différents de ce qu'attend le code.
    """
    cible_normalisee = nom_cible.strip().upper()
    for cle, valeur in os.environ.items():
        if cle.strip().upper() == cible_normalisee:
            valeur_propre = nettoyer_valeur(valeur)
            if valeur_propre:
                return valeur_propre
    return defaut


def corriger_url_wss(url: str) -> str:
    """
    Corrige les erreurs de copier-coller classiques dans une URL WSS,
    par ex. 'wss://://alchemy.com/...' -> 'wss://alchemy.com/...'
    """
    if not url:
        return url
    url = re.sub(r"^wss:/+:*/*", "wss://", url)
    url = re.sub(r"^(wss://)/+", r"\1", url)
    return url


def debug_environnement() -> None:
    """
    Débogage puissant au démarrage : liste toutes les variables d'environnement
    visibles par le processus, en masquant les secrets (tokens/clés/URLs) pour
    ne jamais les afficher en clair dans les logs FadeHost.
    """
    logger.info("=" * 70)
    logger.info("DÉBOGAGE DES VARIABLES D'ENVIRONNEMENT (panel FadeHost)")
    logger.info("=" * 70)
    mots_sensibles = ("TOKEN", "KEY", "WSS", "SECRET", "URL", "PASS")
    for cle in sorted(os.environ.keys()):
        valeur_brute = os.environ[cle]
        valeur_propre = nettoyer_valeur(valeur_brute)
        est_sensible = any(mot in cle.upper() for mot in mots_sensibles)
        if est_sensible:
            if len(valeur_propre) > 12:
                apercu = f"{valeur_propre[:6]}...{valeur_propre[-4:]}"
            else:
                apercu = "***"
            drapeau = " ⚠️ ESPACES/CARACTÈRES CACHÉS DÉTECTÉS" if valeur_brute != valeur_propre else ""
            logger.info(f"  {cle:<25} -> [{len(valeur_propre)} car.] {apercu}{drapeau}")
        else:
            logger.info(f"  {cle:<25} -> {valeur_brute}")
    logger.info("=" * 70)


# --- Chargement forcé et nettoyé de la configuration ---------------------------

DISCORD_TOKEN = get_env_robuste("DISCORD_TOKEN")
WSS_NODE_URL = corriger_url_wss(get_env_robuste("WSS_NODE_URL"))
DISCORD_CHANNEL_ID = get_env_robuste("DISCORD_CHANNEL_ID")
INSIDER_WALLETS = [w.strip().lower() for w in get_env_robuste("INSIDER_WALLETS").split(",") if w.strip()]
SEUIL_GROS_ACHAT_ETH = float(get_env_robuste("SEUIL_GROS_ACHAT_ETH", "5") or "5")


def verifier_configuration() -> None:
    """Arrête proprement le bot si la config essentielle manque, avec un message clair."""
    erreurs = []
    if not DISCORD_TOKEN:
        erreurs.append("DISCORD_TOKEN introuvable ou vide après nettoyage.")
    if not WSS_NODE_URL or not WSS_NODE_URL.startswith("wss://"):
        erreurs.append(f"WSS_NODE_URL invalide après nettoyage : '{WSS_NODE_URL}'")
    if erreurs:
        for e in erreurs:
            logger.error(f"❌ {e}")
        logger.error("⛔ Configuration invalide sur le panel FadeHost -> arrêt.")
        sys.exit(1)


# ==============================================================================
# 3. DÉTECTION ON-CHAIN (routeurs DEX connus + sélecteurs de fonctions)
# ==============================================================================

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
        debut = 10 + index_mot * 64  # 10 = len('0x' + sélecteur 4 octets)
        morceau = data_hex[debut:debut + 64]
        return "0x" + morceau[-40:]
    except (IndexError, ValueError):
        return None


def decoder_token_depuis_swap(data_hex: str) -> str | None:
    """
    Décode l'adresse du token ciblé par un swap en lisant le tableau
    dynamique 'address[] path' du calldata (le token acheté est le dernier
    élément du tableau).
    """
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
    """
    Analyse une transaction en attente et retourne un dict d'alerte si elle
    correspond à un wallet insider, un retrait de liquidité (rug pull) ou
    un gros achat, sinon None.
    """
    try:
        vers = (tx.get("to") or "").lower()
        de = (tx.get("from") or "").lower()
        data = tx.get("input") or "0x"
        selecteur = data[:10] if len(data) >= 10 else ""
        valeur_wei = int(tx.get("value", "0x0"), 16)
        valeur_eth = valeur_wei / 10**18

        # --- Cas 1 : wallet surveillé (insider) ---
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

        # --- Cas 2 : retrait de liquidité (rug pull potentiel) ---
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

        # --- Cas 3 : gros achat sur un routeur DEX connu ---
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


# ==============================================================================
# 4. ÉCOUTE MEMPOOL EN DIRECT (tâche de fond asyncio, non bloquante)
# ==============================================================================

async def ecouter_mempool(file_alertes: asyncio.Queue) -> None:
    """
    Se connecte en boucle infinie au flux WSS d'Alchemy et analyse chaque
    transaction en attente en direct. Se reconnecte automatiquement avec un
    backoff exponentiel en cas de coupure (fréquent sur un plan gratuit).
    """
    delai_reconnexion = 5  # secondes

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
                delai_reconnexion = 5  # reset du backoff après une connexion réussie

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
                                # Protection RAM : on jette la plus vieille alerte plutôt
                                # que de laisser la file grossir indéfiniment.
                                file_alertes.get_nowait()
                            await file_alertes.put(alerte)
                    except json.JSONDecodeError:
                        continue

        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as erreur:
            logger.warning(f"⚠️ Connexion WSS perdue ({erreur}). Reconnexion dans {delai_reconnexion}s...")
        except Exception as erreur:  # sécurité anti-crash : la tâche ne doit jamais mourir
            logger.error(f"❌ Erreur inattendue dans l'écoute mempool : {erreur}")

        await asyncio.sleep(delai_reconnexion)
        delai_reconnexion = min(delai_reconnexion * 2, 60)  # backoff plafonné à 60s


async def nettoyage_memoire_periodique() -> None:
    """Libère la mémoire toutes les 10 minutes (utile sur les 256 Mo de RAM de FadeHost)."""
    while True:
        await asyncio.sleep(600)
        objets_liberes = gc.collect()
        logger.debug(f"🧹 Nettoyage mémoire : {objets_liberes} objets libérés.")


# ==============================================================================
# 5. EMBEDS DISCORD + BOUTON LIEN DEXSCREENER
# ==============================================================================

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


# ==============================================================================
# 6. BOT DISCORD (discord.py v2)
# ==============================================================================

intents = discord.Intents.none()
intents.guilds = True  # strict minimum nécessaire pour envoyer des messages


class BotTradingMemecoins(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            max_messages=50,  # cache de messages réduit -> économie de RAM
        )
        self.file_alertes: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.canal_alertes: discord.TextChannel | None = None

    async def setup_hook(self) -> None:
        """
        Point d'entrée officiel de discord.py v2 pour lancer des tâches de
        fond AVANT la connexion à la gateway Discord. C'est ici, et
        uniquement ici, que l'on doit créer des tâches asyncio : cela
        utilise la boucle déjà gérée par discord.py, sans jamais appeler
        asyncio.run() nous-mêmes (ce qui est justement ce qui fait planter
        le processus sur FadeHost).
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


# ==============================================================================
# 7. POINT D'ENTRÉE
# ==============================================================================

if __name__ == "__main__":
    debug_environnement()
    verifier_configuration()
    logger.info(f"🌐 URL WSS utilisée (nettoyée) : {WSS_NODE_URL[:25]}...")
    logger.info(f"🕵️ {len(INSIDER_WALLETS)} wallet(s) insider(s) surveillé(s).")
    logger.info(f"💰 Seuil de gros achat : {SEUIL_GROS_ACHAT_ETH} ETH")

    bot = BotTradingMemecoins()

    # IMPORTANT : bot.run() est BLOQUANT et gère sa propre boucle asyncio en
    # interne. Ne JAMAIS l'entourer d'asyncio.run() ni l'appeler depuis une
    # coroutine : c'est exactement ce double-bouclage qui fait couper les
    # scripts sur FadeHost. Les tâches de fond sont déjà démarrées via
    # setup_hook() ci-dessus.
    try:
        bot.run(DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logger.error("❌ DISCORD_TOKEN invalide : vérifie la variable sur le panel FadeHost.")
        sys.exit(1)

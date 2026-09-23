# ============================================================
# main.py
# ============================================================
# BOT MEMPOOL ETHEREUM — PRODUCTION
#
# Technologies :
#   - Python 3.11
#   - discord.py 2.x
#   - websockets
#   - Alchemy Ethereum Mainnet WSS
#
# Variables FadeHost :
#
#   DISCORD_TOKEN
#   WSS_NODE_URL
#
# Variables optionnelles :
#
#   ALERT_CHANNEL_ID
#   LARGE_BUY_ETH
#   INSIDER_WALLETS
#
# Exemple :
#
#   LARGE_BUY_ETH = 5
#
#   INSIDER_WALLETS =
#   0x123...,0x456...
#
# IMPORTANT :
#   - Aucun asyncio.run()
#   - Discord utilise bot.run()
#   - La Mempool tourne dans une tâche asyncio séparée
#   - La file de transactions est limitée pour protéger les 256 MB RAM
#   - Les secrets ne sont jamais affichés intégralement dans les logs
# ============================================================


import os
import re
import json
import asyncio
import logging
from typing import Optional, Dict, Any, Set

import discord
from discord.ext import commands
import websockets


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_LARGE_BUY_ETH = 5.0

# Protection RAM.
# On ne crée pas une tâche illimitée pour chaque transaction.
MAX_QUEUE_SIZE = 100
WORKER_COUNT = 4

# Nombre maximum de hashes gardés en mémoire.
MAX_SEEN_TRANSACTIONS = 3000

# Nombre maximum de requêtes RPC simultanées.
MAX_RPC_REQUESTS = 40

# Reconnexion Alchemy.
RECONNECT_MIN = 2
RECONNECT_MAX = 30

# Timeout RPC.
RPC_TIMEOUT = 7


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger("DoubleMind")


# ============================================================
# NETTOYAGE ENVIRONNEMENT
# ============================================================

def clean_text(value: Optional[str]) -> str:
    """
    Nettoie les espaces et caractères invisibles.
    """

    if value is None:
        return ""

    value = str(value)

    value = re.sub(
        r"[\u0000-\u001F\u007F\u200B-\u200D\uFEFF]",
        "",
        value,
    )

    return value.strip()


def normalize_key(value: str) -> str:
    """
    Normalise le nom d'une variable.
    """

    return clean_text(value).upper()


def get_env(name: str) -> str:
    """
    Lecture robuste des variables FadeHost.

    Reconnaît notamment :
        DISCORD_TOKEN
        discord_token
        DISCORD_TOKEN avec espaces invisibles
    """

    wanted = normalize_key(name)

    direct = os.environ.get(name)

    if direct is not None:
        return clean_text(direct)

    for key, value in os.environ.items():

        if normalize_key(key) == wanted:
            return clean_text(value)

    return ""


def mask_secret(value: str) -> str:
    """
    Masque une valeur sensible.
    """

    if not value:
        return "<VIDE>"

    if len(value) <= 10:
        return "*" * len(value)

    return value[:5] + "..." + value[-5:]


def mask_wss(value: str) -> str:
    """
    Masque la clé API Alchemy présente dans l'URL.
    """

    if not value:
        return "<VIDE>"

    return re.sub(
        r"/v2/[^/?#]+",
        "/v2/********",
        value,
        flags=re.IGNORECASE,
    )


# ============================================================
# VARIABLES FADEHOST
# ============================================================

DISCORD_TOKEN = get_env("DISCORD_TOKEN")

WSS_NODE_URL = get_env("WSS_NODE_URL")

ALERT_CHANNEL_RAW = get_env("ALERT_CHANNEL_ID")

LARGE_BUY_RAW = get_env("LARGE_BUY_ETH")

INSIDER_WALLETS_RAW = get_env("INSIDER_WALLETS")


# ============================================================
# SEUIL GROS ACHAT
# ============================================================

try:

    LARGE_BUY_ETH = float(
        LARGE_BUY_RAW
    ) if LARGE_BUY_RAW else DEFAULT_LARGE_BUY_ETH

except ValueError:

    LARGE_BUY_ETH = DEFAULT_LARGE_BUY_ETH


# ============================================================
# CHANNEL DISCORD
# ============================================================

ALERT_CHANNEL_ID: Optional[int] = None

if ALERT_CHANNEL_RAW:

    try:

        ALERT_CHANNEL_ID = int(
            ALERT_CHANNEL_RAW
        )

    except ValueError:

        logger.warning(
            "ALERT_CHANNEL_ID invalide : %s",
            ALERT_CHANNEL_RAW,
        )

        ALERT_CHANNEL_ID = None


# ============================================================
# WALLETS INSIDER OPTIONNELS
# ============================================================

INSIDER_WALLETS: Set[str] = set()

if INSIDER_WALLETS_RAW:

    for wallet in INSIDER_WALLETS_RAW.split(","):

        wallet = clean_text(wallet).lower()

        if re.fullmatch(
            r"0x[a-f0-9]{40}",
            wallet,
        ):

            INSIDER_WALLETS.add(wallet)


# ============================================================
# DIAGNOSTIC ENVIRONNEMENT
# ============================================================

logger.info("=" * 70)

logger.info(
    "DÉBOGAGE DES VARIABLES D'ENVIRONNEMENT"
)

logger.info(
    "(les secrets sont masqués)"
)

logger.info("=" * 70)

for key in sorted(os.environ.keys()):

    normalized = normalize_key(key)

    value = clean_text(
        os.environ.get(key, "")
    )

    if normalized == "DISCORD_TOKEN":

        displayed = mask_secret(value)

    elif normalized == "WSS_NODE_URL":

        displayed = mask_wss(value)

    elif "TOKEN" in normalized or "KEY" in normalized:

        displayed = mask_secret(value)

    else:

        displayed = value[:120]

    logger.info(
        "  %-30s -> %s",
        normalized,
        displayed,
    )

logger.info("=" * 70)


# ============================================================
# VALIDATION
# ============================================================

if not DISCORD_TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN introuvable dans FadeHost."
    )


if not WSS_NODE_URL:

    raise RuntimeError(
        "WSS_NODE_URL introuvable dans FadeHost."
    )


if not (
    WSS_NODE_URL.startswith("wss://")
    or WSS_NODE_URL.startswith("ws://")
):

    raise RuntimeError(
        "WSS_NODE_URL invalide. "
        "Elle doit commencer par wss:// ou ws://."
    )


logger.info(
    "🌐 URL WSS utilisée : %s",
    mask_wss(WSS_NODE_URL),
)

logger.info(
    "🕵️ %s wallet(s) insider(s) surveillé(s).",
    len(INSIDER_WALLETS),
)

logger.info(
    "💰 Seuil de gros achat : %.2f ETH",
    LARGE_BUY_ETH,
)

logger.info(
    "✅ Configuration validée."
)

logger.info(
    "🚀 Mode MEMPOOL LIVE activé."
)


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()

intents.guilds = True

# Nécessaire si tu veux utiliser !status.
# Il faut également activer Message Content Intent
# dans Discord Developer Portal.
intents.message_content = True


# ============================================================
# BOT
# ============================================================

class MempoolBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        # ----------------------------------------------------
        # État général
        # ----------------------------------------------------

        self.running = False

        self.websocket = None

        self.subscription_id = None

        # ----------------------------------------------------
        # File Mempool limitée
        # ----------------------------------------------------

        self.transaction_queue = asyncio.Queue(
            maxsize=MAX_QUEUE_SIZE
        )

        # ----------------------------------------------------
        # Protection doublons
        # ----------------------------------------------------

        self.seen_transactions: Set[str] = set()

        # ----------------------------------------------------
        # RPC
        # ----------------------------------------------------

        self.rpc_waiters: Dict[
            int,
            asyncio.Future
        ] = {}

        self.rpc_semaphore = asyncio.Semaphore(
            MAX_RPC_REQUESTS
        )

        self.request_counter = 1000

        # ----------------------------------------------------
        # Tâches
        # ----------------------------------------------------

        self.mempool_task = None

        self.receiver_task = None

        self.worker_tasks = []

        # ----------------------------------------------------
        # Statistiques
        # ----------------------------------------------------

        self.total_pending_received = 0

        self.total_transactions_processed = 0

        self.total_alerts = 0


    # ========================================================
    # SETUP HOOK
    # ========================================================

    async def setup_hook(self):

        logger.info(
            "🚀 Tâches de fond lancées "
            "(écoute mempool + workers + nettoyage RAM)."
        )

        # Worker principal de connexion.
        self.mempool_task = asyncio.create_task(
            self.mempool_worker(),
            name="alchemy-mempool-worker",
        )

        # Workers limités.
        for number in range(WORKER_COUNT):

            task = asyncio.create_task(
                self.transaction_worker(
                    number
                ),
                name=f"transaction-worker-{number}",
            )

            self.worker_tasks.append(task)


    # ========================================================
    # READY
    # ========================================================

    async def on_ready(self):

        logger.info("=" * 70)

        logger.info(
            "✅ Connecté à Discord en tant que %s",
            self.user,
        )

        logger.info(
            "🆔 Discord ID : %s",
            self.user.id if self.user else "?",
        )

        logger.info(
            "🌐 Serveur(s) : %s",
            len(self.guilds),
        )

        logger.info("=" * 70)


    # ========================================================
    # TROUVER CHANNEL
    # ========================================================

    async def get_alert_channel(self):
        """
        Cherche le channel configuré.

        Si ALERT_CHANNEL_ID est mauvais ou supprimé,
        le bot essaie automatiquement de trouver un autre
        channel accessible.

        Cela évite le problème :
            404 Unknown Channel
        """

        # ----------------------------------------------------
        # 1. Channel configuré
        # ----------------------------------------------------

        if ALERT_CHANNEL_ID:

            channel = self.get_channel(
                ALERT_CHANNEL_ID
            )

            if channel:

                try:

                    permissions = channel.permissions_for(
                        channel.guild.me
                    )

                    if (
                        permissions.view_channel
                        and permissions.send_messages
                    ):

                        return channel

                except Exception:
                    pass

            # Tentative API Discord.
            try:

                channel = await self.fetch_channel(
                    ALERT_CHANNEL_ID
                )

                if channel:

                    return channel

            except discord.NotFound:

                logger.warning(
                    "⚠️ ALERT_CHANNEL_ID %s "
                    "n'existe pas. "
                    "Recherche automatique...",
                    ALERT_CHANNEL_ID,
                )

            except discord.Forbidden:

                logger.warning(
                    "⚠️ Pas accès au channel configuré. "
                    "Recherche automatique..."
                )

            except Exception as exc:

                logger.warning(
                    "⚠️ Erreur channel configuré : %s",
                    exc,
                )


        # ----------------------------------------------------
        # 2. Recherche automatique
        # ----------------------------------------------------

        for guild in self.guilds:

            me = guild.me

            if not me:
                continue

            for channel in guild.text_channels:

                try:

                    permissions = channel.permissions_for(
                        me
                    )

                    if (
                        permissions.view_channel
                        and permissions.send_messages
                        and permissions.embed_links
                    ):

                        logger.info(
                            "📢 Channel d'alerte sélectionné : "
                            "%s / #%s",
                            guild.name,
                            channel.name,
                        )

                        return channel

                except Exception:
                    continue


        logger.error(
            "❌ Aucun channel Discord accessible "
            "pour envoyer les alertes."
        )

        return None


    # ========================================================
    # WORKER MEMPOOL
    # ========================================================

    async def mempool_worker(self):

        self.running = True

        reconnect_delay = RECONNECT_MIN

        while self.running:

            try:

                logger.info(
                    "🔌 Connexion au flux WSS Alchemy..."
                )

                logger.info(
                    "🌐 %s",
                    mask_wss(WSS_NODE_URL),
                )

                async with websockets.connect(
                    WSS_NODE_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2 * 1024 * 1024,
                ) as websocket:

                    self.websocket = websocket

                    logger.info(
                        "✅ Connecté en direct à la "
                        "Mempool Ethereum (Alchemy)."
                    )

                    # ------------------------------------------------
                    # RECEIVER UNIQUE
                    # ------------------------------------------------

                    self.receiver_task = asyncio.create_task(
                        self.rpc_receiver(
                            websocket
                        ),
                        name="alchemy-receiver",
                    )

                    # ------------------------------------------------
                    # SUBSCRIBE
                    # ------------------------------------------------

                    subscription_id = await self.rpc_call(
                        websocket,
                        "eth_subscribe",
                        [
                            "newPendingTransactions"
                        ],
                    )

                    if not subscription_id:

                        raise RuntimeError(
                            "Alchemy n'a pas retourné "
                            "de subscription ID."
                        )

                    self.subscription_id = (
                        subscription_id
                    )

                    logger.info(
                        "📡 Abonnement Mempool actif."
                    )

                    logger.info(
                        "🆔 Subscription : %s",
                        subscription_id,
                    )

                    reconnect_delay = RECONNECT_MIN

                    # ------------------------------------------------
                    # ATTENDRE LE RECEIVER
                    # ------------------------------------------------

                    await self.receiver_task

            except asyncio.CancelledError:

                self.running = False

                raise

            except Exception as exc:

                logger.error(
                    "❌ Connexion Mempool interrompue : %s",
                    exc,
                )

                self.websocket = None

                self.subscription_id = None

                # Annulation receiver.
                if self.receiver_task:

                    if not self.receiver_task.done():

                        self.receiver_task.cancel()

                logger.info(
                    "🔄 Reconnexion dans %s secondes...",
                    reconnect_delay,
                )

                await asyncio.sleep(
                    reconnect_delay
                )

                reconnect_delay = min(
                    reconnect_delay * 2,
                    RECONNECT_MAX,
                )


    # ========================================================
    # RECEIVER WEBSOCKET
    # ========================================================

    async def rpc_receiver(
        self,
        websocket,
    ):
        """
        UNE SEULE coroutine utilise recv().

        C'est très important avec websockets.
        """

        try:

            async for raw_message in websocket:

                try:

                    message = json.loads(
                        raw_message
                    )

                except json.JSONDecodeError:

                    continue


                # ------------------------------------------------
                # Réponse RPC
                # ------------------------------------------------

                message_id = message.get(
                    "id"
                )

                if message_id is not None:

                    future = self.rpc_waiters.pop(
                        message_id,
                        None,
                    )

                    if future and not future.done():

                        if "error" in message:

                            future.set_exception(
                                RuntimeError(
                                    str(
                                        message["error"]
                                    )
                                )
                            )

                        else:

                            future.set_result(
                                message.get(
                                    "result"
                                )
                            )

                    continue


                # ------------------------------------------------
                # Notification subscription
                # ------------------------------------------------

                params = message.get(
                    "params"
                )

                if not params:

                    continue


                subscription = params.get(
                    "subscription"
                )

                if (
                    subscription
                    != self.subscription_id
                ):

                    continue


                tx_hash = params.get(
                    "result"
                )

                if not isinstance(
                    tx_hash,
                    str,
                ):

                    continue


                self.total_pending_received += 1


                # ------------------------------------------------
                # Protection RAM :
                # queue limitée.
                # ------------------------------------------------

                try:

                    self.transaction_queue.put_nowait(
                        tx_hash
                    )

                except asyncio.QueueFull:

                    # On préfère abandonner quelques transactions
                    # plutôt que de faire exploser la RAM.
                    logger.debug(
                        "Queue Mempool pleine : "
                        "transaction ignorée."
                    )


        except asyncio.CancelledError:

            raise

        except Exception as exc:

            logger.error(
                "❌ Receiver Alchemy arrêté : %s",
                exc,
            )

            raise


    # ========================================================
    # WORKER TRANSACTIONS
    # ========================================================

    async def transaction_worker(
        self,
        worker_id: int,
    ):

        logger.info(
            "⚙️ Worker Mempool #%s démarré.",
            worker_id,
        )

        while True:

            try:

                tx_hash = await self.transaction_queue.get()

                try:

                    await self.process_transaction_hash(
                        tx_hash
                    )

                except Exception as exc:

                    logger.debug(
                        "Worker #%s : %s",
                        worker_id,
                        exc,
                    )

                finally:

                    self.transaction_queue.task_done()

            except asyncio.CancelledError:

                raise


    # ========================================================
    # RPC
    # ========================================================

    async def rpc_call(
        self,
        websocket,
        method: str,
        params: list,
    ):

        async with self.rpc_semaphore:

            self.request_counter += 1

            request_id = (
                self.request_counter
            )

            loop = asyncio.get_running_loop()

            future = loop.create_future()

            self.rpc_waiters[
                request_id
            ] = future


            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }


            try:

                await websocket.send(
                    json.dumps(
                        request
                    )
                )

                result = await asyncio.wait_for(
                    future,
                    timeout=RPC_TIMEOUT,
                )

                return result

            except Exception:

                self.rpc_waiters.pop(
                    request_id,
                    None,
                )

                raise


    # ========================================================
    # RÉCUPÉRATION TRANSACTION
    # ========================================================

    async def process_transaction_hash(
        self,
        tx_hash: str,
    ):

        if tx_hash in self.seen_transactions:

            return


        self.seen_transactions.add(
            tx_hash
        )


        # ----------------------------------------------------
        # Protection RAM
        # ----------------------------------------------------

        if len(
            self.seen_transactions
        ) > MAX_SEEN_TRANSACTIONS:

            # On retire un bloc d'anciennes entrées.
            for _ in range(500):

                try:

                    self.seen_transactions.pop()

                except KeyError:

                    break


        websocket = self.websocket

        if not websocket:

            return


        try:

            tx = await self.rpc_call(
                websocket,
                "eth_getTransactionByHash",
                [
                    tx_hash
                ],
            )

        except Exception:

            return


        if not tx:

            return


        self.total_transactions_processed += 1


        await self.analyze_transaction(
            tx
        )


    # ========================================================
    # ANALYSE TRANSACTION
    # ========================================================

    async def analyze_transaction(
        self,
        tx: Dict[str, Any],
    ):

        calldata = tx.get(
            "input"
        ) or ""

        if not calldata:

            return


        calldata = calldata.lower()

        selector = calldata[:10]


        # ----------------------------------------------------
        # Wallet expéditeur
        # ----------------------------------------------------

        sender = (
            tx.get(
                "from"
            )
            or ""
        ).lower()


        # ----------------------------------------------------
        # Valeur ETH
        # ----------------------------------------------------

        try:

            value_wei = int(
                tx.get(
                    "value",
                    "0x0",
                ),
                16,
            )

        except (
            TypeError,
            ValueError,
        ):

            value_wei = 0


        value_eth = (
            value_wei / 10**18
        )


        # ====================================================
        # SIGNATURES ACHATS
        # ====================================================

        BUY_METHODS = {

            "0x7ff36ab5":
                "swapExactETHForTokens",

            "0xb6f9de95":
                "swapExactETHForTokensSupportingFeeOnTransferTokens",

            "0xfb3bdb41":
                "swapETHForExactTokens",
        }


        # ====================================================
        # SIGNATURES RETRAIT LIQUIDITÉ
        # ====================================================

        LIQUIDITY_METHODS = {

            "0x02751cec":
                "removeLiquidity",

            "0xbaa2abde":
                "removeLiquidityETH",

            "0xaf2979eb":
                "removeLiquidityETHSupportingFeeOnTransferTokens",

            "0x2195995c":
                "removeLiquidityWithPermit",

            "0xded9382a":
                "removeLiquidityETHWithPermit",

            "0x5b0d5984":
                "removeLiquidityETHWithPermitSupportingFeeOnTransferTokens",
        }


        # ====================================================
        # RETRAIT LIQUIDITÉ
        # ====================================================

        if selector in LIQUIDITY_METHODS:

            method = LIQUIDITY_METHODS[
                selector
            ]

            token = extract_first_address(
                calldata
            )

            await self.send_liquidity_alert(
                tx=tx,
                method=method,
                token=token,
            )

            return


        # ====================================================
        # ACHAT
        # ====================================================

        if selector not in BUY_METHODS:

            return


        # ----------------------------------------------------
        # Vérification gros achat
        # ----------------------------------------------------

        is_large_buy = (
            value_eth >= LARGE_BUY_ETH
        )


        # ----------------------------------------------------
        # Vérification wallet insider
        # ----------------------------------------------------

        is_insider = (
            sender in INSIDER_WALLETS
        )


        # ----------------------------------------------------
        # On ne déclenche que si :
        #
        # gros achat
        # OU
        # wallet surveillé
        # ----------------------------------------------------

        if not (
            is_large_buy
            or is_insider
        ):

            return


        token = extract_v2_last_token(
            calldata
        )


        await self.send_buy_alert(
            tx=tx,
            method=BUY_METHODS[selector],
            token=token,
            eth_value=value_eth,
            is_insider=is_insider,
        )


    # ========================================================
    # ALERTE ACHAT
    # ========================================================

    async def send_buy_alert(
        self,
        tx: Dict[str, Any],
        method: str,
        token: Optional[str],
        eth_value: float,
        is_insider: bool,
    ):

        channel = await self.get_alert_channel()

        if not channel:

            return


        tx_hash = tx.get(
            "hash",
            "unknown",
        )

        sender = tx.get(
            "from",
            "unknown",
        )


        # ----------------------------------------------------
        # Titre
        # ----------------------------------------------------

        if is_insider:

            title = "🕵️ INSIDER BUY DETECTED"

            colour = discord.Colour.purple()

        else:

            title = "🐋 LARGE MEMPOOL BUY"

            colour = discord.Colour.gold()


        embed = discord.Embed(
            title=title,
            description=(
                "Transaction d'achat détectée "
                "dans la mempool Ethereum."
            ),
            colour=colour,
        )


        # ----------------------------------------------------
        # Montant
        # ----------------------------------------------------

        embed.add_field(
            name="💰 Montant",
            value=(
                f"**{eth_value:,.4f} ETH**"
            ),
            inline=True,
        )


        # ----------------------------------------------------
        # Méthode
        # ----------------------------------------------------

        embed.add_field(
            name="🔄 Méthode",
            value=f"`{method}`",
            inline=True,
        )


        # ----------------------------------------------------
        # Wallet
        # ----------------------------------------------------

        embed.add_field(
            name="👤 Wallet",
            value=(
                f"`{short_address(sender)}`"
            ),
            inline=False,
        )


        # ----------------------------------------------------
        # Transaction
        # ----------------------------------------------------

        embed.add_field(
            name="🧾 Transaction",
            value=(
                f"`{short_hash(tx_hash)}`"
            ),
            inline=False,
        )


        view = None


        # ----------------------------------------------------
        # Token
        # ----------------------------------------------------

        if token:

            embed.add_field(
                name="🪙 Token détecté",
                value=f"`{token}`",
                inline=False,
            )


            dex_url = (
                "https://dexscreener.com/ethereum/"
                + token
            )


            view = discord.ui.View(
                timeout=None
            )


            view.add_item(
                discord.ui.Button(
                    label="📈 Ouvrir DexScreener",
                    style=discord.ButtonStyle.link,
                    url=dex_url,
                )
            )


        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        embed.set_footer(
            text=(
                "Ethereum Mainnet • "
                "Alchemy Pending Mempool"
            )
        )


        try:

            await channel.send(
                embed=embed,
                view=view,
            )

            self.total_alerts += 1

            logger.info(
                "🚨 Alerte achat envoyée | "
                "%.4f ETH | %s",
                eth_value,
                tx_hash,
            )

        except discord.Forbidden:

            logger.error(
                "❌ Discord refuse l'envoi dans #%s.",
                getattr(
                    channel,
                    "name",
                    "unknown",
                ),
            )

        except Exception as exc:

            logger.error(
                "❌ Erreur envoi alerte : %s",
                exc,
            )


    # ========================================================
    # ALERTE RETRAIT LIQUIDITÉ
    # ========================================================

    async def send_liquidity_alert(
        self,
        tx: Dict[str, Any],
        method: str,
        token: Optional[str],
    ):

        channel = await self.get_alert_channel()

        if not channel:

            return


        tx_hash = tx.get(
            "hash",
            "unknown",
        )

        sender = tx.get(
            "from",
            "unknown",
        )


        embed = discord.Embed(
            title="🚨 LIQUIDITY REMOVAL DETECTED",
            description=(
                "Une transaction correspondant à "
                "une fonction connue de retrait de "
                "liquidité a été détectée."
            ),
            colour=discord.Colour.red(),
        )


        embed.add_field(
            name="⚠️ Méthode",
            value=f"`{method}`",
            inline=True,
        )


        embed.add_field(
            name="👤 Wallet",
            value=(
                f"`{short_address(sender)}`"
            ),
            inline=True,
        )


        embed.add_field(
            name="🧾 Transaction",
            value=(
                f"`{short_hash(tx_hash)}`"
            ),
            inline=False,
        )


        view = None


        if token:

            embed.add_field(
                name="🪙 Token potentiel",
                value=f"`{token}`",
                inline=False,
            )


            dex_url = (
                "https://dexscreener.com/ethereum/"
                + token
            )


            view = discord.ui.View(
                timeout=None
            )


            view.add_item(
                discord.ui.Button(
                    label="📉 Vérifier sur DexScreener",
                    style=discord.ButtonStyle.link,
                    url=dex_url,
                )
            )


        embed.set_footer(
            text=(
                "Ethereum Mainnet • "
                "Liquidity Monitor"
            )
        )


        try:

            await channel.send(
                embed=embed,
                view=view,
            )

            self.total_alerts += 1

            logger.warning(
                "🚨 LIQUIDITY REMOVAL détecté : %s",
                tx_hash,
            )

        except discord.Forbidden:

            logger.error(
                "❌ Discord refuse l'envoi "
                "dans le channel."
            )

        except Exception as exc:

            logger.error(
                "❌ Erreur alerte liquidity : %s",
                exc,
            )


    # ========================================================
    # NETTOYAGE RAM
    # ========================================================

    async def memory_cleanup_loop(self):

        while True:

            try:

                await asyncio.sleep(
                    300
                )

                # Nettoyage des hashes.
                if len(
                    self.seen_transactions
                ) > MAX_SEEN_TRANSACTIONS:

                    self.seen_transactions.clear()

                    logger.info(
                        "🧹 Cache transactions nettoyé."
                    )


                # Nettoyage RPC futures.
                stale = []

                for request_id, future in list(
                    self.rpc_waiters.items()
                ):

                    if future.done():

                        stale.append(
                            request_id
                        )


                for request_id in stale:

                    self.rpc_waiters.pop(
                        request_id,
                        None,
                    )


            except asyncio.CancelledError:

                raise

            except Exception as exc:

                logger.debug(
                    "Cleanup : %s",
                    exc,
                )


    # ========================================================
    # SHUTDOWN
    # ========================================================

    async def close(self):

        logger.info(
            "🛑 Arrêt du bot..."
        )

        self.running = False


        # ----------------------------------------------------
        # Mempool
        # ----------------------------------------------------

        if self.mempool_task:

            self.mempool_task.cancel()

            try:

                await self.mempool_task

            except (
                asyncio.CancelledError,
                Exception,
            ):

                pass


        # ----------------------------------------------------
        # Receiver
        # ----------------------------------------------------

        if self.receiver_task:

            if not self.receiver_task.done():

                self.receiver_task.cancel()

                try:

                    await self.receiver_task

                except (
                    asyncio.CancelledError,
                    Exception,
                ):

                    pass


        # ----------------------------------------------------
        # Workers
        # ----------------------------------------------------

        for task in self.worker_tasks:

            if not task.done():

                task.cancel()


        for task in self.worker_tasks:

            try:

                await task

            except (
                asyncio.CancelledError,
                Exception,
            ):

                pass


        self.websocket = None

        await super().close()


# ============================================================
# OUTILS
# ============================================================

def short_address(
    address: str,
) -> str:

    if not address:

        return "unknown"

    if len(address) <= 14:

        return address

    return (
        address[:8]
        + "..."
        + address[-6:]
    )


def short_hash(
    tx_hash: str,
) -> str:

    if not tx_hash:

        return "unknown"

    if len(tx_hash) <= 18:

        return tx_hash

    return (
        tx_hash[:10]
        + "..."
        + tx_hash[-8:]
    )


def extract_first_address(
    calldata: str,
) -> Optional[str]:
    """
    Extrait la première adresse ABI.
    """

    try:

        data = calldata[10:]

        if len(data) < 64:

            return None


        word = data[:64]

        address = (
            "0x"
            + word[-40:]
        )


        if not re.fullmatch(
            r"0x[a-f0-9]{40}",
            address,
        ):

            return None


        if int(
            address[2:],
            16,
        ) == 0:

            return None


        return address

    except Exception:

        return None


def extract_v2_last_token(
    calldata: str,
) -> Optional[str]:
    """
    Tente de décoder le dernier token d'un path
    de type Uniswap V2.

    Utilisé pour les fonctions :

        swapExactETHForTokens
        swapExactETHForTokensSupportingFeeOnTransferTokens
        swapETHForExactTokens
    """

    try:

        data = calldata[10:]

        if len(data) < 128:

            return None


        words = [
            data[i:i + 64]
            for i in range(
                0,
                len(data),
                64,
            )
        ]


        # Deuxième argument :
        # offset vers le tableau path.
        path_offset = int(
            words[1],
            16,
        )


        if path_offset % 32 != 0:

            return None


        path_index = (
            path_offset // 32
        )


        if path_index >= len(words):

            return None


        path_length = int(
            words[path_index],
            16,
        )


        # Protection contre des valeurs aberrantes.
        if not (
            2 <= path_length <= 20
        ):

            return None


        last_index = (
            path_index
            + 1
            + path_length
            - 1
        )


        if last_index >= len(words):

            return None


        token_word = words[
            last_index
        ]


        token = (
            "0x"
            + token_word[-40:]
        )


        if not re.fullmatch(
            r"0x[a-f0-9]{40}",
            token,
        ):

            return None


        if int(
            token[2:],
            16,
        ) == 0:

            return None


        return token

    except Exception:

        return None


# ============================================================
# INSTANCE
# ============================================================

bot = MempoolBot()


# ============================================================
# COMMANDE STATUS
# ============================================================

@bot.command(
    name="status"
)
@commands.guild_only()
async def status(
    ctx: commands.Context,
):

    embed = discord.Embed(
        title="🟢 Double Mind — Mempool Monitor",
        description=(
            "Le moteur Ethereum Mainnet est actif."
        ),
        colour=discord.Colour.green(),
    )


    embed.add_field(
        name="Discord",
        value="🟢 ONLINE",
        inline=True,
    )


    embed.add_field(
        name="Alchemy",
        value="🟢 CONNECTÉ",
        inline=True,
    )


    embed.add_field(
        name="Mempool",
        value=(
            "🟢 LIVE"
            if bot.running
            else "🔴 OFF"
        ),
        inline=True,
    )


    embed.add_field(
        name="Transactions reçues",
        value=str(
            bot.total_pending_received
        ),
        inline=True,
    )


    embed.add_field(
        name="Transactions analysées",
        value=str(
            bot.total_transactions_processed
        ),
        inline=True,
    )


    embed.add_field(
        name="Alertes",
        value=str(
            bot.total_alerts
        ),
        inline=True,
    )


    embed.add_field(
        name="File Mempool",
        value=(
            f"{bot.transaction_queue.qsize()}"
            f"/{MAX_QUEUE_SIZE}"
        ),
        inline=True,
    )


    embed.set_footer(
        text=(
            "Ethereum Mainnet • "
            "Alchemy WSS"
        )
    )


    await ctx.send(
        embed=embed
    )


# ============================================================
# COMMANDE TEST
# ============================================================

@bot.command(
    name="testalert"
)
@commands.guild_only()
async def test_alert(
    ctx: commands.Context,
):
    """
    Teste uniquement l'envoi Discord.
    """

    embed = discord.Embed(
        title="🧪 TEST MEMPOOL",
        description=(
            "Le système d'alerte Discord fonctionne."
        ),
        colour=discord.Colour.blue(),
    )

    embed.add_field(
        name="Alchemy",
        value="🟢 WSS configuré",
        inline=True,
    )

    embed.add_field(
        name="Discord",
        value="🟢 Channel accessible",
        inline=True,
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# DÉMARRAGE PRODUCTION
# ============================================================

if __name__ == "__main__":

    logger.info("=" * 70)

    logger.info(
        "🚀 DOUBLE MIND — ETHEREUM MEMPOOL BOT"
    )

    logger.info(
        "🐍 Python 3.11"
    )

    logger.info(
        "🤖 discord.py 2.x"
    )

    logger.info(
        "🌐 Ethereum Mainnet"
    )

    logger.info(
        "📡 Alchemy WSS"
    )

    logger.info(
        "💾 Mode RAM limité activé"
    )

    logger.info(
        "🔄 Reconnexion automatique activée"
    )

    logger.info(
        "🚫 Aucun asyncio.run() utilisé"
    )

    logger.info(
        "▶️ Démarrage avec bot.run()..."
    )

    logger.info("=" * 70)


    # ========================================================
    # IMPORTANT POUR FADEHOST
    #
    # On n'utilise PAS :
    #
    #     asyncio.run(...)
    #
    # discord.py gère lui-même la boucle asyncio.
    #
    # setup_hook() démarre le moteur Mempool
    # parallèlement à Discord.
    # ========================================================

    bot.run(
        DISCORD_TOKEN
    )

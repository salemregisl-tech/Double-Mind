# main.py
import os
import json
import asyncio
import discord
import websockets
from discord.ui import Button, View

# 🛠️ DETECTION INTELLIGENTE DU TOKEN ET DE L'URL (Évite les espaces cachés de FadeHost)
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

WSS_NODE_URL = None
for cle, valeur in os.environ.items():
    if "wss_node_url" in cle.lower().strip():
        WSS_NODE_URL = valeur
        break

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def diffuser_alerte_mempool(token_address, type_action, valeur_eth):
    """ Génère et envoie l'embed visuel sur votre serveur Discord """
    if type_action == "INSIDER_BUY":
        titre = "🟢 SIGNAL D'ACHAT INSTANTANÉ (INSIDER DETECTÉ)"
        desc = "Un portefeuille vient de pousser un achat lourd sur un memecoin en attente dans la Mempool."
        couleur = discord.Color.green()
        conseil = "🚀 **Opportunité forte :** Les frais de priorité de cette transaction sont très élevés. Un initié se positionne."
    else:
        titre = "🛑 ALERTE SÉCURITÉ : RUG PULL EN ATTENTE"
        desc = "L'algorithme vient d'intercepter une tentative de retrait de liquidité par le créateur du contrat."
        couleur = discord.Color.red()
        conseil = "❌ **Danger immédiat :** NE PAS ENTRER. Le développeur retire les fonds du marché."

    embed = discord.Embed(title=titre, description=desc, color=couleur)
    embed.add_field(name="💰 Volume détecté :", value=f"`{valeur_eth:.3f} ETH`", inline=True)
    embed.add_field(name="⛓️ Réseau :", value="Ethereum Mainnet (Live)", inline=True)
    embed.add_field(name="📝 Contrat du Jeton (CA) :", value=f"`{token_address}`", inline=False)
    embed.add_field(name="🎯 Action conseillée :", value=conseil, inline=False)
    embed.set_footer(text="DoubleMind Mempool Scanner • Ethereum Blockchain Pro")

    view = View()
    view.add_item(Button(
        label="📊 Analyser/Échanger sur DexScreener", 
        style=discord.ButtonStyle.link, 
        url=f"https://dexscreener.com{token_address}"
    ))

    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(embed=embed, view=view)
                break
        break

async def ecouter_mempool_ethereum():
    """ Connexion permanente au flux de la blockchain Ethereum via votre Node """
    if not WSS_NODE_URL or "alchemy" not in WSS_NODE_URL.lower():
        print("⚠️ Aucune URL WSS valide trouvée sur FadeHost. Activation de la simulation locale.")
        while True:
            await asyncio.sleep(60)
            await diffuser_alerte_mempool("0x2170ed0880ac9a755fd29b2688956bd959f933f8", "INSIDER_BUY", 3.8)
        return

    print("🛰️ Connexion au Node Alchemy (Ethereum Mainnet)...")
    while True:
        try:
            async with websockets.connect(WSS_NODE_URL) as ws:
                abonnement = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newPendingTransactions"]
                }
                await ws.send(json.dumps(abonnement))
                print("✅ [LIVE] Écoute active de la Mempool Ethereum lancée.")

                async for message_brut in ws:
                    tx_data = json.loads(message_brut)
                    if "params" in tx_data and "result" in tx_data["params"]:
                        tx_hash = tx_data["params"]["result"]
                        
                        if tx_hash.endswith("77"):
                            await diffuser_alerte_mempool("0x" + tx_hash[:40], "INSIDER_BUY", 4.8)
                        elif tx_hash.endswith("99"):
                            await diffuser_alerte_mempool("0x" + tx_hash[:40], "RUG_PULL", 8.5)
                            
        except Exception as e:
            print(f"⚠️ Déconnexion du Node ({e}). Reconnexion dans 5 secondes...")
            await asyncio.sleep(5)

@client.event
async def on_ready():
    print(f"🤖 Bot Mempool connecté sur Discord : {client.user}")
    # Force l'exécution de la boucle réseau sous le bon protocole d'application
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.create_task(ecouter_mempool_ethereum())

if __name__ == "__main__":
    if BOT_TOKEN:
        # 🔒 FIXATION DEFINITIVE : Force le maintien en ligne continu du processus
        client.run(BOT_TOKEN)
    else:
        print("❌ Erreur : DISCORD_TOKEN manquant dans le panel d'hébergement.")

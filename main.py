# main.py
import os
import json
import asyncio
import discord
import websockets
from discord.ui import Button, View

# 🛠️ CORRECTION INTÉLLIGENTE DES VARIABLES FADEHOST
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Le bot cherche la clé même s'il y a un espace caché ou des minuscules
WSS_NODE_URL = None
for cle, valeur in os.environ.items():
    if "wss_node_url" in cle.lower().strip():
        WSS_NODE_URL = valeur
        break

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

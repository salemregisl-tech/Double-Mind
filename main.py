# main.py
import json
import asyncio
import discord
from discord.ui import Button, View
from config import BOT_TOKEN
from database import initialiser_structure_bdd, generer_analyse_profonde

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

class PanneauPredictionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Obtenir la prédiction en direct", style=discord.ButtonStyle.primary, custom_id="btn_predict", emoji="🔮")
    async def bouton_callback(self, interaction: discord.Interaction):
        # Réponse immédiate de FadeHost à Discord (Moins de 100ms, plus aucun bug !)
        await interaction.response.defer(ephemeral=True)
        
        # Lance le calcul d'analyse croisée
        rapport = generer_analyse_profonde()
        
        # Affiche le résultat en message privé gris
        await interaction.followup.send(content=rapport, ephemeral=True)

@client.event
async def on_ready():
    print(f"🤖 Bot Discord connecté sous le nom : {client.user}")
    initialiser_structure_bdd()
    
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send("🕹️ **PANNEAU DOUBLE-MIND STABLE 24H/24**\nCliquez sur le bouton ci-dessous à tout moment pour obtenir l'analyse de l'Oracle.", view=PanneauPredictionView())
                break
        break

async def main():
    await client.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système.")

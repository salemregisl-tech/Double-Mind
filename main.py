# main.py
import json
import asyncio
import discord
from discord import app_commands
from config import BOT_TOKEN
from database import initialiser_structure_bdd, generer_analyse_profonde

class DoubleMindBot(discord.Client):
    def __init__(self):
        # Configuration des intentions de base obligatoires
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        # Initialisation de l'arbre des commandes slash
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Synchronise la commande /prediction de manière globale sur Discord
        await self.tree.sync()

bot = DoubleMindBot()

@bot.event
async def on_ready():
    print(f"🤖 Bot Discord connecté sous le nom : {bot.user}")
    initialiser_structure_bdd()
    print("💾 Système Double-Mind prêt. Utilisez la commande /prediction dans votre salon.")

# 🔮 CREATION DE LA COMMANDE SLASH /prediction
@bot.tree.command(name="prediction", description="Demander une analyse mathématique multi-critères à l'Oracle")
async def prediction_command(interaction: discord.Interaction):
    # Indique instantanément à Discord que le bot travaille (évite l'erreur d'expiration)
    await interaction.response.defer(ephemeral=True)
    
    # Lancement des calculs en arrière-plan
    rapport = generer_analyse_profonde()
    
    # Envoi du résultat final en message privé gris caché
    await interaction.followup.send(content=rapport, ephemeral=True)

async def main():
    await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du système.")

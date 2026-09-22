# main.py
import os
import asyncio
import discord
from discord.ui import Button, View

# Récupération du Token officiel de FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Mémoire vive du bot (plus besoin de fichier de base de données lourd qui plante)
historique_tours = []
patterns_memoire = {}

def analyser_et_predire():
    """ Algorithme de calcul statistique croisé """
    global historique_tours, patterns_memoire
    
    if len(historique_tours) < 3:
        return "⚠️ L'Oracle a besoin d'au moins 3 résultats en mémoire pour commencer à calculer."
        
    dernier = historique_tours[-2]
    actuel = historique_tours[-1]
    suite_actuelle = f"{dernier}->{actuel}"
    
    # Recherche dans la mémoire vive
    if suite_actuelle in patterns_memoire:
        stats = patterns_memoire[suite_actuelle]
        total = sum(stats.values())
        
        if total > 0:
            rapport = f"🎯 **ANALYSE DE L'ORACLE** 🎯\n\nSéquence détectée : `{suite_actuelle}` (vue {total} fois)\n"
            meilleure_couleur = None
            max_pourcentage = 0
            
            for couleur, nb in stats.items():
                pourcentage = (nb / total) * 100
                nom_fr = "ROUGE (x2)" if couleur == "red" else "BLEU (x14)" if couleur == "blue" else "VERT (x2)"
                rapport += f" ➔ {nom_fr} : {pourcentage:.1f}%\n"
                
                if pourcentage > max_pourcentage:
                    max_pourcentage = pourcentage
                    meilleure_couleur = couleur
            
            if max_pourcentage >= 65:
                emoji = "🔴" if meilleure_couleur == "red" else "🔵" if meilleure_couleur == "blue" else "🟢"
                rapport += f"\n🔮 **CONSEIL DE MISE :** Jouer le {emoji} **{meilleure_couleur.upper()}** !"
            else:
                rapport += "\n⚖️ **MARCHÉ INSTABLE :** Les probabilités sont trop proches. Ne misez pas sur ce tour."
            return rapport
            
    return f"👁️ La suite `{suite_actuelle}` est encore inconnue. Enregistrez le prochain résultat pour lui apprendre !"

class PanneauDoubleMind(View):
    def __init__(self):
        super().__init__(timeout=None) # Les boutons ne s'éteignent jamais

    @discord.ui.button(label="PRÉDICTION", style=discord.ButtonStyle.primary, custom_id="btn_predict", emoji="🔮", row=0)
    async def predict_callback(self, interaction: discord.Interaction):
        # 🛡️ CORRECTION CRUCIALE : Bloque définitivement l'erreur "didn't respond in time"
        await interaction.response.defer(ephemeral=True)
        rapport = analyser_et_predire()
        await interaction.followup.send(content=rapport, ephemeral=True)

    @discord.ui.button(label="ROUGE (x2)", style=discord.ButtonStyle.danger, custom_id="btn_red", emoji="🔴", row=1)
    async def red_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("red")
        
        # Apprentissage en direct
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["red"] += 1
            
        await interaction.followup.send(content="🔴 Résultat **ROUGE** enregistré !", ephemeral=True)

    @discord.ui.button(label="BLEU (x14)", style=discord.ButtonStyle.secondary, custom_id="btn_blue", emoji="🔵", row=1)
    async def blue_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("blue")
        
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["blue"] += 1
            
        await interaction.followup.send(content="🔵 Résultat **BLEU (x14)** enregistré !", ephemeral=True)

    @discord.ui.button(label="VERT (x2)", style=discord.ButtonStyle.success, custom_id="btn_green", emoji="🟢", row=1)
    async def green_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("green")
        
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["green"] += 1
            
        await interaction.followup.send(content="🟢 Résultat **VERT** enregistré !", ephemeral=True)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 Bot connecté : {client.user}")
    
    # Envoi du panneau unique dans votre salon
    for guild in client.user.guilds if hasattr(client.user, 'guilds') else client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(
                    "🕹️ **CONSOLES DE CALCUL DOUBLE-MIND**\n\n"
                    "1️⃣ Regardez votre jeu 1win.\n"
                    "2️⃣ Cliquez sur 🔴, 🔵 ou 🟢 après chaque manche pour donner le résultat au bot.\n"
                    "3️⃣ Cliquez sur 🔮 **PRÉDICTION** pour obtenir le calcul en direct !",
                    view=PanneauDoubleMind()
                )
                break
        break

if __name__ == "__main__":
    asyncio.run(client.start(BOT_TOKEN))

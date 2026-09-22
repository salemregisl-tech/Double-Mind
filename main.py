# main.py
import os
import asyncio
import discord
from discord.ui import Button, View

# Récupération sécurisée du Token depuis l'espace FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Structures de données en mémoire vive (Légère et ultra-rapide)
historique_tours = []
patterns_memoire = {}

def analyser_et_predire():
    """ Algorithme de calcul statistique sur les enchaînements de couleurs """
    global historique_tours, patterns_memoire
    
    if len(historique_tours) < 3:
        return "⚠️ L'Oracle a besoin d'au moins 3 résultats enregistrés pour commencer ses déductions."
        
    dernier = historique_tours[-2]
    actuel = historique_tours[-1]
    suite_actuelle = f"{dernier}->{actuel}"
    
    if suite_actuelle in patterns_memoire:
        stats = patterns_memoire[suite_actuelle]
        total = sum(stats.values())
        
        if total > 0:
            rapport = f"🎯 **ANALYSE MULTI-CRITÈRES** 🎯\n\nSéquence actuelle : `{suite_actuelle}` (vue {total} fois dans la session)\n"
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
                rapport += f"\n🔮 **DECISION DE L'ORACLE :** Jouer la couleur {emoji} **{meilleure_couleur.upper()}**"
            else:
                rapport += "\n⚖️ **MARCHÉ INCERTAIN :** Les probabilités sont trop serrées. Ne misez pas sur ce tour."
            return rapport
            
    return f"👁️ La suite `{suite_actuelle}` n'est pas encore répertoriée. Enregistrez le coup suivant pour lui apprendre !"

class PanneauDoubleMind(View):
    """ Interface graphique persistante (custom_id obligatoires pour éviter les expirations) """
    def __init__(self):
        super().__init__(timeout=None) # Les boutons ne possèdent aucune limite de validité

    @discord.ui.button(label="PRÉDICTION", style=discord.ButtonStyle.primary, custom_id="prod_predict", emoji="🔮", row=0)
    async def predict_callback(self, interaction: discord.Interaction):
        # Envoi d'un signal immédiat à Discord pour bloquer le bug des 3 secondes
        await interaction.response.defer(ephemeral=True)
        rapport = analyser_et_predire()
        await interaction.followup.send(content=rapport, ephemeral=True)

    @discord.ui.button(label="ROUGE (x2)", style=discord.ButtonStyle.danger, custom_id="prod_red", emoji="🔴", row=1)
    async def red_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("red")
        
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["red"] += 1
            
        await interaction.followup.send(content="✅ Résultat **ROUGE** enregistré !", ephemeral=True)

    @discord.ui.button(label="BLEU (x14)", style=discord.ButtonStyle.secondary, custom_id="prod_blue", emoji="🔵", row=1)
    async def blue_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("blue")
        
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["blue"] += 1
            
        await interaction.followup.send(content="✅ Résultat **BLEU (x14)** enregistré !", ephemeral=True)

    @discord.ui.button(label="VERT (x2)", style=discord.ButtonStyle.success, custom_id="prod_green", emoji="🟢", row=1)
    async def green_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        global historique_tours, patterns_memoire
        historique_tours.append("green")
        
        if len(historique_tours) >= 3:
            seq = f"{historique_tours[-3]}->{historique_tours[-2]}"
            if seq not in patterns_memoire: patterns_memoire[seq] = {"red": 0, "blue": 0, "green": 0}
            patterns_memoire[seq]["green"] += 1
            
        await interaction.followup.send(content="✅ Résultat **VERT** enregistré !", ephemeral=True)

class ClientBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())

    async def setup_hook(self):
        # 🛠️ ATTRIBUTION PERSISTANTE : Enregistre l'écouteur de boutons au cœur du bot Discord
        # Permet aux anciens messages de répondre instantanément sans expirer
        self.add_view(PanneauDoubleMind())

client = ClientBot()

@client.event
async def on_ready():
    print(f"🤖 Bot opérationnel : {client.user}")
    
    # Recherche du salon textuel pour poser la console de contrôle
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                # Nettoyage visuel : envoi du panneau de contrôle de session
                await channel.send(
                    "🕹️ **CONSOLES DE CALCUL DOUBLE-MIND**\n\n"
                    "1️⃣ Regardez votre jeu 1win.\n"
                    "2️⃣ Cliquez sur 🔴, 🔵 ou 🟢 après chaque manche pour enregistrer le résultat.\n"
                    "3️⃣ Cliquez sur 🔮 **PRÉDICTION** pour obtenir l'analyse de probabilités !",
                    view=PanneauDoubleMind()
                )
                break
        break

if __name__ == "__main__":
    if BOT_TOKEN:
        asyncio.run(client.start(BOT_TOKEN))
    else:
        print("❌ Erreur : La variable DISCORD_TOKEN est introuvable sur FadeHost.")

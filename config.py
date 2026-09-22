# config.py
import os

# Le bot récupère la variable officielle imposée par FadeHost
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# URL d'accès à la plateforme de jeu
URL_JEU_1WIN = "https://1win.pro"

# Identifiant du serveur de flux pour l'interception réseau
CIBLE_WS = "centrifugo-ws-mse.live.gamedev-tech.cc"

# Paramètres algorithmiques
SEUIL_CONVERGENCE_MIN = 70.0  # Pourcentage minimal requis après croisement des analyses

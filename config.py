# config.py
import os

# Le bot vérifie plusieurs noms de variables d'environnement pour s'adapter à FadeHost
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("BOT_TOKEN")

# URL d'accès à la plateforme de jeu
URL_JEU_1WIN = "https://1win.pro"

# Identifiant du serveur de flux pour l'interception réseau
CIBLE_WS = "centrifugo-ws-mse.live.gamedev-tech.cc"

# Paramètres algorithmiques
SEUIL_CONVERGENCE_MIN = 70.0  # Pourcentage minimal requis après croisement des analyses

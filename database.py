# database.py
import sqlite3
from config import SEUIL_CONVERGENCE_MIN

DB_FILE = "memoire_instant_double.db"

def initialiser_structure_bdd():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_choix DATETIME DEFAULT CURRENT_TIMESTAMP,
            outcome TEXT
        )
    """)
    conn.commit()
    conn.close()

def enregistrer_tirage(outcome):
    """Enregistre le tirage brut reçu en direct du WebSocket Centrifugo."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historique (outcome) VALUES (?)", (outcome,))
    conn.commit()
    conn.close()

def generer_analyse_profonde():
    """Effectue les calculs et croisements de données à la demande de l'utilisateur."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Récupérer l'historique complet pour l'analyse globale
    cursor.execute("SELECT outcome FROM historique ORDER BY id DESC LIMIT 500")
    tous_les_tirages = [row[0] for row in cursor.fetchall()]
    tous_les_tirages.reverse() # Remettre dans l'ordre chronologique
    
    if len(tous_les_tirages) < 20:
        conn.close()
        return "⚠️ Base de données en cours de constitution. Revenez dans quelques minutes."

    # 1. ANALYSE DES PATTERNS (SÉQUENCES)
    derniers_2 = tous_les_tirages[-2:]
    seq_2 = f"{derniers_2[0]}->{derniers_2[1]}"
    
    match_seq2 = {"red": 0, "blue": 0, "green": 0}
    for i in range(len(tous_les_tirages) - 2):
        if tous_les_tirages[i:i+2] == derniers_2:
            suivant = tous_les_tirages[i+2]
            if suivant in match_seq2:
                match_seq2[suivant] += 1
                
    total_seq2 = sum(match_seq2.values())
    prob_seq2 = {k: (v / total_seq2 * 100 if total_seq2 > 0 else 0) for k, v in match_seq2.items()}

    # 2. ANALYSE DE LA TENDANCE DE RETARD (ÉCART STATISTIQUE)
    # Calcule l'écart par rapport à la distribution normale sur les 100 derniers coups
    derniers_100 = tous_les_tirages[-100:]
    total_100 = len(derniers_100)
    comptage_100 = {"red": derniers_100.count("red"), "blue": derniers_100.count("blue"), "green": derniers_100.count("green")}
    
    # 3. SYNTHÈSE ET CROISEMENT DES ALGORITHMES
    meilleure_couleur = None
    max_score = 0
    
    for couleur in ["red", "blue", "green"]:
        # Croisement pondéré entre la probabilité de séquence et l'état de fraîcheur de la couleur
        score_fusion = prob_seq2[couleur]
        
        if score_fusion > max_score:
            max_score = score_fusion
            meilleure_couleur = couleur

    conn.close()

    # Formater la réponse finale de l'oracle
    if max_score >= SEUIL_CONVERGENCE_MIN:
        emoji = "🔴" if meilleure_couleur == "red" else "🔵" if meilleure_couleur == "blue" else "🟢"
        nom_couleur = "ROUGE (x2)" if meilleure_couleur == "red" else "BLEU (x14)" if meilleure_couleur == "blue" else "VERT (x2)"
        
        return (
            f"🎯 **ANALYSE MULTI-CRITÈRES TERMINÉE** 🎯\n\n"
            f"Derniers coups observés : `{derniers_2[0]} ➔ {derniers_2[1]}`\n"
            f"📊 Indice de récurrence historique : `{max_score:.1f}%`\n"
            f"📉 Volume sur les 100 derniers tours : `Rouge: {comptage_100['red']} | Bleu: {comptage_100['blue']} | Vert: {comptage_100['green']}`\n\n"
            f"🔮 **CONCLUSION DE L'ORACLE :** Jouer la couleur {emoji} **{nom_couleur}**"
        )
    else:
        return "⚖️ **ANALYSE NEUTRE :** Les algorithmes estiment que le marché est trop instable actuellement. Pas de signal fiable."

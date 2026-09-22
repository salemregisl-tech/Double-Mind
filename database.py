# database.py
import sqlite3
from config import SEUIL_ECHANTILLON_MIN, SEUIL_PROBABILITE_ALERTE

DB_FILE = "memoire_instant_double.db"

def initialiser_structure_bdd():
    """Crée les tables nécessaires si elles n'existent pas encore."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Stockage chronologique de chaque tirage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_choix DATETIME DEFAULT CURRENT_TIMESTAMP,
            outcome TEXT
        )
    """)
    
    # Stockage matriciel des enchaînements observés
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            sequence TEXT PRIMARY KEY,
            red INTEGER DEFAULT 0,
            blue INTEGER DEFAULT 0,
            green INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def traiter_resultat_et_predire(outcome):
    """Enregistre le tirage actuel et génère une prédiction pour la prochaine manche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Insertion du tirage brut
    cursor.execute("INSERT INTO historique (outcome) VALUES (?)", (outcome,))
    conn.commit()
    
    # 2. Extraction de la séquence pour l'apprentissage du bot
    cursor.execute("SELECT outcome FROM historique ORDER BY id DESC LIMIT 3")
    derniers_coups = [row[0] for row in cursor.fetchall()]
    derniers_coups.reverse()
    
    message_prediction = None
    
    if len(derniers_coups) == 3:
        av_dernier, dernier, actuel = derniers_coups[0], derniers_coups[1], derniers_coups[2]
        sequence_passee = f"{av_dernier}->{dernier}"
        
        # Initialisation ou mise à jour dynamique des compteurs de transition
        cursor.execute("INSERT OR IGNORE INTO patterns (sequence) VALUES (?)", (sequence_passee,))
        
        # Sécurité pour s'assurer que la colonne existe bien
        if actuel in ["red", "blue", "green"]:
            cursor.execute(f"UPDATE patterns SET {actuel} = {actuel} + 1 WHERE sequence = ?", (sequence_passee,))
            conn.commit()
        
        # 3. Calcul analytique basé sur la suite actuelle
        suite_actuelle = f"{dernier}->{actuel}"
        cursor.execute("SELECT red, blue, green FROM patterns WHERE sequence = ?", (suite_actuelle,))
        row = cursor.fetchone()
        
        if row:
            red, blue, green = row[0], row[1], row[2]
            total = red + blue + green
            
            if total >= SEUIL_ECHANTILLON_MIN:
                stats = {"red": red, "blue": blue, "green": green}
                print(f"📊 [ANALYSE] Séquence [{suite_actuelle}] vue {total} fois. Vérification...")
                
                for couleur, nb in stats.items():
                    pourcentage = (nb / total) * 100
                    
                    # Déclenchement si le comportement passé dépasse notre seuil limite
                    if pourcentage >= SEUIL_PROBABILITE_ALERTE:
                        message_prediction = (
                            f"🔮 **PRÉDICTION PROCHAIN TOUR** 🔮\n"
                            f"La suite **[{suite_actuelle}]** s'est produite {total} fois par le passé.\n"
                            f"⚡ *Déduction statistique forte :*\n"
                            f"➡️ La couleur **{couleur.upper()}** est sortie dans **{pourcentage:.1f}%** des cas !\n"
                            f"⏱️ **Statut :** Misez avant le lancement du prochain jeu."
                        )
                        break
                        
    conn.close()
    return message_prediction

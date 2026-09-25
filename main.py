import asyncio
import json
import logging
import os

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

WS_URL = "wss://centrifugo-ws-mse.live.gamedev-tech.cc/connection/websocket"

async def test_websocket():

    logging.info("========================================")
    logging.info("🔌 TEST INSTANT DOUBLE")
    logging.info("========================================")
    logging.info("Connexion à Centrifugo...")

    try:
        async with websockets.connect(
            WS_URL,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=10,
        ) as ws:

            logging.info("✅ CONNEXION WEBSOCKET RÉUSSIE")

            # Test du protocole Centrifugo
            await ws.send(json.dumps({
                "id": 1,
                "connect": {}
            }))

            logging.info("📤 Requête CONNECT envoyée")

            while True:

                message = await ws.recv()

                logging.info("📥 MESSAGE REÇU")

                try:
                    data = json.loads(message)

                    # Affichage compact
                    print(json.dumps(data, ensure_ascii=False))

                    # Recherche du channel Instant Double
                    raw = json.dumps(data, ensure_ascii=False)

                    if "domains:roulette_double-93" in raw:
                        logging.info(
                            "🎯 CHANNEL INSTANT DOUBLE DÉTECTÉ"
                        )

                    # Recherche d'un résultat
                    if '"outcome"' in raw:
                        logging.info(
                            "🔥 OUTCOME DÉTECTÉ"
                        )

                        # Recherche automatique du résultat
                        def chercher_outcome(obj):
                            if isinstance(obj, dict):
                                if "outcome" in obj:
                                    return obj["outcome"]

                                for value in obj.values():
                                    result = chercher_outcome(value)
                                    if result is not None:
                                        return result

                            elif isinstance(obj, list):
                                for value in obj:
                                    result = chercher_outcome(value)
                                    if result is not None:
                                        return result

                            return None

                        outcome = chercher_outcome(data)

                        if outcome:
                            logging.info(
                                "🎲 RÉSULTAT : %s",
                                outcome.upper()
                            )

                except Exception as error:
                    logging.warning(
                        "Impossible d'analyser le message : %s",
                        error
                    )

    except Exception as error:

        logging.error(
            "❌ CONNEXION ÉCHOUÉE : %r",
            error
        )


async def main():
    await test_websocket()


if __name__ == "__main__":
    asyncio.run(main())

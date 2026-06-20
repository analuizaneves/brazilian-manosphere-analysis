"""
search_channels_details.py

Busca detalhes (snippet + statistics) de canais a partir de uma lista de
channelIds.

MUDANÇA em relação à versão original:
  - A API só aceita até 50 IDs por chamada. A versão original recebia
    `lista_canais` pronta (já vinha em chunks de 50 no notebook), mas não
    tinha essa garantia dentro da própria função. Agora a função SEMPRE
    fragmenta internamente em lotes de 50, então pode receber qualquer
    tamanho de lista com segurança.
  - Integração com QuotaManager (1 unidade por lote de até 50 IDs).
"""

import time
from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


def _chunks(lista, tamanho=50):
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


def search_channels(lista_canais, youtube, quota_manager=None, sleep_between_calls=0.05):
    """
    lista_canais: lista de channelIds (qualquer tamanho)
    Retorna (detalhes, completo) onde:
      - detalhes: dict {channelId: {title, subscriberCount, videoCount, viewCount}}
      - completo: True se todos os lotes foram processados, False se a
                  quota impediu processar algum lote
    """
    detalhes = {}
    lista_canais_unicos = list(dict.fromkeys(lista_canais))

    for lote in _chunks(lista_canais_unicos, 50):
        if quota_manager is not None and not quota_manager.can_spend(1):
            return detalhes, False

        try:
            request = youtube.channels().list(
                part="snippet,statistics",
                id=",".join(lote),
                maxResults=50,
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("channels.list", pages=1, note=f"{len(lote)} ids")

        except QuotaExceededError:
            return detalhes, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar detalhes de canais: {e}")
            continue

        for item in response.get("items", []):
            channel_id = item["id"]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            detalhes[channel_id] = {
                "channelId": channel_id,
                "channel_title": snippet.get("title"),
                "subscribers": int(stats["subscriberCount"]) if "subscriberCount" in stats else None,
                "video_count": int(stats["videoCount"]) if "videoCount" in stats else None,
                "view_count": int(stats["viewCount"]) if "viewCount" in stats else None,
            }

        time.sleep(sleep_between_calls)

    return detalhes, True

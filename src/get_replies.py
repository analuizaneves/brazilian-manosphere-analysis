"""
get_replies.py

Busca as respostas (replies) de um comentário, paginando se necessário,
até um limite máximo por thread (confirmado com o usuário: 20 replies/thread).

MUDANÇAS em relação à versão original:
  - Limite configurável de replies por thread (max_replies), evitando que
    threads muito populares (centenas de replies) consumam quota
    desproporcional.
  - Integração com QuotaManager (1 unidade por página de até 100 resultados).
  - Pequena otimização: só chama a API se o comentário pai tiver
    reply_count > 0 (isso é feito no nível do orquestrador, não aqui,
    mas a função aceita reply_count opcional para pular early caso seja 0).
"""

import time
from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


def get_all_replies(parent_id, video_id, youtube, quota_manager=None,
                     max_replies=20, known_reply_count=None, sleep_between_pages=0.05):
    """
    parent_id: ID do comentário top-level (pai)
    known_reply_count: se already conhecido (vem de commentThreads.list),
                        usado para pular a chamada quando for 0 - evita
                        gasto de quota desnecessário.

    Retorna (replies, completo): completo=False se a quota impediu
    terminar de coletar todas as replies deste comentário.
    """
    if known_reply_count is not None and known_reply_count == 0:
        return [], True

    replies = []
    next_page_token = None

    while len(replies) < max_replies:
        page_size = min(100, max_replies - len(replies))

        if quota_manager is not None and not quota_manager.can_spend(1):
            return replies, False

        try:
            request = youtube.comments().list(
                part="snippet",
                parentId=parent_id,
                maxResults=page_size,
                pageToken=next_page_token,
                textFormat="plainText",
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("comments.list", pages=1, note=f"parent={parent_id}")

        except QuotaExceededError:
            return replies, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar replies do comentário {parent_id}: {e}")
            return replies, False

        for item in response.get("items", []):
            snippet = item["snippet"]
            replies.append({
                "comment_id": item["id"],
                "parent_id": parent_id,
                "video_id": video_id,
                "author": snippet.get("authorDisplayName"),
                "text": snippet.get("textDisplay"),
                "likes": snippet.get("likeCount"),
                "published_at": snippet.get("publishedAt"),
                "is_reply": True,
            })
            if len(replies) >= max_replies:
                break

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            return replies, True

        time.sleep(sleep_between_pages)

    return replies, True

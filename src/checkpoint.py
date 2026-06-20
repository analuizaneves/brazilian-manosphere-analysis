"""
checkpoint.py

Sistema simples de checkpoint baseado em arquivos CSV/JSON em disco.
Cada etapa da coleta usa duas estruturas:
  - um CSV "de resultados" (append incremental, é o dado coletado em si)
  - um JSON "de progresso" (quais chaves/IDs já foram processados, para
    poder retomar exatamente de onde parou)

Isso permite interromper a coleta a qualquer momento (ex: quando a quota
acaba) e retomar no dia seguinte sem reprocessar nem perder dados.
"""

import json
import os
import pandas as pd


class ProgressTracker:
    """Controla quais chaves (ex: video_id, channel_id) já foram processadas
    em uma determinada etapa, persistindo em um arquivo JSON simples (set de IDs)."""

    def __init__(self, progress_file):
        self.progress_file = progress_file
        os.makedirs(os.path.dirname(progress_file) or ".", exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, "r", encoding="utf-8") as f:
                self.done = set(json.load(f))
        else:
            self.done = set()

    def _save(self):
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(sorted(self.done), f, ensure_ascii=False, indent=2)

    def is_done(self, key):
        return key in self.done

    def mark_done(self, key):
        self.done.add(key)
        self._save()

    def mark_many_done(self, keys):
        self.done.update(keys)
        self._save()

    def pending(self, all_keys):
        return [k for k in all_keys if k not in self.done]

    def __len__(self):
        return len(self.done)


def append_rows_csv(filepath, rows, dedup_col=None, dedup_cols=None):
    """
    Adiciona linhas (lista de dicts) a um CSV, criando-o se não existir.
    - dedup_col: nome de UMA coluna para deduplicar (mantém última ocorrência).
    - dedup_cols: lista de colunas para deduplicar por chave composta
      (ex: ["query", "id_video"]), útil quando uma única coluna não é
      uma chave natural (ex: o mesmo vídeo pode aparecer em duas queries
      diferentes legitimamente, então a chave é o par).
    """
    if not rows:
        return

    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    df_new = pd.DataFrame(rows)

    if os.path.exists(filepath):
        df_old = pd.read_csv(filepath)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new

    if dedup_cols:
        cols_presentes = [c for c in dedup_cols if c in df_all.columns]
        if cols_presentes:
            df_all = df_all.drop_duplicates(subset=cols_presentes, keep="last")
    elif dedup_col and dedup_col in df_all.columns:
        df_all = df_all.drop_duplicates(subset=[dedup_col], keep="last")

    df_all.to_csv(filepath, index=False)


def load_csv_or_empty(filepath, columns=None):
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return pd.DataFrame(columns=columns or [])

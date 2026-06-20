"""
quota_manager.py

Controla o consumo de quota diária da YouTube Data API v3, persistindo o
estado em disco para que o controle sobreviva a reinícios do kernel/notebook
e a execuções em dias diferentes.

Custos oficiais (unidades) usados neste projeto:
    search.list            -> 100 por página
    videos.list             -> 1 por chamada (até 50 ids)
    channels.list           -> 1 por chamada (até 50 ids)
    commentThreads.list      -> 1 por página (até 100 resultados)
    comments.list (replies) -> 1 por página (até 100 resultados)

Referência: https://developers.google.com/youtube/v3/determine_quota_cost
"""

import json
import os
from datetime import date, datetime

QUOTA_FILE_DEFAULT = "data/quota_state.json"

# Custos por tipo de chamada (ajuste aqui se a documentação mudar)
COSTS = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
    "commentThreads.list": 1,
    "comments.list": 1,
}


class QuotaExceededError(Exception):
    """Levantada quando uma chamada ultrapassaria o limite diário configurado."""
    pass


class QuotaManager:
    def __init__(self, daily_limit=10000, safety_margin=200, state_file=QUOTA_FILE_DEFAULT):
        """
        daily_limit: quota diária total do projeto no Google Cloud (padrão free tier = 10000)
        safety_margin: unidades reservadas que NUNCA serão gastas, para evitar
                       passar do limite por chamadas multi-página/erros de estimativa
        state_file: arquivo onde o estado (data + unidades usadas) é persistido
        """
        self.daily_limit = daily_limit
        self.safety_margin = safety_margin
        self.state_file = state_file
        self._load_state()

    def _load_state(self):
        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {"date": None, "used": 0, "log": []}

        today = str(date.today())
        if self.state.get("date") != today:
            # Novo dia -> reseta o contador (a quota do Google reseta à meia-noite Pacific Time,
            # então pode haver pequena defasagem; o safety_margin absorve isso)
            self.state = {"date": today, "used": 0, "log": []}
            self._save_state()

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    @property
    def used_today(self):
        self._load_state()  # garante que pega o estado mais atual (multi-processo/dias)
        return self.state["used"]

    @property
    def remaining_today(self):
        return max(0, self.daily_limit - self.safety_margin - self.used_today)

    def can_spend(self, units):
        return units <= self.remaining_today

    def register(self, call_type, pages=1, note=""):
        """
        Registra o custo de uma chamada (ou de várias páginas de uma chamada paginada).
        Lança QuotaExceededError ANTES de registrar, se isso ultrapassar o limite seguro.
        """
        unit_cost = COSTS.get(call_type)
        if unit_cost is None:
            raise ValueError(f"Tipo de chamada desconhecido: {call_type}")

        total_cost = unit_cost * pages

        if not self.can_spend(total_cost):
            raise QuotaExceededError(
                f"Operação '{call_type}' (custo {total_cost}) excederia a quota seguro do dia. "
                f"Usado hoje: {self.used_today}, restante seguro: {self.remaining_today}."
            )

        self.state["used"] += total_cost
        self.state["log"].append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "call_type": call_type,
            "pages": pages,
            "cost": total_cost,
            "note": note,
        })
        self._save_state()
        return total_cost

    def status(self):
        return {
            "date": self.state["date"],
            "used_today": self.used_today,
            "daily_limit": self.daily_limit,
            "safety_margin": self.safety_margin,
            "remaining_today": self.remaining_today,
        }

    def print_status(self):
        s = self.status()
        print(f"📊 Quota [{s['date']}]: {s['used_today']}/{s['daily_limit']} usadas "
              f"(margem de segurança: {s['safety_margin']}) "
              f"-> restante hoje (seguro): {s['remaining_today']}")

# projects/modulo2/utils.py

from datetime import date, datetime, timedelta
from typing import Tuple
import unicodedata
import re

def obter_periodo_mes_atual() -> Tuple[date, date]:
    """
    Retorna o período do mês atual: primeiro dia do mês até hoje.
    
    Returns:
        Tuple[data_inicio, data_fim]
    """
    hoje = date.today()
    primeiro_dia_mes = date(hoje.year, hoje.month, 1)
    return primeiro_dia_mes, hoje


def obter_periodo_ano_atual() -> Tuple[date, date]:
    """
    Retorna o período do ano atual: primeiro dia do ano até hoje.
    Usado para importação inicial (Dia 0).
    
    Returns:
        Tuple[data_inicio, data_fim]
    """
    hoje = date.today()
    primeiro_dia_ano = date(hoje.year, 1, 1)
    return primeiro_dia_ano, hoje


def obter_periodo_dia_anterior() -> Tuple[date, date]:
    """
    Retorna o período do dia anterior (usado no agendamento diário às 00:00).
    
    Returns:
        Tuple[data_inicio, data_fim] - ambos são o dia anterior
    """
    ontem = date.today() - timedelta(days=1)
    return ontem, ontem


def normalizar_leve(txt) -> str:
    """
    Normalização leve: remove acentos e converte para maiúsculas.
    Mantém espaços e pontuação.
    """
    if txt is None:
        return ""
    txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.upper().strip()


def normalizar_forte(txt) -> str:
    """
    Normalização forte: remove acentos, converte para maiúsculas
    e remove toda pontuação e espaços.
    """
    if txt is None:
        return ""
    txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"[^A-Z0-9]", "", txt.upper())
    return txt

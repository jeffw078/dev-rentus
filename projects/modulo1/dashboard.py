from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates


# ============================================================
# Router (Módulo 1)
#   - GET  /modulo1/dashboard  -> HTML
#   - POST /modulo1/analyze    -> JSON (para o front)
# ============================================================
router = APIRouter(prefix="/modulo1", tags=["modulo1-dashboard"])

# templates em: <PROJECT_ROOT>/app/templates
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ============================================================
# Logs simples (aparecem no console do Uvicorn)
# ============================================================
def _log(msg: str) -> None:
    print(f"[INFO] {msg}")


# ============================================================
# Normalização / parsing
# ============================================================
def _norm(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _to_float(x: Any) -> float:
    if pd.isna(x):
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    # pt-BR "1.234,56"
    if re.search(r"\d+\.\d+,\d+", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _parse_date_any(x: Any) -> Optional[pd.Timestamp]:
    if pd.isna(x):
        return None
    try:
        ts = pd.to_datetime(x, errors="coerce", dayfirst=True)
        if pd.isna(ts):
            return None
        return ts
    except Exception:
        return None


def _pick_col(cols: List[str], patterns: List[str]) -> Optional[str]:
    norm_map = {c: _norm(c) for c in cols}
    for pat in patterns:
        rx = re.compile(pat)
        for original, n in norm_map.items():
            if rx.search(n):
                return original
    return None


# ============================================================
# Load Excel
# ============================================================
def _load_excel(file_bytes: bytes) -> pd.DataFrame:
    bio = io.BytesIO(file_bytes)
    df = pd.read_excel(bio, sheet_name=0, engine="openpyxl")
    df = df.dropna(how="all")
    return df


# ============================================================
# Core analysis (itens 1..5)
# ============================================================
def analyze_modulo1(df_raw: pd.DataFrame, dt_inicio: date, dt_fim: date, tolerancia: float) -> Dict[str, Any]:
    cols = list(df_raw.columns)

    # Colunas esperadas do arquivo do Módulo 1 (VR/VA/CESTA)
    re_col = _pick_col(cols, [r"^re$", r"matric", r"matricula", r"registro"]) or cols[0]
    nome_col = _pick_col(cols, [r"^nome$", r"colaborador", r"funcionario"])
    op_col = _pick_col(cols, [r"valor_op", r"valor_prev", r"esperado", r"ops"])
    ben_col = _pick_col(cols, [r"valor_benef", r"valor_pago", r"encontrado", r"beneficio"])
    dif_col = _pick_col(cols, [r"^diferenca$", r"dif"])
    alerta_col = _pick_col(cols, [r"alerta", r"motivo", r"observ"])
    demit_col = _pick_col(cols, [r"demit", r"deslig"])
    aviso_col = _pick_col(cols, [r"aviso"])
    situ_col = _pick_col(cols, [r"situacao", r"situa"])
    cargo_col = _pick_col(cols, [r"cargo", r"funcao"])
    escala_col = _pick_col(cols, [r"escala"])
    dias_col = _pick_col(cols, [r"qtd.*dias", r"dias_trab"])
    # Opcional (nem sempre vem)
    data_col = _pick_col(cols, [r"^data$", r"compet", r"periodo", r"pagamento", r"dt_"])

    # Monta DF padronizado
    df = pd.DataFrame()
    df["RE"] = df_raw[re_col].astype(str).str.strip()
    df["NOME"] = df_raw[nome_col].astype(str).str.strip() if nome_col else ""
    df["VALOR_OP"] = df_raw[op_col].apply(_to_float) if op_col else 0.0
    df["VALOR_BENEFICIO"] = df_raw[ben_col].apply(_to_float) if ben_col else 0.0

    if dif_col:
        df["DIF"] = df_raw[dif_col].apply(_to_float)
    else:
        df["DIF"] = df["VALOR_BENEFICIO"] - df["VALOR_OP"]

    df["ALERTA"] = df_raw[alerta_col].astype(str).fillna("").str.strip() if alerta_col else ""

    df["DEMITIDO"] = df_raw[demit_col].astype(str).fillna("").str.strip().str.upper() if demit_col else ""
    df["AVISO_PREVIO"] = df_raw[aviso_col].astype(str).fillna("").str.strip().str.upper() if aviso_col else ""
    df["SITUACAO"] = df_raw[situ_col].astype(str).fillna("").str.strip().str.upper() if situ_col else ""
    df["CARGO"] = df_raw[cargo_col].astype(str).fillna("").str.strip().str.upper() if cargo_col else "N/A"
    df["ESCALA"] = df_raw[escala_col].astype(str).fillna("").str.strip().str.upper() if escala_col else "N/A"
    df["DIAS_TRAB"] = df_raw[dias_col].apply(_to_float) if dias_col else 0.0

    if data_col:
        df["DATA"] = df_raw[data_col].apply(_parse_date_any)
    else:
        df["DATA"] = pd.NaT

    # Filtro por data (se existir)
    start_ts = pd.Timestamp(dt_inicio)
    end_ts = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    filtro_aplicado = False
    if df["DATA"].notna().any():
        df_f = df[(df["DATA"] >= start_ts) & (df["DATA"] <= end_ts)].copy()
        filtro_aplicado = True
    else:
        df_f = df.copy()

    # 1) Indicadores financeiros principais
    total_esperado = float(df_f["VALOR_OP"].sum())
    total_pago = float(df_f["VALOR_BENEFICIO"].sum())
    dif_total = float(total_pago - total_esperado)
    dif_pct = float((dif_total / total_esperado) * 100.0) if total_esperado != 0 else 0.0

    diverg = df_f[df_f["DIF"].abs() > float(tolerancia)].copy()
    diverg = diverg.sort_values("DIF", key=lambda s: s.abs(), ascending=False)
    total_em_risco = float(diverg["DIF"].abs().sum())

    # 2) Pagamentos indevidos (alto risco)
    # heurísticas com o que o arquivo traz:
    # - demitido/aviso prévio != ATIVO e pago > 0
    # - situação contém AFAST (se existir) e pago > 0
    # - RE inválido (não numérico) e pago > 0
    cadastro_ok = df_f["RE"].str.match(r"^\d+$", na=False) & ~df_f["RE"].isin(["", "0", "000000", "NAN", "NONE"])
    df_f["CADASTRO_OK"] = cadastro_ok

    indevidos = df_f[
        (
            ((df_f["DEMITIDO"] != "") & (df_f["DEMITIDO"] != "ATIVO") & (df_f["VALOR_BENEFICIO"] > 0)) |
            ((df_f["AVISO_PREVIO"] != "") & (df_f["AVISO_PREVIO"] != "ATIVO") & (df_f["VALOR_BENEFICIO"] > 0)) |
            ((df_f["SITUACAO"].str.contains("AFAST", na=False)) & (df_f["VALOR_BENEFICIO"] > 0)) |
            ((~df_f["CADASTRO_OK"]) & (df_f["VALOR_BENEFICIO"] > 0))
        )
    ].copy()

    # 3) Divergências de valor (categorias)
    acima = diverg[diverg["DIF"] > 0].copy()
    abaixo = diverg[diverg["DIF"] < 0].copy()
    zerado_indevido = df_f[(df_f["VALOR_OP"] > 0) & (df_f["VALOR_BENEFICIO"] == 0)].copy()

    # duplicidade: RE repetido (ou RE+valor)
    dup_re = df_f[df_f.duplicated(["RE"], keep=False)].copy()
    dup_re = dup_re.sort_values(["RE", "VALOR_BENEFICIO"], ascending=[True, False])

    # 4) Faltantes / omissões
    # - elegível (OP>0) e pago = 0
    faltantes = zerado_indevido.copy()

    # - ativos sem cadastro (se demit/aviso vierem como ATIVO, mas RE inválido)
    ativos_sem_cadastro = df_f[(~df_f["CADASTRO_OK"]) & (df_f["VALOR_OP"] > 0)].copy()

    # 5) Concentração de erros (estratégico)
    # por cargo, escala, situação
    conc_cargo = diverg.groupby("CARGO", dropna=False).agg(
        qtd=("RE", "count"),
        valor=("DIF", lambda s: float(s.abs().sum()))
    ).reset_index().sort_values("valor", ascending=False).head(12)

    conc_escala = diverg.groupby("ESCALA", dropna=False).agg(
        qtd=("RE", "count"),
        valor=("DIF", lambda s: float(s.abs().sum()))
    ).reset_index().sort_values("valor", ascending=False).head(12)

    conc_situacao = diverg.groupby("SITUACAO", dropna=False).agg(
        qtd=("RE", "count"),
        valor=("DIF", lambda s: float(s.abs().sum()))
    ).reset_index().sort_values("valor", ascending=False).head(12)

    # Helpers de saída
    def row_to_dict(r: pd.Series) -> Dict[str, Any]:
        dtv = r.get("DATA")
        return {
            "re": str(r.get("RE", "")),
            "nome": str(r.get("NOME", "")),
            "valor_op": float(r.get("VALOR_OP", 0.0)),
            "valor_beneficio": float(r.get("VALOR_BENEFICIO", 0.0)),
            "dif": float(r.get("DIF", 0.0)),
            "alerta": str(r.get("ALERTA", "")),
            "demitido": str(r.get("DEMITIDO", "")),
            "aviso_previo": str(r.get("AVISO_PREVIO", "")),
            "situacao": str(r.get("SITUACAO", "")),
            "cargo": str(r.get("CARGO", "")),
            "escala": str(r.get("ESCALA", "")),
            "dias_trab": float(r.get("DIAS_TRAB", 0.0)),
            "data": (dtv.date().isoformat() if pd.notna(dtv) else ""),
            "cadastro_ok": bool(r.get("CADASTRO_OK", True)),
        }

    return {
        "meta": {
            "arquivo": "modulo1",
            "periodo": {"inicio": dt_inicio.isoformat(), "fim": dt_fim.isoformat()},
            "tolerancia": float(tolerancia),
            "filtro_data_aplicado": filtro_aplicado,
            "colunas_detectadas": {
                "re": re_col, "nome": nome_col, "valor_op": op_col, "valor_beneficio": ben_col, "dif": dif_col,
                "alerta": alerta_col, "demitido": demit_col, "aviso_previo": aviso_col, "situacao": situ_col,
                "cargo": cargo_col, "escala": escala_col, "dias_trab": dias_col, "data": data_col,
            },
            "linhas_total": int(len(df_raw)),
            "linhas_periodo": int(len(df_f)),
        },

        # 1️⃣ Indicadores Financeiros Principais
        "kpis": {
            "total_esperado": total_esperado,
            "total_pago": total_pago,
            "dif_total": dif_total,
            "dif_pct": dif_pct,
            "total_em_risco": total_em_risco,
            "divergencias_count": int(len(diverg)),
        },

        # 2️⃣ Pagamentos Indevidos
        "pagamentos_indevidos": [row_to_dict(r) for _, r in indevidos.head(500).iterrows()],

        # 3️⃣ Divergências de Valor
        "divergencias": [row_to_dict(r) for _, r in diverg.head(1000).iterrows()],
        "divergencias_acima": [row_to_dict(r) for _, r in acima.head(500).iterrows()],
        "divergencias_abaixo": [row_to_dict(r) for _, r in abaixo.head(500).iterrows()],
        "zerado_indevido": [row_to_dict(r) for _, r in zerado_indevido.head(500).iterrows()],
        "duplicidades_re": [row_to_dict(r) for _, r in dup_re.head(500).iterrows()],

        # 4️⃣ Faltantes e Omissões
        "faltantes": [row_to_dict(r) for _, r in faltantes.head(1000).iterrows()],
        "ativos_sem_cadastro": [row_to_dict(r) for _, r in ativos_sem_cadastro.head(500).iterrows()],

        # 5️⃣ Concentração de Erros
        "concentracao": {
            "por_cargo": [{"chave": str(x["CARGO"]), "qtd": int(x["qtd"]), "valor": float(x["valor"])} for _, x in conc_cargo.iterrows()],
            "por_escala": [{"chave": str(x["ESCALA"]), "qtd": int(x["qtd"]), "valor": float(x["valor"])} for _, x in conc_escala.iterrows()],
            "por_situacao": [{"chave": str(x["SITUACAO"]), "qtd": int(x["qtd"]), "valor": float(x["valor"])} for _, x in conc_situacao.iterrows()],
        },
    }


# ============================================================
# Routes
# ============================================================
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    # template esperado: app/templates/dashboard_modulo1.html
    return templates.TemplateResponse("dashboard_modulo1.html", {"request": request})


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    dt_inicio: str = Form(...),
    dt_fim: str = Form(...),
    tolerancia: float = Form(0.5),
):
    _log("Iniciando análise do módulo 1")
    _log(f"Arquivo recebido: {file.filename}")

    try:
        dti = datetime.fromisoformat(dt_inicio).date()
        dtf = datetime.fromisoformat(dt_fim).date()
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Datas inválidas: {e}"}, status_code=422)

    if dtf < dti:
        return JSONResponse({"success": False, "error": "Data fim menor que data início"}, status_code=422)

    tolerancia = max(0.0, float(tolerancia))

    _log(f"Período: {dti.isoformat()} até {dtf.isoformat()}")
    _log(f"Tolerância: {tolerancia}")

    content = await file.read()
    df_raw = _load_excel(content)

    _log(f"Total linhas: {len(df_raw)}")

    try:
        result = analyze_modulo1(df_raw, dti, dtf, tolerancia)
        _log(f"Divergências encontradas: {result['kpis']['divergencias_count']}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log("Erro na análise:")
        _log(tb)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

import traceback
from datetime import datetime
from pathlib import Path
import importlib

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projects.modulo1.Modulo1 import process_modulo1


# ============================================================
# CONFIG DE PASTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

for d in [UPLOAD_DIR, OUTPUT_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(title="Rentus Analyzer", version="1.0")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ============================================================
# LOGGER
# ============================================================

def create_logger(prefix: str, run_id: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"log-{date_str}-{prefix}-{run_id}.txt"

    def write(msg: str):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def logger(msg: str):
        print(msg)
        write(msg)

    return logger


# ============================================================
# ROTAS HTML
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def modulo16_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/mapping", response_class=HTMLResponse)
async def modulo16_page(request: Request):
    return templates.TemplateResponse("mapping.html", {"request": request})


@app.get("/modulo1", response_class=HTMLResponse)
async def modulo1_page(request: Request):
    return templates.TemplateResponse("modulo1.html", {"request": request})

@app.get("/modulo2", response_class=HTMLResponse)
async def modulo2_page(request: Request):
    return templates.TemplateResponse("modulo2.html", {"request": request})


@app.get("/modulo3", response_class=HTMLResponse)
async def modulo3_page(request: Request):
    return templates.TemplateResponse("modulo3.html", {"request": request})


@app.get("/modulo4", response_class=HTMLResponse)
async def modulo4_page(request: Request):
    return templates.TemplateResponse("modulo4.html", {"request": request})


@app.get("/modulo5", response_class=HTMLResponse)
async def modulo5_page(request: Request):
    return templates.TemplateResponse("modulo5.html", {"request": request})


@app.get("/modulo6", response_class=HTMLResponse)
async def modulo6_page(request: Request):
    return templates.TemplateResponse("modulo6.html", {"request": request})


@app.get("/modulo7", response_class=HTMLResponse)
async def modulo7_page(request: Request):
    return templates.TemplateResponse("modulo7.html", {"request": request})


@app.get("/modulo8", response_class=HTMLResponse)
async def modulo8_page(request: Request):
    return templates.TemplateResponse("modulo8.html", {"request": request})


@app.get("/modulo9", response_class=HTMLResponse)
async def modulo9_page(request: Request):
    return templates.TemplateResponse("modulo9.html", {"request": request})


@app.get("/modulo10", response_class=HTMLResponse)
async def modulo10_page(request: Request):
    return templates.TemplateResponse("modulo10.html", {"request": request})


@app.get("/modulo11", response_class=HTMLResponse)
async def modulo11_page(request: Request):
    return templates.TemplateResponse("modulo11.html", {"request": request})


@app.get("/modulo12", response_class=HTMLResponse)
async def modulo12_page(request: Request):
    return templates.TemplateResponse("modulo12.html", {"request": request})


@app.get("/modulo13", response_class=HTMLResponse)
async def modulo13_page(request: Request):
    return templates.TemplateResponse("modulo13.html", {"request": request})


@app.get("/modulo14", response_class=HTMLResponse)
async def modulo14_page(request: Request):
    return templates.TemplateResponse("modulo14.html", {"request": request})


@app.get("/modulo15", response_class=HTMLResponse)
async def modulo15_page(request: Request):
    return templates.TemplateResponse("modulo15.html", {"request": request})


@app.get("/modulo16", response_class=HTMLResponse)
async def modulo16_page(request: Request):
    return templates.TemplateResponse("modulo16.html", {"request": request})





# ============================================================
# PROCESSAMENTO — MÓDULO 1
# ============================================================

@app.post("/modulo1/process")
async def modulo1_process(
    OPS: UploadFile = File(...),
    demitidos: UploadFile = File(...),
    AVISO_PREVIO: UploadFile = File(...),
    hk_avulso: UploadFile = File(...),
    fp: UploadFile = File(...),
    situacao: UploadFile = File(...)
):
    run_id = datetime.now().strftime("%H%M%S")
    logger = create_logger("modulo1", run_id)

    try:
        logger("[INFO] Iniciando processamento — Módulo 1")

        # Função interna para salvar arquivos
        def save(upload: UploadFile, name: str):
            dest = UPLOAD_DIR / name
            with open(dest, "wb") as f:
                f.write(upload.file.read())
            logger(f"[INFO] Arquivo salvo: {dest}")
            return dest

        ops_path = save(OPS, "OPS.xlsx")
        dem_path = save(demitidos, "demitidos.xls")
        aviso_path = save(AVISO_PREVIO, "AVISO_PREVIO.xls")
        hk_path = save(hk_avulso, "hk_avulso.xlsx")
        fp_path = save(fp, "fp.xlsx")
        sit_path = save(situacao, "situacao.xlsx")

        # ===========================
        # AJUSTE AQUI (ÚNICO NECESSÁRIO)
        # ===========================
        output_file, logs = process_modulo1(
            ops_path=ops_path,
            hk_avulso_path=hk_path,
            demitidos_path=dem_path,
            aviso_previo_path=aviso_path,
            situacao_path=sit_path,
            fp_path=fp_path,
            output_dir=OUTPUT_DIR
        )

        return JSONResponse({
            "success": True,
            "download_url": f"/download/{output_file.name}"
        })

    except Exception as e:
        tb = traceback.format_exc()
        logger(tb)
        return JSONResponse({"success": False, "error": str(e)})


# ============================================================
# PROCESSAMENTO — FICHA PRESENÇA
# ============================================================

@app.post("/ficha/processar")
async def ficha_processar(file: UploadFile = File(...)):
    run_id = datetime.now().strftime("%H%M%S")
    logger = create_logger("ficha", run_id)

    try:
        logger("[INFO] Iniciando análise de Ficha Presença")

        input_path = UPLOAD_DIR / "FP_INPUT.xlsx"
        with open(input_path, "wb") as f:
            f.write(file.file.read())

        logger(f"[INFO] Arquivo salvo: {input_path}")

        try:
            import projects.LocalizaSituacao as loc
            importlib.reload(loc)
        except Exception:
            import projects.LocalizaSituacao as loc

        from projects.LocalizaSituacao import processar_ficha_presenca

        output_path = OUTPUT_DIR / "FP_resultado_clientes.xlsx"

        logger("[INFO] Executando processamento...")
        processar_ficha_presenca(str(input_path), str(output_path))

        return JSONResponse({
            "success": True,
            "download_url": f"/download/{output_path.name}"
        })

    except Exception as e:
        tb = traceback.format_exc()
        logger(tb)
        return JSONResponse({"success": False, "error": str(e)})


# ============================================================
# DOWNLOAD
# ============================================================

@app.get("/download/{filename}")
async def download(filename: str):
    file_path = OUTPUT_DIR / filename

    if not file_path.exists():
        return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

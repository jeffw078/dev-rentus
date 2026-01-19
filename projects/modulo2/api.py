# projects/modulo2/api.py

from fastapi import APIRouter, Query, HTTPException, Body
from datetime import date
from typing import Optional
from pydantic import BaseModel

from .config import DEV_MODE
from .service import (
    consultar_sefaz_quantidade,
    importar_xmls_sefaz,
    importar_xmls_inicial,
    importar_xmls_diario_automatico,
    listar_pendencias,
    listar_postos,
    listar_clientes,
    identificar_pendencia,
    listar_gastos_por_posto
)
from .preview import preview_importacao, preview_importacao_inicial
from .utils import obter_periodo_mes_atual
from .scheduler import get_scheduler

router = APIRouter(prefix="/api/modulo2", tags=["Modulo 2"])


# ================================
# MODELS
# ================================

class IdentificarPendenciaRequest(BaseModel):
    cliente_id: str
    posto_id: int


# ================================
# ROTAS
# ================================
# Nota: Rota raiz removida para evitar conflito com rota HTML /modulo2

@router.get("/status")
def get_status():
    """
    Retorna o status do módulo 2, incluindo se está em modo desenvolvimento.
    """
    return {
        "modulo": "modulo2",
        "dev_mode": DEV_MODE,
        "modo": "desenvolvimento" if DEV_MODE else "producao",
        "mensagem": "Dados mockados (sem SEFAZ real)" if DEV_MODE else "Consultando SEFAZ real"
    }


@router.get("/sefaz/consultar")
def consultar_sefaz(
    data_ini: date = Query(..., description="Data inicial do intervalo"),
    data_fim: date = Query(..., description="Data final do intervalo")
):
    """
    Consulta a SEFAZ para obter quantidade de XMLs disponíveis.
    Retorna quantidade estática por enquanto.
    """
    try:
        result = consultar_sefaz_quantidade(data_ini, data_fim)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sefaz/preview")
def preview_importacao_endpoint():
    """
    Preview da importação: mostra o que será importado sem importar de fato.
    Retorna quantidade de NFs, valor total e lista de fornecedores.
    Usa apenas XMLs novos via NSU incremental.
    """
    try:
        result = preview_importacao()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sefaz/importar")
def importar_xmls():
    """
    Importa XMLs do SEFAZ para o banco de dados.
    Usa NSU incremental automaticamente (apenas XMLs novos).
    Período: primeiro dia do mês atual até hoje (para referência, mas usa NSU).
    """
    try:
        # Usar período do mês atual (para referência, mas importa via NSU incremental)
        data_ini, data_fim = obter_periodo_mes_atual()
        result = importar_xmls_sefaz(data_ini, data_fim)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sefaz/preview-inicial")
def preview_importacao_inicial_endpoint():
    """
    Preview da importação inicial: mostra o que será importado sem importar de fato.
    Retorna quantidade de NFs, valor total e lista de fornecedores.
    Usa apenas XMLs novos via NSU incremental desde início do ano.
    """
    print(f"[API] /sefaz/preview-inicial - Requisicao recebida")
    try:
        print(f"[API] /sefaz/preview-inicial - Chamando preview_importacao_inicial()...")
        result = preview_importacao_inicial()
        print(f"[API] /sefaz/preview-inicial - Preview concluido com status: {result.get('status')}")
        return result
    except Exception as e:
        print(f"[API] /sefaz/preview-inicial - ERRO CRITICO: {type(e).__name__}: {e}")
        import traceback
        print("[API] Traceback completo:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@router.post("/sefaz/importacao-inicial")
def importacao_inicial():
    """
    Importação inicial (Dia 0): Importa todos os XMLs desde início do ano até hoje.
    Usa NSU incremental mas pode demorar várias horas dependendo do volume.
    Processa em lotes para evitar sobrecarga.
    """
    try:
        result = importar_xmls_inicial()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pendencias")
def pendencias(
    limit: int = Query(500, description="Limite de resultados"),
    data_ini: Optional[date] = Query(None, description="Data inicial do filtro (opcional)"),
    data_fim: Optional[date] = Query(None, description="Data final do filtro (opcional)")
):
    """
    Lista pendências de NFes que não foram identificadas automaticamente.
    Pode filtrar por data de emissão da NFe.
    """
    try:
        result = listar_pendencias(limit=limit, data_ini=data_ini, data_fim=data_fim)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pendencias/{pendencia_id}/identificar")
def identificar_pendencia_endpoint(
    pendencia_id: int,
    request: IdentificarPendenciaRequest = Body(...)
):
    """
    Identifica uma pendência associando cliente e posto de trabalho.
    Atualiza a NFe correspondente e marca a pendência como resolvida.
    """
    try:
        result = identificar_pendencia(
            pendencia_id=pendencia_id,
            cliente_id=request.cliente_id,
            posto_id=request.posto_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postos")
def postos():
    """
    Lista todos os postos de trabalho cadastrados.
    """
    try:
        result = listar_postos()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clientes")
def clientes():
    """
    Lista todos os clientes únicos cadastrados.
    """
    try:
        result = listar_clientes()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gastos-por-posto")
def gastos_por_posto(
    data_ini: Optional[date] = Query(None, description="Data inicial do filtro (opcional)"),
    data_fim: Optional[date] = Query(None, description="Data final do filtro (opcional)"),
    cliente: Optional[str] = Query(None, description="Filtrar por cliente específico (opcional)")
):
    """
    Lista gastos agregados por cliente para o gráfico.
    Retorna orçado, realizado e status (orçado - realizado) por cliente.
    Pode filtrar por data de emissão da NFe e por cliente específico.
    """
    try:
        from .service import listar_gastos_por_posto
        result = listar_gastos_por_posto(data_ini=data_ini, data_fim=data_fim, cliente_filtro=cliente)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/totais-gerais")
def totais_gerais(
    data_ini: Optional[date] = Query(None, description="Data inicial do filtro (opcional)"),
    data_fim: Optional[date] = Query(None, description="Data final do filtro (opcional)")
):
    """
    Retorna totais gerais para o dashboard: orçado total e realizado total.
    """
    try:
        from .db import get_conn, _row_to_dict
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Total orçado (soma de todos os postos)
        cur.execute("SELECT COALESCE(SUM(valor_orcado), 0) as total_orcado FROM modulo2_postos_trabalho")
        row = cur.fetchone()
        total_orcado = float(row[0]) if row else 0.0
        
        # Total realizado (soma das NFes no período)
        query = "SELECT COALESCE(SUM(valor_total), 0) as total_realizado FROM modulo2_nfe WHERE 1=1"
        params = []
        
        if data_ini:
            query += " AND data_emissao >= ?"
            params.append(str(data_ini))
        
        if data_fim:
            query += " AND data_emissao <= ?"
            params.append(str(data_fim))
        
        cur.execute(query, params)
        row = cur.fetchone()
        total_realizado = float(row[0]) if row else 0.0
        
        cur.close()
        conn.close()
        
        return {
            "total_orcado": total_orcado,
            "total_realizado": total_realizado,
            "status": total_orcado - total_realizado,
            "percentual": (total_realizado / total_orcado * 100) if total_orcado > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/status")
def scheduler_status():
    """
    Retorna status do agendador de importação automática.
    """
    try:
        scheduler = get_scheduler()
        return scheduler.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/reset-xmls")
def resetar_xmls_disponiveis():
    """
    Reseta o contador de XMLs disponíveis (após importação).
    """
    try:
        scheduler = get_scheduler()
        scheduler.xmls_disponiveis = 0
        return {"success": True, "mensagem": "Contador resetado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/importacoes/log")
def importacoes_log(
    limit: int = Query(10, description="Limite de resultados"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo: 'inicial', 'diaria', 'manual'")
):
    """
    Lista histórico de importações realizadas.
    """
    try:
        from .db import get_conn, _row_to_dict
        
        conn = get_conn()
        cur = conn.cursor()
        
        if tipo:
            query = """
                SELECT id, tipo, data_inicio, data_fim, total_xmls, xmls_processados,
                       xmls_identificados, xmls_pendentes, status, mensagem,
                       tempo_execucao_segundos, iniciado_em, concluido_em
                FROM modulo2_importacoes_log
                WHERE tipo = ?
                ORDER BY iniciado_em DESC
                LIMIT ?
            """
            cur.execute(query, (tipo, limit))
        else:
            query = """
                SELECT id, tipo, data_inicio, data_fim, total_xmls, xmls_processados,
                       xmls_identificados, xmls_pendentes, status, mensagem,
                       tempo_execucao_segundos, iniciado_em, concluido_em
                FROM modulo2_importacoes_log
                ORDER BY iniciado_em DESC
                LIMIT ?
            """
            cur.execute(query, (limit,))
        
        rows = cur.fetchall()
        result = []
        
        for row in rows:
            r = _row_to_dict(row)
            result.append({
                "id": r.get("id"),
                "tipo": r.get("tipo"),
                "data_inicio": r.get("data_inicio"),
                "data_fim": r.get("data_fim"),
                "total_xmls": r.get("total_xmls", 0),
                "xmls_processados": r.get("xmls_processados", 0),
                "xmls_identificados": r.get("xmls_identificados", 0),
                "xmls_pendentes": r.get("xmls_pendentes", 0),
                "status": r.get("status"),
                "mensagem": r.get("mensagem"),
                "tempo_segundos": r.get("tempo_execucao_segundos"),
                "iniciado_em": r.get("iniciado_em"),
                "concluido_em": r.get("concluido_em")
            })
        
        cur.close()
        conn.close()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PROGRESSO E ESTADO DA IMPORTAÇÃO
# ============================================

# Variável global para rastrear progresso (em memória)
import_progress = {
    "em_andamento": False,
    "processados": 0,
    "total": 0,
    "mensagem": ""
}

@router.get("/importacao/progresso")
def obter_progresso_importacao():
    """Retorna progresso da importação em andamento"""
    return import_progress


@router.get("/importacao/estado")
def verificar_estado_importacao():
    """Verifica se já houve importação (para ocultar botão)"""
    try:
        from .db import get_conn
        conn = get_conn()
        cursor = conn.cursor()
        
        # Verificar se há NFes no banco
        cursor.execute("SELECT COUNT(*) FROM modulo2_nfe")
        total_nfes = cursor.fetchone()[0]
        
        # Verificar NSUs
        cursor.execute("SELECT SUM(ultimo_nsu) FROM modulo2_nsu_checkpoint")
        soma_nsus = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        
        # Mostrar botão apenas se banco vazio OU NSUs zerados
        mostrar_botao = (total_nfes == 0) or (soma_nsus == 0 and total_nfes == 0)
        
        return {
            "mostrar_botao_inicial": mostrar_botao,
            "total_nfes": total_nfes,
            "soma_nsus": soma_nsus
        }
    except Exception as e:
        return {
            "mostrar_botao_inicial": True,  # Mostrar por padrão em caso de erro
            "erro": str(e)
        }


@router.get("/estatisticas/resumo")
def obter_estatisticas_resumo():
    """Retorna estatísticas para o popup final"""
    try:
        from .db import get_conn
        conn = get_conn()
        cursor = conn.cursor()
        
        # Total de NFes
        cursor.execute("SELECT COUNT(*) FROM modulo2_nfe")
        total_nfes = cursor.fetchone()[0]
        
        # Identificadas
        cursor.execute("SELECT COUNT(*) FROM modulo2_nfe WHERE status = 'identificado'")
        identificadas = cursor.fetchone()[0]
        
        # Pendentes
        cursor.execute("SELECT COUNT(*) FROM modulo2_pendencias")
        pendentes = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total": total_nfes,
            "identificadas": identificadas,
            "pendentes": pendentes,
            "percentual_identificacao": round((identificadas / total_nfes * 100) if total_nfes > 0 else 0, 1)
        }
    except Exception as e:
        return {
            "total": 0,
            "identificadas": 0,
            "pendentes": 0,
            "percentual_identificacao": 0,
            "erro": str(e)
        }


# ============================================
# ESTADO E ESTATÍSTICAS PARA INTERFACE
# ============================================

@router.get("/status/resumo")
def obter_status_resumo():
    """
    Retorna resumo do status para o tooltip de informação.
    Inclui última atualização, total importado, próxima importação.
    """
    try:
        from .db import get_conn, _row_to_dict
        from datetime import datetime
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Total de NFes
        cur.execute("SELECT COUNT(*) FROM modulo2_nfe")
        total_nfes = cur.fetchone()[0] or 0
        
        # Última importação (data mais recente de data_importacao)
        cur.execute("""
            SELECT data_importacao 
            FROM modulo2_nfe 
            ORDER BY data_importacao DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        ultima_importacao = row[0] if row else None
        
        # Formatar data
        ultima_importacao_formatada = ""
        if ultima_importacao:
            try:
                dt = datetime.fromisoformat(ultima_importacao.replace("Z", ""))
                ultima_importacao_formatada = dt.strftime("%d/%m/%Y %H:%M")
            except:
                ultima_importacao_formatada = ultima_importacao[:16] if len(ultima_importacao) >= 16 else ultima_importacao
        
        # Última importação - quantos XMLs nessa data
        cur.execute("""
            SELECT COUNT(*) FROM modulo2_nfe
            WHERE date(data_importacao) = (SELECT date(MAX(data_importacao)) FROM modulo2_nfe)
        """)
        xmls_ultima_importacao = cur.fetchone()[0] or 0
        
        # Pendências
        cur.execute("SELECT COUNT(*) FROM modulo2_pendencias WHERE status = 'pendente'")
        pendencias = cur.fetchone()[0] or 0
        
        # Identificadas
        cur.execute("SELECT COUNT(*) FROM modulo2_nfe WHERE status = 'identificado'")
        identificadas = cur.fetchone()[0] or 0
        
        # Próxima importação (sempre 00:01 do dia seguinte)
        hoje = datetime.now()
        proxima = hoje.replace(hour=0, minute=1, second=0, microsecond=0)
        if hoje.hour >= 0:
            from datetime import timedelta
            proxima = proxima + timedelta(days=1)
        proxima_formatada = proxima.strftime("%d/%m/%Y - %H:%M")
        
        cur.close()
        conn.close()
        
        return {
            "total_nfes": total_nfes,
            "ultima_importacao": ultima_importacao_formatada,
            "xmls_ultima_importacao": xmls_ultima_importacao,
            "proxima_importacao": proxima_formatada,
            "pendencias": pendencias,
            "identificadas": identificadas,
            "banco_vazio": total_nfes == 0
        }
        
    except Exception as e:
        return {
            "total_nfes": 0,
            "ultima_importacao": "",
            "xmls_ultima_importacao": 0,
            "proxima_importacao": "",
            "pendencias": 0,
            "identificadas": 0,
            "banco_vazio": True,
            "erro": str(e)
        }


@router.post("/resetar-para-importacao-inicial")
def resetar_para_importacao_inicial():
    """
    Reseta NSU de todas as empresas para 0 para permitir busca completa.
    ATENÇÃO: Não deleta NFes existentes (apenas reseta o checkpoint).
    Para buscar TODAS as XMLs desde 01/01/2026, os NSUs precisam estar em 0.
    """
    try:
        from .db import get_conn
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Resetar todos os NSU checkpoints para 0
        cur.execute("UPDATE modulo2_nsu_checkpoint SET ultimo_nsu = 0, atualizado_em = datetime('now')")
        
        # Verificar quantas empresas foram afetadas
        cur.execute("SELECT COUNT(*) FROM modulo2_nsu_checkpoint")
        total_empresas = cur.fetchone()[0] or 0
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "mensagem": f"NSU resetado para 0 em {total_empresas} empresa(s). Próxima consulta buscará desde o início.",
            "empresas_resetadas": total_empresas
        }
        
    except Exception as e:
        return {
            "success": False,
            "erro": str(e)
        }


@router.get("/sefaz/verificar-bloqueio")
def verificar_bloqueio_sefaz():
    """
    Verifica se há risco de bloqueio antes de iniciar importação.
    Faz uma consulta simples ao SEFAZ para verificar status.
    
    Retorna:
    - status: 'livre', 'risco' ou 'bloqueado'
    - pode_importar: True/False
    - mensagem: Explicação para o usuário
    - tempo_espera_minutos: Tempo sugerido de espera (se bloqueado)
    """
    try:
        from .db import get_empresas, get_ultimo_nsu
        from .rate_limiter import get_rate_limiter
        from datetime import datetime, timedelta
        
        # Verificar rate limiter
        rl = get_rate_limiter()
        
        # Verificar se houve muitas requisições recentes
        agora = datetime.now()
        requisicoes_ultima_hora = 0
        requisicoes_ultimo_minuto = 0
        
        for ts in rl.requests:
            diff = (agora - ts).total_seconds()
            if diff < 3600:  # Última hora
                requisicoes_ultima_hora += 1
            if diff < 60:  # Último minuto
                requisicoes_ultimo_minuto += 1
        
        # Limites de segurança
        LIMITE_HORA = 80  # SEFAZ limita ~100/hora
        LIMITE_MINUTO = 5  # SEFAZ limita ~20/min
        
        # Análise de risco
        if requisicoes_ultima_hora >= LIMITE_HORA:
            tempo_espera = 60 - int((agora - rl.requests[0]).total_seconds() / 60) if rl.requests else 60
            return {
                "status": "bloqueado",
                "pode_importar": False,
                "mensagem": f"Limite de requisições por hora atingido ({requisicoes_ultima_hora}/h). Aguarde {tempo_espera} minutos.",
                "tempo_espera_minutos": tempo_espera,
                "detalhes": {
                    "requisicoes_hora": requisicoes_ultima_hora,
                    "requisicoes_minuto": requisicoes_ultimo_minuto,
                    "limite_hora": LIMITE_HORA,
                    "limite_minuto": LIMITE_MINUTO
                }
            }
        
        if requisicoes_ultimo_minuto >= LIMITE_MINUTO:
            return {
                "status": "risco",
                "pode_importar": False,
                "mensagem": f"Muitas requisições no último minuto ({requisicoes_ultimo_minuto}/min). Aguarde 1-2 minutos.",
                "tempo_espera_minutos": 2,
                "detalhes": {
                    "requisicoes_hora": requisicoes_ultima_hora,
                    "requisicoes_minuto": requisicoes_ultimo_minuto,
                    "limite_hora": LIMITE_HORA,
                    "limite_minuto": LIMITE_MINUTO
                }
            }
        
        # Verificar se há empresas configuradas
        empresas = get_empresas()
        if not empresas:
            return {
                "status": "erro",
                "pode_importar": False,
                "mensagem": "Nenhuma empresa configurada. Verifique certificados/empresas.json",
                "tempo_espera_minutos": 0
            }
        
        # Tudo OK - pode importar
        return {
            "status": "livre",
            "pode_importar": True,
            "mensagem": f"Sistema pronto para importação. {len(empresas)} empresa(s) configurada(s).",
            "tempo_espera_minutos": 0,
            "detalhes": {
                "requisicoes_hora": requisicoes_ultima_hora,
                "requisicoes_minuto": requisicoes_ultimo_minuto,
                "limite_hora": LIMITE_HORA,
                "limite_minuto": LIMITE_MINUTO,
                "empresas": len(empresas)
            }
        }
        
    except Exception as e:
        return {
            "status": "erro",
            "pode_importar": False,
            "mensagem": f"Erro ao verificar status: {str(e)}",
            "tempo_espera_minutos": 5
        }


# ============================================
# EXPORTAÇÃO EXCEL
# ============================================

@router.get("/exportar/excel")
def exportar_nfes_excel_endpoint(
    data_inicio: Optional[date] = Query(None, description="Data inicial (padrão: 01/01/2026)"),
    data_fim: Optional[date] = Query(None, description="Data final (padrão: hoje)"),
    apenas_pendentes: bool = Query(False, description="Exportar apenas NFes pendentes")
):
    """
    Exporta todas as NFes para um arquivo Excel.
    
    Campos incluídos:
    - Chave da NF, Número da NF, NSU vinculado, Data da NF
    - Fornecedor, Valor da NF, Impostos (ICMS, IPI, PIS, COFINS)
    - Informações de destinatário, Informações complementares
    - Status (identificada ou não), Motivo (se não identificada)
    
    Retorna o caminho do arquivo gerado.
    """
    try:
        from .service import exportar_nfes_excel
        
        caminho = exportar_nfes_excel(
            data_inicio=data_inicio,
            data_fim=data_fim,
            apenas_pendentes=apenas_pendentes
        )
        
        return {
            "status": "ok",
            "arquivo": caminho,
            "mensagem": "Arquivo Excel gerado com sucesso"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exportar/download/{filename}")
def download_excel(filename: str):
    """
    Faz download do arquivo Excel gerado.
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    output_dir = Path(__file__).parent / "output"
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/exportar/lista")
def listar_arquivos_exportados():
    """
    Lista arquivos Excel exportados disponíveis para download.
    """
    from pathlib import Path
    import os
    
    output_dir = Path(__file__).parent / "output"
    
    if not output_dir.exists():
        return {"arquivos": []}
    
    arquivos = []
    for f in output_dir.glob("*.xlsx"):
        stat = f.stat()
        arquivos.append({
            "nome": f.name,
            "tamanho_bytes": stat.st_size,
            "tamanho_formatado": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024 * 1024 else f"{stat.st_size / 1024 / 1024:.1f} MB",
            "criado_em": os.path.getctime(f),
            "download_url": f"/api/modulo2/exportar/download/{f.name}"
        })
    
    # Ordenar por data (mais recente primeiro)
    arquivos.sort(key=lambda x: x["criado_em"], reverse=True)
    
    return {"arquivos": arquivos}

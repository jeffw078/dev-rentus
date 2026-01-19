# auth/audit_log.py
# Sistema de logs e auditoria

from typing import Optional
from datetime import datetime, timedelta
from .database import get_auth_conn
from .logger import log_error, log_info


def registrar_log(
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    acao: str = "",
    categoria: str = "",
    descricao: Optional[str] = None,
    modulo: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    dados_antes: Optional[str] = None,
    dados_depois: Optional[str] = None,
    sucesso: bool = True,
    erro_mensagem: Optional[str] = None
):
    """
    Registra uma ação no log de auditoria
    
    Categorias:
    - auth: autenticação (login, logout, etc)
    - usuarios: gestão de usuários
    - perfis: gestão de perfis
    - permissoes: alteração de permissões
    - modulos: acesso a módulos
    - dados: operações com dados (importação, exportação, etc)
    - configuracoes: alterações em configurações
    - sistema: eventos do sistema
    """
    conn = None
    try:
        conn = get_auth_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO audit_log (
                user_id, user_email, acao, categoria, descricao, modulo,
                ip_address, user_agent, dados_antes, dados_depois,
                sucesso, erro_mensagem
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, user_email, acao, categoria, descricao, modulo,
            ip_address, user_agent, dados_antes, dados_depois,
            sucesso, erro_mensagem
        ))
        
        conn.commit()
        cur.close()
        
    except Exception as e:
        log_error(f"AUDIT - Erro ao registrar log: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def listar_logs(
    user_id: Optional[int] = None,
    categoria: Optional[str] = None,
    acao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    apenas_falhas: bool = False,
    limit: int = 100,
    offset: int = 0
):
    """Lista logs de auditoria com filtros"""
    conn = None
    try:
        conn = get_auth_conn()
        cur = conn.cursor()
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if categoria:
            query += " AND categoria = ?"
            params.append(categoria)
        
        if acao:
            query += " AND acao = ?"
            params.append(acao)
        
        if data_inicio:
            query += " AND criado_em >= ?"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND criado_em <= ?"
            params.append(data_fim)
        
        if apenas_falhas:
            query += " AND sucesso = 0"
        
        query += " ORDER BY criado_em DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        logs = [dict(row) for row in rows]
        cur.close()
        
        return logs
        
    except Exception as e:
        log_error(f"AUDIT - Erro ao listar logs: {e}")
        return []
    finally:
        if conn:
            conn.close()


def limpar_logs_antigos(dias_retencao: int = 90):
    """Remove logs mais antigos que N dias"""
    conn = None
    try:
        conn = get_auth_conn()
        cur = conn.cursor()
        
        data_corte = (datetime.now() - timedelta(days=dias_retencao)).isoformat()
        
        cur.execute("DELETE FROM audit_log WHERE criado_em < ?", (data_corte,))
        linhas_deletadas = cur.rowcount
        
        conn.commit()
        cur.close()
        
        log_info(f"AUDIT - {linhas_deletadas} logs antigos removidos (> {dias_retencao} dias)")
        return linhas_deletadas
        
    except Exception as e:
        log_error(f"AUDIT - Erro ao limpar logs: {e}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()


def estatisticas_logs(data_inicio: Optional[str] = None, data_fim: Optional[str] = None):
    """Retorna estatísticas dos logs"""
    conn = None
    try:
        conn = get_auth_conn()
        cur = conn.cursor()
        
        query_base = "SELECT COUNT(*) as total FROM audit_log WHERE 1=1"
        params = []
        
        if data_inicio:
            query_base += " AND criado_em >= ?"
            params.append(data_inicio)
        
        if data_fim:
            query_base += " AND criado_em <= ?"
            params.append(data_fim)
        
        # Total de logs
        cur.execute(query_base, params)
        total = cur.fetchone()[0]
        
        # Logs por categoria
        query = query_base.replace("COUNT(*) as total", "categoria, COUNT(*) as total")
        query += " GROUP BY categoria ORDER BY total DESC"
        cur.execute(query, params)
        por_categoria = [dict(row) for row in cur.fetchall()]
        
        # Logs por ação
        query = query_base.replace("COUNT(*) as total", "acao, COUNT(*) as total")
        query += " GROUP BY acao ORDER BY total DESC LIMIT 10"
        cur.execute(query, params)
        por_acao = [dict(row) for row in cur.fetchall()]
        
        # Falhas
        query_falhas = query_base + " AND sucesso = 0"
        cur.execute(query_falhas, params)
        total_falhas = cur.fetchone()[0]
        
        # Usuários mais ativos
        query = query_base.replace("COUNT(*) as total", "user_email, COUNT(*) as total")
        query += " AND user_email IS NOT NULL GROUP BY user_email ORDER BY total DESC LIMIT 10"
        cur.execute(query, params)
        usuarios_ativos = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        
        return {
            "total": total,
            "total_falhas": total_falhas,
            "por_categoria": por_categoria,
            "por_acao": por_acao,
            "usuarios_mais_ativos": usuarios_ativos
        }
        
    except Exception as e:
        log_error(f"AUDIT - Erro ao gerar estatísticas: {e}")
        return {}
    finally:
        if conn:
            conn.close()

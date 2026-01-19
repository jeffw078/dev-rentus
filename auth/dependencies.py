# auth/dependencies.py
# Dependencies para proteção de rotas FastAPI

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .service import AuthService
from .security import verificar_token, hash_token
from .database import get_auth_conn
from .audit_log import registrar_log


# Security scheme para JWT
security = HTTPBearer()


# ============================================================
# DEPENDÊNCIAS BÁSICAS
# ============================================================

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependência que valida o token JWT e retorna o usuário atual
    Usar em rotas protegidas: @app.get("/rota", dependencies=[Depends(get_current_user)])
    """
    token = credentials.credentials
    
    # Verificar token JWT
    payload = verificar_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
    
    # Buscar usuário
    user = AuthService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )
    
    # Verificar se sessão ainda é válida (apenas 1 sessão por vez)
    conn = get_auth_conn()
    cur = conn.cursor()
    
    token_hash_value = hash_token(token)
    cur.execute("""
        SELECT id, expira_em FROM sessoes_ativas 
        WHERE user_id = ? AND token_hash = ?
    """, (user_id, token_hash_value))
    
    sessao = cur.fetchone()
    cur.close()
    conn.close()
    
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Faça login novamente.",
        )
    
    # Verificar expiração
    from datetime import datetime
    expira_em = datetime.fromisoformat(sessao[1])
    if datetime.utcnow() > expira_em:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada. Faça login novamente.",
        )
    
    # Atualizar última atividade
    conn = get_auth_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sessoes_ativas 
        SET ultima_atividade = datetime('now')
        WHERE user_id = ?
    """, (user_id,))
    cur.execute("""
        UPDATE users
        SET ultima_atividade = datetime('now')
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    # Adicionar informações extras ao user
    user["ip_address"] = request.client.host if request.client else None
    user["user_agent"] = request.headers.get("user-agent")
    
    return user


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependência que verifica se o usuário está ativo
    """
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )
    return current_user


async def require_admin(
    current_user: dict = Depends(get_current_active_user)
) -> dict:
    """
    Dependência que exige que o usuário seja admin
    """
    if not current_user.get("is_admin"):
        registrar_log(
            user_id=current_user.get("id"),
            user_email=current_user.get("email"),
            acao="acesso_negado_admin",
            categoria="auth",
            descricao="Tentativa de acesso a área administrativa sem permissão",
            ip_address=current_user.get("ip_address"),
            sucesso=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user


# ============================================================
# VERIFICAÇÃO DE PERMISSÕES
# ============================================================

def require_permission(modulo_codigo: str, permissao_codigo: str):
    """
    Factory para criar dependência de verificação de permissão
    
    Uso:
    @app.get("/modulo2", dependencies=[Depends(require_permission("modulo2", "view"))])
    """
    async def _verificar_permissao(
        current_user: dict = Depends(get_current_active_user)
    ) -> dict:
        user_id = current_user.get("id")
        
        # Admin tem acesso a tudo
        if current_user.get("is_admin"):
            return current_user
        
        # Verificar permissão
        tem_permissao = AuthService.verificar_permissao(
            user_id=user_id,
            modulo_codigo=modulo_codigo,
            permissao_codigo=permissao_codigo
        )
        
        if not tem_permissao:
            registrar_log(
                user_id=user_id,
                user_email=current_user.get("email"),
                acao="acesso_negado",
                categoria="permissoes",
                descricao=f"Acesso negado ao módulo {modulo_codigo} (permissão {permissao_codigo})",
                modulo=modulo_codigo,
                ip_address=current_user.get("ip_address"),
                sucesso=False
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Você não tem permissão para acessar este recurso",
            )
        
        return current_user
    
    return _verificar_permissao


# ============================================================
# OPCIONAL: Extração do usuário sem exigir autenticação
# ============================================================

async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Retorna o usuário atual se autenticado, ou None se não autenticado
    Não lança exceção, útil para rotas que funcionam com ou sem auth
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verificar_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = AuthService.get_user_by_id(int(user_id))
        if user:
            user["ip_address"] = request.client.host if request.client else None
            user["user_agent"] = request.headers.get("user-agent")
        
        return user
    except:
        return None

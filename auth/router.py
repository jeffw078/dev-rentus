# auth/router.py
# Rotas da API de autenticação

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .models import (
    LoginRequest,
    LoginResponse,
    User,
    UserCreate,
    UserUpdate,
    UserSetPassword,
    UserChangePassword,
    UserResetPasswordRequest,
    UserResetPassword,
    Perfil,
    Modulo
)
from .service import AuthService
from .dependencies import (
    get_current_user,
    get_current_active_user,
    require_admin,
    require_permission
)
from .audit_log import registrar_log, listar_logs, estatisticas_logs
from .security import hash_senha, verificar_senha


router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================
# AUTENTICAÇÃO
# ============================================================

@router.post("/login")
async def login(request: Request, login_data: LoginRequest):
    """Realiza login e retorna token JWT"""
    ip_address = request.client.host if request.client else None
    
    result = AuthService.login(
        email=login_data.email,
        senha=login_data.senha,
        ip_address=ip_address
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )
    
    if "error" in result:
        # Erros específicos (bloqueio, inativo, senha incorreta, etc.)
        # Determinar status code apropriado
        if result["error"] == "bloqueado":
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_401_UNAUTHORIZED
        
        # Retornar JSON com estrutura clara
        return JSONResponse(
            status_code=status_code,
            content={
                "error": result["error"],
                "message": result["message"],
                "detail": result.get("detail", result["message"])
            }
        )
    
    # Login bem-sucedido - criar resposta com cookie
    response = JSONResponse(content=result)
    
    # Definir cookie com o token (httponly para segurança)
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,  # Não acessível via JavaScript (mais seguro)
        secure=False,   # True apenas em HTTPS (desenvolvimento = False)
        samesite="lax", # Proteção CSRF
        max_age=3600    # 1 hora (mesmo tempo do token JWT)
    )
    
    return response


@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_active_user)):
    """Realiza logout do usuário"""
    # Extrair token do header ou cookie
    token = None
    
    # Tentar header primeiro
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    
    # Se não tiver no header, tentar cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token não fornecido"
        )
    
    AuthService.logout(
        user_id=current_user["id"],
        token=token
    )
    
    # Criar resposta e remover cookie
    response = JSONResponse(content={"message": "Logout realizado com sucesso"})
    response.delete_cookie("access_token")
    
    return response


@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """Retorna informações do usuário logado"""
    return current_user


@router.get("/check-session")
async def check_session(current_user: dict = Depends(get_current_active_user)):
    """Verifica se a sessão ainda é válida"""
    return {
        "valid": True,
        "user_id": current_user["id"],
        "email": current_user["email"]
    }


# ============================================================
# GERENCIAMENTO DE SENHA
# ============================================================

@router.post("/change-password")
async def change_password(
    change_data: UserChangePassword,
    current_user: dict = Depends(get_current_active_user)
):
    """Permite usuário alterar sua própria senha"""
    from .database import get_auth_conn
    
    conn = get_auth_conn()
    cur = conn.cursor()
    
    try:
        # Buscar senha atual do usuário
        cur.execute("SELECT senha_hash FROM users WHERE id = ?", (current_user["id"],))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        senha_hash_atual = row[0]
        
        # Verificar senha atual
        if not verificar_senha(change_data.senha_atual, senha_hash_atual):
            registrar_log(
                user_id=current_user["id"],
                user_email=current_user["email"],
                acao="change_password_senha_incorreta",
                categoria="auth",
                descricao="Tentativa de troca de senha com senha atual incorreta",
                sucesso=False
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha atual incorreta"
            )
        
        # Atualizar senha
        nova_senha_hash = hash_senha(change_data.nova_senha)
        cur.execute("""
            UPDATE users 
            SET senha_hash = ?, deve_trocar_senha = 0, senha_temporaria = 0
            WHERE id = ?
        """, (nova_senha_hash, current_user["id"]))
        
        conn.commit()
        
        registrar_log(
            user_id=current_user["id"],
            user_email=current_user["email"],
            acao="change_password_sucesso",
            categoria="auth",
            descricao="Senha alterada com sucesso",
            sucesso=True
        )
        
        return {"message": "Senha alterada com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/set-password")
async def set_password(set_data: UserSetPassword):
    """Define senha via token de convite (primeiro acesso)"""
    from .database import get_auth_conn
    from .security import verificar_token_expirado
    
    conn = get_auth_conn()
    cur = conn.cursor()
    
    try:
        # Buscar usuário pelo token
        cur.execute("""
            SELECT id, email, token_convite_expira
            FROM users
            WHERE token_convite = ?
        """, (set_data.token,))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido"
            )
        
        user_id = row[0]
        email = row[1]
        token_expira = row[2]
        
        # Verificar expiração
        if verificar_token_expirado(token_expira):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token expirado. Solicite um novo convite ao administrador."
            )
        
        # Definir nova senha
        nova_senha_hash = hash_senha(set_data.nova_senha)
        cur.execute("""
            UPDATE users 
            SET senha_hash = ?,
                token_convite = NULL,
                token_convite_expira = NULL,
                senha_temporaria = 0,
                deve_trocar_senha = 0,
                is_active = 1
            WHERE id = ?
        """, (nova_senha_hash, user_id))
        
        conn.commit()
        
        registrar_log(
            user_id=user_id,
            user_email=email,
            acao="set_password_primeiro_acesso",
            categoria="auth",
            descricao="Senha definida com sucesso no primeiro acesso",
            sucesso=True
        )
        
        return {"message": "Senha definida com sucesso! Você já pode fazer login."}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/request-reset-password")
async def request_reset_password(reset_request: UserResetPasswordRequest):
    """Solicita reset de senha (envia email com link)"""
    from .database import get_auth_conn
    from .security import gerar_token_reset_senha
    
    conn = get_auth_conn()
    cur = conn.cursor()
    
    try:
        # Buscar usuário
        cur.execute("SELECT id FROM users WHERE email = ?", (reset_request.email,))
        row = cur.fetchone()
        
        # Sempre retornar sucesso (não revelar se email existe)
        if not row:
            return {"message": "Se o email estiver cadastrado, você receberá instruções para resetar a senha."}
        
        user_id = row[0]
        
        # Gerar token
        token, expira_em = gerar_token_reset_senha()
        
        # Salvar token
        cur.execute("""
            UPDATE users
            SET token_reset_senha = ?, token_reset_expira = ?
            WHERE id = ?
        """, (token, expira_em.isoformat(), user_id))
        
        conn.commit()
        
        # TODO: Enviar email com link
        # link_reset = f"https://seudominio.com/auth/reset-password?token={token}"
        
        registrar_log(
            user_id=user_id,
            user_email=reset_request.email,
            acao="request_reset_password",
            categoria="auth",
            descricao="Solicitação de reset de senha",
            sucesso=True
        )
        
        return {"message": "Se o email estiver cadastrado, você receberá instruções para resetar a senha."}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/reset-password")
async def reset_password(reset_data: UserResetPassword):
    """Reseta senha via token"""
    from .database import get_auth_conn
    from .security import verificar_token_expirado
    
    conn = get_auth_conn()
    cur = conn.cursor()
    
    try:
        # Buscar usuário pelo token
        cur.execute("""
            SELECT id, email, token_reset_expira
            FROM users
            WHERE token_reset_senha = ?
        """, (reset_data.token,))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido"
            )
        
        user_id = row[0]
        email = row[1]
        token_expira = row[2]
        
        # Verificar expiração
        if verificar_token_expirado(token_expira):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token expirado. Solicite um novo reset de senha."
            )
        
        # Atualizar senha
        nova_senha_hash = hash_senha(reset_data.nova_senha)
        cur.execute("""
            UPDATE users 
            SET senha_hash = ?,
                token_reset_senha = NULL,
                token_reset_expira = NULL,
                deve_trocar_senha = 0
            WHERE id = ?
        """, (nova_senha_hash, user_id))
        
        conn.commit()
        
        registrar_log(
            user_id=user_id,
            user_email=email,
            acao="reset_password_sucesso",
            categoria="auth",
            descricao="Senha resetada com sucesso",
            sucesso=True
        )
        
        return {"message": "Senha resetada com sucesso! Você já pode fazer login."}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


# ============================================================
# GERENCIAMENTO DE USUÁRIOS (Admin)
# ============================================================

@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(apenas_ativos: bool = False):
    """Lista todos os usuários (apenas admin)"""
    usuarios = AuthService.listar_usuarios(apenas_ativos=apenas_ativos)
    return usuarios


@router.post("/users", dependencies=[Depends(require_admin)])
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_admin)
):
    """Cria novo usuário (apenas admin)"""
    result = AuthService.criar_usuario(
        user_data=user_data,
        criado_por_id=current_user["id"]
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return result


@router.get("/users/{user_id}")
async def get_user(user_id: int, current_user: dict = Depends(get_current_active_user)):
    """Busca usuário por ID"""
    # Usuário pode ver próprio perfil, admin pode ver todos
    if not current_user["is_admin"] and current_user["id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )
    
    user = AuthService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    return user


# ============================================================
# MÓDULOS E PERMISSÕES
# ============================================================

@router.get("/my-modules")
async def get_my_modules(current_user: dict = Depends(get_current_active_user)):
    """Retorna módulos que o usuário tem acesso"""
    modulos = AuthService.listar_modulos_usuario(current_user["id"])
    return modulos


@router.get("/check-permission/{modulo_codigo}/{permissao_codigo}")
async def check_permission(
    modulo_codigo: str,
    permissao_codigo: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Verifica se usuário tem permissão específica"""
    tem_permissao = AuthService.verificar_permissao(
        user_id=current_user["id"],
        modulo_codigo=modulo_codigo,
        permissao_codigo=permissao_codigo
    )
    return {"has_permission": tem_permissao}


# ============================================================
# LOGS E AUDITORIA (Admin)
# ============================================================

@router.get("/audit-log", dependencies=[Depends(require_admin)])
async def get_audit_log(
    user_id: Optional[int] = None,
    categoria: Optional[str] = None,
    acao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    apenas_falhas: bool = False,
    limit: int = 100,
    offset: int = 0
):
    """Lista logs de auditoria (apenas admin)"""
    from datetime import datetime
    
    logs = listar_logs(
        user_id=user_id,
        categoria=categoria,
        acao=acao,
        data_inicio=data_inicio,
        data_fim=data_fim,
        apenas_falhas=apenas_falhas,
        limit=limit,
        offset=offset
    )
    
    # Formatar data/hora para cada log
    for log in logs:
        if log.get("criado_em"):
            try:
                # Parse ISO datetime
                dt = datetime.fromisoformat(log["criado_em"].replace("Z", "+00:00"))
                # Formatar como DD/MM/YYYY HH:MM:SS
                log["data_hora_formatada"] = dt.strftime("%d/%m/%Y %H:%M:%S")
                log["data_formatada"] = dt.strftime("%d/%m/%Y")
                log["hora_formatada"] = dt.strftime("%H:%M:%S")
            except:
                log["data_hora_formatada"] = log["criado_em"]
                log["data_formatada"] = log["criado_em"]
                log["hora_formatada"] = ""
    
    return logs


@router.get("/audit-log/stats", dependencies=[Depends(require_admin)])
async def get_audit_stats(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
):
    """Retorna estatísticas dos logs (apenas admin)"""
    stats = estatisticas_logs(data_inicio=data_inicio, data_fim=data_fim)
    return stats

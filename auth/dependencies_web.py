# auth/dependencies_web.py
# Dependencies para proteger rotas WEB (HTML)

from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from .service import AuthService
from .security import verificar_token


async def require_auth_web(request: Request):
    """
    Middleware para rotas web que exigem autenticação
    Redireciona para login se não autenticado
    """
    # Tentar extrair token do cookie ou header
    token = None
    
    # 1. Tentar cookie
    token = request.cookies.get("access_token")
    
    # 2. Tentar header Authorization
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    # 3. Sem token - redirecionar para login
    if not token:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # 4. Verificar token
    payload = verificar_token(token)
    if not payload:
        # Token inválido - redirecionar para login
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("access_token")
        return response
    
    # 5. Buscar usuário
    user_id = payload.get("sub")
    if not user_id:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    try:
        user_id = int(user_id)
    except:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    user = AuthService.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # Usuário autenticado - retornar dados do usuário
    return user


async def require_admin_web(request: Request):
    """
    Middleware para rotas web que exigem admin
    Redireciona para index se não for admin
    """
    user = await require_auth_web(request)
    
    # Se já retornou RedirectResponse, retornar
    if isinstance(user, RedirectResponse):
        return user
    
    # Verificar se é admin
    if not user.get("is_admin"):
        return RedirectResponse(url="/index", status_code=status.HTTP_302_FOUND)
    
    return user


async def get_current_user_web(request: Request) -> Optional[dict]:
    """
    Retorna usuário atual para templates (sem redirecionar se não autenticado)
    Útil para páginas que podem funcionar com ou sem auth
    """
    token = request.cookies.get("access_token")
    
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        return None
    
    payload = verificar_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_id = int(user_id)
    except:
        return None
    
    user = AuthService.get_user_by_id(user_id)
    return user if user and user.get("is_active") else None

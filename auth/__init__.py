# auth/__init__.py
# Sistema de Autenticação e Controle de Acesso - Rentus Analyzer

from .database import init_auth_db, get_auth_conn
from .models import User, UserCreate, UserUpdate, UserInDB
from .security import (
    verificar_senha,
    hash_senha,
    criar_token_acesso,
    verificar_token,
    gerar_token_convite,
    gerar_token_reset_senha
)
from .dependencies import (
    get_current_user,
    get_current_active_user,
    require_admin,
    require_permission
)
from .service import AuthService

__all__ = [
    "init_auth_db",
    "get_auth_conn",
    "User",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "verificar_senha",
    "hash_senha",
    "criar_token_acesso",
    "verificar_token",
    "gerar_token_convite",
    "gerar_token_reset_senha",
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_permission",
    "AuthService"
]

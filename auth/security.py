# auth/security.py
# Funções de segurança: hashing, JWT, tokens

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import os

# Configurações de segurança
SECRET_KEY = os.getenv("SECRET_KEY", "rentus-secret-key-change-in-production-123456789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hora
REFRESH_TOKEN_EXPIRE_DAYS = 7
INVITE_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_HOURS = 24

# Context para hashing de senhas (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# HASHING DE SENHAS
# ============================================================

def hash_senha(senha: str) -> str:
    """Gera hash bcrypt da senha"""
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    try:
        return pwd_context.verify(senha_plana, senha_hash)
    except Exception:
        return False


# ============================================================
# JWT TOKENS
# ============================================================

def criar_token_acesso(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Cria um token JWT de acesso"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verificar_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica e decodifica um token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def extrair_user_id_token(token: str) -> Optional[int]:
    """Extrai o user_id de um token JWT"""
    payload = verificar_token(token)
    if payload:
        return payload.get("sub")
    return None


# ============================================================
# TOKENS DE CONVITE E RESET
# ============================================================

def gerar_token_seguro() -> str:
    """Gera um token seguro aleatório"""
    return secrets.token_urlsafe(32)


def gerar_token_convite() -> tuple[str, datetime]:
    """Gera um token de convite e sua data de expiração"""
    token = gerar_token_seguro()
    expira_em = datetime.utcnow() + timedelta(days=INVITE_TOKEN_EXPIRE_DAYS)
    return token, expira_em


def gerar_token_reset_senha() -> tuple[str, datetime]:
    """Gera um token de reset de senha e sua data de expiração"""
    token = gerar_token_seguro()
    expira_em = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
    return token, expira_em


def verificar_token_expirado(data_expiracao: str) -> bool:
    """Verifica se um token está expirado"""
    try:
        expira_em = datetime.fromisoformat(data_expiracao.replace('Z', '+00:00'))
        return datetime.utcnow() > expira_em
    except:
        return True


# ============================================================
# VALIDAÇÃO DE SENHA
# ============================================================

def validar_complexidade_senha(senha: str) -> tuple[bool, str]:
    """
    Valida complexidade da senha
    Retorna: (is_valid, mensagem_erro)
    """
    import re
    
    if len(senha) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    
    if not re.search(r'[A-Z]', senha):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    
    if not re.search(r'[a-z]', senha):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    
    if not re.search(r'[0-9]', senha):
        return False, "Senha deve conter pelo menos um número"
    
    if not re.search(r'[@#$%&*!]', senha):
        return False, "Senha deve conter pelo menos um caractere especial (@#$%&*!)"
    
    return True, "Senha válida"


# ============================================================
# HASH DE TOKENS (para armazenar no banco)
# ============================================================

def hash_token(token: str) -> str:
    """Gera hash do token para armazenamento seguro"""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================
# GERAÇÃO DE SENHA TEMPORÁRIA
# ============================================================

def gerar_senha_temporaria() -> str:
    """Gera uma senha temporária segura"""
    import random
    import string
    
    # Garantir pelo menos um de cada requisito
    chars = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("@#$%&*!")
    ]
    
    # Completar com caracteres aleatórios
    all_chars = string.ascii_letters + string.digits + "@#$%&*!"
    chars.extend(random.choice(all_chars) for _ in range(8))
    
    # Embaralhar
    random.shuffle(chars)
    
    return ''.join(chars)

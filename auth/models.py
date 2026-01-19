# auth/models.py
# Modelos de dados Pydantic para autenticação

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
import re


# ============================================================
# USER MODELS
# ============================================================

class UserBase(BaseModel):
    email: EmailStr
    nome_completo: str = Field(..., min_length=3, max_length=200)
    departamento: Optional[str] = None
    cargo: Optional[str] = None
    perfil_principal: str = "operacional"


class UserCreate(UserBase):
    """Criação de usuário (admin cria sem senha, envia convite)"""
    perfis_adicionais: Optional[List[str]] = []
    enviar_convite: bool = True


class UserCreateWithPassword(UserBase):
    """Criação de usuário com senha (para seed/testes)"""
    senha: str = Field(..., min_length=8)
    perfis_adicionais: Optional[List[str]] = []
    deve_trocar_senha: bool = False
    
    @validator('senha')
    def validar_senha(cls, v):
        if len(v) < 8:
            raise ValueError('Senha deve ter no mínimo 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Senha deve conter pelo menos um número')
        if not re.search(r'[@#$%&*!]', v):
            raise ValueError('Senha deve conter pelo menos um caractere especial (@#$%&*!)')
        return v


class UserUpdate(BaseModel):
    """Atualização de usuário"""
    nome_completo: Optional[str] = None
    departamento: Optional[str] = None
    cargo: Optional[str] = None
    perfil_principal: Optional[str] = None
    perfis_adicionais: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserSetPassword(BaseModel):
    """Definir senha via token de convite"""
    token: str
    nova_senha: str = Field(..., min_length=8)
    confirmar_senha: str
    
    @validator('confirmar_senha')
    def senhas_devem_ser_iguais(cls, v, values):
        if 'nova_senha' in values and v != values['nova_senha']:
            raise ValueError('Senhas não conferem')
        return v
    
    @validator('nova_senha')
    def validar_senha(cls, v):
        if len(v) < 8:
            raise ValueError('Senha deve ter no mínimo 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Senha deve conter pelo menos um número')
        if not re.search(r'[@#$%&*!]', v):
            raise ValueError('Senha deve conter pelo menos um caractere especial (@#$%&*!)')
        return v


class UserChangePassword(BaseModel):
    """Alterar senha (usuário logado)"""
    senha_atual: str
    nova_senha: str = Field(..., min_length=8)
    confirmar_senha: str
    
    @validator('confirmar_senha')
    def senhas_devem_ser_iguais(cls, v, values):
        if 'nova_senha' in values and v != values['nova_senha']:
            raise ValueError('Senhas não conferem')
        return v
    
    @validator('nova_senha')
    def validar_senha(cls, v):
        if len(v) < 8:
            raise ValueError('Senha deve ter no mínimo 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Senha deve conter pelo menos um número')
        if not re.search(r'[@#$%&*!]', v):
            raise ValueError('Senha deve conter pelo menos um caractere especial (@#$%&*!)')
        return v


class UserResetPasswordRequest(BaseModel):
    """Solicitar reset de senha"""
    email: EmailStr


class UserResetPassword(BaseModel):
    """Resetar senha via token"""
    token: str
    nova_senha: str = Field(..., min_length=8)
    confirmar_senha: str
    
    @validator('confirmar_senha')
    def senhas_devem_ser_iguais(cls, v, values):
        if 'nova_senha' in values and v != values['nova_senha']:
            raise ValueError('Senhas não conferem')
        return v
    
    @validator('nova_senha')
    def validar_senha(cls, v):
        if len(v) < 8:
            raise ValueError('Senha deve ter no mínimo 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Senha deve conter pelo menos um número')
        if not re.search(r'[@#$%&*!]', v):
            raise ValueError('Senha deve conter pelo menos um caractere especial (@#$%&*!)')
        return v


class User(UserBase):
    """Usuário completo (resposta)"""
    id: int
    is_active: bool
    is_admin: bool
    deve_trocar_senha: bool
    perfis: List[str] = []
    criado_em: str
    ultimo_login: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """Usuário no banco (com senha hash)"""
    senha_hash: str


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
    deve_trocar_senha: bool


# ============================================================
# PERFIS
# ============================================================

class PerfilBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    nivel_hierarquia: int = 0
    cor_badge: str = "#6B7280"


class PerfilCreate(PerfilBase):
    pass


class PerfilUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    nivel_hierarquia: Optional[int] = None
    cor_badge: Optional[str] = None


class Perfil(PerfilBase):
    id: int
    criado_em: str
    
    class Config:
        from_attributes = True


# ============================================================
# MÓDULOS
# ============================================================

class ModuloBase(BaseModel):
    codigo: str
    nome: str
    descricao: Optional[str] = None
    icone: Optional[str] = None
    ordem: int = 0
    categoria: Optional[str] = None


class ModuloCreate(ModuloBase):
    pass


class ModuloUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    icone: Optional[str] = None
    ordem: Optional[int] = None
    is_active: Optional[bool] = None
    categoria: Optional[str] = None


class Modulo(ModuloBase):
    id: int
    is_active: bool
    criado_em: str
    
    class Config:
        from_attributes = True


# ============================================================
# PERMISSÕES
# ============================================================

class PermissaoBase(BaseModel):
    nome: str
    codigo: str
    descricao: Optional[str] = None


class Permissao(PermissaoBase):
    id: int
    criado_em: str
    
    class Config:
        from_attributes = True


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLogCreate(BaseModel):
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    acao: str
    categoria: str
    descricao: Optional[str] = None
    modulo: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    dados_antes: Optional[str] = None
    dados_depois: Optional[str] = None
    sucesso: bool = True
    erro_mensagem: Optional[str] = None


class AuditLog(AuditLogCreate):
    id: int
    criado_em: str
    
    class Config:
        from_attributes = True


# ============================================================
# PERMISSÕES POR PERFIL/MÓDULO
# ============================================================

class PerfilModuloPermissaoUpdate(BaseModel):
    """Atualizar permissões de um perfil em um módulo"""
    perfil_id: int
    modulo_id: int
    permissoes: List[int]  # Lista de IDs de permissões a conceder


class UserPermissaoCustomUpdate(BaseModel):
    """Atualizar permissões customizadas de um usuário"""
    user_id: int
    modulo_id: int
    permissoes: List[int]  # Lista de IDs de permissões a conceder
    motivo: Optional[str] = None
    expira_em: Optional[str] = None

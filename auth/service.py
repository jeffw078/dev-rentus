# auth/service.py
# Serviço de autenticação - Lógica de negócio

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import sqlite3

from .database import get_auth_conn
from .security import (
    hash_senha,
    verificar_senha,
    criar_token_acesso,
    gerar_token_convite,
    gerar_token_reset_senha,
    verificar_token_expirado,
    hash_token
)
from .models import (
    User,
    UserCreate,
    UserCreateWithPassword,
    UserUpdate,
    LoginRequest,
    UserInDB
)
from .audit_log import registrar_log


class AuthService:
    """Serviço de autenticação e gerenciamento de usuários"""
    
    # ========================================
    # AUTENTICAÇÃO
    # ========================================
    
    @staticmethod
    def login(email: str, senha: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Realiza login do usuário
        Retorna: dict com token e dados do usuário, ou None se falhar
        """
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            # Buscar usuário por email
            cur.execute("""
                SELECT id, email, nome_completo, senha_hash, perfil_principal,
                       is_active, is_admin, deve_trocar_senha, bloqueado_ate,
                       tentativas_login_falhas, departamento, cargo
                FROM users WHERE email = ?
            """, (email,))
            
            row = cur.fetchone()
            
            if not row:
                # Usuário não existe - registrar tentativa falha
                registrar_log(
                    user_email=email,
                    acao="login_falha",
                    categoria="auth",
                    descricao=f"Tentativa de login com email não cadastrado: {email}",
                    ip_address=ip_address,
                    sucesso=False
                )
                return {
                    "error": "credenciais_invalidas",
                    "message": "Email ou senha incorretos",
                    "detail": "Email ou senha incorretos"
                }
            
            user_dict = dict(row)
            user_id = user_dict["id"]
            
            # Verificar se está bloqueado
            if user_dict["bloqueado_ate"]:
                bloqueado_ate = datetime.fromisoformat(user_dict["bloqueado_ate"])
                if datetime.utcnow() < bloqueado_ate:
                    tempo_restante = (bloqueado_ate - datetime.utcnow()).total_seconds() / 60
                    registrar_log(
                        user_id=user_id,
                        user_email=email,
                        acao="login_bloqueado",
                        categoria="auth",
                        descricao=f"Tentativa de login com usuário bloqueado. Tempo restante: {tempo_restante:.1f} minutos",
                        ip_address=ip_address,
                        sucesso=False
                    )
                    mensagem_bloqueio = f"Usuário bloqueado por excesso de tentativas. Aguarde {tempo_restante:.0f} minutos."
                    return {
                        "error": "bloqueado",
                        "message": mensagem_bloqueio,
                        "detail": mensagem_bloqueio
                    }
                else:
                    # Bloqueio expirou - resetar
                    cur.execute("""
                        UPDATE users 
                        SET bloqueado_ate = NULL, tentativas_login_falhas = 0
                        WHERE id = ?
                    """, (user_id,))
                    conn.commit()
            
            # Verificar se está ativo
            if not user_dict["is_active"]:
                registrar_log(
                    user_id=user_id,
                    user_email=email,
                    acao="login_usuario_inativo",
                    categoria="auth",
                    descricao="Tentativa de login com usuário inativo",
                    ip_address=ip_address,
                    sucesso=False
                )
                return {
                    "error": "inativo", 
                    "message": "Usuário inativo. Contate o administrador.",
                    "detail": "Usuário inativo. Contate o administrador."
                }
            
            # Verificar senha
            if not verificar_senha(senha, user_dict["senha_hash"]):
                # Senha incorreta - incrementar tentativas
                tentativas = user_dict["tentativas_login_falhas"] + 1
                
                if tentativas >= 5:
                    # Bloquear por 15 minutos
                    bloqueado_ate = datetime.utcnow() + timedelta(minutes=15)
                    cur.execute("""
                        UPDATE users 
                        SET tentativas_login_falhas = ?, bloqueado_ate = ?
                        WHERE id = ?
                    """, (tentativas, bloqueado_ate.isoformat(), user_id))
                    conn.commit()
                    
                    registrar_log(
                        user_id=user_id,
                        user_email=email,
                        acao="usuario_bloqueado",
                        categoria="auth",
                        descricao=f"Usuário bloqueado por {tentativas} tentativas falhas de login",
                        ip_address=ip_address,
                        sucesso=False
                    )
                    
                    return {
                        "error": "bloqueado", 
                        "message": "Usuário bloqueado por excesso de tentativas. Aguarde 15 minutos.",
                        "detail": "Usuário bloqueado por excesso de tentativas. Aguarde 15 minutos."
                    }
                else:
                    # Apenas incrementar tentativas
                    cur.execute("""
                        UPDATE users 
                        SET tentativas_login_falhas = ?
                        WHERE id = ?
                    """, (tentativas, user_id))
                    conn.commit()
                    
                    registrar_log(
                        user_id=user_id,
                        user_email=email,
                        acao="login_senha_incorreta",
                        categoria="auth",
                        descricao=f"Senha incorreta. Tentativa {tentativas}/5",
                        ip_address=ip_address,
                        sucesso=False
                    )
                    
                    tentativas_restantes = 5 - tentativas
                    mensagem = f"Senha incorreta. Você tem {tentativas_restantes} tentativa(s) restante(s)."
                    return {
                        "error": "senha_incorreta",
                        "message": mensagem,
                        "detail": mensagem
                    }
            
            # Login bem-sucedido!
            
            # Buscar perfis do usuário
            cur.execute("""
                SELECT p.nome
                FROM user_perfis up
                INNER JOIN perfis p ON up.perfil_id = p.id
                WHERE up.user_id = ?
            """, (user_id,))
            perfis = [row[0] for row in cur.fetchall()]
            
            if not perfis:
                perfis = [user_dict["perfil_principal"]]
            
            # Criar token JWT
            token_data = {
                "sub": str(user_id),
                "email": email,
                "perfil": user_dict["perfil_principal"],
                "is_admin": user_dict["is_admin"]
            }
            access_token = criar_token_acesso(token_data)
            
            # Invalidar sessão anterior (apenas 1 sessão por vez)
            cur.execute("DELETE FROM sessoes_ativas WHERE user_id = ?", (user_id,))
            
            # Criar nova sessão
            token_hash_value = hash_token(access_token)
            expira_em = datetime.utcnow() + timedelta(minutes=60)
            cur.execute("""
                INSERT INTO sessoes_ativas (
                    user_id, token_hash, ip_address, expira_em, ultima_atividade
                )
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (user_id, token_hash_value, ip_address, expira_em.isoformat()))
            
            # Atualizar usuário
            cur.execute("""
                UPDATE users 
                SET tentativas_login_falhas = 0,
                    bloqueado_ate = NULL,
                    ultimo_login = datetime('now'),
                    sessao_ativa_token = ?,
                    ultima_atividade = datetime('now')
                WHERE id = ?
            """, (token_hash_value, user_id))
            
            conn.commit()
            cur.close()
            
            # Registrar log de sucesso
            registrar_log(
                user_id=user_id,
                user_email=email,
                acao="login_sucesso",
                categoria="auth",
                descricao=f"Login realizado com sucesso",
                ip_address=ip_address,
                sucesso=True
            )
            
            # Retornar resposta
            user_response = {
                "id": user_id,
                "email": email,
                "nome_completo": user_dict["nome_completo"],
                "departamento": user_dict.get("departamento"),
                "cargo": user_dict.get("cargo"),
                "perfil_principal": user_dict["perfil_principal"],
                "perfis": perfis,
                "is_active": user_dict["is_active"],
                "is_admin": user_dict["is_admin"],
                "deve_trocar_senha": user_dict["deve_trocar_senha"],
                "criado_em": "",
                "ultimo_login": datetime.utcnow().isoformat()
            }
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_response,
                "deve_trocar_senha": user_dict["deve_trocar_senha"]
            }
            
        except Exception as e:
            print(f"[AUTH] Erro no login: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if conn:
                conn.close()
    
    
    @staticmethod
    def logout(user_id: int, token: str):
        """Realiza logout do usuário"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            # Buscar email para log
            cur.execute("SELECT email FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            email = row[0] if row else "unknown"
            
            # Remover sessão ativa
            token_hash_value = hash_token(token)
            cur.execute("DELETE FROM sessoes_ativas WHERE user_id = ? AND token_hash = ?", 
                       (user_id, token_hash_value))
            
            # Limpar token do usuário
            cur.execute("UPDATE users SET sessao_ativa_token = NULL WHERE id = ?", (user_id,))
            
            conn.commit()
            cur.close()
            
            # Registrar log
            registrar_log(
                user_id=user_id,
                user_email=email,
                acao="logout",
                categoria="auth",
                descricao="Logout realizado",
                sucesso=True
            )
            
            return True
            
        except Exception as e:
            print(f"[AUTH] Erro no logout: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Busca usuário por ID"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, email, nome_completo, departamento, cargo,
                       perfil_principal, is_active, is_admin, deve_trocar_senha,
                       criado_em, ultimo_login
                FROM users WHERE id = ?
            """, (user_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            user_dict = dict(row)
            
            # Buscar perfis
            cur.execute("""
                SELECT p.nome
                FROM user_perfis up
                INNER JOIN perfis p ON up.perfil_id = p.id
                WHERE up.user_id = ?
            """, (user_id,))
            perfis = [r[0] for r in cur.fetchall()]
            
            if not perfis:
                perfis = [user_dict["perfil_principal"]]
            
            user_dict["perfis"] = perfis
            cur.close()
            
            return user_dict
            
        except Exception as e:
            print(f"[AUTH] Erro ao buscar usuário: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    
    @staticmethod
    def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
        """Busca usuário a partir de um token JWT"""
        from .security import verificar_token
        
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
        
        return AuthService.get_user_by_id(user_id)
    
    
    # ========================================
    # GERENCIAMENTO DE USUÁRIOS
    # ========================================
    
    @staticmethod
    def criar_usuario(user_data: UserCreate, criado_por_id: int) -> Optional[Dict[str, Any]]:
        """Cria um novo usuário e envia convite"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            # Verificar se email já existe
            cur.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
            if cur.fetchone():
                return {"error": "Email já cadastrado"}
            
            # Gerar token de convite
            token_convite, token_expira = gerar_token_convite()
            
            # Senha temporária (será ignorada, usuário definirá via link)
            senha_temp_hash = hash_senha("TEMP_SENHA_INVALIDA_" + token_convite)
            
            # Inserir usuário
            cur.execute("""
                INSERT INTO users (
                    email, nome_completo, senha_hash, departamento, cargo,
                    perfil_principal, is_active, is_admin, deve_trocar_senha,
                    senha_temporaria, token_convite, token_convite_expira,
                    criado_por
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, 1, 1, ?, ?, ?)
            """, (
                user_data.email,
                user_data.nome_completo,
                senha_temp_hash,
                user_data.departamento,
                user_data.cargo,
                user_data.perfil_principal,
                token_convite,
                token_expira.isoformat(),
                criado_por_id
            ))
            
            user_id = cur.lastrowid
            
            # Buscar ID do perfil principal
            cur.execute("SELECT id FROM perfis WHERE nome = ?", (user_data.perfil_principal,))
            perfil_row = cur.fetchone()
            if perfil_row:
                perfil_id = perfil_row[0]
                cur.execute("""
                    INSERT INTO user_perfis (user_id, perfil_id, criado_por)
                    VALUES (?, ?, ?)
                """, (user_id, perfil_id, criado_por_id))
            
            # Adicionar perfis adicionais
            if user_data.perfis_adicionais:
                for perfil_nome in user_data.perfis_adicionais:
                    cur.execute("SELECT id FROM perfis WHERE nome = ?", (perfil_nome,))
                    perfil_row = cur.fetchone()
                    if perfil_row:
                        cur.execute("""
                            INSERT INTO user_perfis (user_id, perfil_id, criado_por)
                            VALUES (?, ?, ?)
                            ON CONFLICT DO NOTHING
                        """, (user_id, perfil_row[0], criado_por_id))
            
            conn.commit()
            cur.close()
            
            # Registrar log
            registrar_log(
                user_id=criado_por_id,
                acao="criar_usuario",
                categoria="usuarios",
                descricao=f"Usuário criado: {user_data.email}",
                dados_depois=f"ID: {user_id}, Email: {user_data.email}",
                sucesso=True
            )
            
            # TODO: Enviar email com link de convite
            # link_convite = f"https://seudominio.com/auth/set-password?token={token_convite}"
            
            return {
                "success": True,
                "user_id": user_id,
                "token_convite": token_convite,
                "message": "Usuário criado com sucesso. Link de convite gerado."
            }
            
        except Exception as e:
            print(f"[AUTH] Erro ao criar usuário: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.rollback()
            return {"error": str(e)}
        finally:
            if conn:
                conn.close()
    
    
    @staticmethod
    def listar_usuarios(apenas_ativos: bool = False) -> List[Dict[str, Any]]:
        """Lista todos os usuários"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            query = """
                SELECT id, email, nome_completo, departamento, cargo,
                       perfil_principal, is_active, is_admin, criado_em, ultimo_login
                FROM users
            """
            
            if apenas_ativos:
                query += " WHERE is_active = 1"
            
            query += " ORDER BY nome_completo"
            
            cur.execute(query)
            rows = cur.fetchall()
            
            usuarios = []
            for row in rows:
                user_dict = dict(row)
                user_id = user_dict["id"]
                
                # Buscar perfis
                cur.execute("""
                    SELECT p.nome
                    FROM user_perfis up
                    INNER JOIN perfis p ON up.perfil_id = p.id
                    WHERE up.user_id = ?
                """, (user_id,))
                perfis = [r[0] for r in cur.fetchall()]
                
                user_dict["perfis"] = perfis if perfis else [user_dict["perfil_principal"]]
                usuarios.append(user_dict)
            
            cur.close()
            return usuarios
            
        except Exception as e:
            print(f"[AUTH] Erro ao listar usuários: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    
    # ========================================
    # PERMISSÕES
    # ========================================
    
    @staticmethod
    def verificar_permissao(user_id: int, modulo_codigo: str, permissao_codigo: str) -> bool:
        """Verifica se o usuário tem permissão para acessar um módulo"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            # Verificar se é admin (tem acesso a tudo)
            cur.execute("SELECT is_admin, is_active FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                return False
            
            if not row["is_active"]:
                return False
            
            if row["is_admin"]:
                return True  # Admin tem acesso a tudo
            
            # Buscar permissões customizadas do usuário (sobrescreve perfil)
            cur.execute("""
                SELECT umpc.concedido
                FROM user_modulo_permissoes_customizadas umpc
                INNER JOIN modulos m ON umpc.modulo_id = m.id
                INNER JOIN permissoes p ON umpc.permissao_id = p.id
                WHERE umpc.user_id = ? AND m.codigo = ? AND p.codigo = ?
                  AND (umpc.expira_em IS NULL OR umpc.expira_em > datetime('now'))
            """, (user_id, modulo_codigo, permissao_codigo))
            
            row = cur.fetchone()
            if row:
                return bool(row[0])  # Permissão customizada encontrada
            
            # Buscar permissões por perfil
            cur.execute("""
                SELECT pmp.concedido
                FROM perfil_modulo_permissoes pmp
                INNER JOIN user_perfis up ON pmp.perfil_id = up.perfil_id
                INNER JOIN modulos m ON pmp.modulo_id = m.id
                INNER JOIN permissoes p ON pmp.permissao_id = p.id
                WHERE up.user_id = ? AND m.codigo = ? AND p.codigo = ? AND pmp.concedido = 1
                LIMIT 1
            """, (user_id, modulo_codigo, permissao_codigo))
            
            row = cur.fetchone()
            cur.close()
            
            return bool(row)
            
        except Exception as e:
            print(f"[AUTH] Erro ao verificar permissão: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    
    @staticmethod
    def listar_modulos_usuario(user_id: int) -> List[Dict[str, Any]]:
        """Lista módulos que o usuário tem acesso"""
        conn = None
        try:
            conn = get_auth_conn()
            cur = conn.cursor()
            
            # Verificar se é admin
            cur.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if row and row[0]:
                # Admin vê tudo
                cur.execute("""
                    SELECT id, codigo, nome, descricao, icone, ordem, categoria
                    FROM modulos
                    WHERE is_active = 1
                    ORDER BY ordem
                """)
            else:
                # Usuário normal: apenas módulos com permissão
                cur.execute("""
                    SELECT DISTINCT m.id, m.codigo, m.nome, m.descricao, m.icone, m.ordem, m.categoria
                    FROM modulos m
                    INNER JOIN perfil_modulo_permissoes pmp ON m.id = pmp.modulo_id
                    INNER JOIN user_perfis up ON pmp.perfil_id = up.perfil_id
                    WHERE up.user_id = ? AND m.is_active = 1 AND pmp.concedido = 1
                    ORDER BY m.ordem
                """, (user_id,))
            
            rows = cur.fetchall()
            modulos = [dict(row) for row in rows]
            cur.close()
            
            return modulos
            
        except Exception as e:
            print(f"[AUTH] Erro ao listar módulos do usuário: {e}")
            return []
        finally:
            if conn:
                conn.close()

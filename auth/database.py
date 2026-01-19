# auth/database.py
# Gerenciamento do banco de dados de autenticação

import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime
from .logger import log_info, log_success, log_error, log_warning

# Caminho do banco de dados central
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "rentus_auth.db"

# Garantir que o diretório data/ existe
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_db_initialized = False


def get_auth_conn():
    """Retorna uma conexão SQLite com o banco de autenticação"""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except:
        pass
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_auth_db():
    """Inicializa o banco de dados de autenticação"""
    global _db_initialized
    
    if _db_initialized:
        log_info("Banco já inicializado")
        return
    
    conn = None
    try:
        # Ler schema SQL
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            log_error(f"Schema não encontrado em {schema_path}")
            return
        
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        conn = get_auth_conn()
        cur = conn.cursor()
        
        # Executar schema completo de uma vez (SQLite suporta executescript)
        try:
            cur.executescript(schema_sql)
            conn.commit()
        except Exception as e:
            log_error(f"Erro ao executar schema: {e}")
            import traceback
            traceback.print_exc()
        
        cur.close()
        
        log_success("Banco de autenticacao inicializado com sucesso")
        
        # Seed inicial
        _seed_initial_data()
        
        _db_initialized = True
        
    except Exception as e:
        log_error(f"Erro ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def _seed_initial_data():
    """Popula dados iniciais (perfis, módulos, permissões)"""
    conn = None
    try:
        conn = get_auth_conn()
        cur = conn.cursor()
        
        # ========================================
        # 1. PERFIS
        # ========================================
        perfis = [
            ("admin", "Administrador - Acesso completo ao sistema", 100, "#DC2626"),
            ("direcao", "Direção - Apenas dashboards sem pendências", 90, "#7C3AED"),
            ("gestor", "Gestor/Supervisor - Dashboards sem pendências", 80, "#2563EB"),
            ("auditor", "Auditores - Dashboard + correções + encaminhar demandas", 70, "#059669"),
            ("operacional", "Operacional - Correções de dados", 60, "#F59E0B"),
            ("loyal", "Loyal - Categoria especial com acesso específico", 50, "#EC4899"),
        ]
        
        for nome, desc, nivel, cor in perfis:
            try:
                cur.execute("""
                    INSERT INTO perfis (nome, descricao, nivel_hierarquia, cor_badge)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(nome) DO NOTHING
                """, (nome, desc, nivel, cor))
            except Exception as e:
                log_warning(f"Erro ao inserir perfil {nome}: {e}")
        
        # ========================================
        # 2. MÓDULOS
        # ========================================
        modulos = [
            ("dashboard", "Dashboard Geral", "Visão geral do sistema", "📊", 0, "principal"),
            ("modulo1", "Módulo 1 - OPS/Demitidos", "Gestão de operações e demissões", "👥", 1, "operacional"),
            ("modulo2", "Módulo 2 - NFe/Suprimentos", "Gestão de notas fiscais e suprimentos", "📄", 2, "operacional"),
            ("modulo3", "Módulo 3", "Módulo 3 do sistema", "📋", 3, "operacional"),
            ("modulo4", "Módulo 4", "Módulo 4 do sistema", "📋", 4, "operacional"),
            ("modulo5", "Módulo 5", "Módulo 5 do sistema", "📋", 5, "operacional"),
            ("modulo6", "Módulo 6", "Módulo 6 do sistema", "📋", 6, "operacional"),
            ("modulo7", "Módulo 7", "Módulo 7 do sistema", "📋", 7, "operacional"),
            ("modulo8", "Módulo 8", "Módulo 8 do sistema", "📋", 8, "operacional"),
            ("modulo9", "Módulo 9", "Módulo 9 do sistema", "📋", 9, "operacional"),
            ("modulo10", "Módulo 10", "Módulo 10 do sistema", "📋", 10, "operacional"),
            ("modulo11", "Módulo 11", "Módulo 11 do sistema", "📋", 11, "operacional"),
            ("modulo12", "Módulo 12", "Módulo 12 do sistema", "📋", 12, "operacional"),
            ("modulo13", "Módulo 13", "Módulo 13 do sistema", "📋", 13, "operacional"),
            ("modulo14", "Módulo 14", "Módulo 14 do sistema", "📋", 14, "operacional"),
            ("modulo15", "Módulo 15", "Módulo 15 do sistema", "📋", 15, "operacional"),
            ("modulo16", "Módulo 16", "Módulo 16 do sistema", "📋", 16, "operacional"),
            ("admin_users", "Gestão de Usuários", "Criar, editar e gerenciar usuários", "👤", 100, "admin"),
            ("admin_roles", "Gestão de Perfis", "Configurar perfis e permissões", "🔐", 101, "admin"),
            ("admin_audit", "Logs e Auditoria", "Visualizar logs do sistema", "📝", 102, "admin"),
            ("teste_acesso", "Teste de Controle de Acesso", "Página de teste de permissões", "🧪", 200, "teste"),
        ]
        
        for codigo, nome, desc, icone, ordem, cat in modulos:
            try:
                cur.execute("""
                    INSERT INTO modulos (codigo, nome, descricao, icone, ordem, categoria)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(codigo) DO NOTHING
                """, (codigo, nome, desc, icone, ordem, cat))
            except Exception as e:
                log_warning(f"Erro ao inserir módulo {codigo}: {e}")
        
        # ========================================
        # 3. PERMISSÕES
        # ========================================
        permissoes = [
            ("visualizar", "view", "Pode visualizar/ler dados"),
            ("criar", "create", "Pode criar novos registros"),
            ("editar", "edit", "Pode editar registros existentes"),
            ("deletar", "delete", "Pode deletar registros"),
            ("aprovar", "approve", "Pode aprovar alterações"),
            ("exportar", "export", "Pode exportar dados"),
            ("importar", "import", "Pode importar dados"),
            ("admin", "admin", "Administração total do módulo"),
        ]
        
        for nome, codigo, desc in permissoes:
            try:
                cur.execute("""
                    INSERT INTO permissoes (nome, codigo, descricao)
                    VALUES (?, ?, ?)
                    ON CONFLICT(codigo) DO NOTHING
                """, (nome, codigo, desc))
            except Exception as e:
                log_warning(f"Erro ao inserir permissão {codigo}: {e}")
        
        conn.commit()
        
        # ========================================
        # 4. PERMISSÕES PADRÃO POR PERFIL
        # ========================================
        _seed_default_permissions(conn)
        
        # ========================================
        # 5. USUÁRIOS PADRÃO PARA TESTE
        # ========================================
        _seed_default_users(conn)
        
        cur.close()
        log_success("Dados iniciais carregados com sucesso")
        
    except Exception as e:
        log_error(f"Erro ao popular dados iniciais: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def _seed_default_permissions(conn):
    """Define permissões padrão para cada perfil"""
    try:
        cur = conn.cursor()
        
        # Buscar IDs
        cur.execute("SELECT id, nome FROM perfis")
        perfis = {row["nome"]: row["id"] for row in cur.fetchall()}
        
        cur.execute("SELECT id, codigo FROM modulos")
        modulos = {row["codigo"]: row["id"] for row in cur.fetchall()}
        
        cur.execute("SELECT id, codigo FROM permissoes")
        permissoes = {row["codigo"]: row["id"] for row in cur.fetchall()}
        
        # Admin: acesso total a tudo
        if "admin" in perfis:
            for modulo_id in modulos.values():
                for perm_id in permissoes.values():
                    try:
                        cur.execute("""
                            INSERT INTO perfil_modulo_permissoes (perfil_id, modulo_id, permissao_id, concedido)
                            VALUES (?, ?, ?, 1)
                            ON CONFLICT DO NOTHING
                        """, (perfis["admin"], modulo_id, perm_id))
                    except:
                        pass
        
        # Direção: apenas visualizar dashboards (sem módulos admin)
        if "direcao" in perfis:
            modulos_direcao = ["dashboard", "modulo1", "modulo2", "modulo3", "modulo4", "modulo5", 
                              "modulo6", "modulo7", "modulo8", "modulo9", "modulo10", "modulo11",
                              "modulo12", "modulo13", "modulo14", "modulo15", "modulo16"]
            for mod_code in modulos_direcao:
                if mod_code in modulos and "view" in permissoes:
                    try:
                        cur.execute("""
                            INSERT INTO perfil_modulo_permissoes (perfil_id, modulo_id, permissao_id, concedido)
                            VALUES (?, ?, ?, 1)
                            ON CONFLICT DO NOTHING
                        """, (perfis["direcao"], modulos[mod_code], permissoes["view"]))
                    except:
                        pass
        
        # Gestor: mesmo que direção
        if "gestor" in perfis:
            modulos_gestor = ["dashboard", "modulo1", "modulo2", "modulo3", "modulo4", "modulo5",
                             "modulo6", "modulo7", "modulo8", "modulo9", "modulo10", "modulo11",
                             "modulo12", "modulo13", "modulo14", "modulo15", "modulo16"]
            for mod_code in modulos_gestor:
                if mod_code in modulos and "view" in permissoes:
                    try:
                        cur.execute("""
                            INSERT INTO perfil_modulo_permissoes (perfil_id, modulo_id, permissao_id, concedido)
                            VALUES (?, ?, ?, 1)
                            ON CONFLICT DO NOTHING
                        """, (perfis["gestor"], modulos[mod_code], permissoes["view"]))
                    except:
                        pass
        
        # Auditor: visualizar, editar, exportar
        if "auditor" in perfis:
            modulos_auditor = ["dashboard", "modulo1", "modulo2"]
            perms_auditor = ["view", "edit", "export"]
            for mod_code in modulos_auditor:
                if mod_code in modulos:
                    for perm_code in perms_auditor:
                        if perm_code in permissoes:
                            try:
                                cur.execute("""
                                    INSERT INTO perfil_modulo_permissoes (perfil_id, modulo_id, permissao_id, concedido)
                                    VALUES (?, ?, ?, 1)
                                    ON CONFLICT DO NOTHING
                                """, (perfis["auditor"], modulos[mod_code], permissoes[perm_code]))
                            except:
                                pass
        
        # Operacional: visualizar, editar
        if "operacional" in perfis:
            modulos_operacional = ["dashboard", "modulo1", "modulo2"]
            perms_operacional = ["view", "edit"]
            for mod_code in modulos_operacional:
                if mod_code in modulos:
                    for perm_code in perms_operacional:
                        if perm_code in permissoes:
                            try:
                                cur.execute("""
                                    INSERT INTO perfil_modulo_permissoes (perfil_id, modulo_id, permissao_id, concedido)
                                    VALUES (?, ?, ?, 1)
                                    ON CONFLICT DO NOTHING
                                """, (perfis["operacional"], modulos[mod_code], permissoes[perm_code]))
                            except:
                                pass
        
        conn.commit()
        log_success("Permissoes padrao configuradas")
        
    except Exception as e:
        log_error(f"Erro ao configurar permissões padrão: {e}")
        import traceback
        traceback.print_exc()


def _seed_default_users(conn):
    """Cria usuários padrão para testes"""
    from .security import hash_senha
    
    try:
        cur = conn.cursor()
        
        # Buscar IDs dos perfis
        cur.execute("SELECT id, nome FROM perfis")
        perfis = {row["nome"]: row["id"] for row in cur.fetchall()}
        
        # Usuários padrão: perfil/perfil (ex: admin/admin)
        usuarios_padrao = [
            ("admin", "admin@rentus.com", "Administrador Sistema", "TI", "Administrador", True),
            ("direcao", "direcao@rentus.com", "Direção Geral", "Direção", "Diretor", False),
            ("gestor", "gestor@rentus.com", "Gestor Sistema", "Gestão", "Gestor", False),
            ("auditor", "auditor@rentus.com", "Auditor Sistema", "Auditoria", "Auditor", False),
            ("operacional", "operacional@rentus.com", "Operacional Sistema", "Operações", "Operador", False),
            ("loyal", "loyal@rentus.com", "Loyal Sistema", "Loyal", "Analista", False),
        ]
        
        for perfil_nome, email, nome, depto, cargo, is_admin in usuarios_padrao:
            try:
                # Verificar se usuário já existe
                cur.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cur.fetchone():
                    continue  # Já existe
                
                # Hash da senha (senha = nome do perfil)
                senha_hash = hash_senha(perfil_nome)
                
                # Inserir usuário
                cur.execute("""
                    INSERT INTO users (
                        email, nome_completo, senha_hash, departamento, cargo,
                        perfil_principal, is_active, is_admin, deve_trocar_senha
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0)
                """, (email, nome, senha_hash, depto, cargo, perfil_nome, 1 if is_admin else 0))
                
                user_id = cur.lastrowid
                
                # Associar perfil ao usuário
                if perfil_nome in perfis:
                    cur.execute("""
                        INSERT INTO user_perfis (user_id, perfil_id)
                        VALUES (?, ?)
                        ON CONFLICT DO NOTHING
                    """, (user_id, perfis[perfil_nome]))
                
                log_success(f"Usuario criado: {email} (senha: {perfil_nome})")
                
            except Exception as e:
                log_warning(f"Erro ao criar usuário {email}: {e}")
        
        conn.commit()
        log_success("Usuarios padrao criados")
        
    except Exception as e:
        log_error(f"Erro ao criar usuários padrão: {e}")
        import traceback
        traceback.print_exc()

-- ============================================================
-- SCHEMA DO BANCO CENTRAL DE AUTENTICAÇÃO E CONTROLE DE ACESSO
-- Sistema: Rentus Analyzer
-- Database: rentus_auth.db (SQLite)
-- ============================================================

-- ============================================================
-- TABELA: users
-- Armazena todos os usuários do sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    nome_completo TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    departamento TEXT,
    cargo TEXT,
    
    -- Controle de acesso
    perfil_principal TEXT NOT NULL DEFAULT 'operacional',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_admin BOOLEAN NOT NULL DEFAULT 0,
    
    -- Controle de senha
    senha_temporaria BOOLEAN NOT NULL DEFAULT 0,
    deve_trocar_senha BOOLEAN NOT NULL DEFAULT 1,
    token_convite TEXT,
    token_convite_expira TEXT,
    token_reset_senha TEXT,
    token_reset_expira TEXT,
    
    -- Controle de bloqueio
    tentativas_login_falhas INTEGER DEFAULT 0,
    bloqueado_ate TEXT,
    
    -- Controle de sessão
    sessao_ativa_token TEXT,
    ultima_atividade TEXT,
    
    -- Auditoria
    criado_em TEXT DEFAULT (datetime('now')),
    criado_por INTEGER,
    atualizado_em TEXT DEFAULT (datetime('now')),
    atualizado_por INTEGER,
    ultimo_login TEXT,
    
    FOREIGN KEY(criado_por) REFERENCES users(id),
    FOREIGN KEY(atualizado_por) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_perfil ON users(perfil_principal);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_token_convite ON users(token_convite);
CREATE INDEX IF NOT EXISTS idx_users_token_reset ON users(token_reset_senha);


-- ============================================================
-- TABELA: perfis
-- Define os perfis de acesso disponíveis no sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS perfis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT,
    nivel_hierarquia INTEGER DEFAULT 0,
    cor_badge TEXT DEFAULT '#6B7280',
    criado_em TEXT DEFAULT (datetime('now')),
    atualizado_em TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_perfis_nome ON perfis(nome);


-- ============================================================
-- TABELA: modulos
-- Define os módulos/páginas do sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS modulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    icone TEXT,
    ordem INTEGER DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    categoria TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    atualizado_em TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_modulos_codigo ON modulos(codigo);
CREATE INDEX IF NOT EXISTS idx_modulos_active ON modulos(is_active);


-- ============================================================
-- TABELA: permissoes
-- Define as permissões disponíveis (criar, ler, editar, deletar, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS permissoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    descricao TEXT,
    criado_em TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_permissoes_codigo ON permissoes(codigo);


-- ============================================================
-- TABELA: perfil_modulo_permissoes
-- Relaciona PERFIL + MÓDULO + PERMISSÕES
-- Ex: Perfil "Auditor" no "Módulo 2" pode "ler" e "editar"
-- ============================================================
CREATE TABLE IF NOT EXISTS perfil_modulo_permissoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil_id INTEGER NOT NULL,
    modulo_id INTEGER NOT NULL,
    permissao_id INTEGER NOT NULL,
    concedido BOOLEAN NOT NULL DEFAULT 1,
    criado_em TEXT DEFAULT (datetime('now')),
    criado_por INTEGER,
    
    UNIQUE(perfil_id, modulo_id, permissao_id),
    FOREIGN KEY(perfil_id) REFERENCES perfis(id) ON DELETE CASCADE,
    FOREIGN KEY(modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
    FOREIGN KEY(permissao_id) REFERENCES permissoes(id) ON DELETE CASCADE,
    FOREIGN KEY(criado_por) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_pmp_perfil ON perfil_modulo_permissoes(perfil_id);
CREATE INDEX IF NOT EXISTS idx_pmp_modulo ON perfil_modulo_permissoes(modulo_id);
CREATE INDEX IF NOT EXISTS idx_pmp_permissao ON perfil_modulo_permissoes(permissao_id);


-- ============================================================
-- TABELA: user_perfis
-- Usuários podem ter múltiplos perfis (ex: Operacional + Loyal)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_perfis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    perfil_id INTEGER NOT NULL,
    criado_em TEXT DEFAULT (datetime('now')),
    criado_por INTEGER,
    
    UNIQUE(user_id, perfil_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(perfil_id) REFERENCES perfis(id) ON DELETE CASCADE,
    FOREIGN KEY(criado_por) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_up_user ON user_perfis(user_id);
CREATE INDEX IF NOT EXISTS idx_up_perfil ON user_perfis(perfil_id);


-- ============================================================
-- TABELA: user_modulo_permissoes_customizadas
-- Permissões específicas por usuário (sobrescreve perfil)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_modulo_permissoes_customizadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    modulo_id INTEGER NOT NULL,
    permissao_id INTEGER NOT NULL,
    concedido BOOLEAN NOT NULL DEFAULT 1,
    motivo TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    criado_por INTEGER,
    expira_em TEXT,
    
    UNIQUE(user_id, modulo_id, permissao_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
    FOREIGN KEY(permissao_id) REFERENCES permissoes(id) ON DELETE CASCADE,
    FOREIGN KEY(criado_por) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_umpc_user ON user_modulo_permissoes_customizadas(user_id);
CREATE INDEX IF NOT EXISTS idx_umpc_modulo ON user_modulo_permissoes_customizadas(modulo_id);


-- ============================================================
-- TABELA: audit_log
-- Registra todas as ações importantes no sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_email TEXT,
    acao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    descricao TEXT,
    modulo TEXT,
    ip_address TEXT,
    user_agent TEXT,
    dados_antes TEXT,
    dados_depois TEXT,
    sucesso BOOLEAN DEFAULT 1,
    erro_mensagem TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_acao ON audit_log(acao);
CREATE INDEX IF NOT EXISTS idx_audit_categoria ON audit_log(categoria);
CREATE INDEX IF NOT EXISTS idx_audit_data ON audit_log(criado_em);
CREATE INDEX IF NOT EXISTS idx_audit_modulo ON audit_log(modulo);


-- ============================================================
-- TABELA: sessoes_ativas
-- Controla sessões ativas (apenas 1 sessão por usuário)
-- ============================================================
CREATE TABLE IF NOT EXISTS sessoes_ativas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    token_hash TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    expira_em TEXT NOT NULL,
    ultima_atividade TEXT DEFAULT (datetime('now')),
    
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessoes_user ON sessoes_ativas(user_id);
CREATE INDEX IF NOT EXISTS idx_sessoes_token ON sessoes_ativas(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessoes_expira ON sessoes_ativas(expira_em);


-- ============================================================
-- TABELA: notificacoes
-- Sistema de notificações para usuários
-- ============================================================
CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    mensagem TEXT,
    tipo TEXT DEFAULT 'info',
    link TEXT,
    lida BOOLEAN DEFAULT 0,
    criado_em TEXT DEFAULT (datetime('now')),
    lida_em TEXT,
    
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notif_user ON notificacoes(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_lida ON notificacoes(lida);
CREATE INDEX IF NOT EXISTS idx_notif_criado ON notificacoes(criado_em);

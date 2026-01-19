-- Schema para Enriquecimento Automático de CEPs
-- Adicionar ao schema existente

-- ============================================================
-- CACHE DE CEPs (evitar consultas repetidas à API)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_cache_ceps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cep TEXT UNIQUE NOT NULL,
    logradouro TEXT,
    complemento TEXT,
    bairro TEXT,
    localidade TEXT,
    uf TEXT,
    ddd TEXT,
    ibge TEXT,
    valido INTEGER DEFAULT 1,
    consultado_em TEXT DEFAULT (datetime('now')),
    fonte TEXT DEFAULT 'viacep'
);

CREATE INDEX IF NOT EXISTS idx_cache_ceps_cep ON modulo2_cache_ceps(cep);

-- ============================================================
-- POSTOS SUGERIDOS (postos encontrados nos XMLs mas não cadastrados)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_postos_sugeridos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_sugerido TEXT,
    logradouro TEXT,
    numero TEXT,
    complemento TEXT,
    bairro TEXT,
    cidade TEXT,
    uf TEXT,
    cep TEXT,
    fonte_xml TEXT,  -- Chave da NFe que originou a sugestão
    nfe_id INTEGER,
    status TEXT DEFAULT 'pendente',  -- 'pendente', 'aprovado', 'rejeitado'
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (nfe_id) REFERENCES modulo2_nfe(id)
);

CREATE INDEX IF NOT EXISTS idx_postos_sugeridos_status ON modulo2_postos_sugeridos(status);
CREATE INDEX IF NOT EXISTS idx_postos_sugeridos_cep ON modulo2_postos_sugeridos(cep);

-- ============================================================
-- LOG DE ENRIQUECIMENTO (auditoria de atualizações automáticas)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_log_enriquecimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    posto_id INTEGER,
    campo_atualizado TEXT,
    valor_antigo TEXT,
    valor_novo TEXT,
    fonte TEXT,  -- 'xml', 'api_viacep', 'manual'
    nfe_id INTEGER,
    atualizado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (posto_id) REFERENCES modulo2_postos_trabalho(id),
    FOREIGN KEY (nfe_id) REFERENCES modulo2_nfe(id)
);

CREATE INDEX IF NOT EXISTS idx_log_enriquecimento_posto ON modulo2_log_enriquecimento(posto_id);
CREATE INDEX IF NOT EXISTS idx_log_enriquecimento_data ON modulo2_log_enriquecimento(atualizado_em);

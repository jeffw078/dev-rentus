-- Schema SQLite para Módulo 2 (Suprimentos) - Versão Completa
-- Compatível com estrutura PostgreSQL para facilitar migração futura

PRAGMA foreign_keys = ON;

-- ============================================================
-- EMPRESAS / CERTIFICADOS
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_empresas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cnpj TEXT UNIQUE NOT NULL,
  razao_social TEXT,
  cert_pfx TEXT NOT NULL,
  cert_senha TEXT NOT NULL,
  uf INTEGER NOT NULL,
  sefaz_endpoint TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- CONTROLE DE NSU (Checkpoint por empresa)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_nsu_checkpoint (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER NOT NULL REFERENCES modulo2_empresas(id) ON DELETE CASCADE,
  ultimo_nsu INTEGER NOT NULL DEFAULT 0,
  atualizado_em TEXT DEFAULT (datetime('now')),
  UNIQUE(empresa_id)
);

-- ============================================================
-- POSTOS DE TRABALHO (Base do JSON)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_postos_trabalho (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT UNIQUE,
  nomecli TEXT NOT NULL,
  nomepos TEXT NOT NULL,
  end TEXT,
  bairro TEXT,
  cep TEXT,
  nomecid TEXT,
  estado TEXT,
  valor_orcado REAL DEFAULT 0,  -- Valor orçado mensal para o posto
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mod2_postos_codigo ON modulo2_postos_trabalho(codigo);
CREATE INDEX IF NOT EXISTS idx_mod2_postos_nomecli ON modulo2_postos_trabalho(nomecli);
CREATE INDEX IF NOT EXISTS idx_mod2_postos_nomepos ON modulo2_postos_trabalho(nomepos);
CREATE INDEX IF NOT EXISTS idx_mod2_postos_cep ON modulo2_postos_trabalho(cep);

-- ============================================================
-- NF-e (Notas Fiscais Eletrônicas)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_nfe (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER NOT NULL REFERENCES modulo2_empresas(id) ON DELETE CASCADE,
  chave_acesso TEXT UNIQUE NOT NULL,
  nsu INTEGER NOT NULL,
  data_emissao TEXT,
  data_importacao TEXT DEFAULT (datetime('now')),
  valor_total REAL,
  
  -- Emitente (Fornecedor)
  cnpj_emitente TEXT,
  nome_emitente TEXT,
  
  -- Destinatário
  cnpj_destinatario TEXT,
  nome_destinatario TEXT,
  
  -- Endereço de entrega (JSON como TEXT)
  endereco_entrega TEXT,
  
  -- Informações adicionais (infCpl)
  info_adicional TEXT,
  
  -- Relacionamento com posto (pode ser NULL se não identificado)
  posto_id INTEGER REFERENCES modulo2_postos_trabalho(id),
  
  -- Status: 'pendente' | 'identificado' | 'processado'
  status TEXT DEFAULT 'pendente',
  
  -- XML completo da NFe
  xml TEXT NOT NULL,
  
  -- Metadados
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mod2_nfe_empresa_id ON modulo2_nfe(empresa_id);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_chave ON modulo2_nfe(chave_acesso);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_nsu ON modulo2_nfe(nsu);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_data_emissao ON modulo2_nfe(data_emissao);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_posto_id ON modulo2_nfe(posto_id);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_status ON modulo2_nfe(status);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_cnpj_emitente ON modulo2_nfe(cnpj_emitente);

-- ============================================================
-- PENDÊNCIAS (NFes sem posto identificado)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_pendencias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nfe_id INTEGER NOT NULL REFERENCES modulo2_nfe(id) ON DELETE CASCADE,
  chave_nfe TEXT NOT NULL,
  valor REAL,
  fornecedor TEXT,
  cliente TEXT,
  posto_trabalho TEXT,  -- Posto tentado identificar (pode estar vazio)
  motivo TEXT,          -- Motivo da pendência
  status TEXT DEFAULT 'pendente',  -- 'pendente' | 'resolvida'
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  resolvido_em TEXT,
  resolvido_por TEXT
);

CREATE INDEX IF NOT EXISTS idx_mod2_pendencias_nfe_id ON modulo2_pendencias(nfe_id);
CREATE INDEX IF NOT EXISTS idx_mod2_pendencias_chave ON modulo2_pendencias(chave_nfe);
CREATE INDEX IF NOT EXISTS idx_mod2_pendencias_status ON modulo2_pendencias(status);

-- ============================================================
-- ITENS DA NF-e (Produtos) - Salva todos os itens de cada NF
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_nfe_itens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nfe_id INTEGER NOT NULL,
  numero_item INTEGER NOT NULL,
  codigo_produto TEXT,
  descricao_produto TEXT,
  ncm TEXT,
  cfop TEXT,
  unidade TEXT,
  quantidade REAL,
  valor_unitario REAL,
  valor_total REAL,
  icms_base REAL DEFAULT 0,
  icms_valor REAL DEFAULT 0,
  icms_aliquota REAL DEFAULT 0,
  ipi_valor REAL DEFAULT 0,
  pis_valor REAL DEFAULT 0,
  cofins_valor REAL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (nfe_id) REFERENCES modulo2_nfe(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mod2_nfe_itens_nfe ON modulo2_nfe_itens(nfe_id);
CREATE INDEX IF NOT EXISTS idx_mod2_nfe_itens_ncm ON modulo2_nfe_itens(ncm);

-- ============================================================
-- ORÇADO POR POSTO (Valores orçados por posto de trabalho)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_orcado_posto (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  posto_id INTEGER NOT NULL REFERENCES modulo2_postos_trabalho(id) ON DELETE CASCADE,
  valor_orcado REAL NOT NULL DEFAULT 0,
  ano_mes TEXT,  -- YYYY-MM para controle mensal (ex: "2025-01")
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(posto_id, ano_mes)
);

CREATE INDEX IF NOT EXISTS idx_mod2_orcado_posto_id ON modulo2_orcado_posto(posto_id);
CREATE INDEX IF NOT EXISTS idx_mod2_orcado_ano_mes ON modulo2_orcado_posto(ano_mes);

-- ============================================================
-- HISTÓRICO DE IMPORTAÇÕES (Log de execuções automáticas)
-- ============================================================
CREATE TABLE IF NOT EXISTS modulo2_importacoes_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL,  -- 'inicial' | 'diaria' | 'manual'
  data_inicio DATE,
  data_fim DATE,
  total_xmls INTEGER DEFAULT 0,
  xmls_processados INTEGER DEFAULT 0,
  xmls_identificados INTEGER DEFAULT 0,
  xmls_pendentes INTEGER DEFAULT 0,
  status TEXT DEFAULT 'em_andamento',  -- 'em_andamento' | 'concluido' | 'erro'
  mensagem TEXT,
  tempo_execucao_segundos INTEGER,
  iniciado_em TEXT DEFAULT (datetime('now')),
  concluido_em TEXT,
  UNIQUE(id)
);

CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_tipo ON modulo2_importacoes_log(tipo);
CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_status ON modulo2_importacoes_log(status);
CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_data ON modulo2_importacoes_log(data_inicio);

# projects/modulo2/db.py

import os
import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime

# ================================
# CONFIGURAÇÃO DO BANCO (SQLite)
# ================================
# Banco de dados CENTRAL em ./data/rentus.db
# Todos os módulos usam este banco com prefixo nas tabelas (ex: modulo2_nfe)
# Facilita migração para PostgreSQL com schemas separados
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent  # Sobe de projects/modulo2 para raiz do projeto
DATA_DIR = PROJECT_ROOT / "data"

# Criar diretório data se não existir
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Banco central - todos os módulos usam este arquivo
DB_PATH = DATA_DIR / "rentus.db"

# Função auxiliar para encontrar arquivo de empresas
def _find_empresas_json():
    """Encontra o arquivo empresas.json usando app/main.py como referência"""
    # Procurar app/main.py para encontrar a raiz do projeto
    possiveis_raizes = []
    
    # Opção 1: Diretório atual de trabalho (mais comum quando servidor roda da raiz)
    current = Path.cwd()
    if (current / "app" / "main.py").exists():
        possiveis_raizes.append(current)
    
    # Opção 2: Subir de BASE_DIR até encontrar app/main.py
    # BASE_DIR = projects/modulo2/db.py
    # Procurar em: projects/, raiz do projeto
    base = BASE_DIR  # projects/modulo2/
    for nivel in [1, 2, 3]:  # projects/, raiz/, acima da raiz
        try:
            parent = base.parents[nivel - 1] if nivel > 1 else base.parent
            if (parent / "app" / "main.py").exists():
                possiveis_raizes.append(parent)
        except IndexError:
            break
    
    # Opção 3: Se app/main.py não for encontrado, tentar diretório atual
    if not possiveis_raizes:
        possiveis_raizes.append(Path.cwd())
    
    # Tentar cada raiz possível
    for raiz in possiveis_raizes:
        json_path = raiz / "certificados" / "empresas.json"
        try:
            if json_path.exists() and json_path.is_file():
                print(f"[DB] Arquivo empresas.json encontrado em: {json_path.resolve()}")
                return json_path.resolve()
        except Exception as e:
            print(f"[DB] Erro ao verificar {json_path}: {e}")
            continue
    
    return None


def get_conn():
    """Retorna uma conexão SQLite com configurações otimizadas"""
    # Timeout de 20 segundos para evitar database locked
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Habilitar WAL mode para melhor concorrência (ajuda com database locked)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except:
        pass  # WAL pode não estar disponível em todas as versões
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")  # Balance entre segurança e performance
    return conn


def _row_to_dict(row, default=None):
    """Converte sqlite3.Row para dicionário comum ou retorna valor padrão se None"""
    if row is None:
        return default or {}
    # sqlite3.Row pode ser convertido para dict usando keys()
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    return dict(row) if isinstance(row, (dict, tuple)) else row


# ================================
# INIT DB
# ================================

# Flag global para evitar múltiplas inicializações
_db_initialized = False

def init_db():
    """Inicializa o banco de dados criando as tabelas se não existirem"""
    global _db_initialized
    
    # Evitar múltiplas inicializações
    if _db_initialized:
        return
    
    conn = None
    try:
        # Ler schema SQL
        schema_path = BASE_DIR / "schema_sqlite.sql"
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            
            conn = get_conn()
            cur = conn.cursor()
            
            # Executar schema (SQLite executa múltiplos comandos separadamente)
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--') and len(statement) > 0:
                    try:
                        cur.execute(statement)
                    except sqlite3.OperationalError as e:
                        error_str = str(e).lower()
                        # Ignorar erros de "already exists" que são esperados
                        if "already exists" not in error_str and "duplicate" not in error_str:
                            print(f"[DB] AVISO ao executar statement: {e}")
            
            conn.commit()
            
            # Verificar se as tabelas foram criadas corretamente
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'modulo2%'")
            tabelas_criadas = [row[0] for row in cur.fetchall()]
            cur.close()
            
            print(f"[DB] Tabelas encontradas após schema: {tabelas_criadas}")
            
            # Se não houver tabela modulo2_empresas, usar fallback
            if "modulo2_empresas" not in tabelas_criadas:
                print("[DB] AVISO: Tabela modulo2_empresas não encontrada após schema SQL. Usando fallback...")
                if conn:
                    conn.close()
                _create_tables_fallback()
            else:
                if conn:
                    conn.close()
            
            print("[DB] Schema SQLite inicializado com sucesso")
            
            # Seed empresas do JSON (carregar se necessário)
            seed_empresas_from_json(force=False)
            
            # Migration: Criar tabelas novas se não existirem
            try:
                conn_migration = get_conn()
                cur_migration = conn_migration.cursor()
                
                # Verificar e criar tabela de orçado por posto
                cur_migration.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='modulo2_orcado_posto'
                """)
                if not cur_migration.fetchone():
                    print("[DB] Criando tabela modulo2_orcado_posto...")
                    cur_migration.execute("""
                        CREATE TABLE modulo2_orcado_posto (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            posto_id INTEGER NOT NULL REFERENCES modulo2_postos_trabalho(id) ON DELETE CASCADE,
                            valor_orcado REAL NOT NULL DEFAULT 0,
                            ano_mes TEXT,
                            created_at TEXT DEFAULT (datetime('now')),
                            updated_at TEXT DEFAULT (datetime('now')),
                            UNIQUE(posto_id, ano_mes)
                        )
                    """)
                    cur_migration.execute("CREATE INDEX IF NOT EXISTS idx_mod2_orcado_posto_id ON modulo2_orcado_posto(posto_id)")
                    cur_migration.execute("CREATE INDEX IF NOT EXISTS idx_mod2_orcado_ano_mes ON modulo2_orcado_posto(ano_mes)")
                    conn_migration.commit()
                    print("[DB] Tabela modulo2_orcado_posto criada com sucesso")
                else:
                    print("[DB] Tabela modulo2_orcado_posto já existe")
                
                # Verificar e criar tabela de log de importações
                cur_migration.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='modulo2_importacoes_log'
                """)
                if not cur_migration.fetchone():
                    print("[DB] Criando tabela modulo2_importacoes_log...")
                    cur_migration.execute("""
                        CREATE TABLE modulo2_importacoes_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tipo TEXT NOT NULL,
                            data_inicio DATE,
                            data_fim DATE,
                            total_xmls INTEGER DEFAULT 0,
                            xmls_processados INTEGER DEFAULT 0,
                            xmls_identificados INTEGER DEFAULT 0,
                            xmls_pendentes INTEGER DEFAULT 0,
                            status TEXT DEFAULT 'em_andamento',
                            mensagem TEXT,
                            tempo_execucao_segundos INTEGER,
                            iniciado_em TEXT DEFAULT (datetime('now')),
                            concluido_em TEXT
                        )
                    """)
                    cur_migration.execute("CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_tipo ON modulo2_importacoes_log(tipo)")
                    cur_migration.execute("CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_status ON modulo2_importacoes_log(status)")
                    cur_migration.execute("CREATE INDEX IF NOT EXISTS idx_mod2_importacoes_data ON modulo2_importacoes_log(data_inicio)")
                    conn_migration.commit()
                    print("[DB] Tabela modulo2_importacoes_log criada com sucesso")
                else:
                    print("[DB] Tabela modulo2_importacoes_log já existe")
                
                cur_migration.close()
                conn_migration.close()
            except Exception as e:
                print(f"[DB] AVISO ao criar tabelas de migração: {e}")
                import traceback
                traceback.print_exc()
            
            _db_initialized = True
            
        else:
            print(f"[DB] AVISO: Schema não encontrado em {schema_path}")
            _create_tables_fallback()
            _db_initialized = True
            
    except Exception as e:
        print(f"[DB] ERRO ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def _create_tables_fallback():
    """Cria tabelas básicas se o schema SQL não estiver disponível"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Tabelas básicas (versão simplificada)
        cur.execute("""
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
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS modulo2_nsu_checkpoint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa_id INTEGER NOT NULL,
                ultimo_nsu INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT DEFAULT (datetime('now')),
                UNIQUE(empresa_id),
                FOREIGN KEY(empresa_id) REFERENCES modulo2_empresas(id) ON DELETE CASCADE
            )
        """)
        
        cur.execute("""
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
                orcado REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS modulo2_nfe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa_id INTEGER NOT NULL,
                chave_acesso TEXT UNIQUE NOT NULL,
                nsu INTEGER NOT NULL,
                data_emissao TEXT,
                data_importacao TEXT DEFAULT (datetime('now')),
                valor_total REAL,
                cnpj_emitente TEXT,
                nome_emitente TEXT,
                cnpj_destinatario TEXT,
                nome_destinatario TEXT,
                endereco_entrega TEXT,
                info_adicional TEXT,
                posto_id INTEGER,
                status TEXT DEFAULT 'pendente',
                xml TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(empresa_id) REFERENCES modulo2_empresas(id) ON DELETE CASCADE,
                FOREIGN KEY(posto_id) REFERENCES modulo2_postos_trabalho(id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS modulo2_pendencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nfe_id INTEGER NOT NULL,
                chave_nfe TEXT NOT NULL,
                valor REAL,
                fornecedor TEXT,
                cliente TEXT,
                posto_trabalho TEXT,
                motivo TEXT,
                status TEXT DEFAULT 'pendente',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                resolvido_em TEXT,
                resolvido_por TEXT,
                FOREIGN KEY(nfe_id) REFERENCES modulo2_nfe(id) ON DELETE CASCADE
            )
        """)
        
        # Criar índices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mod2_nfe_chave ON modulo2_nfe(chave_acesso)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mod2_nfe_status ON modulo2_nfe(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mod2_pendencias_status ON modulo2_pendencias(status)")
        
        conn.commit()
        cur.close()
        
        print("[DB] Tabelas fallback criadas com sucesso")
        
        # Seed empresas (carregar do JSON se necessário)
        seed_empresas_from_json(force=False)
        
    except Exception as e:
        print(f"[DB] ERRO no fallback: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ================================
# SEED EMPRESAS DO JSON
# ================================

_seed_empresas_executado = False

def seed_empresas_from_json(force: bool = False):
    """Carrega empresas do arquivo certificados/empresas.json"""
    global _seed_empresas_executado
    
    # Se já foi executado e não é forçado, verificar se há empresas no banco
    if _seed_empresas_executado and not force:
        # Verificar se há empresas no banco
        temp_conn = None
        try:
            temp_conn = get_conn()
            cur = temp_conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM modulo2_empresas")
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            if count > 0:
                print(f"[DB] Empresas já carregadas ({count} empresas). Use force=True para recarregar.")
                return
            else:
                print("[DB] Nenhuma empresa no banco. Forçando recarregamento...")
                # Resetar flag para permitir recarregamento
                _seed_empresas_executado = False
        except Exception as e:
            print(f"[DB] ERRO ao verificar empresas existentes: {e}")
        finally:
            if temp_conn:
                try:
                    temp_conn.close()
                except:
                    pass
    
    conn = None
    try:
        # Encontrar arquivo empresas.json
        json_path = _find_empresas_json()
        
        if not json_path:
            print(f"[DB] ERRO: Arquivo empresas.json não encontrado.")
            print(f"[DB] Diretório atual de trabalho: {Path.cwd()}")
            print(f"[DB] BASE_DIR: {BASE_DIR}")
            print(f"[DB] Tentou encontrar app/main.py como referência para localizar certificados/empresas.json")
            print(f"[DB] Caminhos testados:")
            print(f"  - {Path.cwd() / 'certificados' / 'empresas.json'}")
            print(f"  - {BASE_DIR.parent.parent / 'certificados' / 'empresas.json'}")
            # Não marcar como executado se arquivo não existe (permite tentar novamente)
            return
        
        # json_path já foi logado em _find_empresas_json
        
        print(f"[DB] Carregando empresas de: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        empresas = data.get("empresas", [])
        if not empresas:
            print("[DB] AVISO: Nenhuma empresa encontrada no JSON (lista vazia)")
            _seed_empresas_executado = True
            return
        
        print(f"[DB] Encontradas {len(empresas)} empresas no JSON")
        
        conn = get_conn()
        cur = conn.cursor()
        
        inseridas = 0
        atualizadas = 0
        
        for emp in empresas:
            try:
                cnpj = emp.get("cnpj", "").strip()
                if not cnpj:
                    continue
                
                cur.execute("""
                    INSERT INTO modulo2_empresas (
                        cnpj, razao_social, cert_pfx, cert_senha, uf, sefaz_endpoint
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cnpj) DO UPDATE SET
                        razao_social = excluded.razao_social,
                        cert_pfx = excluded.cert_pfx,
                        cert_senha = excluded.cert_senha,
                        uf = excluded.uf,
                        sefaz_endpoint = excluded.sefaz_endpoint,
                        updated_at = datetime('now')
                """, (
                    cnpj,
                    emp.get("razao_social", ""),
                    emp.get("cert_pfx", ""),
                    emp.get("cert_senha", ""),
                    emp.get("uf", 35),
                    emp.get("sefaz_endpoint", "")
                ))
                
                # Verificar se foi inserção ou atualização
                if cur.lastrowid and cur.lastrowid > 0:
                    inseridas += 1
                elif cur.rowcount > 0:
                    atualizadas += 1
                        
            except Exception as e:
                print(f"[DB] ERRO ao inserir empresa {emp.get('cnpj', 'DESCONHECIDO')}: {e}")
                continue
        
        conn.commit()
        cur.close()
        
        print(f"[DB] Empresas carregadas: {inseridas} inseridas, {atualizadas} atualizadas")
        _seed_empresas_executado = True
        
        # Verificar se realmente foram inseridas empresas
        if inseridas == 0 and atualizadas == 0:
            print("[DB] AVISO: Nenhuma empresa foi inserida ou atualizada. Verifique o JSON.")
        
    except json.JSONDecodeError as e:
        print(f"[DB] ERRO: JSON inválido em empresas.json: {e}")
        import traceback
        traceback.print_exc()
        if not _seed_empresas_executado:
            _seed_empresas_executado = True
    except Exception as e:
        print(f"[DB] ERRO ao carregar empresas do JSON: {e}")
        import traceback
        traceback.print_exc()
        if not _seed_empresas_executado:
            _seed_empresas_executado = True
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ================================
# EMPRESAS
# ================================

def get_empresas() -> List[dict]:
    """Retorna todas as empresas cadastradas"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT id, cnpj, razao_social, cert_pfx, cert_senha, uf, sefaz_endpoint FROM modulo2_empresas")
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            # sqlite3.Row permite acesso direto por nome ou índice
            # Usar acesso direto por nome que funciona com Row
            result.append({
                "id": row["id"],
                "cnpj": row["cnpj"],
                "razao_social": row["razao_social"] if row["razao_social"] else None,
                "cert_pfx": row["cert_pfx"],
                "cert_senha": row["cert_senha"],
                "uf": row["uf"],
                "sefaz_endpoint": row["sefaz_endpoint"] if row["sefaz_endpoint"] else None
            })
        
        cur.close()
        print(f"[DB] get_empresas retornou {len(result)} empresa(s)")
        return result
    except Exception as e:
        print(f"[DB] ERRO ao buscar empresas: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ================================
# NSU / CHECKPOINT
# ================================

def get_ultimo_nsu(cnpj: str) -> int:
    """Retorna o último NSU processado para uma empresa"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Buscar empresa_id pelo CNPJ
        cur.execute("SELECT id FROM modulo2_empresas WHERE cnpj = ?", (cnpj,))
        empresa_row = cur.fetchone()
        
        if not empresa_row:
            cur.close()
            conn.close()
            return 0
        
        empresa_id = empresa_row[0]
        
        # Buscar último NSU
        cur.execute("""
            SELECT ultimo_nsu FROM modulo2_nsu_checkpoint 
            WHERE empresa_id = ?
        """, (empresa_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row and row[0] is not None:
            return int(row[0])
        return 0
        
    except Exception as e:
        print(f"[DB] ERRO ao buscar último NSU: {e}")
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def atualizar_nsu(cnpj: str, ultimo_nsu: int):
    """Atualiza o checkpoint de NSU para uma empresa (função auxiliar, preferir atualizar dentro da mesma transação)"""
    conn = None
    max_retries = 3
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        try:
            conn = get_conn()
            cur = conn.cursor()
            
            # Buscar empresa_id
            cur.execute("SELECT id FROM modulo2_empresas WHERE cnpj = ?", (cnpj,))
            empresa_row = cur.fetchone()
            
            if not empresa_row:
                cur.close()
                conn.close()
                return
            
            empresa_id = empresa_row[0]
            
            # Atualizar ou inserir checkpoint
            cur.execute("""
                INSERT INTO modulo2_nsu_checkpoint (empresa_id, ultimo_nsu, atualizado_em)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(empresa_id) 
                DO UPDATE SET ultimo_nsu = ?, atualizado_em = datetime('now')
            """, (empresa_id, ultimo_nsu, ultimo_nsu))
            
            conn.commit()
            cur.close()
            conn.close()
            return  # Sucesso, sair do loop
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                if conn:
                    try:
                        cur.close()
                        conn.close()
                    except:
                        pass
                import time
                time.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
                continue
            else:
                print(f"[DB] ERRO ao atualizar NSU (tentativa {attempt + 1}/{max_retries}): {e}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
        except Exception as e:
            print(f"[DB] ERRO ao atualizar NSU: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            break
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass


# ================================
# EXTRAIR ITENS DO XML
# ================================

def extrair_itens_xml(root) -> List[dict]:
    """
    Extrai todos os itens/produtos do XML da NFe.
    Retorna lista de dicts com informações de cada item.
    """
    itens = []
    
    # Buscar todos os elementos <det> (detalhe de item)
    for det in root.iter():
        if not det.tag.endswith("det"):
            continue
        
        try:
            # Número do item
            nItem = det.attrib.get("nItem", "0")
            
            item = {
                "numero_item": int(nItem),
                "codigo_produto": "",
                "descricao_produto": "",
                "ncm": "",
                "cfop": "",
                "unidade": "",
                "quantidade": 0.0,
                "valor_unitario": 0.0,
                "valor_total": 0.0,
                "icms_base": 0.0,
                "icms_valor": 0.0,
                "icms_aliquota": 0.0,
                "ipi_valor": 0.0,
                "pis_valor": 0.0,
                "cofins_valor": 0.0
            }
            
            # Buscar elemento <prod> (produto)
            for prod in det:
                if prod.tag.endswith("prod"):
                    for child in prod:
                        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        
                        if tag == "cProd":
                            item["codigo_produto"] = child.text or ""
                        elif tag == "xProd":
                            item["descricao_produto"] = child.text or ""
                        elif tag == "NCM":
                            item["ncm"] = child.text or ""
                        elif tag == "CFOP":
                            item["cfop"] = child.text or ""
                        elif tag == "uCom":
                            item["unidade"] = child.text or ""
                        elif tag == "qCom":
                            try:
                                item["quantidade"] = float(child.text or 0)
                            except:
                                pass
                        elif tag == "vUnCom":
                            try:
                                item["valor_unitario"] = float(child.text or 0)
                            except:
                                pass
                        elif tag == "vProd":
                            try:
                                item["valor_total"] = float(child.text or 0)
                            except:
                                pass
                
                # Buscar impostos
                elif prod.tag.endswith("imposto"):
                    for imposto in prod:
                        tag_imp = imposto.tag.split("}")[-1] if "}" in imposto.tag else imposto.tag
                        
                        # ICMS
                        if tag_imp == "ICMS":
                            for icms_tipo in imposto:
                                for icms_elem in icms_tipo:
                                    tag_icms = icms_elem.tag.split("}")[-1] if "}" in icms_elem.tag else icms_elem.tag
                                    try:
                                        if tag_icms == "vBC":
                                            item["icms_base"] = float(icms_elem.text or 0)
                                        elif tag_icms == "vICMS":
                                            item["icms_valor"] = float(icms_elem.text or 0)
                                        elif tag_icms == "pICMS":
                                            item["icms_aliquota"] = float(icms_elem.text or 0)
                                    except:
                                        pass
                        
                        # IPI
                        elif tag_imp == "IPI":
                            for ipi_elem in imposto.iter():
                                if ipi_elem.tag.endswith("vIPI"):
                                    try:
                                        item["ipi_valor"] = float(ipi_elem.text or 0)
                                    except:
                                        pass
                        
                        # PIS
                        elif tag_imp == "PIS":
                            for pis_elem in imposto.iter():
                                if pis_elem.tag.endswith("vPIS"):
                                    try:
                                        item["pis_valor"] = float(pis_elem.text or 0)
                                    except:
                                        pass
                        
                        # COFINS
                        elif tag_imp == "COFINS":
                            for cofins_elem in imposto.iter():
                                if cofins_elem.tag.endswith("vCOFINS"):
                                    try:
                                        item["cofins_valor"] = float(cofins_elem.text or 0)
                                    except:
                                        pass
            
            itens.append(item)
            
        except Exception as e:
            print(f"[DB] AVISO ao extrair item {nItem}: {e}")
            continue
    
    return itens


# ================================
# SALVAR XMLs / NFe
# ================================

def salvar_xmls_e_nsu(
    cnpj: str,
    xmls: List[Tuple[str, str]],
    ultimo_nsu: int
):
    """
    Salva XMLs no banco e atualiza o NSU.
    xmls: lista de tuplas (nsu, xml_string)
    """
    if not xmls:
        return
    
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Buscar empresa_id
        cur.execute("SELECT id FROM modulo2_empresas WHERE cnpj = ?", (cnpj,))
        empresa_row = cur.fetchone()
        
        if not empresa_row:
            cur.close()
            print(f"[DB] Empresa {cnpj} não encontrada")
            return
        
        empresa_id = empresa_row[0]
        
        # Salvar cada XML
        salvos = 0
        rejeitados_mock = 0
        
        for nsu_str, xml_str in xmls:
            try:
                # Validar XML antes de processar (prevenir dados mock)
                try:
                    from .validacao import validar_xml_recebido
                    is_valid, msg_validacao = validar_xml_recebido(xml_str, int(nsu_str))
                    if not is_valid:
                        print(f"[DB] AVISO: XML NSU {nsu_str} rejeitado: {msg_validacao}")
                        rejeitados_mock += 1
                        continue
                except ImportError:
                    # Se módulo de validação não estiver disponível, continuar sem validação
                    pass
                
                # Parse básico do XML para extrair informações
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_str)
                
                # Extrair chave de acesso
                chave = None
                for elem in root.iter():
                    if elem.tag.endswith("infNFe"):
                        chave = elem.attrib.get("Id", "").replace("NFe", "").replace("NFE", "")
                        break
                
                if not chave:
                    continue
                
                # Extrair outras informações básicas
                valor_total = None
                data_emissao = None
                cnpj_emitente = None
                nome_emitente = None
                
                # Buscar emitente primeiro - tentar diferentes namespaces
                for prefix in ["{http://www.portalfiscal.inf.br/nfe}", "{*}", ""]:
                    emit_elem = root.find(f".//{prefix}emit")
                    if emit_elem is not None:
                        for child in emit_elem:
                            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if tag_name == "CNPJ":
                                cnpj_emitente = child.text
                            elif tag_name == "xNome":
                                nome_emitente = child.text
                        if nome_emitente:
                            break
                
                # Buscar valor total e data
                for elem in root.iter():
                    if elem.tag.endswith("vNF"):
                        try:
                            valor_total = float(elem.text or 0)
                        except:
                            pass
                    elif elem.tag.endswith("dhEmi"):
                        # Formato: 2024-01-15T10:30:00-03:00
                        data_str = elem.text or ""
                        if data_str:
                            try:
                                # Extrair apenas a parte da data (YYYY-MM-DD)
                                if "T" in data_str:
                                    data_emissao = data_str.split("T")[0]
                                elif " " in data_str:
                                    data_emissao = data_str.split(" ")[0]
                                else:
                                    data_emissao = data_str[:10] if len(data_str) >= 10 else None
                            except:
                                pass
                
                # Inserir ou atualizar NFe
                cur.execute("""
                    INSERT INTO modulo2_nfe (
                        empresa_id, chave_acesso, nsu, data_emissao,
                        valor_total, cnpj_emitente, nome_emitente,
                        xml, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
                    ON CONFLICT(chave_acesso) DO NOTHING
                """, (
                    empresa_id, chave, int(nsu_str), data_emissao,
                    valor_total, cnpj_emitente, nome_emitente,
                    xml_str
                ))
                
                if cur.rowcount > 0:
                    salvos += 1
                    
                    # Obter o ID da NFe recém inserida
                    nfe_id = cur.lastrowid
                    
                    # Extrair e salvar itens da NFe
                    try:
                        itens = extrair_itens_xml(root)
                        for item in itens:
                            cur.execute("""
                                INSERT INTO modulo2_nfe_itens (
                                    nfe_id, numero_item, codigo_produto, descricao_produto,
                                    ncm, cfop, unidade, quantidade, valor_unitario, valor_total,
                                    icms_base, icms_valor, icms_aliquota,
                                    ipi_valor, pis_valor, cofins_valor
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                nfe_id, item["numero_item"], item["codigo_produto"],
                                item["descricao_produto"], item["ncm"], item["cfop"],
                                item["unidade"], item["quantidade"], item["valor_unitario"],
                                item["valor_total"], item["icms_base"], item["icms_valor"],
                                item["icms_aliquota"], item["ipi_valor"], item["pis_valor"],
                                item["cofins_valor"]
                            ))
                    except Exception as e:
                        # Se falhar ao salvar itens, não impede o salvamento da NFe
                        print(f"[DB] AVISO ao salvar itens da NFe {chave}: {e}")
                
            except Exception as e:
                print(f"[DB] ERRO ao processar XML (NSU {nsu_str}): {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Atualizar checkpoint NSU dentro da mesma transação (evita database locked)
        try:
            cur.execute("""
                INSERT INTO modulo2_nsu_checkpoint (empresa_id, ultimo_nsu, atualizado_em)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(empresa_id) 
                DO UPDATE SET ultimo_nsu = ?, atualizado_em = datetime('now')
            """, (empresa_id, ultimo_nsu, ultimo_nsu))
        except Exception as e:
            print(f"[DB] AVISO ao atualizar NSU na mesma transação: {e}")
            # Continuar mesmo se NSU update falhar - XMLs já foram salvos
        
        # Commit de tudo de uma vez
        conn.commit()
        cur.close()
        
        total_processados = salvos + rejeitados_mock
        if rejeitados_mock > 0:
            print(f"[DB] {salvos} XMLs salvos para empresa {cnpj} (de {len(xmls)} recebidos, {rejeitados_mock} rejeitados por validação)")
        else:
            print(f"[DB] {salvos} XMLs salvos para empresa {cnpj} (de {len(xmls)} recebidos)")
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print(f"[DB] AVISO: Database temporariamente bloqueado. Tentando novamente após delay...")
            if conn:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                    cur.close()
                    conn.close()
                except:
                    pass
            # Retry uma vez após delay
            time.sleep(0.2)
            # Tentar novamente (mas limitar para evitar loop infinito)
            try:
                return salvar_xmls_e_nsu(cnpj, xmls, ultimo_nsu)
            except:
                print(f"[DB] ERRO: Falha no retry. Continuando sem salvar este lote.")
                return
        else:
            print(f"[DB] ERRO ao salvar XMLs: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
    except Exception as e:
        print(f"[DB] ERRO ao salvar XMLs: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ================================
# POSTOS DE TRABALHO
# ================================

def listar_postos_db() -> List[dict]:
    """Lista todos os postos de trabalho"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, codigo, nomecli, nomepos, end, bairro, cep, nomecid, estado
            FROM modulo2_postos_trabalho
            ORDER BY nomecli, nomepos
        """)
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            # Converter Row para dict para acesso seguro
            r = _row_to_dict(row)
            result.append({
                "id": r["id"],
                "codigo": r.get("codigo"),
                "nomecli": r["nomecli"],
                "nomepos": r["nomepos"],
                "end": r.get("end"),
                "bairro": r.get("bairro"),
                "cep": r.get("cep"),
                "nomecid": r.get("nomecid"),
                "estado": r.get("estado")
            })
        
        cur.close()
        return result
    except Exception as e:
        print(f"[DB] ERRO ao listar postos: {e}")
        return []
    finally:
        if conn:
            conn.close()


def salvar_posto(posto_data: dict) -> Optional[int]:
    """Salva ou atualiza um posto de trabalho. Retorna o ID."""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO modulo2_postos_trabalho (
                codigo, nomecli, nomepos, end, bairro, cep, nomecid, estado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(codigo) DO UPDATE SET
                nomecli = excluded.nomecli,
                nomepos = excluded.nomepos,
                end = excluded.end,
                bairro = excluded.bairro,
                cep = excluded.cep,
                nomecid = excluded.nomecid,
                estado = excluded.estado,
                updated_at = datetime('now')
        """, (
            posto_data.get("codigo"),
            posto_data.get("nomecli", ""),
            posto_data.get("nomepos", ""),
            posto_data.get("end"),
            posto_data.get("bairro"),
            posto_data.get("cep"),
            posto_data.get("nomecid"),
            posto_data.get("estado")
        ))
        
        # Buscar ID
        if posto_data.get("codigo"):
            cur.execute("SELECT id FROM modulo2_postos_trabalho WHERE codigo = ?", 
                       (posto_data.get("codigo"),))
        else:
            posto_id = cur.lastrowid
            conn.commit()
            cur.close()
            return posto_id
        
        row = cur.fetchone()
        posto_id = row[0] if row else None
        
        conn.commit()
        cur.close()
        
        return posto_id
        
    except Exception as e:
        print(f"[DB] ERRO ao salvar posto: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


# ================================
# ORÇADO POR POSTO
# ================================

def salvar_orcado_posto(posto_id: int, valor_orcado: float, ano_mes: str = None) -> bool:
    """
    Salva ou atualiza valor orçado de um posto.
    Se ano_mes não for fornecido, usa o mês atual.
    """
    from datetime import datetime
    
    if ano_mes is None:
        ano_mes = datetime.now().strftime("%Y-%m")
    
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO modulo2_orcado_posto (posto_id, valor_orcado, ano_mes, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(posto_id, ano_mes) 
            DO UPDATE SET 
                valor_orcado = excluded.valor_orcado,
                updated_at = datetime('now')
        """, (posto_id, valor_orcado, ano_mes))
        
        conn.commit()
        cur.close()
        return True
        
    except Exception as e:
        print(f"[DB] ERRO ao salvar orçado do posto: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def listar_orcado_por_cliente(ano_mes: str = None) -> Dict[str, float]:
    """
    Lista orçado agrupado por cliente (nomecli).
    Retorna dict: {nomecli: total_orcado}
    """
    from datetime import datetime
    
    if ano_mes is None:
        ano_mes = datetime.now().strftime("%Y-%m")
    
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                pt.nomecli,
                COALESCE(SUM(op.valor_orcado), 0) as total_orcado
            FROM modulo2_orcado_posto op
            INNER JOIN modulo2_postos_trabalho pt ON op.posto_id = pt.id
            WHERE op.ano_mes = ? OR op.ano_mes IS NULL
            GROUP BY pt.nomecli
        """, (ano_mes,))
        
        rows = cur.fetchall()
        result = {}
        
        for row in rows:
            r = _row_to_dict(row)
            nomecli = r.get("nomecli", "")
            if nomecli:
                result[nomecli] = float(r.get("total_orcado", 0) or 0)
        
        cur.close()
        return result
        
    except Exception as e:
        print(f"[DB] ERRO ao listar orçado por cliente: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def listar_orcado_por_posto(posto_id: int = None, ano_mes: str = None) -> List[dict]:
    """
    Lista valores orçados por posto.
    Se posto_id fornecido, retorna apenas aquele posto.
    Se ano_mes fornecido, filtra por mês específico.
    """
    from datetime import datetime
    
    if ano_mes is None:
        ano_mes = datetime.now().strftime("%Y-%m")
    
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if posto_id:
            query = """
                SELECT 
                    op.id,
                    op.posto_id,
                    pt.nomecli,
                    pt.nomepos,
                    op.valor_orcado,
                    op.ano_mes,
                    op.created_at,
                    op.updated_at
                FROM modulo2_orcado_posto op
                INNER JOIN modulo2_postos_trabalho pt ON op.posto_id = pt.id
                WHERE op.posto_id = ? AND (op.ano_mes = ? OR op.ano_mes IS NULL)
            """
            params = (posto_id, ano_mes)
        else:
            query = """
                SELECT 
                    op.id,
                    op.posto_id,
                    pt.nomecli,
                    pt.nomepos,
                    op.valor_orcado,
                    op.ano_mes,
                    op.created_at,
                    op.updated_at
                FROM modulo2_orcado_posto op
                INNER JOIN modulo2_postos_trabalho pt ON op.posto_id = pt.id
                WHERE op.ano_mes = ? OR op.ano_mes IS NULL
                ORDER BY pt.nomecli, pt.nomepos
            """
            params = (ano_mes,)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            r = _row_to_dict(row)
            result.append({
                "id": r.get("id"),
                "posto_id": r.get("posto_id"),
                "nomecli": r.get("nomecli"),
                "nomepos": r.get("nomepos"),
                "valor_orcado": float(r.get("valor_orcado", 0) or 0),
                "ano_mes": r.get("ano_mes"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at")
            })
        
        cur.close()
        return result
        
    except Exception as e:
        print(f"[DB] ERRO ao listar orçado por posto: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ================================
# PENDÊNCIAS
# ================================

def listar_pendencias_db(limit: int = 500, data_ini: date = None, data_fim: date = None) -> List[dict]:
    """Lista pendências de identificação de posto com filtro opcional por data"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        query = """
            SELECT 
                p.id,
                p.chave_nfe,
                p.valor,
                p.fornecedor,
                p.cliente,
                p.posto_trabalho,
                p.motivo,
                p.status,
                p.created_at,
                n.data_emissao,
                n.nome_emitente
            FROM modulo2_pendencias p
            LEFT JOIN modulo2_nfe n ON n.chave_acesso = p.chave_nfe
            WHERE p.status = 'pendente'
        """
        
        params = []
        
        # Adicionar filtro de data se fornecido
        if data_ini:
            query += " AND (n.data_emissao >= ? OR n.data_emissao IS NULL)"
            params.append(str(data_ini))
        
        if data_fim:
            query += " AND (n.data_emissao <= ? OR n.data_emissao IS NULL)"
            params.append(str(data_fim))
        
        query += " ORDER BY p.created_at DESC LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        
        # Converter para formato esperado pelo frontend
        result = []
        for row in rows:
            # Converter Row para dict para acesso seguro
            r = _row_to_dict(row)
            result.append({
                "id": r["id"],
                "chave_nfe": r.get("chave_nfe", ""),
                "valor": float(r.get("valor", 0)) if r.get("valor") else 0,
                "fornecedor": r.get("nome_emitente") or r.get("fornecedor", ""),
                "cliente": r.get("cliente", ""),
                "posto_trabalho": r.get("posto_trabalho", ""),
                "motivo": r.get("motivo", ""),
                "status": r.get("status", "pendente"),
                "data_emissao": str(r.get("data_emissao", "")) if r.get("data_emissao") else ""
            })
        
        return result
        
    except Exception as e:
        print(f"[DB] ERRO ao listar pendências: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def criar_pendencia(nfe_id: int, chave_nfe: str, valor: float, fornecedor: str, motivo: str):
    """Cria uma pendência para uma NFe não identificada"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Verificar se já existe
        cur.execute("SELECT id FROM modulo2_pendencias WHERE chave_nfe = ? AND status = 'pendente'", 
                   (chave_nfe,))
        if cur.fetchone():
            cur.close()
            return  # Já existe pendência ativa
        
        cur.execute("""
            INSERT INTO modulo2_pendencias (
                nfe_id, chave_nfe, valor, fornecedor, motivo, status
            )
            VALUES (?, ?, ?, ?, ?, 'pendente')
        """, (nfe_id, chave_nfe, valor, fornecedor, motivo))
        
        conn.commit()
        cur.close()
        
    except Exception as e:
        print(f"[DB] ERRO ao criar pendência: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def atualizar_pendencia_com_posto(pendencia_id: int, posto_id: int, cliente_nome: str):
    """Atualiza uma pendência identificando o posto"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Buscar NFe relacionada
        cur.execute("SELECT nfe_id FROM modulo2_pendencias WHERE id = ?", (pendencia_id,))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            return False
        
        nfe_id = row[0]
        
        # Atualizar NFe com posto_id
        cur.execute("""
            UPDATE modulo2_nfe 
            SET posto_id = ?, status = 'identificado', updated_at = datetime('now')
            WHERE id = ?
        """, (posto_id, nfe_id))
        
        # Atualizar pendência
        cur.execute("""
            UPDATE modulo2_pendencias
            SET status = 'resolvida', cliente = ?, resolvido_em = datetime('now'), updated_at = datetime('now')
            WHERE id = ?
        """, (cliente_nome, pendencia_id))
        
        conn.commit()
        cur.close()
        
        return True
        
    except Exception as e:
        print(f"[DB] ERRO ao atualizar pendência: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


# ================================
# CONSULTA POR INTERVALO DE DATAS
# ================================

def consultar_nfes_por_data(data_ini: date, data_fim: date) -> List[dict]:
    """Consulta NFes por intervalo de datas"""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT chave_acesso, nsu, data_emissao, valor_total, nome_emitente
            FROM modulo2_nfe
            WHERE data_emissao >= ? AND data_emissao <= ?
            ORDER BY data_emissao, nsu
        """, (str(data_ini), str(data_fim)))
        
        rows = cur.fetchall()
        cur.close()
        
        result = []
        for row in rows:
            # Converter Row para dict para acesso seguro
            r = _row_to_dict(row)
            result.append({
                "chave_acesso": r["chave_acesso"],
                "nsu": r["nsu"],
                "data_emissao": r.get("data_emissao"),
                "valor_total": float(r.get("valor_total", 0)) if r.get("valor_total") else 0,
                "nome_emitente": r.get("nome_emitente")
            })
        
        return result
        
    except Exception as e:
        print(f"[DB] ERRO ao consultar NFes por data: {e}")
        return []
    finally:
        if conn:
            conn.close()

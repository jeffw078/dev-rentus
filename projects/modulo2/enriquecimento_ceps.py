"""
Módulo de Enriquecimento Automático de CEPs
Consulta APIs e atualiza base de postos durante importação de XMLs
"""
import requests
import re
import time
from typing import Optional, Dict, Tuple
from .db import get_conn
from .utils import normalizar_forte


# ============================================
# CONSULTA DE CEP VIA API
# ============================================

def consultar_viacep(cep: str, usar_cache: bool = True) -> Optional[Dict]:
    """
    Consulta CEP na API ViaCEP com cache
    
    Args:
        cep: CEP a consultar (com ou sem formatação)
        usar_cache: Se deve usar cache local
    
    Returns:
        Dict com dados do CEP ou None se não encontrado
    """
    # Limpar CEP
    cep_limpo = re.sub(r'\D', '', cep)
    
    if len(cep_limpo) != 8:
        return None
    
    # Verificar cache primeiro
    if usar_cache:
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT logradouro, complemento, bairro, localidade, uf, ddd, ibge, valido
            FROM modulo2_cache_ceps
            WHERE cep = ?
        """, (cep_limpo,))
        
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if resultado:
            logr, compl, bairro, cidade, uf, ddd, ibge, valido = resultado
            
            # Se estava marcado como inválido, retornar None
            if not valido:
                return None
            
            return {
                'cep': cep_limpo,
                'logradouro': logr,
                'complemento': compl,
                'bairro': bairro,
                'localidade': cidade,
                'uf': uf,
                'ddd': ddd,
                'ibge': ibge,
                'cached': True
            }
    
    # Consultar API
    try:
        print(f"[ENRIQUECIMENTO] Consultando ViaCEP: {cep_limpo}")
        url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        dados = response.json()
        
        # Verificar se CEP existe
        if 'erro' in dados and dados['erro']:
            # Cachear como inválido
            _cachear_cep_invalido(cep_limpo)
            return None
        
        # Cachear resultado válido
        _cachear_cep(cep_limpo, dados)
        
        dados['cached'] = False
        return dados
        
    except requests.exceptions.Timeout:
        print(f"[ENRIQUECIMENTO] ⚠️  Timeout ao consultar CEP {cep_limpo}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ENRIQUECIMENTO] ⚠️  Erro ao consultar CEP {cep_limpo}: {e}")
        return None
    except Exception as e:
        print(f"[ENRIQUECIMENTO] ⚠️  Erro inesperado ao consultar CEP {cep_limpo}: {e}")
        return None


def _cachear_cep(cep: str, dados: Dict):
    """Armazena CEP válido no cache"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO modulo2_cache_ceps 
            (cep, logradouro, complemento, bairro, localidade, uf, ddd, ibge, valido)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(cep) DO UPDATE SET
                logradouro = excluded.logradouro,
                complemento = excluded.complemento,
                bairro = excluded.bairro,
                localidade = excluded.localidade,
                uf = excluded.uf,
                ddd = excluded.ddd,
                ibge = excluded.ibge,
                valido = 1,
                consultado_em = datetime('now')
        """, (
            cep,
            dados.get('logradouro'),
            dados.get('complemento'),
            dados.get('bairro'),
            dados.get('localidade'),
            dados.get('uf'),
            dados.get('ddd'),
            dados.get('ibge')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[ENRIQUECIMENTO] Erro ao cachear CEP: {e}")


def _cachear_cep_invalido(cep: str):
    """Marca CEP como inválido no cache para não consultar novamente"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO modulo2_cache_ceps (cep, valido)
            VALUES (?, 0)
            ON CONFLICT(cep) DO UPDATE SET
                valido = 0,
                consultado_em = datetime('now')
        """, (cep,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[ENRIQUECIMENTO] Erro ao cachear CEP inválido: {e}")


# ============================================
# MATCHING DE POSTOS
# ============================================

def buscar_posto_similar(nome: str = None, endereco: str = None, cidade: str = None, 
                         cep: str = None, threshold: int = 70) -> Optional[Dict]:
    """
    Busca posto similar no cadastro usando diferentes critérios
    
    Args:
        nome: Nome do posto (extraído de infCpl)
        endereco: Endereço completo
        cidade: Cidade
        cep: CEP
        threshold: Score mínimo para considerar match (0-100)
    
    Returns:
        Dict com dados do posto mais similar ou None
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, codigo, nomecli, nomepos, end, bairro, cep, nomecid, estado
        FROM modulo2_postos_trabalho
    """)
    
    postos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not postos:
        return None
    
    melhor_match = None
    melhor_score = 0
    
    for posto in postos:
        posto_id, codigo, nomecli, nomepos, end_posto, bairro_posto, cep_posto, cidade_posto, uf = posto
        
        score = 0
        
        # Match por CEP (peso alto - 40 pontos)
        if cep and cep_posto:
            cep_limpo = re.sub(r'\D', '', cep)
            cep_posto_limpo = re.sub(r'\D', '', cep_posto)
            
            if cep_limpo == cep_posto_limpo:
                score += 40
        
        # Match por nome do posto (peso médio-alto - 35 pontos)
        if nome and nomepos:
            nome_norm = normalizar_forte(nome)
            nomepos_norm = normalizar_forte(nomepos)
            
            if nome_norm and nomepos_norm:
                # Match exato
                if nome_norm == nomepos_norm:
                    score += 35
                # Substring
                elif nome_norm in nomepos_norm or nomepos_norm in nome_norm:
                    score += 25
                # Palavras em comum
                else:
                    palavras_nome = set(nome_norm.split())
                    palavras_posto = set(nomepos_norm.split())
                    if palavras_nome and palavras_posto:
                        palavras_comuns = palavras_nome & palavras_posto
                        if palavras_comuns:
                            score += int(len(palavras_comuns) / max(len(palavras_nome), len(palavras_posto)) * 20)
        
        # Match por endereço (peso médio - 15 pontos)
        if endereco and end_posto:
            end_norm = normalizar_forte(endereco)
            end_posto_norm = normalizar_forte(end_posto)
            
            if end_norm and end_posto_norm:
                if end_norm in end_posto_norm or end_posto_norm in end_norm:
                    score += 15
        
        # Match por cidade (peso baixo - 10 pontos)
        if cidade and cidade_posto:
            cidade_norm = normalizar_forte(cidade)
            cidade_posto_norm = normalizar_forte(cidade_posto)
            
            if cidade_norm == cidade_posto_norm:
                score += 10
        
        # Atualizar melhor match
        if score > melhor_score and score >= threshold:
            melhor_score = score
            melhor_match = {
                'id': posto_id,
                'codigo': codigo,
                'nomecli': nomecli,
                'nomepos': nomepos,
                'end': end_posto,
                'bairro': bairro_posto,
                'cep': cep_posto,
                'nomecid': cidade_posto,
                'estado': uf,
                'score': score
            }
    
    return melhor_match


# ============================================
# ATUALIZAÇÃO DE POSTOS
# ============================================

def atualizar_cep_posto(posto_id: int, cep_novo: str, nfe_id: int = None) -> bool:
    """
    Atualiza CEP de um posto existente e registra log
    
    Args:
        posto_id: ID do posto a atualizar
        cep_novo: Novo CEP
        nfe_id: ID da NFe que originou a atualização (opcional)
    
    Returns:
        True se atualizou com sucesso
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Buscar CEP atual
        cursor.execute("SELECT cep FROM modulo2_postos_trabalho WHERE id = ?", (posto_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            cursor.close()
            conn.close()
            return False
        
        cep_antigo = resultado[0]
        
        # Se CEP já está igual, não fazer nada
        if cep_antigo == cep_novo:
            cursor.close()
            conn.close()
            return False
        
        # Atualizar CEP
        cursor.execute("""
            UPDATE modulo2_postos_trabalho
            SET cep = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (cep_novo, posto_id))
        
        # Registrar log de enriquecimento
        cursor.execute("""
            INSERT INTO modulo2_log_enriquecimento
            (posto_id, campo_atualizado, valor_antigo, valor_novo, fonte, nfe_id)
            VALUES (?, 'cep', ?, ?, 'xml+api', ?)
        """, (posto_id, cep_antigo, cep_novo, nfe_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[ENRIQUECIMENTO] [OK] CEP atualizado - Posto {posto_id}: {cep_antigo or '(vazio)'} -> {cep_novo}")
        
        return True
        
    except Exception as e:
        print(f"[ENRIQUECIMENTO] Erro ao atualizar CEP do posto {posto_id}: {e}")
        return False


def criar_posto_sugerido(nome: str = None, logradouro: str = None, numero: str = None,
                         complemento: str = None, bairro: str = None, cidade: str = None,
                         uf: str = None, cep: str = None, nfe_id: int = None, 
                         chave_nfe: str = None) -> bool:
    """
    Cria sugestão de novo posto encontrado em XML
    
    Args:
        nome: Nome do posto (extraído de infCpl)
        logradouro, numero, complemento, bairro, cidade, uf, cep: Dados do endereço
        nfe_id: ID da NFe que originou a sugestão
        chave_nfe: Chave da NFe (para referência)
    
    Returns:
        True se criou com sucesso
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO modulo2_postos_sugeridos
            (nome_sugerido, logradouro, numero, complemento, bairro, cidade, uf, cep, 
             fonte_xml, nfe_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
        """, (nome, logradouro, numero, complemento, bairro, cidade, uf, cep, 
              chave_nfe, nfe_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[ENRIQUECIMENTO] [NOVO] Posto sugerido criado: {nome or logradouro} - {cidade}/{uf}")
        
        return True
        
    except Exception as e:
        print(f"[ENRIQUECIMENTO] Erro ao criar posto sugerido: {e}")
        return False


# ============================================
# ESTATÍSTICAS E RELATÓRIOS
# ============================================

def obter_estatisticas_enriquecimento() -> Dict:
    """
    Retorna estatísticas sobre o enriquecimento de CEPs
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    stats = {}
    
    # CEPs em cache
    cursor.execute("SELECT COUNT(*) FROM modulo2_cache_ceps WHERE valido = 1")
    stats['ceps_cache'] = cursor.fetchone()[0]
    
    # Postos atualizados
    cursor.execute("SELECT COUNT(DISTINCT posto_id) FROM modulo2_log_enriquecimento WHERE campo_atualizado = 'cep'")
    stats['postos_atualizados'] = cursor.fetchone()[0]
    
    # Postos sugeridos
    cursor.execute("SELECT COUNT(*) FROM modulo2_postos_sugeridos WHERE status = 'pendente'")
    stats['postos_sugeridos_pendentes'] = cursor.fetchone()[0]
    
    # Postos sem CEP
    cursor.execute("SELECT COUNT(*) FROM modulo2_postos_trabalho WHERE cep IS NULL OR cep = ''")
    stats['postos_sem_cep'] = cursor.fetchone()[0]
    
    # Postos com CEP
    cursor.execute("SELECT COUNT(*) FROM modulo2_postos_trabalho WHERE cep IS NOT NULL AND cep != ''")
    stats['postos_com_cep'] = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return stats

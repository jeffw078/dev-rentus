"""
Integração do Enriquecimento com Processamento de XMLs
Processa cada XML importado para enriquecer base de postos
"""
import xml.etree.ElementTree as ET
import re
from typing import Optional, Dict, Tuple
from .enriquecimento_ceps import (
    consultar_viacep,
    buscar_posto_similar,
    atualizar_cep_posto,
    criar_posto_sugerido
)


def processar_enriquecimento_xml(xml_string: str, nfe_id: int = None, chave_nfe: str = None) -> Dict:
    """
    Processa um XML de NFe para enriquecer base de postos com CEPs
    
    Extrai endereço de entrega, consulta CEP se necessário,
    tenta identificar posto existente e atualiza ou sugere novo.
    
    Args:
        xml_string: String com XML da NFe
        nfe_id: ID da NFe no banco (opcional)
        chave_nfe: Chave da NFe (opcional)
    
    Returns:
        Dict com resultado do processamento:
        {
            'success': bool,
            'cep_atualizado': bool,
            'posto_sugerido': bool,
            'posto_id': int (se encontrou),
            'mensagem': str
        }
    """
    resultado = {
        'success': False,
        'cep_atualizado': False,
        'posto_sugerido': False,
        'posto_id': None,
        'mensagem': ''
    }
    
    try:
        root = ET.fromstring(xml_string)
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # ============================================
        # 1. EXTRAIR DADOS DO XML
        # ============================================
        
        # Extrair enderDest (endereço de entrega) - PRIORIDADE 1
        dados_endereco = _extrair_endereco_entrega(root, ns)
        
        # Extrair infCpl (informações complementares) - PRIORIDADE 2
        infcpl = _extrair_infcpl(root, ns)
        nome_posto = _extrair_nome_posto_de_infcpl(infcpl)
        
        if not dados_endereco:
            resultado['mensagem'] = 'Endereço de entrega não encontrado no XML'
            return resultado
        
        # ============================================
        # 2. VALIDAR/OBTER CEP
        # ============================================
        
        cep = dados_endereco.get('cep')
        
        # Se não tem CEP no XML, tentar consultar API com endereço
        if not cep or len(re.sub(r'\D', '', cep)) != 8:
            # Aqui poderíamos implementar busca reversa, mas por ora pulamos
            resultado['mensagem'] = 'CEP não encontrado ou inválido no XML'
            return resultado
        
        # Validar CEP via API (e cachear)
        cep_limpo = re.sub(r'\D', '', cep)
        dados_cep = consultar_viacep(cep_limpo, usar_cache=True)
        
        if not dados_cep:
            resultado['mensagem'] = f'CEP {cep_limpo} inválido ou não encontrado'
            return resultado
        
        # ============================================
        # 3. BUSCAR POSTO SIMILAR NO CADASTRO
        # ============================================
        
        posto_similar = buscar_posto_similar(
            nome=nome_posto,
            endereco=dados_endereco.get('logradouro'),
            cidade=dados_endereco.get('cidade'),
            cep=cep_limpo,
            threshold=70  # Score mínimo 70%
        )
        
        if posto_similar:
            # Posto encontrado!
            resultado['posto_id'] = posto_similar['id']
            resultado['success'] = True
            
            # Verificar se precisa atualizar CEP
            cep_atual = posto_similar.get('cep')
            
            if not cep_atual or cep_atual == '' or cep_atual == '00000000':
                # Posto não tem CEP - ATUALIZAR
                if atualizar_cep_posto(posto_similar['id'], cep_limpo, nfe_id):
                    resultado['cep_atualizado'] = True
                    resultado['mensagem'] = f"CEP atualizado no posto: {posto_similar['nomepos']}"
                else:
                    resultado['mensagem'] = f"Posto encontrado mas falhou ao atualizar CEP: {posto_similar['nomepos']}"
            else:
                resultado['mensagem'] = f"Posto encontrado (já tem CEP): {posto_similar['nomepos']}"
        
        else:
            # Posto NÃO encontrado - criar sugestão
            if criar_posto_sugerido(
                nome=nome_posto,
                logradouro=dados_endereco.get('logradouro'),
                numero=dados_endereco.get('numero'),
                complemento=dados_endereco.get('complemento'),
                bairro=dados_endereco.get('bairro'),
                cidade=dados_endereco.get('cidade'),
                uf=dados_endereco.get('uf'),
                cep=cep_limpo,
                nfe_id=nfe_id,
                chave_nfe=chave_nfe
            ):
                resultado['posto_sugerido'] = True
                resultado['success'] = True
                resultado['mensagem'] = f"Novo posto sugerido: {nome_posto or dados_endereco.get('cidade')}"
            else:
                resultado['mensagem'] = "Falhou ao criar posto sugerido"
        
        return resultado
        
    except Exception as e:
        resultado['mensagem'] = f"Erro ao processar enriquecimento: {e}"
        print(f"[ENRIQUECIMENTO] ❌ {resultado['mensagem']}")
        return resultado


# ============================================
# FUNÇÕES AUXILIARES DE EXTRAÇÃO
# ============================================

def _extrair_endereco_entrega(root, ns) -> Optional[Dict]:
    """
    Extrai endereço de entrega do XML (enderDest)
    """
    try:
        enderdest = root.find('.//nfe:dest/nfe:enderDest', ns)
        
        if enderdest is None:
            return None
        
        endereco = {}
        
        # Logradouro
        logr = enderdest.find('nfe:xLgr', ns)
        if logr is not None and logr.text:
            endereco['logradouro'] = logr.text.strip()
        
        # Número
        nro = enderdest.find('nfe:nro', ns)
        if nro is not None and nro.text:
            endereco['numero'] = nro.text.strip()
        
        # Complemento
        compl = enderdest.find('nfe:xCpl', ns)
        if compl is not None and compl.text:
            endereco['complemento'] = compl.text.strip()
        
        # Bairro
        bairro = enderdest.find('nfe:xBairro', ns)
        if bairro is not None and bairro.text:
            endereco['bairro'] = bairro.text.strip()
        
        # Município
        mun = enderdest.find('nfe:xMun', ns)
        if mun is not None and mun.text:
            endereco['cidade'] = mun.text.strip()
        
        # UF
        uf = enderdest.find('nfe:UF', ns)
        if uf is not None and uf.text:
            endereco['uf'] = uf.text.strip()
        
        # CEP
        cep = enderdest.find('nfe:CEP', ns)
        if cep is not None and cep.text:
            endereco['cep'] = cep.text.strip()
        
        return endereco if endereco else None
        
    except Exception as e:
        print(f"[ENRIQUECIMENTO] Erro ao extrair enderDest: {e}")
        return None


def _extrair_infcpl(root, ns) -> str:
    """
    Extrai informações complementares do XML (infCpl)
    """
    try:
        infcpl_elem = root.find('.//nfe:infCpl', ns)
        if infcpl_elem is not None and infcpl_elem.text:
            return infcpl_elem.text.strip()
        return ""
    except:
        return ""


def _extrair_nome_posto_de_infcpl(infcpl: str) -> Optional[str]:
    """
    Tenta extrair nome do posto das informações complementares
    
    Padrões comuns:
    - "LOCAL DE ENTREGA: [nome do posto]"
    - "POSTO: [nome]"
    - "ENTREGA EM: [nome]"
    - "ENTREGAR EM: [nome]"
    """
    if not infcpl:
        return None
    
    # Lista de padrões para buscar
    padroes = [
        r'LOCAL\s+DE\s+ENTREGA\s*:\s*([^\n\r;]+)',
        r'POSTO\s*:\s*([^\n\r;]+)',
        r'ENTREGA\s+EM\s*:\s*([^\n\r;]+)',
        r'ENTREGAR\s+EM\s*:\s*([^\n\r;]+)',
        r'DESTINAT[AÁ]RIO\s*:\s*([^\n\r;]+)',
        r'ENDERE[CÇ]O\s+DE\s+ENTREGA\s*:\s*([^\n\r;]+)',
    ]
    
    for padrao in padroes:
        match = re.search(padrao, infcpl, re.IGNORECASE)
        if match:
            nome = match.group(1).strip()
            # Limpar pontuação extra
            nome = re.sub(r'\s+', ' ', nome)
            return nome[:200]  # Limitar tamanho
    
    return None


# ============================================
# FUNÇÃO PARA PROCESSAR EM LOTE
# ============================================

def processar_enriquecimento_lote(nfes: list, delay: float = 0.5) -> Dict:
    """
    Processa enriquecimento para múltiplas NFes em lote
    
    Args:
        nfes: Lista de tuplas (xml, nfe_id, chave)
        delay: Delay entre requisições à API (segundos)
    
    Returns:
        Dict com estatísticas do processamento
    """
    import time
    
    stats = {
        'total': len(nfes),
        'processados': 0,
        'ceps_atualizados': 0,
        'postos_sugeridos': 0,
        'erros': 0
    }
    
    for xml, nfe_id, chave in nfes:
        resultado = processar_enriquecimento_xml(xml, nfe_id, chave)
        
        stats['processados'] += 1
        
        if resultado['success']:
            if resultado['cep_atualizado']:
                stats['ceps_atualizados'] += 1
            if resultado['posto_sugerido']:
                stats['postos_sugeridos'] += 1
        else:
            stats['erros'] += 1
        
        # Delay para não sobrecarregar API
        if delay > 0:
            time.sleep(delay)
    
    return stats

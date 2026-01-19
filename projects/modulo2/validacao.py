# projects/modulo2/validacao.py

"""
Validações para prevenir dados mock e garantir qualidade dos dados recebidos.
"""

from .config import DEV_MODE

# Fornecedores mockados conhecidos (para rejeitar em produção)
FORNECEDORES_MOCK = [
    "FORNECEDOR ABC LTDA",
    "SUPPLY COMPANY XYZ",
    "SUPPLY COMANY XYZ",  # Versão com erro de digitação
    "DISTRIBUIDORA 123",
    "COMERCIAL DEF LTDA"
]


def validar_nome_emitente(nome_emitente: str) -> tuple[bool, str]:
    """
    Valida se o nome do emitente não é mock.
    Em DEV_MODE, aceita nomes mockados.
    
    Returns:
        (is_valid, mensagem)
    """
    if not nome_emitente:
        return True, ""  # Nome vazio é permitido (será preenchido depois)
    
    # Em modo DEV, aceitar qualquer nome (incluindo mocks)
    if DEV_MODE:
        return True, ""
    
    nome_upper = nome_emitente.upper().strip()
    
    # Verificar se contém algum nome mock conhecido
    for fornecedor_mock in FORNECEDORES_MOCK:
        if fornecedor_mock.upper() in nome_upper:
            return False, f"Nome mock detectado: {fornecedor_mock}"
    
    return True, ""


def validar_xml_recebido(xml_string: str, nsu: int = None):
    """
    Valida se o XML recebido parece ser válido e não mock.
    Em DEV_MODE, aceita todos os XMLs (incluindo mocks).
    
    Returns:
        (is_valid, mensagem)
    """
    # Em modo DEV, aceitar qualquer XML
    if DEV_MODE:
        return True, ""
    
    import xml.etree.ElementTree as ET
    
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        return False, f"XML inválido (erro de parse): {str(e)[:100]}"
    
    # Verificar se tem estrutura básica de NFe
    if not root.findall(".//{*}infNFe") and not root.findall(".//{*}NFe") and not root.findall(".//infNFe"):
        return False, "XML não parece ser uma NFe válida (sem infNFe)"
    
    # Extrair nome do emitente e validar
    nome_emitente = None
    for prefix in ["{http://www.portalfiscal.inf.br/nfe}", "{*}", ""]:
        emit_elem = root.find(f".//{prefix}emit")
        if emit_elem is not None:
            for child in emit_elem:
                tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag_name == "xNome":
                    nome_emitente = child.text
                    break
            if nome_emitente:
                break
    
    if nome_emitente:
        is_valid, msg = validar_nome_emitente(nome_emitente)
        if not is_valid:
            return False, msg
    
    # Verificar chave de acesso (deve ter 44 caracteres)
    chave = None
    for elem in root.iter():
        if elem.tag.endswith("infNFe"):
            chave = elem.attrib.get("Id", "").replace("NFe", "").replace("NFE", "")
            if chave:
                break
    
    if chave and len(chave) != 44:
        return False, f"Chave de acesso inválida (tamanho: {len(chave)}, esperado: 44)"
    
    return True, ""

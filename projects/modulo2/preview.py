# projects/modulo2/preview.py

from datetime import date, datetime
from typing import Dict, List, Set, Tuple
import xml.etree.ElementTree as ET
import time
import random

from .config import DEV_MODE
from .db import get_empresas, get_ultimo_nsu, atualizar_nsu
from .rate_limiter import wait_before_sefaz_request, get_rate_limiter
from .utils import obter_periodo_ano_atual
from .preview_cache import get_preview_cache

# Importar SEFAZClient apenas se disponível
try:
    from .sefaz_client import SEFAZClient
except ImportError:
    SEFAZClient = None


def consultar_com_auto_recuperacao_nsu(client, cnpj: str, ultimo_nsu: int, max_iteracoes: int = 20, atualizar_banco: bool = False) -> Tuple[List[dict], int]:
    """
    Consulta SEFAZ com proteção automática contra NSU desatualizado.
    
    Se receber erro 656 indicando NSU desatualizado:
    1. Captura o NSU correto retornado pelo SEFAZ
    2. [OPCIONAL] Atualiza no banco de dados (só se atualizar_banco=True)
    3. Tenta novamente UMA VEZ com o NSU correto
    
    Args:
        client: Cliente SEFAZ configurado
        cnpj: CNPJ da empresa
        ultimo_nsu: NSU inicial para busca
        max_iteracoes: Máximo de iterações na busca completa
        atualizar_banco: Se True, persiste NSU corrigido no banco (usado na importação real)
                        Se False, só usa NSU em memória (usado no preview)
    
    Returns:
        (lista_de_xmls, maior_nsu)
    
    Raises:
        RuntimeError: Se erro persistir após correção automática
    """
    tentativas = 0
    max_tentativas = 2  # Tentativa inicial + 1 retry com NSU corrigido
    
    while tentativas < max_tentativas:
        tentativas += 1
        
        try:
            print(f"[AUTO-RECUPERACAO NSU] Tentativa {tentativas}/{max_tentativas} - NSU {ultimo_nsu}")
            xmls, maior_nsu = client.consultar_todos_por_nsu(ultimo_nsu, max_iteracoes)
            print(f"[AUTO-RECUPERACAO NSU] Sucesso! {len(xmls)} XMLs encontrados")
            return xmls, maior_nsu
            
        except RuntimeError as e:
            erro_msg = str(e)
            
            # Verificar se é erro de NSU desatualizado
            if erro_msg.startswith("NSU_DESATUALIZADO:"):
                partes = erro_msg.split(":")
                if len(partes) >= 2:
                    try:
                        nsu_correto = int(partes[1])
                        diferenca = nsu_correto - ultimo_nsu
                        
                        print(f"[AUTO-RECUPERACAO NSU] NSU DESATUALIZADO detectado!")
                        print(f"[AUTO-RECUPERACAO NSU] NSU antigo: {ultimo_nsu}")
                        print(f"[AUTO-RECUPERACAO NSU] NSU correto: {nsu_correto}")
                        print(f"[AUTO-RECUPERACAO NSU] Diferenca: {diferenca} documentos")
                        
                        if tentativas < max_tentativas:
                            if atualizar_banco:
                                print(f"[AUTO-RECUPERACAO NSU] Atualizando NSU no banco de dados...")
                                atualizar_nsu(cnpj, nsu_correto)
                                print(f"[AUTO-RECUPERACAO NSU] NSU atualizado no banco!")
                            else:
                                print(f"[AUTO-RECUPERACAO NSU] Usando NSU corrigido apenas em memoria (preview nao persiste)")
                            
                            print(f"[AUTO-RECUPERACAO NSU] Tentando novamente com NSU {nsu_correto}...")
                            
                            # Atualizar NSU para próxima tentativa
                            ultimo_nsu = nsu_correto
                            
                            # Aguardar 3 segundos antes de tentar novamente
                            time.sleep(3)
                            continue
                        else:
                            print(f"[AUTO-RECUPERACAO NSU] Limite de tentativas atingido")
                            raise RuntimeError(f"NSU foi corrigido para {nsu_correto}, mas erro persistiu")
                    
                    except (ValueError, IndexError) as parse_error:
                        print(f"[AUTO-RECUPERACAO NSU] Erro ao parsear NSU correto: {parse_error}")
                        raise e
            
            # Verificar se é bloqueio temporário do SEFAZ
            elif erro_msg.startswith("SEFAZ_BLOQUEADO:"):
                print(f"[AUTO-RECUPERACAO NSU] Sistema BLOQUEADO pelo SEFAZ (codigo 656)")
                print(f"[AUTO-RECUPERACAO NSU] Aguarde aproximadamente 1 hora antes de tentar novamente")
                raise RuntimeError(f"SEFAZ bloqueado temporariamente. Aguarde 1 hora. Motivo: {erro_msg}")
            
            # Outros erros são propagados
            else:
                print(f"[AUTO-RECUPERACAO NSU] Erro nao relacionado a NSU: {erro_msg}")
                raise e
    
    # Se chegou aqui, excedeu tentativas
    raise RuntimeError(f"Falha após {max_tentativas} tentativas de auto-recuperacao de NSU")


def preview_importacao() -> Dict:
    """
    Faz preview da importação (contagem) sem importar de fato.
    Usa NSU incremental para contar apenas XMLs novos disponíveis.
    Em DEV_MODE, retorna dados simulados.
    
    Returns:
        Dict com: total_encontrado, valor_total, fornecedores (lista), periodo
    """
    # MODO DEV: Retornar dados mockados
    if DEV_MODE:
        print(f"[PREVIEW] Modo: DESENVOLVIMENTO (dados mockados)")
        fornecedores_mock = ["FORNECEDOR ABC LTDA", "SUPPLY COMPANY XYZ", "DISTRIBUIDORA 123"]
        total_mock = random.randint(10, 30)
        valor_mock = round(random.uniform(10000, 50000), 2)
        
        return {
            "status": "ok",
            "total_encontrado": total_mock,
            "valor_total": valor_mock,
            "fornecedores": fornecedores_mock,
            "modo": "desenvolvimento",
            "mensagem": f"[MODO DEV] {total_mock} XMLs simulados disponíveis"
        }
    
    try:
        empresas = get_empresas()
        if not empresas:
            return {
                "status": "error",
                "total_encontrado": 0,
                "valor_total": 0.0,
                "fornecedores": [],
                "mensagem": "Nenhuma empresa configurada"
            }
        
        total_xmls = 0
        valor_total = 0.0
        fornecedores_set: Set[str] = set()
        erros = []
        
        # Fazer consulta inicial para cada empresa (usando NSU incremental)
        for empresa in empresas:
            cnpj = empresa["cnpj"]
            try:
                # Buscar último NSU (vai buscar apenas XMLs novos)
                ultimo_nsu = get_ultimo_nsu(cnpj)
                
                # Preparar certificado
                cert_pfx = empresa.get("cert_pfx") or empresa.get("caminho_certificado")
                cert_senha = empresa.get("cert_senha") or empresa.get("senha_certificado")
                uf = empresa.get("uf", 35)
                endpoint = empresa.get("sefaz_endpoint")
                
                if not cert_pfx or not cert_senha:
                    continue
                
                if not SEFAZClient:
                    erros.append(f"SEFAZClient não disponível para empresa {cnpj}")
                    continue
                
                # Rate limiting
                wait_time = wait_before_sefaz_request(cnpj)
                if wait_time > 0:
                    print(f"[PREVIEW] Rate limiting: aguardando {wait_time:.1f}s")
                    time.sleep(wait_time)
                
                # Criar cliente SEFAZ e fazer consulta
                client = SEFAZClient(
                    cnpj=cnpj,
                    cert_pfx=cert_pfx,
                    cert_senha=cert_senha,
                    endpoint=endpoint,
                    uf=uf
                )
                
                # Consultar TODOS os XMLs novos com auto-recuperação de NSU
                # IMPORTANTE: atualizar_banco=False porque é só PREVIEW (não persiste NSU)
                xmls, maior_nsu = consultar_com_auto_recuperacao_nsu(client, cnpj, ultimo_nsu, max_iteracoes=20, atualizar_banco=False)
                
                # Registrar requisição no rate limiter
                get_rate_limiter().record_request(cnpj)
                
                # Processar XMLs para extrair informações (sem salvar no banco)
                for xml_data in xmls:
                    try:
                        xml_str = xml_data.get("xml", "")
                        root = ET.fromstring(xml_str)
                        
                        # Extrair valor total
                        valor = 0.0
                        for elem in root.iter():
                            if elem.tag.endswith("vNF"):
                                try:
                                    valor = float(elem.text or 0)
                                    break
                                except:
                                    pass
                        
                        # Extrair fornecedor
                        fornecedor = "DESCONHECIDO"
                        for elem in root.iter():
                            if elem.tag.endswith("emit"):
                                for child in elem:
                                    if child.tag.endswith("xNome"):
                                        fornecedor = child.text or "DESCONHECIDO"
                                        break
                                if fornecedor != "DESCONHECIDO":
                                    break
                        
                        total_xmls += 1
                        valor_total += valor
                        if fornecedor and fornecedor != "DESCONHECIDO":
                            fornecedores_set.add(fornecedor)
                            
                    except Exception as e:
                        print(f"[PREVIEW] ERRO ao processar XML para preview: {e}")
                        continue
                
                print(f"[PREVIEW] Empresa {cnpj}: {len(xmls)} XMLs novos encontrados")
                
            except Exception as e:
                erro_msg = f"Erro ao consultar empresa {cnpj}: {str(e)}"
                print(f"[PREVIEW] {erro_msg}")
                erros.append(erro_msg)
                continue
        
        # Calcular período (primeiro dia do mês até hoje)
        hoje = date.today()
        primeiro_dia_mes = date(hoje.year, hoje.month, 1)
        
        return {
            "status": "ok",
            "total_encontrado": total_xmls,
            "valor_total": round(valor_total, 2),
            "fornecedores": sorted(list(fornecedores_set)),
            "periodo": {
                "data_inicio": primeiro_dia_mes.isoformat(),
                "data_fim": hoje.isoformat(),
                "descricao": f"{primeiro_dia_mes.strftime('%d/%m/%Y')} até {hoje.strftime('%d/%m/%Y')}"
            },
            "mensagem": f"{total_xmls} NFs encontradas (novos XMLs via NSU incremental)",
            "avisos": erros if erros else None
        }
        
    except Exception as e:
        print(f"[PREVIEW] ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "total_encontrado": 0,
            "valor_total": 0.0,
            "fornecedores": [],
            "mensagem": f"Erro ao fazer preview: {str(e)}"
        }


def preview_importacao_inicial() -> Dict:
    """
    Faz preview da importação inicial (contagem) sem importar de fato.
    Usa NSU incremental para contar apenas XMLs novos disponíveis desde início do ano.
    Em DEV_MODE, retorna dados simulados sem consultar SEFAZ.
    
    Returns:
        Dict com: total_encontrado, valor_total, fornecedores (lista), periodo
    """
    print(f"[PREVIEW INICIAL] ===== INICIANDO PREVIEW =====")
    
    # ========================================
    # MODO DEV: Retornar dados mockados
    # ========================================
    if DEV_MODE:
        print(f"[PREVIEW INICIAL] Modo: DESENVOLVIMENTO (dados mockados)")
        
        # Gerar dados mock
        fornecedores_mock = [
            "FORNECEDOR ABC LTDA",
            "SUPPLY COMPANY XYZ", 
            "DISTRIBUIDORA 123",
            "COMERCIAL DEF LTDA",
            "ATACADAO MATERIAIS LTDA"
        ]
        
        total_mock = random.randint(30, 80)
        valor_mock = round(random.uniform(50000, 200000), 2)
        
        data_ini, data_fim = obter_periodo_ano_atual()
        
        return {
            "status": "ok",
            "total_encontrado": total_mock,
            "valor_total": valor_mock,
            "fornecedores": fornecedores_mock,
            "periodo": {
                "data_inicio": data_ini.isoformat(),
                "data_fim": data_fim.isoformat()
            },
            "modo": "desenvolvimento",
            "mensagem": f"[MODO DEV] {total_mock} XMLs simulados disponíveis"
        }
    
    # ========================================
    # MODO PRODUÇÃO: Consultar SEFAZ real
    # ========================================
    try:
        print(f"[PREVIEW INICIAL] Buscando empresas...")
        empresas = get_empresas()
        if not empresas:
            print(f"[PREVIEW INICIAL] Nenhuma empresa encontrada")
            return {
                "status": "error",
                "total_encontrado": 0,
                "valor_total": 0.0,
                "fornecedores": [],
                "mensagem": "Nenhuma empresa configurada"
            }
        
        print(f"[PREVIEW INICIAL] {len(empresas)} empresa(s) encontrada(s)")
        
        # Obter período do ano atual
        print(f"[PREVIEW INICIAL] Calculando período...")
        data_ini, data_fim = obter_periodo_ano_atual()
        print(f"[PREVIEW INICIAL] Período: {data_ini} até {data_fim}")
        
        total_xmls = 0
        valor_total = 0.0
        fornecedores_set: Set[str] = set()
        erros = []
        
        # Cache para armazenar XMLs consultados
        xmls_por_empresa: Dict[str, List[dict]] = {}
        nsu_por_empresa: Dict[str, int] = {}
        
        # Fazer consulta inicial para cada empresa (usando NSU incremental)
        print(f"[PREVIEW INICIAL] Iniciando consultas por empresa...")
        for idx, empresa in enumerate(empresas, 1):
            cnpj = empresa["cnpj"]
            print(f"[PREVIEW INICIAL] [{idx}/{len(empresas)}] Processando empresa {cnpj}...")
            try:
                # Buscar último NSU (vai buscar apenas XMLs novos)
                print(f"[PREVIEW INICIAL]   - Buscando último NSU conhecido...")
                ultimo_nsu = get_ultimo_nsu(cnpj)
                print(f"[PREVIEW INICIAL]   - Último NSU: {ultimo_nsu}")
                
                # Preparar certificado
                print(f"[PREVIEW INICIAL]   - Preparando certificado...")
                cert_pfx = empresa.get("cert_pfx") or empresa.get("caminho_certificado")
                cert_senha = empresa.get("cert_senha") or empresa.get("senha_certificado")
                uf = empresa.get("uf", 35)
                endpoint = empresa.get("sefaz_endpoint")
                print(f"[PREVIEW INICIAL]   - Certificado preparado (pfx: {bool(cert_pfx)}, senha: {bool(cert_senha)})")
                
                if not cert_pfx or not cert_senha:
                    print(f"[PREVIEW INICIAL]   - [AVISO] Certificado não configurado, pulando empresa")
                    continue
                
                if not SEFAZClient:
                    erro_msg = f"SEFAZClient não disponível para empresa {cnpj}"
                    print(f"[PREVIEW INICIAL]   - [ERRO] {erro_msg}")
                    erros.append(erro_msg)
                    continue
                
                # Rate limiting
                print(f"[PREVIEW INICIAL]   - Verificando rate limiting...")
                wait_time = wait_before_sefaz_request(cnpj)
                print(f"[PREVIEW INICIAL]   - Rate limiting verificado (wait_time retornado: {wait_time:.1f}s)")
                
                # Criar cliente SEFAZ e fazer consulta
                print(f"[PREVIEW INICIAL]   - Criando cliente SEFAZ...")
                client = SEFAZClient(
                    cnpj=cnpj,
                    cert_pfx=cert_pfx,
                    cert_senha=cert_senha,
                    endpoint=endpoint,
                    uf=uf
                )
                print(f"[PREVIEW INICIAL]   - Cliente SEFAZ criado com sucesso")
                
                # Consultar TODOS os XMLs disponíveis com auto-recuperação de NSU
                # IMPORTANTE: atualizar_banco=False porque é só PREVIEW (não persiste NSU)
                print(f"[PREVIEW INICIAL]   - Consultando SEFAZ por NSU (pode demorar, buscando TODOS os XMLs)...")
                xmls, maior_nsu = consultar_com_auto_recuperacao_nsu(client, cnpj, ultimo_nsu, max_iteracoes=20, atualizar_banco=False)
                print(f"[PREVIEW INICIAL]   - Consulta concluída: {len(xmls)} XMLs encontrados (NSU até {maior_nsu})")
                
                # Armazenar XMLs e NSU no cache
                xmls_por_empresa[cnpj] = xmls
                nsu_por_empresa[cnpj] = maior_nsu
                
                # Registrar requisição no rate limiter
                get_rate_limiter().record_request(cnpj)
                
                # Processar XMLs para extrair informações (sem salvar no banco)
                for xml_data in xmls:
                    try:
                        xml_str = xml_data.get("xml", "")
                        root = ET.fromstring(xml_str)
                        
                        # Extrair valor total
                        valor = 0.0
                        for elem in root.iter():
                            if elem.tag.endswith("vNF"):
                                try:
                                    valor = float(elem.text or 0)
                                    break
                                except:
                                    pass
                        
                        # Extrair fornecedor
                        fornecedor = "DESCONHECIDO"
                        for elem in root.iter():
                            if elem.tag.endswith("emit"):
                                for child in elem:
                                    if child.tag.endswith("xNome"):
                                        fornecedor = child.text or "DESCONHECIDO"
                                        break
                                if fornecedor != "DESCONHECIDO":
                                    break
                        
                        total_xmls += 1
                        valor_total += valor
                        if fornecedor and fornecedor != "DESCONHECIDO":
                            fornecedores_set.add(fornecedor)
                            
                    except Exception as e:
                        print(f"[PREVIEW INICIAL] ERRO ao processar XML para preview: {e}")
                        continue
                
                print(f"[PREVIEW INICIAL]   - [OK] Empresa {cnpj}: {len(xmls)} XMLs novos encontrados")
                
            except FileNotFoundError as e:
                erro_msg = f"Certificado nao encontrado para empresa {cnpj}: {str(e)}"
                print(f"[PREVIEW INICIAL]   - [ERRO] {erro_msg}")
                erros.append(erro_msg)
            except RuntimeError as e:
                erro_msg = f"Erro na comunicacao com SEFAZ para empresa {cnpj}: {str(e)}"
                print(f"[PREVIEW INICIAL]   - [ERRO] {erro_msg}")
                erros.append(erro_msg)
            except Exception as e:
                erro_msg = f"Erro inesperado ao consultar empresa {cnpj}: {type(e).__name__}: {str(e)}"
                print(f"[PREVIEW INICIAL]   - [ERRO CRITICO] {erro_msg}")
                import traceback
                print(f"[PREVIEW INICIAL]   - Traceback completo:")
                traceback.print_exc()
                erros.append(erro_msg)
                continue
        
        print(f"[PREVIEW INICIAL] ===== PREVIEW CONCLUÍDO =====")
        print(f"[PREVIEW INICIAL] Total: {total_xmls} XMLs, {len(fornecedores_set)} fornecedores únicos")
        
        # Armazenar XMLs consultados no cache para evitar re-consultar na importação
        if xmls_por_empresa:
            cache = get_preview_cache()
            cache.set(xmls_por_empresa, nsu_por_empresa)
            print(f"[PREVIEW INICIAL] XMLs armazenados no cache (validade: 15 minutos)")
        
        return {
            "status": "ok",
            "total_encontrado": total_xmls,
            "valor_total": round(valor_total, 2),
            "fornecedores": sorted(list(fornecedores_set)),
            "periodo": {
                "data_inicio": data_ini.isoformat(),
                "data_fim": data_fim.isoformat(),
                "descricao": f"{data_ini.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')} (ano {data_fim.year})"
            },
            "mensagem": f"{total_xmls} NFs encontradas (novos XMLs via NSU incremental desde início do ano)",
            "avisos": erros if erros else None,
            "tipo": "inicial"
        }
        
    except Exception as e:
        print(f"[PREVIEW INICIAL] ===== ERRO CRITICO =====")
        print(f"[PREVIEW INICIAL] Tipo: {type(e).__name__}")
        print(f"[PREVIEW INICIAL] Erro: {e}")
        import traceback
        print(f"[PREVIEW INICIAL] Traceback completo:")
        traceback.print_exc()
        print(f"[PREVIEW INICIAL] ===== FIM DO ERRO =====")
        return {
            "status": "error",
            "total_encontrado": 0,
            "valor_total": 0.0,
            "fornecedores": [],
            "mensagem": f"{type(e).__name__}: {str(e)}",
            "tipo": "inicial"
        }

import os
import subprocess
import tempfile
import requests
import urllib3
from typing import Tuple, List

# Desativa warnings de SSL (necessário em DEV)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SEFAZ_ENDPOINT = "https://www.svrs.rs.gov.br/ws/NfeDistribuicaoDFe/NfeDistribuicaoDFe.asmx"



class SEFAZClient:
    def __init__(
        self,
        cnpj: str,
        cert_pfx: str,
        cert_senha: str,
        endpoint: str = None,
        uf: int = None
    ):
        """
        Cliente para consulta à SEFAZ.
        
        Args:
            cnpj: CNPJ da empresa
            cert_pfx: Caminho do certificado (.pfx ou .sfx - OpenSSL aceita ambos)
            cert_senha: Senha do certificado
            endpoint: URL do endpoint SEFAZ (opcional, usa padrão se não informado)
            uf: UF da autorizadora (opcional, será inferido se não informado)
        """
        self.cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")  # Limpa CNPJ
        self.certificado_pfx = cert_pfx
        self.senha_certificado = cert_senha
        self.endpoint = endpoint or SEFAZ_ENDPOINT
        self.uf = uf or 43  # RS como padrão, mas deve ser configurado por empresa

        # Caminho absoluto do projeto
        self.base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../")
        )

        self.cert_pem = self._converter_pfx_para_pem()

    # =========================================================
    # CONVERSÃO DO CERTIFICADO PFX → PEM
    # =========================================================
    def _converter_pfx_para_pem(self) -> Tuple[str, str]:
        """
        Converte o certificado PFX/SFX em PEM usando OpenSSL.
        Suporta arquivos .pfx, .sfx e outros formatos PKCS#12.
        Retorna (cert.pem, key.pem)
        """

        # Se o caminho for absoluto, usar diretamente; senão, relativo ao base_dir
        if os.path.isabs(self.certificado_pfx):
            pfx_path = self.certificado_pfx
        else:
            pfx_path = os.path.join(self.base_dir, self.certificado_pfx)

        if not os.path.exists(pfx_path):
            raise FileNotFoundError(f"Certificado não encontrado: {pfx_path}")

        tmp_dir = tempfile.mkdtemp()

        cert_pem = os.path.join(tmp_dir, "cert.pem")
        key_pem = os.path.join(tmp_dir, "key.pem")

        # Detecta OpenSSL no sistema (Windows e Linux)
        openssl_bin = None
        possible_paths = [
            r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
            r"C:\Program Files\OpenSSL\bin\openssl.exe",
            r"C:\OpenSSL-Win64\bin\openssl.exe",
            "/usr/bin/openssl",
            "/usr/local/bin/openssl",
            "openssl"  # Se estiver no PATH
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    openssl_bin = path
                    break
            except:
                continue

        if not openssl_bin:
            raise RuntimeError(
                "OpenSSL não encontrado. "
                "Instale OpenSSL e verifique o PATH ou configure OPENSSL_BIN."
            )

        # Extrai certificado
        cmd_cert = [
            openssl_bin,
            "pkcs12",
            "-in", pfx_path,
            "-clcerts",
            "-nokeys",
            "-out", cert_pem,
            "-passin", f"pass:{self.senha_certificado}"
        ]

        # Extrai chave privada
        cmd_key = [
            openssl_bin,
            "pkcs12",
            "-in", pfx_path,
            "-nocerts",
            "-nodes",
            "-out", key_pem,
            "-passin", f"pass:{self.senha_certificado}"
        ]

        subprocess.check_call(cmd_cert)
        subprocess.check_call(cmd_key)

        return cert_pem, key_pem

    # =========================================================
    # CONSULTA POR NSU (NFeDistribuicaoDFe)
    # =========================================================
    def consultar_todos_por_nsu(self, ultimo_nsu: int, max_iteracoes: int = 20) -> Tuple[List[dict], int]:
        """
        Consulta a SEFAZ usando NSU e faz múltiplas requisições iterativas
        até buscar TODOS os XMLs disponíveis.
        
        O SEFAZ retorna no máximo 50 XMLs por requisição. Se houver mais,
        esta função faz novas consultas automaticamente.
        
        Args:
            ultimo_nsu: NSU inicial para busca
            max_iteracoes: Máximo de iterações (proteção contra loop infinito)
        
        Returns:
            (lista_de_xmls, maior_nsu)
        """
        print(f"[SEFAZ CLIENT] Iniciando busca completa de XMLs a partir de NSU {ultimo_nsu}")
        
        todos_xmls = []
        nsu_atual = ultimo_nsu
        maior_nsu_encontrado = ultimo_nsu
        iteracao = 0
        
        while iteracao < max_iteracoes:
            iteracao += 1
            print(f"[SEFAZ CLIENT] Iteracao {iteracao}/{max_iteracoes} - Consultando NSU {nsu_atual}")
            
            try:
                # Fazer consulta única
                xmls, maior_nsu = self.consultar_por_nsu(nsu_atual)
                
                if not xmls:
                    print(f"[SEFAZ CLIENT] Nenhum XML retornado na iteracao {iteracao}. Busca concluida.")
                    break
                
                # Adicionar XMLs encontrados
                todos_xmls.extend(xmls)
                maior_nsu_encontrado = max(maior_nsu_encontrado, maior_nsu)
                
                print(f"[SEFAZ CLIENT] Iteracao {iteracao}: {len(xmls)} XMLs encontrados (Total acumulado: {len(todos_xmls)})")
                
                # Se retornou menos de 50 XMLs, provavelmente não há mais documentos
                if len(xmls) < 50:
                    print(f"[SEFAZ CLIENT] Retornou menos de 50 XMLs. Fim da busca.")
                    break
                
                # Atualizar NSU para próxima iteração
                nsu_atual = maior_nsu
                
                # Pequeno delay entre requisições (Rate limiting interno)
                import time
                time.sleep(2)  # 2 segundos entre requisições
                
            except RuntimeError as e:
                # Erros do SEFAZ (656, etc) são propagados
                print(f"[SEFAZ CLIENT] Erro na iteracao {iteracao}: {e}")
                # Se já encontramos algum XML, retornar o que temos
                if todos_xmls:
                    print(f"[SEFAZ CLIENT] Retornando {len(todos_xmls)} XMLs encontrados antes do erro")
                    return todos_xmls, maior_nsu_encontrado
                else:
                    raise
        
        if iteracao >= max_iteracoes:
            print(f"[SEFAZ CLIENT] AVISO: Atingido limite de {max_iteracoes} iteracoes. Pode haver mais XMLs.")
        
        print(f"[SEFAZ CLIENT] Busca completa finalizada: {len(todos_xmls)} XMLs encontrados no total")
        return todos_xmls, maior_nsu_encontrado

    def consultar_por_nsu(self, ultimo_nsu: int) -> Tuple[List[dict], int]:
        """
        Consulta a SEFAZ usando NSU (consulta única, retorna até 50 XMLs).
        Para buscar TODOS os XMLs disponíveis, use consultar_todos_por_nsu().
        
        Retorna (lista_de_xmls, maior_nsu)
        """

        # XML SOAP no formato oficial do SEFAZ Nacional
        # Ref: Manual de Integracao NFeDistribuicaoDFe v1.01
        nsu_formatado = str(ultimo_nsu).zfill(15)
        
        soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <soap:Header>
        <nfeCabecMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
            <cUF>{self.uf}</cUF>
            <versaoDados>1.00</versaoDados>
        </nfeCabecMsg>
    </soap:Header>
    <soap:Body>
        <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
            <nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
                <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
                    <tpAmb>1</tpAmb>
                    <cUFAutor>{self.uf}</cUFAutor>
                    <CNPJ>{self.cnpj}</CNPJ>
                    <distNSU>
                        <ultNSU>{nsu_formatado}</ultNSU>
                    </distNSU>
                </distDFeInt>
            </nfeDadosMsg>
        </nfeDistDFeInteresse>
    </soap:Body>
</soap:Envelope>"""

        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }

        print(f"[SEFAZ CLIENT] Enviando requisicao para {self.endpoint}")
        print(f"[SEFAZ CLIENT] CNPJ: {self.cnpj}, NSU: {ultimo_nsu}")
        
        try:
            response = requests.post(
                self.endpoint,
                data=soap_xml,
                headers=headers,
                cert=self.cert_pem,   # (cert.pem, key.pem)
                verify=False,         # Necessario em DEV
                timeout=60
            )
            
            print(f"[SEFAZ CLIENT] Status HTTP: {response.status_code}")
            response.raise_for_status()

        except requests.exceptions.Timeout as e:
            erro_msg = f"Timeout ao conectar SEFAZ (60s): {e}"
            print(f"[SEFAZ CLIENT] ERRO: {erro_msg}")
            raise RuntimeError(erro_msg)
        except requests.exceptions.ConnectionError as e:
            erro_msg = f"Erro de conexao com SEFAZ: {e}"
            print(f"[SEFAZ CLIENT] ERRO: {erro_msg}")
            raise RuntimeError(erro_msg)
        except requests.exceptions.HTTPError as e:
            erro_msg = f"HTTP Error {response.status_code}: {e}"
            print(f"[SEFAZ CLIENT] ERRO: {erro_msg}")
            print(f"[SEFAZ CLIENT] Resposta: {response.text[:500]}")
            raise RuntimeError(erro_msg)
        except Exception as e:
            erro_msg = f"Erro desconhecido ao conectar SEFAZ: {e}"
            print(f"[SEFAZ CLIENT] ERRO: {erro_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(erro_msg)

        return self._processar_resposta(response.text, ultimo_nsu)

    # =========================================================
    # PROCESSAMENTO DA RESPOSTA SOAP
    # =========================================================
    def _processar_resposta(self, xml_retorno: str, ultimo_nsu: int) -> Tuple[List[dict], int]:
        """
        Extrai docZip (XML compactado) e NSU da resposta SOAP
        """

        import base64
        import gzip
        import xml.etree.ElementTree as ET

        xmls = []
        maior_nsu = 0

        try:
            root = ET.fromstring(xml_retorno)
        except ET.ParseError as e:
            print(f"[SEFAZ CLIENT] ERRO: XML mal formado na resposta do SEFAZ")
            print(f"[SEFAZ CLIENT] Parse Error: {e}")
            print(f"[SEFAZ CLIENT] Resposta (primeiros 1000 chars): {xml_retorno[:1000]}")
            raise RuntimeError(f"Resposta SEFAZ com XML invalido: {e}")

        # Verificar se ha erro SOAP Fault
        fault = root.find(".//{*}Fault")
        if fault is not None:
            fault_string = fault.find(".//{*}faultstring")
            fault_code = fault.find(".//{*}faultcode")
            erro_msg = f"SOAP Fault: {fault_string.text if fault_string is not None else 'Desconhecido'}"
            print(f"[SEFAZ CLIENT] ERRO: {erro_msg}")
            if fault_code is not None:
                print(f"[SEFAZ CLIENT] Fault Code: {fault_code.text}")
            raise RuntimeError(erro_msg)

        # Verificar codigos de status do SEFAZ
        cstat = root.find(".//{*}cStat")
        xmotivo = root.find(".//{*}xMotivo")
        if cstat is not None:
            codigo = cstat.text
            motivo = xmotivo.text if xmotivo is not None else "Sem descricao"
            print(f"[SEFAZ CLIENT] Resposta SEFAZ - Codigo: {codigo}, Motivo: {motivo}")
            
            # Codigo 656: Consumo indevido - NSU incorreto ou bloqueio temporário
            if codigo == "656":
                print(f"[SEFAZ CLIENT] ATENCAO: Codigo 656 - NSU atual ({ultimo_nsu}) pode estar desatualizado ou sistema bloqueado")
                
                # Verificar se ha ultNSU na resposta
                ult_nsu_elem = root.find(".//{*}ultNSU")
                nsu_correto = None
                if ult_nsu_elem is not None:
                    try:
                        nsu_correto = int(ult_nsu_elem.text)
                        print(f"[SEFAZ CLIENT] ultNSU retornado pelo SEFAZ: {nsu_correto}")
                        
                        # Se o NSU retornado é diferente do enviado, significa que está desatualizado
                        if nsu_correto != ultimo_nsu:
                            diferenca = nsu_correto - ultimo_nsu
                            print(f"[SEFAZ CLIENT] NSU DESATUALIZADO detectado! Diferenca: {diferenca} documentos")
                            print(f"[SEFAZ CLIENT] O sistema tentara atualizar automaticamente")
                            
                            # Incluir o NSU correto na exceção para captura posterior
                            raise RuntimeError(f"NSU_DESATUALIZADO:{nsu_correto}:{motivo}")
                        else:
                            print(f"[SEFAZ CLIENT] NSU esta correto, mas sistema foi BLOQUEADO temporariamente")
                            print(f"[SEFAZ CLIENT] Aguarde aproximadamente 1 hora antes de tentar novamente")
                            raise RuntimeError(f"SEFAZ_BLOQUEADO:{motivo}")
                    except ValueError:
                        pass
                
                # Se não conseguiu determinar, lançar erro genérico
                print(f"[SEFAZ CLIENT] Solucao: Aguardar 1 hora ou verificar NSU manualmente")
                raise RuntimeError(f"SEFAZ codigo 656: {motivo}. NSU atual: {ultimo_nsu}")
            
            # Codigos de erro (nao informacionais)
            if codigo not in ["138", "137"]:  # 138=sucesso, 137=nenhum doc
                if codigo.startswith("2"):  # Erros comecam com 2
                    raise RuntimeError(f"SEFAZ retornou erro {codigo}: {motivo}")

        # Extrair XMLs compactados
        try:
            for doc in root.findall(".//{*}docZip"):
                nsu = int(doc.attrib.get("NSU", "0"))
                maior_nsu = max(maior_nsu, nsu)

                conteudo = gzip.decompress(
                    base64.b64decode(doc.text)
                ).decode("utf-8")

                xmls.append({
                    "nsu": nsu,
                    "xml": conteudo
                })
        except Exception as e:
            print(f"[SEFAZ CLIENT] ERRO ao processar docZip: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Erro ao descompactar XMLs da resposta: {e}")

        print(f"[SEFAZ CLIENT] Processamento concluido: {len(xmls)} XMLs extraidos, maior NSU: {maior_nsu}")
        return xmls, maior_nsu

    # =========================================================
    # CONSULTA ÚNICA DE NF POR CHAVE (exemplo)
    # =========================================================
    def consultar_nfe_por_chave(self, chave_nfe: str) -> dict:
        """
        Consulta uma única NF-e pela chave de acesso.
        Exemplo de uso para buscar uma NF específica.
        
        NOTA: Esta função requer um endpoint específico de consulta de NF-e.
        O endpoint NFeDistribuicaoDFe não retorna NF-e individual por chave.
        Esta é uma implementação de exemplo que pode precisar ser ajustada
        conforme o ambiente SEFAZ específico.
        
        Args:
            chave_nfe: Chave de acesso da NF-e (44 dígitos)
            
        Returns:
            dict com informações da NF-e ou None se não encontrada
        """
        # Exemplo de SOAP para consulta por chave (ajustar conforme necessário)
        # Esta é uma implementação de referência - pode precisar ajustes
        
        soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeConsultaNF xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeConsultaProtocolo4">
      <nfeDadosMsg>
        <![CDATA[
        <consSitNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
          <tpAmb>1</tpAmb>
          <xServ>CONSULTAR</xServ>
          <chNFe>{chave_nfe}</chNFe>
        </consSitNFe>
        ]]>
      </nfeDadosMsg>
    </nfeConsultaNF>
  </soap12:Body>
</soap12:Envelope>
"""

        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }

        try:
            # IMPORTANTE: Este endpoint pode ser diferente dependendo da UF
            # Para RS (SVRS), usar: https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx
            consulta_endpoint = self.endpoint.replace("NfeDistribuicaoDFe", "NfeConsulta4")
            
            response = requests.post(
                consulta_endpoint,
                data=soap_xml,
                headers=headers,
                cert=self.cert_pem,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            # Processar resposta (implementação simplificada)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            
            # Extrair status da NF
            status_elem = root.find(".//{http://www.portalfiscal.inf.br/nfe}cStat")
            motivo_elem = root.find(".//{http://www.portalfiscal.inf.br/nfe}xMotivo")
            
            return {
                "chave_nfe": chave_nfe,
                "status": status_elem.text if status_elem is not None else None,
                "motivo": motivo_elem.text if motivo_elem is not None else None,
                "xml_resposta": response.text
            }
            
        except Exception as e:
            raise RuntimeError(f"Erro ao consultar NF-e por chave: {e}")

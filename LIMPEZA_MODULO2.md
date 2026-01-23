# 🔧 LIMPEZA MÓDULO 2 - REMOÇÃO DE DADOS MOCKADOS

## 📋 Resumo das Alterações

O módulo 2 foi reconfigurado para **usar APENAS dados do arquivo `produtos_com_posto.json`**. Todos os dados mockados e geração de XMLs fictícios foram **desabilitados permanentemente**.

---

## ❌ O QUE FOI REMOVIDO

### 1. **Geração de XMLs Mockados** (`_gerar_xml_mock()`)
- ✅ Função desabilitada em `projects/modulo2/service.py`
- ✅ Retorna erro quando chamada
- **Razão:** XMLs fictícios causavam conflito com dados reais

### 2. **Modo Desenvolvimento (DEV_MODE)**
- ✅ Desabilitado em `projects/modulo2/service.py`
- ✅ `consultar_sefaz_quantidade()` agora retorna erro
- ✅ `importar_xmls_sefaz()` agora retorna erro
- **Razão:** Modo DEV gerava dados falsos automaticamente

### 3. **CNPJs e Fornecedores Mockados**
- Fornecedores mockados removidos:
  - `FORNECEDOR ABC LTDA`
  - `SUPPLY COMPANY XYZ`
  - `DISTRIBUIDORA 123`
  - `COMERCIAL DEF LTDA`
- CNPJs mockados removidos:
  - `12817803000112`
  - `08818229000140`
  - `56419492000109`

---

## ✅ O QUE FAZER AGORA

### **PASSO 1: Limpar dados mockados do banco**

Execute o script de limpeza para remover TODAS as NFes mockadas:

```bash
cd c:\Users\Jefferson\Desktop\DATABOOSTER\Rentus\DEV\modulo 2
python projects/modulo2/limpar_tudo_mock.py --confirmar
```

**Isso vai remover:**
- ✓ 1780+ NFes mockadas
- ✓ 5000+ itens mockados
- ✓ 1000+ pendências associadas
- ✓ Empresas orfãs

### **PASSO 2: Importar dados do JSON**

Importe APENAS dados do arquivo `produtos_com_posto.json`:

```bash
python projects/modulo2/importar_json_produtos.py
```

**Resultado:**
- ✓ 536 NFes importadas
- ✓ 1780 produtos processados
- ✓ 1086 produtos identificados
- ✓ 189 produtos pendentes para revisão

---

## 📊 Arquivos Modificados

### `projects/modulo2/service.py`
- ✅ Desabilitada: `_gerar_xml_mock()` (linhas ~257-300)
- ✅ Desabilitada: Geração de XMLs em `importar_xmls_sefaz()` (linhas ~413-462)
- ✅ Modificada: `consultar_sefaz_quantidade()` (retorna erro)
- ✅ Modificada: `importar_xmls_sefaz()` (retorna erro)

### `projects/modulo2/limpar_tudo_mock.py` (NOVO)
- ✅ Script para identificar e remover dados mockados
- ✅ Remove NFes, itens, pendências e empresas orfãs
- ✅ Modo seguro: primeiro lista, depois remove com `--confirmar`

---

## 🔍 Como Verificar se Funcionou

### **1. Contar dados mockados (antes de limpar)**
```bash
python projects/modulo2/limpar_tudo_mock.py
```
Mostra quantos dados mockados existem no banco.

### **2. Limpar dados mockados**
```bash
python projects/modulo2/limpar_tudo_mock.py --confirmar
```
Remove todos os dados mockados.

### **3. Verificar banco após limpeza**
```bash
# No Python
from projects.modulo2.db import get_conn

conn = get_conn()
cur = conn.cursor()

# Contar NFes por origem
cur.execute("""
    SELECT 
        CASE 
            WHEN xml LIKE '%JSON%' THEN 'JSON'
            WHEN xml LIKE '%origem%' THEN 'Outras'
            ELSE 'Desconhecida'
        END as origem,
        COUNT(*) as total
    FROM modulo2_nfe
    GROUP BY origem
""")

for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} NFes")

cur.close()
conn.close()
```

---

## 🚨 Estrutura de Dados (produtos_com_posto.json)

O arquivo `produtos_com_posto.json` contém:

```json
{
  "metadata": {
    "total_xmls": 536,
    "total_produtos": 1780,
    "produtos_limpeza": 1470,
    "produtos_identificados": 1086,
    "produtos_pendentes": 189
  },
  "produtos": [
    {
      "chave_nf": "32260109570732000868550060000590091779111124",
      "empresa": "PRESSSEG SERVICOS DE SEGURANCA EIRELI",
      "cliente": "",
      "posto_trabalho": "",
      "codpos": "",
      "produto": "SAMSUNG CONDENSADORA INVERTER...",
      "ncm": "84151011",
      "categoria": "OUTROS",
      "quantidade": 1.0,
      "valor_unitario": 2911.3,
      "valor_total_produto": 2911.3,
      "_status": "PENDENTE",
      "_eh_limpeza": false,
      "_score": 1.2166666666666668
    }
  ]
}
```

**Campos importantes:**
- `chave_nf`: Identificador único da NFe
- `_status`: "OK" ou "PENDENTE"
- `_eh_limpeza`: Se é operação de limpeza (retorno de produtos)
- Dados de `cliente` e `posto_trabalho` para identificação

---

## ⚠️ Configuração de Ambiente

### Desabilitar DEV_MODE (opcional, se usar .env)

Se você tiver arquivo `.env`, remova ou altere:

```env
# Antes:
MODULO2_DEV_MODE=true

# Depois:
MODULO2_DEV_MODE=false
```

Ou remova a linha completamente (usa `false` por padrão).

---

## 📝 Log do Que Vai Acontecer

Quando você executar:

```bash
python projects/modulo2/limpar_tudo_mock.py --confirmar
```

Saída esperada:

```
======================================================================
LIMPEZA COMPLETA DE DADOS MOCKADOS DO MÓDULO 2
======================================================================

Dados mockados identificados:
  - NFes com fornecedores mockados: 485
  - NFes com CNPJs mockados: 1295
  - NFes com origem JSON: 0
  - Total de NFes mockadas a remover: 1780

======================================================================
INICIANDO LIMPEZA...
======================================================================

Encontradas 1780 NFes mockadas para remover
  ✓ Removidas 2400 pendências
  ✓ Removidos 5800 itens de NFes
  ✓ Removidas 1780 NFes mockadas
  ✓ Removidas 3 empresas orfãs

======================================================================
LIMPEZA CONCLUÍDA COM SUCESSO!
======================================================================

Resumo da remoção:
  - NFes mockadas removidas: 1780
  - Itens removidos: 5800
  - Pendências removidas: 2400
  - Empresas orfãs removidas: 3

[!] O banco foi limpo de todos os dados mockados.
[!] Agora você pode importar dados APENAS do arquivo produtos_com_posto.json
======================================================================
```

Depois execute:

```bash
python projects/modulo2/importar_json_produtos.py
```

Saída esperada:

```
[IMPORT] Carregando JSON: c:\...\produtos_com_posto.json
[IMPORT] Iniciando importação...
[IMPORT] Processando 1780 produtos de 536 NFes...
[IMPORT] Encontradas 536 NFes únicas.
[IMPORT] Processadas 100 NFes...
[IMPORT] Processadas 200 NFes...
...
[IMPORT] Importação concluída!
  - NFes processadas: 536
  - Produtos processados: 1780
  - Pendências criadas: 189

[IMPORT] Concluido com sucesso!
```

---

## 🎯 Benefícios

✅ **Dados Limpos:** Apenas dados reais do arquivo JSON  
✅ **Sem Conflitos:** Nenhum arquivo mockado interferindo  
✅ **Auditável:** Origem de todos os dados é JSON  
✅ **Produção Pronto:** Sem código de desenvolvimento  
✅ **Simples:** Uma única fonte de dados  

---

## 📞 Próximos Passos

1. ✅ Execute: `python projects/modulo2/limpar_tudo_mock.py --confirmar`
2. ✅ Execute: `python projects/modulo2/importar_json_produtos.py`
3. ✅ Verifique: Dados no banco de dados
4. ✅ Teste: APIs do módulo 2 com dados reais

---

**Última atualização:** 2026-01-23  
**Versão:** 1.0

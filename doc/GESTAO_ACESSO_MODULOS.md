# 🔐 Gestão de Acesso aos Módulos

## 📋 3 Formas de Controlar Acesso

### **Opção 1: Via Template HTML (Mais Simples)** ⭐ RECOMENDADO

Editar o arquivo `app/templates/index.html` e adicionar condições Jinja2:

#### **Exemplo 1: Módulo apenas para Admin**
```html
<!-- Mostrar APENAS para Admin -->
{% if user and user.get('is_admin') %}
<button onclick="window.location.href='/modulo1';">
  <span>MÓDULO 1</span>
  <span>OPS/Demitidos</span>
</button>
{% endif %}
```

#### **Exemplo 2: Módulo para Direção e Gestor**
```html
<!-- Mostrar para Direção OU Gestor -->
{% set perfil_principal_lower = user.get('perfil_principal', '').lower() if user else '' %}
{% set perfis_lower = user.get('perfis', []) | map('lower') | list if user else [] %}
{% if user and (perfil_principal_lower in ['direcao', 'gestor'] or 'direcao' in perfis_lower or 'gestor' in perfis_lower) %}
<button onclick="window.location.href='/modulo3';">
  <span>MÓDULO 3</span>
  <span>Férias Cheque</span>
</button>
{% endif %}
```

#### **Exemplo 3: Módulo para Todos EXCETO Direção**
```html
<!-- Esconder APENAS de Direção -->
{% set perfil_principal_lower = user.get('perfil_principal', '').lower() if user else '' %}
{% set perfis_lower = user.get('perfis', []) | map('lower') | list if user else [] %}
{% if user and perfil_principal_lower != 'direcao' and 'direcao' not in perfis_lower %}
<button onclick="window.location.href='/modulo4';">
  <span>MÓDULO 4</span>
  <span>Seguro de Vida</span>
</button>
{% endif %}
```

#### **Exemplo 4: Módulo para Auditores e Operacional**
```html
<!-- Mostrar para Auditores OU Operacional -->
{% set perfil_principal_lower = user.get('perfil_principal', '').lower() if user else '' %}
{% set perfis_lower = user.get('perfis', []) | map('lower') | list if user else [] %}
{% if user and (perfil_principal_lower in ['auditores', 'operacional'] or 'auditores' in perfis_lower or 'operacional' in perfis_lower) %}
<button onclick="window.location.href='/modulo5';">
  <span>MÓDULO 5</span>
  <span>13º Salário</span>
</button>
{% endif %}
```

---

### **Opção 2: Via Banco de Dados (Mais Flexível)**

O sistema já tem estrutura para isso! Use a tabela `profile_module_permissions`:

#### **SQL para dar acesso:**
```sql
-- Dar acesso ao Módulo 2 para o perfil Direção
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome = 'Direção'),
    (SELECT id FROM modulos WHERE codigo = 'modulo2'),
    1, 0, 0;
```

#### **Consultar permissões atuais:**
```sql
SELECT 
    p.nome as perfil,
    m.nome as modulo,
    pmp.can_view as visualizar,
    pmp.can_edit as editar,
    pmp.can_delete as deletar
FROM profile_module_permissions pmp
JOIN perfis p ON pmp.perfil_id = p.id
JOIN modulos m ON pmp.modulo_id = m.id
ORDER BY p.nome, m.ordem;
```

#### **Remover acesso:**
```sql
-- Remover acesso ao Módulo 1 do perfil Direção
DELETE FROM profile_module_permissions
WHERE perfil_id = (SELECT id FROM perfis WHERE nome = 'Direção')
  AND modulo_id = (SELECT id FROM modulos WHERE codigo = 'modulo1');
```

---

### **Opção 3: Via API (Programático)**

Usar endpoints da API para gerenciar programaticamente:

#### **Endpoint disponível:**
```python
GET /api/auth/my-modules
```

**Resposta:**
```json
[
  {
    "codigo": "modulo1",
    "nome": "OPS/Demitidos",
    "can_view": true,
    "can_edit": false,
    "can_delete": false
  },
  {
    "codigo": "modulo2",
    "nome": "Suprimentos",
    "can_view": true,
    "can_edit": true,
    "can_delete": false
  }
]
```

---

## 🎯 EXEMPLO PRÁTICO COMPLETO

### **Cenário: Configurar acesso aos módulos**

#### **Requisitos:**
- **Admin**: Acesso a TODOS os módulos
- **Direção**: Apenas módulos 1, 2, 3 (só visualização)
- **Gestor**: Apenas módulos 1, 2, 3 (só visualização)
- **Auditores**: Módulos 1, 2, 4, 5, 6 (visualização + edição)
- **Operacional**: Módulos 1, 2, 4, 5, 6 (visualização + edição)
- **Loyal**: Módulo especial + todos os outros

---

### **SOLUÇÃO 1: Via Template (Simples)**

Editar `app/templates/index.html`:

```html
<!-- MÓDULO 1 - Todos veem -->
<button onclick="window.location.href='/modulo1';">
  <span>MÓDULO 1</span>
  <span>OPS/Demitidos</span>
</button>

<!-- MÓDULO 2 - Todos veem -->
<button onclick="window.location.href='/modulo2';">
  <span>MÓDULO 2</span>
  <span>Suprimentos</span>
</button>

<!-- MÓDULO 3 - Apenas Direção e Gestor -->
{% set perfil = user.get('perfil_principal', '').lower() if user else '' %}
{% if user and perfil in ['admin', 'direcao', 'gestor'] %}
<button onclick="window.location.href='/modulo3';">
  <span>MÓDULO 3</span>
  <span>Férias Cheque</span>
</button>
{% endif %}

<!-- MÓDULO 4 - Auditores e Operacional -->
{% if user and perfil in ['admin', 'auditores', 'operacional'] %}
<button onclick="window.location.href='/modulo4';">
  <span>MÓDULO 4</span>
  <span>Seguro de Vida</span>
</button>
{% endif %}

<!-- MÓDULO 5 - Auditores e Operacional -->
{% if user and perfil in ['admin', 'auditores', 'operacional'] %}
<button onclick="window.location.href='/modulo5';">
  <span>MÓDULO 5</span>
  <span>13º Salário</span>
</button>
{% endif %}
```

---

### **SOLUÇÃO 2: Via Banco de Dados (Dinâmico)**

**Script SQL completo:**

```sql
-- ============================================
-- CONFIGURAÇÃO DE PERMISSÕES POR MÓDULO
-- ============================================

-- Limpar permissões existentes
DELETE FROM profile_module_permissions;

-- ============================================
-- PERFIL: DIREÇÃO
-- ============================================
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome = 'Direção'),
    m.id,
    1, 0, 0  -- Apenas visualização
FROM modulos m
WHERE m.codigo IN ('modulo1', 'modulo2', 'modulo3');

-- ============================================
-- PERFIL: GESTOR
-- ============================================
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome = 'Gestor'),
    m.id,
    1, 0, 0  -- Apenas visualização
FROM modulos m
WHERE m.codigo IN ('modulo1', 'modulo2', 'modulo3');

-- ============================================
-- PERFIL: AUDITORES
-- ============================================
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome = 'Auditores'),
    m.id,
    1, 1, 0  -- Visualização + Edição
FROM modulos m
WHERE m.codigo IN ('modulo1', 'modulo2', 'modulo4', 'modulo5', 'modulo6');

-- ============================================
-- PERFIL: OPERACIONAL
-- ============================================
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome = 'Operacional'),
    m.id,
    1, 1, 0  -- Visualização + Edição
FROM modulos m
WHERE m.codigo IN ('modulo1', 'modulo2', 'modulo4', 'modulo5', 'modulo6');

-- ============================================
-- VERIFICAR CONFIGURAÇÃO
-- ============================================
SELECT 
    p.nome as 'Perfil',
    m.codigo as 'Módulo',
    m.nome as 'Nome Módulo',
    CASE WHEN pmp.can_view = 1 THEN '✓' ELSE '✗' END as 'Ver',
    CASE WHEN pmp.can_edit = 1 THEN '✓' ELSE '✗' END as 'Editar',
    CASE WHEN pmp.can_delete = 1 THEN '✓' ELSE '✗' END as 'Deletar'
FROM profile_module_permissions pmp
JOIN perfis p ON pmp.perfil_id = p.id
JOIN modulos m ON pmp.modulo_id = m.id
ORDER BY p.nome, m.ordem;
```

---

## 🛠️ CRIAR FUNÇÃO HELPER NO TEMPLATE

Para facilitar, crie um arquivo `app/templates/_helpers.html`:

```jinja
{# Macro para verificar se usuário tem perfil #}
{% macro has_profile(user, profiles) %}
  {% set perfil_principal_lower = user.get('perfil_principal', '').lower() if user else '' %}
  {% set perfis_lower = user.get('perfis', []) | map('lower') | list if user else [] %}
  {% set profiles_lower = profiles | map('lower') | list %}
  {{ perfil_principal_lower in profiles_lower or (perfis_lower | select('in', profiles_lower) | list | length > 0) }}
{% endmacro %}

{# Macro para renderizar módulo com controle de acesso #}
{% macro modulo_button(user, modulo_num, nome, perfis_permitidos) %}
  {% if user and (user.get('is_admin') or has_profile(user, perfis_permitidos)) %}
  <button onclick="window.location.href='/modulo{{ modulo_num }}';">
    <span>MÓDULO {{ modulo_num }}</span>
    <span>{{ nome }}</span>
  </button>
  {% endif %}
{% endmacro %}
```

**Usar no index.html:**

```html
{% import '_helpers.html' as helpers %}

<!-- Módulo 1 - Todos -->
{{ helpers.modulo_button(user, 1, 'OPS/Demitidos', ['admin', 'direcao', 'gestor', 'auditores', 'operacional']) }}

<!-- Módulo 3 - Apenas Direção e Gestor -->
{{ helpers.modulo_button(user, 3, 'Férias Cheque', ['direcao', 'gestor']) }}

<!-- Módulo 4 - Auditores e Operacional -->
{{ helpers.modulo_button(user, 4, 'Seguro de Vida', ['auditores', 'operacional']) }}
```

---

## 📊 MATRIZ DE ACESSO (Exemplo)

| Módulo | Admin | Direção | Gestor | Auditores | Operacional | Loyal |
|--------|-------|---------|--------|-----------|-------------|-------|
| Módulo 1 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Módulo 2 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Módulo 3 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Módulo 4 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Módulo 5 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Módulo 6 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Premium | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 🎯 RECOMENDAÇÃO

### **Para Começar (Mais Simples):**
✅ Use **Opção 1 (Template HTML)**
- Edite `app/templates/index.html`
- Adicione condições `{% if %}` em cada módulo
- Resultado imediato
- Fácil de entender e modificar

### **Para Sistema Complexo (Mais Flexível):**
✅ Use **Opção 2 (Banco de Dados)**
- Configure permissões via SQL
- Modifique template para ler do banco
- Permite mudanças sem redeploy
- Escala melhor

---

## 📝 EXEMPLO COMPLETO: Módulo 3

### **1. Template (index.html):**
```html
{% set perfil = user.get('perfil_principal', '').lower() if user else '' %}
{% if user and perfil in ['admin', 'direcao', 'gestor'] %}
<button onclick="window.location.href='/modulo3';">
  <span>MÓDULO 3</span>
  <span>Férias Cheque</span>
</button>
{% endif %}
```

### **2. Proteção Backend (main.py):**
```python
@app.get("/modulo3", response_class=HTMLResponse)
async def modulo3_page(request: Request):
    user = await require_auth_web(request)
    if isinstance(user, RedirectResponse):
        return user
    
    # Verificar perfil
    perfil = user.get('perfil_principal', '').lower()
    perfis = [p.lower() for p in user.get('perfis', [])]
    
    if not user.get('is_admin') and perfil not in ['direcao', 'gestor'] and 'direcao' not in perfis and 'gestor' not in perfis:
        return RedirectResponse(url="/index")
    
    return templates.TemplateResponse("modulo3.html", {
        "request": request,
        "user": user
    })
```

### **3. SQL (opcional):**
```sql
-- Configurar no banco
INSERT INTO profile_module_permissions (perfil_id, modulo_id, can_view, can_edit, can_delete)
SELECT 
    (SELECT id FROM perfis WHERE nome IN ('Direção', 'Gestor')),
    (SELECT id FROM modulos WHERE codigo = 'modulo3'),
    1, 0, 0;
```

---

## ✅ CHECKLIST

Para cada módulo que você quer restringir:

1. ☐ **Decidir quais perfis têm acesso**
2. ☐ **Adicionar condição no template** (`{% if %}`)
3. ☐ **Proteger rota no backend** (verificar perfil)
4. ☐ **Testar com cada perfil**
5. ☐ **Documentar matriz de acesso**

---

## 🚀 COMO COMEÇAR AGORA

### **Passo 1: Defina a Matriz**
Crie um arquivo `matriz_acesso.md`:
```
Módulo 1: Todos
Módulo 2: Todos
Módulo 3: Direção, Gestor
Módulo 4: Auditores, Operacional
...
```

### **Passo 2: Edite o Template**
Abra `app/templates/index.html` e adicione condições nos módulos.

### **Passo 3: Teste**
Faça login com cada perfil e verifique quais módulos aparecem.

---

**Quer que eu implemente isso para você? Me diga a matriz de acesso que você quer!**

// auth.js
// Funções compartilhadas de autenticação

/**
 * Verifica se o usuário está autenticado
 * Redireciona para login se não estiver
 */
function checkAuth() {
  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/';
    return false;
  }
  return true;
}

/**
 * Retorna o token de acesso
 */
function getToken() {
  return localStorage.getItem('access_token');
}

/**
 * Retorna os dados do usuário armazenados
 */
function getStoredUser() {
  const userStr = localStorage.getItem('user');
  return userStr ? JSON.parse(userStr) : null;
}

/**
 * Faz logout do sistema
 */
async function logout() {
  const token = getToken();
  
  if (token) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
    } catch (error) {
      console.error('Erro no logout:', error);
    }
  }
  
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
  window.location.href = '/';
}

/**
 * Busca informações atualizadas do usuário
 */
async function getCurrentUser() {
  const token = getToken();
  if (!token) return null;
  
  try {
    const response = await fetch('/api/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Sessão inválida');
    }
    
    const user = await response.json();
    
    // Atualizar localStorage
    localStorage.setItem('user', JSON.stringify(user));
    
    return user;
  } catch (error) {
    console.error('Erro ao buscar usuário:', error);
    logout();
    return null;
  }
}

/**
 * Verifica se o usuário tem uma permissão específica
 */
async function hasPermission(moduloCodigo, permissaoCodigo) {
  const token = getToken();
  if (!token) return false;
  
  try {
    const response = await fetch(`/api/auth/check-permission/${moduloCodigo}/${permissaoCodigo}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) return false;
    
    const data = await response.json();
    return data.has_permission;
  } catch (error) {
    console.error('Erro ao verificar permissão:', error);
    return false;
  }
}

/**
 * Busca módulos acessíveis pelo usuário
 */
async function getMyModules() {
  const token = getToken();
  if (!token) return [];
  
  try {
    const response = await fetch('/api/auth/my-modules', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) return [];
    
    return await response.json();
  } catch (error) {
    console.error('Erro ao buscar módulos:', error);
    return [];
  }
}

/**
 * Verifica se o usuário é admin
 */
function isAdmin() {
  const user = getStoredUser();
  return user ? user.is_admin : false;
}

/**
 * Exibe informações do usuário logado no header
 */
async function displayUserInfo(elementId = 'user-display') {
  const user = await getCurrentUser();
  if (user) {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = user.nome_completo;
    }
  }
}

/**
 * Mostra/esconde elementos baseado em permissão
 */
async function toggleElementByPermission(elementId, moduloCodigo, permissaoCodigo) {
  const has = await hasPermission(moduloCodigo, permissaoCodigo);
  const element = document.getElementById(elementId);
  
  if (element) {
    if (has) {
      element.classList.remove('hidden');
    } else {
      element.classList.add('hidden');
    }
  }
}

/**
 * Mostra/esconde elementos apenas para admin
 */
function toggleElementForAdmin(elementId) {
  const element = document.getElementById(elementId);
  
  if (element) {
    if (isAdmin()) {
      element.classList.remove('hidden');
    } else {
      element.classList.add('hidden');
    }
  }
}

// Exportar para uso global
window.authUtils = {
  checkAuth,
  getToken,
  getStoredUser,
  logout,
  getCurrentUser,
  hasPermission,
  getMyModules,
  isAdmin,
  displayUserInfo,
  toggleElementByPermission,
  toggleElementForAdmin
};

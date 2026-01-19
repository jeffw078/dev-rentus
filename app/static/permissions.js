// permissions.js
// Sistema para ocultar/mostrar elementos baseado em permissões

/**
 * Verifica permissão e retorna true/false
 */
async function checkPermission(moduloCodigo, permissaoCodigo) {
  const token = localStorage.getItem('access_token');
  if (!token) return false;
  
  try {
    const response = await fetch(`/api/auth/check-permission/${moduloCodigo}/${permissaoCodigo}`, {
      headers: { 'Authorization': `Bearer ${token}` }
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
 * Verifica se o usuário tem um perfil específico
 */
async function hasProfile(profileName) {
  const token = localStorage.getItem('access_token');
  if (!token) return false;
  
  try {
    const response = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) return false;
    
    const user = await response.json();
    
    // Normalizar para lowercase para comparação
    const profileLower = profileName.toLowerCase();
    const userPerfis = (user.perfis || []).map(p => p.toLowerCase());
    const perfilPrincipal = (user.perfil_principal || '').toLowerCase();
    
    return userPerfis.includes(profileLower) || perfilPrincipal === profileLower;
  } catch (error) {
    console.error('Erro ao verificar perfil:', error);
    return false;
  }
}

/**
 * Verifica se o usuário é admin
 */
async function isAdmin() {
  const token = localStorage.getItem('access_token');
  if (!token) return false;
  
  try {
    const response = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) return false;
    
    const user = await response.json();
    return user.is_admin;
  } catch (error) {
    console.error('Erro ao verificar admin:', error);
    return false;
  }
}

/**
 * Oculta elemento se o usuário NÃO tiver permissão
 * Uso: data-require-permission="modulo2:edit"
 */
async function hideElementsWithoutPermission() {
  const elements = document.querySelectorAll('[data-require-permission]');
  
  for (const element of elements) {
    const permission = element.getAttribute('data-require-permission');
    const [modulo, permissao] = permission.split(':');
    
    const hasPermission = await checkPermission(modulo, permissao);
    
    if (!hasPermission) {
      element.style.display = 'none';
      element.setAttribute('data-hidden-by-permission', 'true');
    }
  }
}

/**
 * Oculta elemento se o usuário NÃO tiver o perfil
 * Uso: data-require-profile="admin"
 */
async function hideElementsWithoutProfile() {
  const elements = document.querySelectorAll('[data-require-profile]');
  
  console.log(`[Permissions] Verificando ${elements.length} elemento(s) com data-require-profile`);
  
  for (const element of elements) {
    const requiredProfile = element.getAttribute('data-require-profile');
    console.log(`[Permissions] Verificando perfil requerido: "${requiredProfile}"`);
    
    const userHasProfile = await hasProfile(requiredProfile);
    console.log(`[Permissions] Usuário tem perfil "${requiredProfile}": ${userHasProfile}`);
    
    if (!userHasProfile) {
      element.style.display = 'none';
      element.setAttribute('data-hidden-by-profile', 'true');
      console.log(`[Permissions] Elemento escondido (perfil não encontrado)`);
    } else {
      console.log(`[Permissions] Elemento visível (perfil encontrado)`);
    }
  }
}

/**
 * Oculta elemento se o usuário NÃO for admin
 * Uso: data-require-admin="true"
 */
async function hideElementsNonAdmin() {
  const elements = document.querySelectorAll('[data-require-admin="true"]');
  
  const userIsAdmin = await isAdmin();
  
  if (!userIsAdmin) {
    elements.forEach(element => {
      element.style.display = 'none';
      element.setAttribute('data-hidden-by-admin', 'true');
    });
  }
}

/**
 * Oculta elementos para perfis específicos (blacklist)
 * Uso: data-hide-for-profiles="direcao,gestor"
 */
async function hideElementsForProfiles() {
  const elements = document.querySelectorAll('[data-hide-for-profiles]');
  
  if (elements.length === 0) return;
  
  const token = localStorage.getItem('access_token');
  if (!token) return;
  
  try {
    const response = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) return;
    
    const user = await response.json();
    
    elements.forEach(element => {
      const hiddenProfiles = element.getAttribute('data-hide-for-profiles').split(',');
      
      // Verificar se usuário tem algum dos perfis que devem esconder o elemento
      const shouldHide = user.perfis.some(perfil => hiddenProfiles.includes(perfil)) ||
                        hiddenProfiles.includes(user.perfil_principal);
      
      if (shouldHide) {
        element.style.display = 'none';
        element.setAttribute('data-hidden-for-profile', 'true');
      }
    });
  } catch (error) {
    console.error('Erro ao verificar perfis:', error);
  }
}

/**
 * Mostra elementos apenas para perfis específicos (whitelist)
 * Uso: data-show-for-profiles="admin,auditor"
 */
async function showElementsForProfiles() {
  const elements = document.querySelectorAll('[data-show-for-profiles]');
  
  if (elements.length === 0) return;
  
  const token = localStorage.getItem('access_token');
  if (!token) return;
  
  try {
    const response = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) return;
    
    const user = await response.json();
    
    elements.forEach(element => {
      const allowedProfiles = element.getAttribute('data-show-for-profiles').split(',');
      
      // Verificar se usuário tem algum dos perfis permitidos
      const shouldShow = user.is_admin || // Admin sempre vê
                        user.perfis.some(perfil => allowedProfiles.includes(perfil)) ||
                        allowedProfiles.includes(user.perfil_principal);
      
      if (!shouldShow) {
        element.style.display = 'none';
        element.setAttribute('data-hidden-show-only', 'true');
      }
    });
  } catch (error) {
    console.error('Erro ao verificar perfis:', error);
  }
}

/**
 * Inicializa o sistema de permissões
 * Chame esta função no DOMContentLoaded de cada página
 */
async function initPermissions() {
  await hideElementsWithoutPermission();
  await hideElementsWithoutProfile();
  await hideElementsNonAdmin();
  await hideElementsForProfiles();
  await showElementsForProfiles();
  
  // Marcar que as permissões foram verificadas
  // Isso permite que o CSS mostre os elementos permitidos
  document.body.classList.add('permissions-checked');
  console.log('[Permissions] Verificação concluída');
}

// Auto-inicializar se document já carregou
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPermissions);
} else {
  initPermissions();
}

// Exportar para uso global
window.permissionsSystem = {
  checkPermission,
  hasProfile,
  isAdmin,
  hideElementsWithoutPermission,
  hideElementsWithoutProfile,
  hideElementsNonAdmin,
  hideElementsForProfiles,
  showElementsForProfiles,
  initPermissions
};

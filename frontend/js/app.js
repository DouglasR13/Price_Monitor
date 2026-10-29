/**
 * Price Monitor Bot - Web Dashboard Controller
 */

// Determine API base URL dynamically
const API_BASE = (window.location.protocol === 'file:' || window.location.origin === 'null')
  ? 'http://127.0.0.1:8080'
  : ((window.location.port === '5500' || window.location.port === '3000')
      ? 'http://127.0.0.1:8080'
      : window.location.origin);

const state = {
  products: [],
  filteredProducts: [],
  stats: {},
  users: [],
  currentUser: { id: 1, name: "Administrador", role: "admin", email: "admin@radar.com" },
  activeFilter: 'all',
  searchQuery: '',
  selectedProduct: null,
  chart: null
};

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
  state.chart = new PriceHistoryChart('priceHistoryChart');
  initEventListeners();
  initAuthEventListeners();
  checkInitialAuth();
});

function checkInitialAuth() {
  const savedUser = localStorage.getItem('priceradar_user');
  const overlay = document.getElementById('authScreenOverlay');

  if (savedUser) {
    try {
      state.currentUser = JSON.parse(savedUser);
      if (overlay) overlay.classList.add('hidden');
      loadUsers();
      loadDashboardData();
    } catch (e) {
      localStorage.removeItem('priceradar_user');
      if (overlay) overlay.classList.remove('hidden');
    }
  } else {
    if (overlay) overlay.classList.remove('hidden');
  }
}

function initAuthEventListeners() {
  // Tab Switching (Entrar vs Criar Conta)
  const tabLogin = document.getElementById('tabBtnLogin');
  const tabReg = document.getElementById('tabBtnRegister');
  const formLogin = document.getElementById('authLoginForm');
  const formReg = document.getElementById('authRegisterForm');

  tabLogin?.addEventListener('click', () => {
    tabLogin.classList.add('active');
    tabReg?.classList.remove('active');
    formLogin.style.display = 'block';
    formReg.style.display = 'none';
  });

  tabReg?.addEventListener('click', () => {
    tabReg.classList.add('active');
    tabLogin?.classList.remove('active');
    formReg.style.display = 'block';
    formLogin.style.display = 'none';
  });

  // Real-Time Password Strength Live Validator on Register
  const regPwdInput = document.getElementById('regPassword');
  regPwdInput?.addEventListener('input', () => {
    validatePasswordLive(regPwdInput.value);
  });

  // Login Submit
  document.getElementById('authLoginForm')?.addEventListener('submit', handleAuthLogin);
  // Register Submit
  document.getElementById('authRegisterForm')?.addEventListener('submit', handleAuthRegister);
  // Logout
  document.getElementById('btnLogout')?.addEventListener('click', handleLogout);

  // Email Report Modal & Trigger
  document.getElementById('btnEmailReport')?.addEventListener('click', openEmailReportModal);
  document.getElementById('btnTriggerEmailNow')?.addEventListener('click', handleTriggerEmailNow);
}

function initEventListeners() {
  // Search input
  const searchInput = document.getElementById('productSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.toLowerCase().trim();
      applyFilters();
    });
  }

  // Filter Pills
  const pills = document.querySelectorAll('.pill-btn');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeFilter = pill.dataset.filter;
      applyFilters();
    });
  });

  // User Profile Switcher (Admin only)
  const userSelect = document.getElementById('userSelector');
  if (userSelect) {
    userSelect.addEventListener('change', (e) => {
      const selectedId = parseInt(e.target.value);
      const found = state.users.find(u => u.id === selectedId);
      if (found) {
        state.currentUser = found;
        localStorage.setItem('priceradar_user', JSON.stringify(found));
        updateUserUI();
        loadDashboardData();
        showToast(`Perfil alterado para: ${found.name} (${found.role === 'admin' ? 'Administrador' : 'Usuário'})`);
      }
    });
  }

  // Open New User Modal
  document.getElementById('btnOpenNewUserModal')?.addEventListener('click', () => openModal('newUserModal'));
  document.getElementById('formNewUser')?.addEventListener('submit', handleCreateUser);

  // Header Action Buttons
  document.getElementById('btnNewProduct')?.addEventListener('click', () => openModal('newProductModal'));
  document.getElementById('btnSettings')?.addEventListener('click', openSettingsModal);
  document.getElementById('btnCheckAll')?.addEventListener('click', handleCheckAll);
  document.getElementById('btnManageStores')?.addEventListener('click', openStoresManagementModal);
  document.getElementById('btnBlockStoreManual')?.addEventListener('click', handleAddIgnoredStoreManual);

  // Modal Closers
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal-backdrop');
      if (modal) closeModal(modal.id);
    });
  });

  // Click outside modal to close
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal(modal.id);
    });
  });

  // New Product Form
  document.getElementById('formNewProduct')?.addEventListener('submit', handleCreateProduct);
  document.getElementById('btnPreviewSearch')?.addEventListener('click', handlePreviewSearch);

  // Settings Form
  document.getElementById('formSettings')?.addEventListener('submit', handleSaveSettings);
  document.getElementById('btnTestTelegram')?.addEventListener('click', handleTestTelegram);
}

// ==================== AUTH CONTROLLERS ====================

let lockoutTimerInterval = null;

function validatePasswordLive(pwd) {
  const hasLen = pwd.length >= 8;
  const hasUpper = /[A-Z]/.test(pwd);
  const hasNum = /[0-9]/.test(pwd);
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(pwd);

  updateRuleUI('ruleLen', hasLen);
  updateRuleUI('ruleUpper', hasUpper);
  updateRuleUI('ruleNum', hasNum);
  updateRuleUI('ruleSpecial', hasSpecial);

  const allValid = hasLen && hasUpper && hasNum && hasSpecial;
  const submitBtn = document.getElementById('btnSubmitRegister');
  if (submitBtn) {
    submitBtn.style.opacity = allValid ? '1' : '0.85';
  }
  return allValid;
}

function updateRuleUI(elementId, isValid) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.className = `rule-item ${isValid ? 'valid' : 'invalid'}`;
  const icon = el.querySelector('span');
  if (icon) icon.textContent = isValid ? '🟢' : '⚪';
}

async function handleAuthLogin(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  const feedback = document.getElementById('loginFeedback');
  const submitBtn = document.getElementById('btnSubmitLogin');

  feedback.style.display = 'none';
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner"></span> Verificando credenciais...`;

  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (!res.ok) {
      const err = data.detail || {};
      if (res.status === 429 || err.error === 'LOCKED') {
        // Account is locked for 3 minutes!
        startLockoutCountdown(err.remaining_seconds || 180);
      } else {
        feedback.style.display = 'block';
        feedback.textContent = err.message || 'E-mail ou senha incorretos.';
      }
      return;
    }

    // Success!
    state.currentUser = data.user;
    localStorage.setItem('priceradar_user', JSON.stringify(data.user));
    document.getElementById('authScreenOverlay')?.classList.add('hidden');
    document.getElementById('authLoginForm').reset();
    showToast(`Bem-vindo de volta, ${data.user.name}!`);

    await loadUsers();
    await loadDashboardData();
  } catch (err) {
    feedback.style.display = 'block';
    feedback.textContent = 'Erro ao conectar ao servidor. Tente novamente.';
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `Entrar no Sistema`;
  }
}

function startLockoutCountdown(seconds) {
  const banner = document.getElementById('loginLockoutBanner');
  const timerText = document.getElementById('lockoutTimerText');
  const submitBtn = document.getElementById('btnSubmitLogin');
  const pwdInput = document.getElementById('loginPassword');

  if (banner) banner.classList.add('show');
  if (submitBtn) submitBtn.disabled = true;
  if (pwdInput) pwdInput.disabled = true;

  if (lockoutTimerInterval) clearInterval(lockoutTimerInterval);

  let remaining = seconds;
  const updateDisplay = () => {
    const m = Math.floor(remaining / 60).toString().padStart(2, '0');
    const s = (remaining % 60).toString().padStart(2, '0');
    if (timerText) timerText.textContent = `${m}:${s}`;
  };

  updateDisplay();

  lockoutTimerInterval = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(lockoutTimerInterval);
      if (banner) banner.classList.remove('show');
      if (submitBtn) submitBtn.disabled = false;
      if (pwdInput) pwdInput.disabled = false;
      showToast('Bloqueio encerrado. Você já pode tentar realizar o login novamente.', 'success');
    } else {
      updateDisplay();
    }
  }, 1000);
}

async function handleAuthRegister(e) {
  e.preventDefault();
  const name = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value.trim();
  const feedback = document.getElementById('regFeedback');
  const submitBtn = document.getElementById('btnSubmitRegister');

  if (feedback) feedback.style.display = 'none';

  if (!name) {
    if (feedback) {
      feedback.style.display = 'block';
      feedback.textContent = 'Por favor, informe seu nome completo.';
    }
    return;
  }

  if (!validatePasswordLive(password)) {
    if (feedback) {
      feedback.style.display = 'block';
      feedback.textContent = '⚠️ A senha não cumpre todos os requisitos de segurança listados acima (mínimo 8 caracteres, 1 maiúscula, 1 número e 1 caractere especial).';
    }
    showToast('A senha não cumpre todos os requisitos de segurança.', 'error');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner"></span> Criando perfil seguro no Supabase...`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Erro ao registrar.');
    }

    // Auto-login
    state.currentUser = data.user;
    localStorage.setItem('priceradar_user', JSON.stringify(data.user));
    document.getElementById('authScreenOverlay')?.classList.add('hidden');
    document.getElementById('authRegisterForm').reset();
    showToast(`Conta criada com sucesso! Bem-vindo, ${name}!`, 'success');

    await loadUsers();
    await loadDashboardData();
  } catch (err) {
    const msg = err.name === 'AbortError'
      ? 'Tempo limite esgotado ao conectar ao servidor. Verifique sua conexão ou se o backend está ligado.'
      : (err.message || 'Erro ao registrar usuário.');
    if (feedback) {
      feedback.style.display = 'block';
      feedback.textContent = msg;
    }
    showToast(`Erro no cadastro: ${msg}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `Cadastrar e Acessar Monitor`;
  }
}

function handleLogout() {
  localStorage.removeItem('priceradar_user');
  document.getElementById('authScreenOverlay')?.classList.remove('hidden');
  showToast('Você saiu da sua conta.');
}

window.fillDemoCredentials = function(email, password) {
  const emailInput = document.getElementById('loginEmail');
  const pwdInput = document.getElementById('loginPassword');
  if (emailInput) emailInput.value = email;
  if (pwdInput) pwdInput.value = password;
  document.getElementById('loginFeedback').style.display = 'none';
};

// ==================== USER PROFILE & PERMISSIONS MANAGEMENT ====================

async function loadUsers() {
  try {
    const res = await fetch(`${API_BASE}/api/auth/users`);
    if (!res.ok) return;
    state.users = await res.json();
    setupUserSelector();
  } catch (err) {
    console.error('Erro ao carregar usuários:', err);
  }
}

function setupUserSelector() {
  const select = document.getElementById('userSelector');
  if (!select) return;

  select.innerHTML = state.users.map(u => `
    <option value="${u.id}" ${u.id === state.currentUser.id ? 'selected' : ''}>
      ${u.role === 'admin' ? '👑' : '👤'} ${u.name} (${u.role === 'admin' ? 'Admin' : 'Usuário'})
    </option>
  `).join('');

  updateUserUI();
}

function updateUserUI() {
  const u = state.currentUser;
  const avatar = document.getElementById('userAvatar');
  const roleTag = document.getElementById('userRoleTag');
  const userName = document.getElementById('userName');
  const banner = document.getElementById('userScopeBanner');
  const bannerText = document.getElementById('userScopeText');
  const userSelectorWrapper = document.getElementById('userProfileBadge');

  if (avatar) avatar.textContent = u.role === 'admin' ? '👑' : '👤';
  if (roleTag) {
    roleTag.textContent = u.role === 'admin' ? 'Admin' : 'Usuário';
    roleTag.style.color = u.role === 'admin' ? '#38bdf8' : '#34d399';
  }
  if (userName) userName.textContent = u.name;

  // PERMISSION CONTROL: Hide Admin-Only buttons for regular users!
  const adminOnlyButtons = document.querySelectorAll('[data-admin-only="true"]');
  adminOnlyButtons.forEach(btn => {
    btn.style.display = u.role === 'admin' ? 'inline-flex' : 'none';
  });

  // Scope Banner
  if (banner && bannerText) {
    if (u.role === 'admin') {
      banner.className = 'user-scope-banner admin';
      bannerText.innerHTML = `👑 <strong>Modo Administrador Ativo:</strong> Visualizando todos os produtos monitorados de todos os usuários.`;
      document.getElementById('btnOpenNewUserModal').style.display = 'inline-block';
    } else {
      banner.className = 'user-scope-banner user';
      bannerText.innerHTML = `👤 <strong>Sua Área Segura (${u.name}):</strong> Visualizando exclusivamente os seus produtos monitorados com alertas automáticos de preços.`;
      document.getElementById('btnOpenNewUserModal').style.display = 'none';
    }
  }
}

async function handleCreateUser(e) {
  e.preventDefault();
  const name = document.getElementById('newUserName').value.trim();
  const email = document.getElementById('newUserEmail').value.trim();
  const password = document.getElementById('newUserPassword').value.trim();
  const telegram = document.getElementById('newUserTelegram').value.trim();

  const submitBtn = document.getElementById('btnSubmitNewUser');
  submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password, telegram_chat_id: telegram })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha ao criar usuário');

    showToast(`Usuário "${name}" cadastrado com sucesso!`, 'success');
    closeModal('newUserModal');
    document.getElementById('formNewUser').reset();

    await loadUsers();
    // Switch to new user
    state.currentUser = data.user;
    localStorage.setItem('priceradar_user', JSON.stringify(data.user));
    setupUserSelector();
    await loadDashboardData();
  } catch (err) {
    showToast(`Erro: ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
  }
}

// ==================== EMAIL REPORT 22:00 MODAL & TRIGGER ====================

function openEmailReportModal() {
  const u = state.currentUser;
  const recipientSpan = document.getElementById('emailModalRecipient');
  if (recipientSpan) recipientSpan.textContent = `${u.name} <${u.email}>`;
  const feedback = document.getElementById('emailTestFeedback');
  if (feedback) feedback.style.display = 'none';
  openModal('emailReportModal');
}

async function handleTriggerEmailNow() {
  const btn = document.getElementById('btnTriggerEmailNow');
  const feedback = document.getElementById('emailTestFeedback');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Gerando e enviando relatório...`;
  feedback.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/api/email/test-daily-report?user_id=${state.currentUser.id}`, {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha ao enviar relatório.');

    feedback.style.display = 'block';
    feedback.style.background = 'rgba(16, 185, 129, 0.15)';
    feedback.style.border = '1px solid rgba(16, 185, 129, 0.4)';
    feedback.style.color = '#a7f3d0';

    if (data.mode === 'SMTP_SENT') {
      feedback.innerHTML = `✅ <strong>E-mail real enviado com sucesso!</strong><br />Verifique a caixa de entrada de <em>${data.recipient}</em>.`;
    } else {
      feedback.innerHTML = `✅ <strong>Relatório gerado com sucesso!</strong><br />${data.message}<br /><span style="font-size: 0.75rem; color: #94a3b8;">${data.products_count} produtos incluídos com comparativo de lojas e recomendação de compra.</span>`;
    }
    showToast('Relatório de e-mail enviado com sucesso!', 'success');
  } catch (err) {
    feedback.style.display = 'block';
    feedback.style.background = 'rgba(244, 63, 94, 0.15)';
    feedback.style.border = '1px solid rgba(244, 63, 94, 0.4)';
    feedback.style.color = '#fecdd3';
    feedback.innerHTML = `⚠️ Erro ao disparar e-mail: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `✉️ Enviar / Testar Relatório por E-mail Agora`;
  }
}

// ==================== DATA FETCHING ====================

async function loadDashboardData() {
  try {
    await Promise.all([fetchProducts(), fetchStats()]);
  } catch (err) {
    console.error('Erro carregando dados:', err);
    showToast('Erro ao carregar dados do servidor', 'error');
  }
}

async function fetchProducts() {
  const u = state.currentUser;
  const url = `${API_BASE}/api/products?role=${u.role}&user_id=${u.id}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Falha ao buscar produtos');
  state.products = await res.json();
  applyFilters();
}

async function fetchStats() {
  const res = await fetch(`${API_BASE}/api/dashboard/stats`);
  if (!res.ok) return;
  state.stats = await res.json();
  renderStats();
}

function applyFilters() {
  let list = [...state.products];

  // Search filter
  if (state.searchQuery) {
    list = list.filter(p => 
      p.name.toLowerCase().includes(state.searchQuery) ||
      p.brand.toLowerCase().includes(state.searchQuery) ||
      p.category.toLowerCase().includes(state.searchQuery)
    );
  }

  // Category & Bargain pills
  if (state.activeFilter === 'bargain') {
    list = list.filter(p => p.latest_record?.recommendation === 'EXCELLENT');
  } else if (state.activeFilter !== 'all') {
    list = list.filter(p => p.category.toLowerCase() === state.activeFilter.toLowerCase());
  }

  state.filteredProducts = list;
  renderProducts();
}

// ==================== RENDERING ====================

function renderStats() {
  const s = state.stats;
  document.getElementById('statTotalTracked').textContent = s.total_products || 0;
  document.getElementById('statBargains').textContent = s.today_bargains || 0;
  
  const avg = s.average_market_price || 0;
  document.getElementById('statAvgPrice').textContent = 'R$ ' + avg.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  
  document.getElementById('statTotalChecks').textContent = s.total_price_checks || 0;
}

function renderProducts() {
  const container = document.getElementById('productsGrid');
  if (!container) return;

  if (state.filteredProducts.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: #64748b;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
        <h3>Nenhum produto encontrado</h3>
        <p style="font-size: 0.9rem; margin-top: 0.5rem;">Tente ajustar seus termos de busca ou adicione um novo produto para monitorar.</p>
        <button class="btn btn-primary btn-sm" style="margin-top: 1.25rem;" onclick="openModal('newProductModal')">+ Adicionar Produto</button>
      </div>
    `;
    return;
  }

  container.innerHTML = state.filteredProducts.map(p => {
    const rec = p.latest_record || {};
    const minPrice = rec.min_price || 0;
    const avgPrice = rec.avg_price || 0;
    const maxPrice = rec.max_price || 0;
    const bestStore = rec.best_store || 'Loja Online';
    const bestUrl = rec.best_url || '#';
    const delta = rec.delta_pct || 0;
    const recommendation = rec.recommendation || 'NORMAL';
    const reason = rec.recommendation_reason || 'Monitoramento em andamento.';

    const recClass = recommendation === 'EXCELLENT' ? 'rec-excellent' : (recommendation === 'HIGH' ? 'rec-high' : 'rec-normal');

    let deltaBadge = '';
    if (delta < 0) {
      deltaBadge = `<span class="price-delta drop">📉 ${delta.toFixed(1)}%</span>`;
    } else if (delta > 0) {
      deltaBadge = `<span class="price-delta rise">📈 +${delta.toFixed(1)}%</span>`;
    } else {
      deltaBadge = `<span class="price-delta stable">➡️ 0.0%</span>`;
    }

    let verdictIcon = '⚖️';
    let verdictTitle = 'Preço Regular';
    if (recommendation === 'EXCELLENT') {
      verdictIcon = '🎯';
      verdictTitle = 'Excelente Momento de Compra!';
    } else if (recommendation === 'HIGH') {
      verdictIcon = '⏳';
      verdictTitle = 'Preço Alto — Aguarde';
    }

    const defaultImg = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&auto=format&fit=crop&q=80';
    const imgUrl = p.image_url || defaultImg;
    const offers = rec.offers || [];
    const offersCount = offers.length;

    let offersPreviewHtml = '';
    if (offersCount > 0) {
      const topStores = offers.slice(0, 3).map(o => {
        const offBadge = o.is_official ? '⭐' : '';
        return `<span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; color: #cbd5e1; white-space: nowrap;">${offBadge}${o.store_name}: <strong>R$ ${Math.round(o.price).toLocaleString('pt-BR')}</strong></span>`;
      }).join(' ');
      offersPreviewHtml = `
        <div style="margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; cursor: pointer;" onclick="openProductStoresModal(${p.id})" title="Clique para ver todas as lojas">
          ${topStores}
          ${offersCount > 3 ? `<span style="font-size: 0.7rem; color: #38bdf8;">+${offersCount - 3} lojas</span>` : ''}
        </div>
      `;
    }

    return `
      <div class="product-card ${recClass}" id="product-card-${p.id}">
        <div class="card-top">
          <div class="product-thumb-wrapper">
            <img src="${imgUrl}" alt="${p.name}" class="product-thumb" loading="lazy" onerror="this.src='${defaultImg}'" />
          </div>
          <div class="product-meta">
            <div class="badges-row">
              <span class="tag-badge brand">${p.brand}</span>
              <span class="tag-badge">${p.category}</span>
              ${state.currentUser.role === 'admin' ? `<span class="tag-badge" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1;" title="Cadastrado por ${p.owner_name || 'Admin'}">👤 ${p.owner_name || 'Admin'}</span>` : ''}
            </div>
            <h3 class="product-title" title="${p.name}">${p.name}</h3>
            ${p.target_price ? `<div style="font-size: 0.72rem; color: #f59e0b;">🎯 Alvo: R$ ${p.target_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>` : ''}
          </div>
        </div>

        <div class="price-section">
          <div class="main-price-row">
            <div>
              <div class="price-label">Menor Preço Hoje</div>
              <div class="price-current">R$ ${minPrice.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
            </div>
            <div>${deltaBadge}</div>
          </div>
          <div class="store-min-max-bar">
            <span>Loja: <strong class="best-store-chip">🏪 ${bestStore}</strong></span>
            <span>Média: R$ ${Math.round(avgPrice).toLocaleString('pt-BR')}</span>
          </div>
          ${offersPreviewHtml}
        </div>

        <div class="verdict-pill ${recClass}">
          <span class="verdict-icon">${verdictIcon}</span>
          <div>
            <strong>${verdictTitle}</strong><br />
            <span>${reason}</span>
          </div>
        </div>

        <div class="card-actions">
          <a href="${bestUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-emerald btn-sm btn-store">
            🛒 Comprar na ${bestStore}
          </a>
          <button class="btn btn-secondary btn-sm" onclick="openProductStoresModal(${p.id})" title="Ver todas as lojas onde este produto foi achado">
            🏪 Lojas (${offersCount || 1})
          </button>
          <button class="btn btn-secondary btn-sm" onclick="openHistoryModal(${p.id})">
            📈 Gráfico
          </button>
          <button class="btn btn-secondary btn-sm" id="btn-check-${p.id}" onclick="handleSingleCheck(${p.id})">
            🔄 Verificar
          </button>
          <button class="btn btn-outline-danger btn-sm" title="Excluir monitoramento deste produto" onclick="handleDeleteProduct(${p.id}, '${p.name.replace(/'/g, "\\'")}')">
            🗑️ Excluir
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// ==================== ACTIONS ====================

async function handleDeleteProduct(productId, productName) {
  const confirmed = confirm(`Deseja realmente excluir o monitoramento de:\n\n"${productName}"\n\nTodos os registros e gráficos deste produto serão apagados.`);
  if (!confirmed) return;

  try {
    const res = await fetch(`${API_BASE}/api/products/${productId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Falha ao excluir produto');
    showToast(`Produto "${productName}" excluído com sucesso!`, 'success');
    await loadDashboardData();
  } catch (err) {
    console.error(err);
    showToast('Erro ao excluir produto.', 'error');
  }
}

async function handleSingleCheck(productId) {
  const btn = document.getElementById(`btn-check-${productId}`);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Buscando...`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/products/${productId}/check?notify_telegram=false`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Falha na verificação de preço');
    const data = await res.json();
    
    showToast(`Preço atualizado: R$ ${data.record.min_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})} (${data.record.best_store})`, 'success');
    await loadDashboardData();
  } catch (err) {
    console.error(err);
    showToast('Erro ao verificar preço do produto.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `🔄 Verificar`;
    }
  }
}

async function handleCheckAll() {
  const btn = document.getElementById('btnCheckAll');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Verificando Todos...`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/check-all?notify_telegram=true`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Falha na varredura geral');
    const data = await res.json();
    showToast(`Varredura concluída! ${data.total_checked} produtos verificados.`, 'success');
    await loadDashboardData();
  } catch (err) {
    console.error(err);
    showToast('Erro ao executar varredura geral.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `🔄 Verificar Todos Agora`;
    }
  }
}

async function handlePreviewSearch() {
  const name = document.getElementById('newProdName').value.trim();
  const brand = document.getElementById('newProdBrand').value.trim();
  const query = document.getElementById('newProdQuery').value.trim() || `${brand} ${name}`;

  if (!query) {
    showToast('Digite ao menos o nome do produto ou termo de busca.', 'error');
    return;
  }

  const btn = document.getElementById('btnPreviewSearch');
  const box = document.getElementById('previewResultsBox');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Buscando ofertas ao vivo...`;

  try {
    const res = await fetch(`${API_BASE}/api/search-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, brand })
    });
    const data = await res.json();

    if (data.offers && data.offers.length > 0) {
      box.classList.add('visible');
      box.innerHTML = `
        <div style="font-size: 0.8rem; color: #34d399; font-weight: 700; margin-bottom: 0.5rem;">
          ✅ Encontramos ${data.offers.length} ofertas ao vivo no mercado!
        </div>
        <div style="font-size: 0.85rem; color: #fff; margin-bottom: 0.3rem;">
          Menor Preço: <strong style="color: #38bdf8;">R$ ${data.min_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</strong> (${data.best_store})
        </div>
        <div style="font-size: 0.78rem; color: #94a3b8;">
          Média: R$ ${data.avg_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})} | Maior: R$ ${data.max_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}
        </div>
      `;
      // Auto fill image if found
      if (data.image_url && !document.getElementById('newProdImage').value) {
        document.getElementById('newProdImage').value = data.image_url;
      }
    } else {
      box.classList.add('visible');
      box.innerHTML = `<span style="color: #f59e0b; font-size: 0.82rem;">⚠️ Nenhuma oferta direta encontrada para esse termo. Ajuste a busca.</span>`;
    }
  } catch (err) {
    console.error(err);
    showToast('Erro ao testar busca.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🔍 Testar Busca ao Vivo`;
  }
}

async function handleCreateProduct(e) {
  e.preventDefault();
  const name = document.getElementById('newProdName').value.trim();
  const brand = document.getElementById('newProdBrand').value.trim();
  const category = document.getElementById('newProdCategory').value;
  const targetPriceVal = document.getElementById('newProdTargetPrice').value;
  const search_query = document.getElementById('newProdQuery').value.trim() || `${brand} ${name}`;
  const image_url = document.getElementById('newProdImage').value.trim() || null;

  const payload = {
    name,
    brand,
    category,
    search_query,
    target_price: targetPriceVal ? parseFloat(targetPriceVal) : null,
    image_url,
    is_active: true
  };

  const submitBtn = document.getElementById('btnSubmitNewProd');
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner"></span> Cadastrando e Buscando...`;

  try {
    const res = await fetch(`${API_BASE}/api/products?user_id=${state.currentUser.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Falha ao cadastrar produto');
    
    showToast(`Produto "${name}" cadastrado com sucesso!`, 'success');
    closeModal('newProductModal');
    document.getElementById('formNewProduct').reset();
    document.getElementById('previewResultsBox').classList.remove('visible');
    await loadDashboardData();
  } catch (err) {
    console.error(err);
    showToast('Erro ao cadastrar produto.', 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `Cadastrar e Começar a Monitorar`;
  }
}

// ==================== HISTORY MODAL & CHART ====================

async function openHistoryModal(productId) {
  const prod = state.products.find(p => p.id === productId);
  if (!prod) return;

  state.selectedProduct = prod;
  document.getElementById('historyProdTitle').textContent = `${prod.name} (${prod.brand})`;
  document.getElementById('historyTargetPrice').textContent = prod.target_price ? `R$ ${prod.target_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}` : 'Não definida';
  
  openModal('historyModal');

  try {
    const res = await fetch(`${API_BASE}/api/products/${productId}/history?limit=30`);
    const history = await res.json();

    // Summary stats
    if (history.length > 0) {
      const minP = Math.min(...history.map(h => h.min_price));
      const maxP = Math.max(...history.map(h => h.max_price));
      const avgP = history.reduce((acc, h) => acc + h.min_price, 0) / history.length;

      document.getElementById('chartMinPrice').textContent = `R$ ${minP.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
      document.getElementById('chartMaxPrice').textContent = `R$ ${maxP.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
      document.getElementById('chartAvgPrice').textContent = `R$ ${avgP.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
      document.getElementById('chartPointsCount').textContent = history.length;

      // Update Chart
      setTimeout(() => {
        state.chart.setData(history, prod.target_price);
      }, 50);

      // Render Table
      const tbody = document.getElementById('historyTableBody');
      tbody.innerHTML = history.slice().reverse().map(h => {
        const dateStr = h.checked_at.replace('T', ' ').slice(0, 16);
        const delta = h.delta_pct || 0;
        let deltaHtml = '0.0%';
        if (delta < 0) deltaHtml = `<span style="color: #34d399;">📉 ${delta.toFixed(1)}%</span>`;
        else if (delta > 0) deltaHtml = `<span style="color: #fb7185;">📈 +${delta.toFixed(1)}%</span>`;

        return `
          <tr>
            <td>${dateStr}</td>
            <td><strong>R$ ${h.min_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</strong></td>
            <td>${h.best_store}</td>
            <td>${deltaHtml}</td>
          </tr>
        `;
      }).join('');
    }
  } catch (err) {
    console.error('Erro ao buscar histórico:', err);
  }
}

// ==================== SETTINGS MODAL ====================

async function openSettingsModal() {
  try {
    const res = await fetch(`${API_BASE}/api/settings`);
    const data = await res.json();
    document.getElementById('inputTelegramToken').value = data.telegram_bot_token || '';
    document.getElementById('inputTelegramChatId').value = data.telegram_chat_id || '';
  } catch (err) {
    console.error(err);
  }
  openModal('settingsModal');
}

async function handleSaveSettings(e) {
  e.preventDefault();
  const token = document.getElementById('inputTelegramToken').value.trim();
  const chat_id = document.getElementById('inputTelegramChatId').value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chat_id })
    });
    if (!res.ok) throw new Error('Falha ao salvar configurações');
    showToast('Configurações salvas com sucesso!', 'success');
    closeModal('settingsModal');
  } catch (err) {
    showToast('Erro ao salvar configurações.', 'error');
  }
}

async function handleTestTelegram() {
  const token = document.getElementById('inputTelegramToken').value.trim();
  const chat_id = document.getElementById('inputTelegramChatId').value.trim();

  if (!chat_id) {
    showToast('Preencha seu Chat ID do Telegram.', 'error');
    return;
  }

  const btn = document.getElementById('btnTestTelegram');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Enviando teste...`;

  try {
    const res = await fetch(`${API_BASE}/api/telegram/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: token, chat_id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao enviar mensagem');
    showToast('Mensagem de teste enviada para seu Telegram! Verifique seu app.', 'success');
  } catch (err) {
    showToast(`Falha no Telegram: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🔔 Enviar Mensagem de Teste`;
  }
}

// ==================== MODAL UTILS ====================

function openModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) {
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('open'), 10);
  }
}

function closeModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) {
    m.classList.remove('open');
    setTimeout(() => m.style.display = 'none', 200);
  }
}

function showToast(message, type = 'success') {
  let toast = document.getElementById('appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }

  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : '⚠️'}</span> <div>${message}</div>`;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 4000);
}

// ==================== STORE COMPARISON & BLACKLIST CONTROLLERS ====================

function openProductStoresModal(productId) {
  const prod = state.products.find(p => p.id === productId);
  if (!prod) return;

  const rec = prod.latest_record || {};
  const offers = rec.offers || [];

  document.getElementById('productStoresModalTitle').textContent = `🏪 ${prod.name} (${prod.brand})`;
  document.getElementById('productStoresModalSubtitle').textContent = `Foram encontradas ${offers.length} ofertas em lojas monitoradas`;

  const container = document.getElementById('productStoresList');
  if (!container) return;

  if (offers.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem; color: #64748b;">
        Nenhuma oferta detalhada disponível no momento. Clique em "Verificar" no card para atualizar.
      </div>
    `;
    openModal('modalProductStores');
    return;
  }

  container.innerHTML = offers.map(o => {
    const isBest = o.is_best;
    const isOfficial = o.is_official;
    const bestBadge = isBest ? `<span style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 0.72rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; border: 1px solid rgba(16, 185, 129, 0.4);">🟢 Menor Preço</span>` : '';
    const officialBadge = isOfficial ? `<span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; font-size: 0.72rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; border: 1px solid rgba(99, 102, 241, 0.4);">⭐ Loja Oficial da Marca</span>` : '';
    const storeLink = o.url || rec.best_url || '#';

    return `
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid ${isBest ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.08)'}; border-radius: 8px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px;">
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <strong style="font-size: 0.95rem; color: #f8fafc;">🏪 ${o.store_name}</strong>
            ${bestBadge}
            ${officialBadge}
          </div>
          <div style="font-size: 0.78rem; color: #94a3b8;">
            ${o.product_title || prod.name}
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="text-align: right;">
            <div style="font-size: 1.15rem; font-weight: 8px; color: ${isBest ? '#34d399' : '#38bdf8'}; font-family: monospace; font-weight: bold;">
              R$ ${o.price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}
            </div>
          </div>

          <a href="${storeLink}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="font-size: 0.75rem; padding: 0.4rem 0.75rem;">
            Abrir Loja ↗
          </a>

          <button class="btn btn-outline-danger btn-sm" style="font-size: 0.75rem; padding: 0.4rem 0.65rem;" title="Ignorar esta loja (remover dos cálculos de menor preço)" onclick="handleIgnoreStore('${o.store_name.replace(/'/g, "\\'")}', ${prod.id})">
            🚫 Ignorar
          </button>
        </div>
      </div>
    `;
  }).join('');

  openModal('modalProductStores');
}

async function handleIgnoreStore(storeName, productId) {
  const confirmed = confirm(`Deseja realmente ignorar a loja "${storeName}"?\n\nEla será bloqueada do seu perfil e o menor preço será recalculado sem ela.`);
  if (!confirmed) return;

  try {
    const res = await fetch(`${API_BASE}/api/user/ignore-store`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: state.currentUser.id,
        store_name: storeName,
        product_id: productId
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao ignorar loja');

    showToast(`A loja "${storeName}" foi bloqueada com sucesso!`, 'success');
    closeModal('modalProductStores');
    await loadDashboardData();
  } catch (err) {
    showToast(`Erro ao ignorar loja: ${err.message}`, 'error');
  }
}

async function openStoresManagementModal() {
  openModal('modalStoresManagement');
  await renderIgnoredStoresList();
}

async function renderIgnoredStoresList() {
  const container = document.getElementById('ignoredStoresContainer');
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; color: #64748b; font-size: 0.8rem; padding: 10px;">Carregando lojas bloqueadas...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/user/ignored-stores?user_id=${state.currentUser.id}`);
    const data = await res.json();
    const stores = data.ignored_stores || [];

    if (stores.length === 0) {
      container.innerHTML = `
        <div style="color: #64748b; font-size: 0.85rem; text-align: center; padding: 12px;">
          Nenhuma loja bloqueada no momento. Todas as lojas estão ativas nas buscas.
        </div>
      `;
      return;
    }

    container.innerHTML = stores.map(storeName => `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 6px; margin-bottom: 6px; border: 1px solid rgba(255,255,255,0.05);">
        <span style="font-size: 0.85rem; color: #f8fafc;">🚫 <strong>${storeName}</strong></span>
        <button class="btn btn-secondary btn-sm" style="font-size: 0.72rem; padding: 2px 8px;" onclick="handleUnignoreStore('${storeName.replace(/'/g, "\\'")}')">
          Restaurar Loja
        </button>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; font-size: 0.8rem; padding: 8px;">Erro ao carregar lojas bloqueadas.</div>`;
  }
}

async function handleUnignoreStore(storeName) {
  try {
    const res = await fetch(`${API_BASE}/api/user/unignore-store`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: state.currentUser.id,
        store_name: storeName
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao restaurar loja');

    showToast(`A loja "${storeName}" foi restaurada!`, 'success');
    await renderIgnoredStoresList();
    await loadDashboardData();
  } catch (err) {
    showToast(`Erro ao restaurar loja: ${err.message}`, 'error');
  }
}

async function handleAddIgnoredStoreManual() {
  const input = document.getElementById('inputBlockStoreName');
  const storeName = input ? input.value.trim() : '';

  if (!storeName) {
    showToast('Digite o nome da loja que deseja bloquear.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/user/ignore-store`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: state.currentUser.id,
        store_name: storeName
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao bloquear loja');

    showToast(`Loja "${storeName}" bloqueada com sucesso!`, 'success');
    if (input) input.value = '';
    await renderIgnoredStoresList();
    await loadDashboardData();
  } catch (err) {
    showToast(`Erro: ${err.message}`, 'error');
  }
}

/* auth.js - Login / Register / Logout */

function showAuthModal() {
  document.getElementById('auth-modal').classList.remove('hidden');
}

function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach((t,i) => {
    t.classList.toggle('active', (i===0 && tab==='login') || (i===1 && tab==='register'));
  });
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  try {
    const data = await Api.login(
      document.getElementById('login-email').value,
      document.getElementById('login-password').value
    );
    onLoginSuccess(data);
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const errEl = document.getElementById('reg-error');
  errEl.classList.add('hidden');
  try {
    const data = await Api.register(
      document.getElementById('reg-email').value,
      document.getElementById('reg-username').value,
      document.getElementById('reg-password').value
    );
    onLoginSuccess(data);
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
}

function onLoginSuccess(data) {
  localStorage.setItem('token', data.access_token);
  localStorage.setItem('user', JSON.stringify(data.user));
  State.currentUser = data.user;
  updateAuthUI(data.user);
  document.getElementById('auth-modal').classList.add('hidden');
  toast(`Welcome, ${data.user.username}!`, 'ok');
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  State.currentUser = null;
  updateAuthUI(null);
  toast('Logged out');
}

function updateAuthUI(user) {
  document.getElementById('btn-login').classList.toggle('hidden', !!user);
  document.getElementById('user-info').classList.toggle('hidden', !user);
  if (user) document.getElementById('user-name').textContent = user.username;
}

function restoreSession() {
  const token = localStorage.getItem('token');
  const user  = localStorage.getItem('user');
  if (token && user) {
    try {
      State.currentUser = JSON.parse(user);
      updateAuthUI(State.currentUser);
    } catch {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  }
}

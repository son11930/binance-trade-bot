// auth.js — Session Authentication and Token Management

function logout() {
    localStorage.removeItem('bot_token');
    sessionStorage.removeItem('bot_token');
    authToken = null;
    shouldReconnect = false;
    if (ws) ws.close();
    window.location.reload();
}

function setLoginError(message) {
    const errorEl = document.getElementById('login-error');
    if (!errorEl) return;
    errorEl.classList.remove('hidden');
    errorEl.innerText = message;
}

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const usernameEl = document.getElementById('username');
            const passwordEl = document.getElementById('password');
            const rememberEl = document.getElementById('remember');
            if (!usernameEl || !passwordEl || !rememberEl) return;

            const u = usernameEl.value;
            const p = passwordEl.value;
            const r = rememberEl.checked;
            
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p, remember_me: r})
                });
                
                if (res.ok) {
                    const data = await res.json();
                    authToken = data.token;
                    if (r) localStorage.setItem('bot_token', authToken);
                    else sessionStorage.setItem('bot_token', authToken);
                    
                    const loginError = document.getElementById('login-error');
                    if (loginError) loginError.classList.add('hidden');
                    shouldReconnect = true;
                    if (typeof startApp === 'function') {
                        startApp();
                    }
                } else {
                    setLoginError("Invalid credentials. Access Denied.");
                }
            } catch (err) {
                setLoginError("Network Error. Is the backend running?");
            }
        });
    }
});

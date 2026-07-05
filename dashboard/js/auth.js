// auth.js — Session Authentication and Token Management

function logout() {
    localStorage.removeItem('bot_token');
    sessionStorage.removeItem('bot_token');
    if (ws) ws.close();
    window.location.reload();
}

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const u = document.getElementById('username').value;
            const p = document.getElementById('password').value;
            const r = document.getElementById('remember').checked;
            
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
                    
                    document.getElementById('login-error').classList.add('hidden');
                    if (typeof startApp === 'function') {
                        startApp();
                    }
                } else {
                    document.getElementById('login-error').classList.remove('hidden');
                    document.getElementById('login-error').innerText = "Invalid credentials. Access Denied.";
                }
            } catch (err) {
                document.getElementById('login-error').classList.remove('hidden');
                document.getElementById('login-error').innerText = "Network Error. Is the backend running?";
            }
        });
    }
});

// app.js — Lightweight Application Coordinator and Entry Point
// Preserves 100% backward compatibility while delegating rendering to modular js/ files.

document.addEventListener('DOMContentLoaded', () => {
    if (typeof authToken !== 'undefined' && authToken) {
        if (typeof startApp === 'function') {
            startApp();
        }
    }
});

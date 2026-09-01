/**
 * Venezuela Noticias & COBALTO — PWA Installer & Offline Monitor for Android
 */
(function() {
    let deferredPrompt = null;

    // 1. REGISTRO DEL SERVICE WORKER
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
            navigator.serviceWorker.register('/service-worker.js')
                .then(function(reg) {
                    console.log('[PWA] Service Worker registrado exitosamente:', reg.scope);
                })
                .catch(function(err) {
                    console.warn('[PWA] Error al registrar Service Worker:', err);
                });
        });
    }

    // 2. CAPTURA DEL EVENTO DE INSTALACIÓN EN ANDROID
    window.addEventListener('beforeinstallprompt', function(e) {
        e.preventDefault();
        deferredPrompt = e;
        showInstallBanner();
    });

    function showInstallBanner() {
        if (document.getElementById('pwa-install-banner')) return;

        const banner = document.createElement('div');
        banner.id = 'pwa-install-banner';
        banner.innerHTML = `
            <div style="position:fixed; bottom:20px; left:50%; transform:translateX(-50%); width:90%; max-width:440px; background:#0f172a; border:1px solid #00E5FF; border-radius:14px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 10px 30px rgba(0,229,255,0.3); z-index:99999; animation:slideUpPwa 0.3s ease-out;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <img src="/static/img/vn_logo.png" style="width:38px; height:38px; border-radius:8px; object-fit:cover;" alt="Logo">
                    <div>
                        <div style="color:#fff; font-weight:800; font-size:0.88rem; font-family:'Outfit', sans-serif;">Instalar Venezuela Noticias</div>
                        <div style="color:#94a3b8; font-size:0.75rem;">Modo App Android • Lectura ultra-rápida sin internet</div>
                    </div>
                </div>
                <div style="display:flex; gap:6px;">
                    <button id="pwa-install-btn" style="background:#00E5FF; color:#000; border:none; padding:8px 14px; border-radius:8px; font-weight:800; font-size:0.8rem; cursor:pointer;">INSTALAR</button>
                    <button id="pwa-close-btn" style="background:transparent; color:#94a3b8; border:none; padding:8px; font-size:1.1rem; cursor:pointer;">✕</button>
                </div>
            </div>
            <style>
                @keyframes slideUpPwa {
                    from { transform: translate(-50%, 100px); opacity:0; }
                    to { transform: translate(-50%, 0); opacity:1; }
                }
            </style>
        `;
        document.body.appendChild(banner);

        document.getElementById('pwa-install-btn').addEventListener('click', function() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(function(choiceResult) {
                    if (choiceResult.outcome === 'accepted') {
                        console.log('[PWA] Usuario aceptó instalar la App');
                    }
                    deferredPrompt = null;
                    banner.remove();
                });
            }
        });

        document.getElementById('pwa-close-btn').addEventListener('click', function() {
            banner.remove();
        });
    }

    // 3. INDICADOR DE ESTADO DE RED (ONLINE / OFFLINE TOAST)
    function updateNetworkStatus() {
        if (!navigator.onLine) {
            let toast = document.getElementById('offline-toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'offline-toast';
                toast.style.cssText = 'position:fixed; top:12px; left:50%; transform:translateX(-50%); background:#e11d48; color:#fff; padding:6px 16px; border-radius:20px; font-size:0.78rem; font-weight:700; z-index:99999; box-shadow:0 4px 12px rgba(0,0,0,0.5); font-family:sans-serif;';
                toast.innerHTML = '⚡ MODO FUERA DE LÍNEA — Leyendo desde la memoria del dispositivo';
                document.body.appendChild(toast);
            }
        } else {
            const toast = document.getElementById('offline-toast');
            if (toast) toast.remove();
        }
    }

    window.addEventListener('online', updateNetworkStatus);
    window.addEventListener('offline', updateNetworkStatus);
    window.addEventListener('DOMContentLoaded', updateNetworkStatus);
})();

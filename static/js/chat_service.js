window.CobaltoChat = {
    CHAT_KEY: 'cobalto_chat_v2',
    MAX_RETRIES: 3,

    _fetchWithRetry: async function(url, options, retries) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const res = await fetch(url, options);
                if (res.ok) return res;
                const body = await res.text();
                let data;
                try { data = JSON.parse(body); } catch(e) { data = {response: null}; }
                if (data && data.response) return {ok: true, json: () => data};
                if (attempt < retries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt), 8000);
                    await new Promise(r => setTimeout(r, delay));
                    continue;
                }
                return res;
            } catch (err) {
                if (attempt < retries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt), 8000);
                    await new Promise(r => setTimeout(r, delay));
                    continue;
                }
                throw err;
            }
        }
    },

    getActiveTabContext: function() {
        const activeTab = document.querySelector('.tab-content.active');
        if (!activeTab) return '';
        const tabId = activeTab.id || '';
        const titleEl = document.getElementById('main-title');
        const title = titleEl ? titleEl.innerText : tabId;
        return `[Pestaña Activa: ${title}]`;
    },

    sendQuickPrompt: function(text) {
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            this.sendMessage();
        }
    },

    syncModelBadge: async function() {
        const badge = document.getElementById('ai-model-badge');
        if (!badge) return;
        try {
            const resp = await fetch('/api/config');
            if (resp.ok) {
                const data = await resp.json();
                const model = data.OLLAMA_MODEL || data.AI_MODEL || 'llama3.2:latest';
                badge.innerText = `OLLAMA: ${model.split(':')[0]}`;
                badge.title = `Modelo Ollama Activo: ${model}`;
            }
        } catch(e) {
            badge.innerText = 'OLLAMA LOCAL';
        }
    },

    sendMessage: async function() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message) return;

        const sendBtn = document.getElementById('chat-send-btn');
        input.disabled = true;
        if (sendBtn) sendBtn.disabled = true;

        const chatBox = document.getElementById('chat-box');
        const userMsg = { role: 'user', text: message, timestamp: Date.now() };
        this.appendMessageToUI(userMsg);
        input.value = '';

        const typingId = 'typing-' + Date.now();
        chatBox.innerHTML += `<div id="${typingId}" class="msg msg-cobalto" style="opacity:0.7"><i>Procesando inteligencia...</i></div>`;
        chatBox.scrollTop = chatBox.scrollHeight;

        const personaSelect = document.getElementById('chat-persona-select');
        const persona = personaSelect ? personaSelect.value : 'GENERAL';
        const contextStr = this.getActiveTabContext();
        const fullMessage = contextStr ? `${contextStr} ${message}` : message;

        if (window.showAIThinkingToast) {
            window.showAIThinkingToast('ASISTENTE IA PENSANDO...', `Procesando consulta en modo ${persona}`);
        }

        const controller = new AbortController();
        const timeout = setTimeout(function() { controller.abort(); }, 45000);

        try {
            const res = await this._fetchWithRetry('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: fullMessage, persona: persona }),
                signal: controller.signal
            }, this.MAX_RETRIES);

            clearTimeout(timeout);
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();

            let data;
            try { data = await res.json(); } catch(e) { data = {response: null}; }

            const responseText = data && data.response
                ? data.response
                : '<span style="color:#FFAA00;">⚠️ El sistema está experimentando alta demanda. Intenta de nuevo en unos segundos.</span>';

            const aiMsg = { role: 'cobalto', text: responseText, timestamp: Date.now() };
            this.appendMessageToUI(aiMsg);

            await this.saveToHistory(userMsg);
            await this.saveToHistory(aiMsg);

            if (window.hideAIThinkingToast) {
                window.hideAIThinkingToast(true, 'Consulta procesada correctamente');
            }

        } catch (err) {
            clearTimeout(timeout);
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();
            chatBox.innerHTML += `<div class="msg msg-cobalto" style="color:#FFAA00;border:1px solid #FFAA00;padding:10px;border-radius:6px;">
                <b>⚠️ REDES DE IA NO DISPONIBLES</b><br>
                El sistema está funcionando en modo local. Los datos de inteligencia siguen recolectándose normalmente.
                <br><small style="opacity:0.7">Intenta de nuevo en unos segundos. Si el problema persiste, verifica conectividad.</small>
            </div>`;
            if (window.hideAIThinkingToast) {
                window.hideAIThinkingToast(false, 'Error al conectar con la IA local');
            }
        }

        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
        chatBox.scrollTop = chatBox.scrollHeight;
    },

    appendMessageToUI: function(msg) {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;
        const escapeFn = (window.CobaltoCore && window.CobaltoCore.utils && window.CobaltoCore.utils.escapeHTML) || 
            (s => String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m])));
        const className = msg.role === 'user' ? 'msg-user' : 'msg-cobalto';
        const content = msg.role === 'user' ? escapeFn(msg.text) : msg.text;
        chatBox.innerHTML += `<div class="msg ${className}">${content}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    },

    saveToHistory: async function(msg) {
        if (!window.CobaltoCore || !window.CobaltoCore.db) return;
        const history = await window.CobaltoCore.db.get(this.CHAT_KEY) || [];
        history.push(msg);
        if (history.length > 150) history.shift();
        await window.CobaltoCore.db.set(this.CHAT_KEY, history);
    },

    restoreChatHistory: async function() {
        if (!window.CobaltoCore || !window.CobaltoCore.db) return;
        const history = await window.CobaltoCore.db.get(this.CHAT_KEY);
        const chatBox = document.getElementById('chat-box');
        if (chatBox && history && Array.isArray(history)) {
            const welcomeMsg = chatBox.firstElementChild;
            chatBox.innerHTML = '';
            if (welcomeMsg) chatBox.appendChild(welcomeMsg.cloneNode(true));
            history.forEach(msg => this.appendMessageToUI(msg));
        }
        this.syncModelBadge();
    },

    handleEnter: function(e) {
        if (e.key === 'Enter') this.sendMessage();
    },

    clearChat: async function() {
        if (confirm("¿Confirmas la purga del historial de chat táctico?")) {
            const chatBox = document.getElementById('chat-box');
            if (chatBox) chatBox.innerHTML = ''; 
            if (window.CobaltoCore && window.CobaltoCore.db) {
                await window.CobaltoCore.db.set(this.CHAT_KEY, []);
            }
        }
    },

    toggleAI: function() {
        const panel = document.getElementById('ai-panel');
        const expandBtn = document.getElementById('ai-expand-btn');
        if (panel) {
            if (window.innerWidth > 1200) {
                panel.classList.toggle('collapsed');
                const isCollapsed = panel.classList.contains('collapsed');
                localStorage.setItem('ai-panel-collapsed', isCollapsed ? 'true' : 'false');
                
                if (expandBtn) {
                    expandBtn.style.display = isCollapsed ? 'flex' : 'none';
                }
                
                setTimeout(() => {
                    window.dispatchEvent(new Event('resize'));
                    if (window.CobaltoMap && window.CobaltoMap._map) {
                        window.CobaltoMap._map.invalidateSize();
                    }
                }, 350);
            } else {
                panel.classList.toggle('open');
                document.body.style.overflow = panel.classList.contains('open') ? 'hidden' : '';
                if (expandBtn) expandBtn.style.display = 'none';
            }
        }
    }
};

(function() {
    let touchStartX = 0;
    let touchCurrentX = 0;
    const SWIPE_THRESHOLD = 80;

    document.addEventListener('touchstart', function(e) {
        const panel = document.getElementById('ai-panel');
        if (!panel || !panel.classList.contains('open')) return;
        if (panel.contains(e.target)) {
            touchStartX = e.touches[0].clientX;
            touchCurrentX = touchStartX;
            panel.style.transition = 'none';
        }
    }, { passive: true });

    document.addEventListener('touchmove', function(e) {
        const panel = document.getElementById('ai-panel');
        if (!touchStartX || !panel || !panel.classList.contains('open')) return;
        touchCurrentX = e.touches[0].clientX;
        const diff = touchCurrentX - touchStartX;
        if (diff > 0) {
            panel.style.transform = `translateX(${Math.min(diff, 200)}px)`;
            panel.style.opacity = 1 - (diff / 300);
        }
    }, { passive: true });

    document.addEventListener('touchend', function() {
        const panel = document.getElementById('ai-panel');
        if (!touchStartX || !panel || !panel.classList.contains('open')) return;
        panel.style.transition = '';
        panel.style.transform = '';
        panel.style.opacity = '';
        const diff = touchCurrentX - touchStartX;
        if (diff > SWIPE_THRESHOLD) {
            window.CobaltoChat.toggleAI();
        }
        touchStartX = 0;
        touchCurrentX = 0;
    }, { passive: true });
})();

document.addEventListener('DOMContentLoaded', () => window.CobaltoChat.restoreChatHistory());

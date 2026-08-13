/**
 * COBALTO HUB - Controles Tácticos en Caliente
 * Sliders paramétricos con actualización vía Redis PubSub.
 * Desplegable lateral desde el botón 🎛️
 */

window.CobaltoTactical = (function() {
    var panelVisible = false;
    var panelEl = null;
    var btnEl = null;
    var sliders = [];
    var configCache = {};

    var SLIDER_DEFS = [
        { key: 'SEISMIC_MAX_DISTANCE_KM', label: 'Radio Sísmico', unit: 'km', min: 50, max: 2000, step: 50, def: 400, group: '🌍 Sísmico', color: '#FF9500' },
        { key: 'SEISMIC_MIN_MAGNITUDE', label: 'Mag. Mínima', unit: 'Mw', min: 0.5, max: 9.5, step: 0.5, def: 4.0, group: '🌍 Sísmico', color: '#FF9500' },
        { key: 'ASN_DROP_THRESHOLD', label: 'Caída Red', unit: '%', min: 5, max: 100, step: 5, def: 30, group: '🔌 Apagones', color: '#FF2D55' },
        { key: 'GDACS_MAX_DISTANCE_KM', label: 'Radio Desastres', unit: 'km', min: 50, max: 5000, step: 50, def: 500, group: '🌪️ GDACS', color: '#00ffaa' },
        { key: 'CACHE_MAX_AGE_MINUTES', label: 'Cache OSINT', unit: 'min', min: 1, max: 120, step: 5, def: 15, group: '⚙️ Sistema', color: '#B388FF' }
    ];

    function escHtml(str) {
        if (str == null) return '';
        return String(str).replace(/[&<>"']/g, function(m) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m];
        });
    }

    function debounce(fn, wait) {
        var timer;
        return function() {
            var ctx = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() { fn.apply(ctx, args); }, wait);
        };
    }

    var updateConfig = debounce(function(key, value) {
        var payload = {};
        payload[key] = value;
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(function(data) {
            if (window.showTacticalToast) {
                window.showTacticalToast('⚡ ' + key + ' = ' + value, 'success');
            }
        })
        .catch(function(err) {
            console.error('[TACTICAL] Error:', err);
            if (window.showTacticalToast) {
                window.showTacticalToast('✗ Error: ' + key, 'warning');
            }
        });
    }, 400);

    function loadInitialValues() {
        fetch('/api/config')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                configCache = data;
                sliders.forEach(function(s) {
                    var val = data[s.key] !== undefined ? data[s.key] : s.def;
                    s.input.value = val;
                    s.display.textContent = val;
                });
            })
            .catch(function(err) {
                console.warn('[TACTICAL] No se pudo cargar config, usando defaults:', err);
            });
    }

    function createSlider(sliderDef) {
        var container = document.createElement('div');
        container.style.cssText = 'margin-bottom:12px;padding:8px 12px;border-radius:6px;background:rgba(255,255,255,0.02);border-left:3px solid ' + sliderDef.color + ';';

        var header = document.createElement('div');
        header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';

        var label = document.createElement('label');
        label.style.cssText = 'color:#ccc;font-size:0.7rem;font-family:\'Roboto Mono\',monospace;cursor:pointer;';
        label.textContent = sliderDef.label;

        var valueSpan = document.createElement('span');
        valueSpan.style.cssText = 'color:' + sliderDef.color + ';font-size:0.75rem;font-family:\'Roboto Mono\',monospace;font-weight:bold;';
        valueSpan.textContent = sliderDef.def + ' ' + sliderDef.unit;

        header.appendChild(label);
        header.appendChild(valueSpan);

        var input = document.createElement('input');
        input.type = 'range';
        input.min = sliderDef.min;
        input.max = sliderDef.max;
        input.step = sliderDef.step;
        input.value = sliderDef.def;
        input.style.cssText = 'width:100%;height:4px;-webkit-appearance:none;appearance:none;background:rgba(255,255,255,0.1);border-radius:2px;outline:none;cursor:pointer;';
        input.style.background = 'linear-gradient(to right, ' + sliderDef.color + ' 0%, ' + sliderDef.color + ' ' + ((sliderDef.def - sliderDef.min) / (sliderDef.max - sliderDef.min) * 100) + '%, rgba(255,255,255,0.1) ' + ((sliderDef.def - sliderDef.min) / (sliderDef.max - sliderDef.min) * 100) + '%)';

        var sliderObj = { key: sliderDef.key, input: input, display: valueSpan, def: sliderDef.def };
        sliders.push(sliderObj);

        input.addEventListener('input', function() {
            var val = parseFloat(this.value);
            var pct = (val - sliderDef.min) / (sliderDef.max - sliderDef.min) * 100;
            this.style.background = 'linear-gradient(to right, ' + sliderDef.color + ' 0%, ' + sliderDef.color + ' ' + pct + '%, rgba(255,255,255,0.1) ' + pct + '%)';
            valueSpan.textContent = val + ' ' + sliderDef.unit;
            updateConfig(sliderDef.key, val);
        });

        container.appendChild(header);
        container.appendChild(input);
        return container;
    }

    function createPanel() {
        panelEl = document.createElement('div');
        panelEl.id = 'tactical-panel';
        panelEl.style.cssText = 'position:fixed;top:80px;left:50%;z-index:99999;width:340px;max-height:calc(100vh - 100px);overflow-y:auto;background:rgba(10,11,16,0.97);border:1px solid rgba(0,229,255,0.2);border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.8),0 0 40px rgba(0,229,255,0.05);backdrop-filter:blur(16px);padding:16px;transform:translateX(-50%) translateY(-120%);transition:transform 0.35s cubic-bezier(0.175,0.885,0.32,1.275);';

        var header = document.createElement('div');
        header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid rgba(0,229,255,0.1);';

        var title = document.createElement('div');
        title.style.cssText = 'color:#00E5FF;font-weight:bold;font-family:\'Roboto Mono\',monospace;font-size:0.8rem;letter-spacing:1px;display:flex;align-items:center;gap:8px;';
        title.innerHTML = '🎛️ CONTROL TÁCTICO';

        var closeBtn = document.createElement('span');
        closeBtn.style.cssText = 'color:#888;font-size:0.7rem;font-family:monospace;cursor:pointer;padding:4px 8px;border-radius:4px;transition:background 0.2s;';
        closeBtn.textContent = '✕ CERRAR';
        closeBtn.onmouseover = function() { this.style.background = 'rgba(255,255,255,0.05)'; };
        closeBtn.onmouseout = function() { this.style.background = 'transparent'; };
        closeBtn.onclick = function() { togglePanel(false); };

        header.appendChild(title);
        header.appendChild(closeBtn);
        panelEl.appendChild(header);

        var groups = {};
        SLIDER_DEFS.forEach(function(sd) {
            if (!groups[sd.group]) groups[sd.group] = [];
            groups[sd.group].push(sd);
        });

        for (var g in groups) {
            var groupHeader = document.createElement('div');
            groupHeader.style.cssText = 'color:#888;font-size:0.6rem;font-family:\'Roboto Mono\',monospace;letter-spacing:1px;text-transform:uppercase;margin:12px 0 6px 4px;';
            groupHeader.textContent = g;
            panelEl.appendChild(groupHeader);

            groups[g].forEach(function(sd) {
                panelEl.appendChild(createSlider(sd));
            });
        }

        var footer = document.createElement('div');
        footer.style.cssText = 'margin-top:16px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.05);font-size:0.6rem;color:#555;font-family:\'Roboto Mono\',monospace;text-align:center;';
        footer.textContent = 'Los cambios se aplican en caliente vía Redis PubSub';
        panelEl.appendChild(footer);

        document.body.appendChild(panelEl);
    }

    function createToggleButton() {
        btnEl = document.createElement('button');
        btnEl.id = 'tactical-toggle-btn';
        btnEl.title = 'Controles Tácticos en Caliente';
        btnEl.style.cssText = 'position:fixed;top:18px;right:420px;z-index:100000;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.3);border-radius:8px;color:#00E5FF;padding:6px 12px;cursor:pointer;font-size:0.85rem;transition:all 0.3s;box-shadow:0 0 10px rgba(0,229,255,0.1);backdrop-filter:blur(10px);display:flex;align-items:center;gap:6px;font-family:\'Roboto Mono\',monospace;font-weight:bold;';
        btnEl.innerHTML = '🎛️ CTRL TÁCTICO';
        btnEl.onmouseover = function() { this.style.borderColor = '#00E5FF'; this.style.boxShadow = '0 0 20px rgba(0,229,255,0.25)'; };
        btnEl.onmouseout = function() { this.style.borderColor = 'rgba(0,229,255,0.3)'; this.style.boxShadow = '0 0 15px rgba(0,229,255,0.1)'; };
        btnEl.onclick = function() { togglePanel(); };
        document.body.appendChild(btnEl);
    }

    function togglePanel(forceState) {
        var willShow = forceState !== undefined ? forceState : !panelVisible;
        panelVisible = willShow;
        panelEl.style.transform = willShow ? 'translateX(-50%) translateY(0)' : 'translateX(-50%) translateY(-120%)';
        if (willShow) {
            loadInitialValues();
        }
    }

    function init() {
        if (document.getElementById('tactical-panel')) return;
        createPanel();
        createToggleButton();
        console.log('[TACTICAL] Controles tácticos en caliente listos.');
    }

    return {
        init: init,
        toggle: togglePanel,
        refresh: loadInitialValues
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    if (window.CobaltoTactical) {
        window.CobaltoTactical.init();
    }
});

/**
 * COBALTO HUB - Sistema de Voz Táctico (Voice STT / TTS Engine)
 * Control por voz, sintesis de alertas tempranas y dictado para asistente IA.
 */

window.CobaltoVoice = (function() {
    var isListening = false;
    var isSpeaking = false;
    var activeInputId = null;
    var recognition = null;
    var synth = window.speechSynthesis || null;
    var selectedVoice = null;
    var autoTTS = localStorage.getItem('cobalto_voice_autotts') !== 'false';
    var sttSupported = false;
    var ttsSupported = false;

    function getSpeechRecognitionClass() {
        return window.SpeechRecognition || window.webkitSpeechRecognition || window.mozSpeechRecognition || window.msSpeechRecognition || null;
    }

    function initVoices() {
        if (!synth) return;
        var voices = synth.getVoices();
        if (!voices || !voices.length) return;

        for (var i = 0; i < voices.length; i++) {
            var v = voices[i];
            var lang = (v.lang || '').toLowerCase();
            if (lang.startsWith('es') || lang.includes('spanish')) {
                selectedVoice = v;
                if (lang.includes('es-es') || lang.includes('es-mx') || lang.includes('es-co')) {
                    break;
                }
            }
        }
        if (!selectedVoice && voices.length > 0) {
            selectedVoice = voices[0];
        }
    }

    function sanitizeTextForSpeech(text) {
        if (!text) return '';
        var clean = String(text)
            .replace(/<[^>]*>/g, '')
            .replace(/https?:\/\/\S+/gi, '')
            .replace(/[\*\_~`#|>]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        return clean;
    }

    function showVoiceToast(msg, type) {
        if (typeof window.showTacticalToast === 'function') {
            window.showTacticalToast(msg, type || 'info');
        }
    }

    function playAudioBeep(freq, duration) {
        try {
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            var ctx = new AudioCtx();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq || 880;
            gain.gain.value = 0.05;
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            setTimeout(function() {
                osc.stop();
                ctx.close();
            }, duration || 120);
        } catch(e) {}
    }

    function processVoiceCommand(transcript) {
        var raw = transcript.trim();
        var lower = raw.toLowerCase();
        console.log('[VOICE] Procesando comando de voz:', raw);

        var cleanCmd = lower.replace(/^cobalto\b\s*,?\s*/i, '').trim();

        if (cleanCmd.startsWith('/') && window.CobaltoSlash) {
            var searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.value = cleanCmd;
                searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                var enterEvt = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
                searchInput.dispatchEvent(enterEvt);
                showVoiceToast('🎙️ Comando Slash ejecutado: ' + cleanCmd, 'success');
                return true;
            }
        }

        if (/^(ir a|cambiar a|ver|mostrar|tab)\s+(.+)/i.test(cleanCmd)) {
            var match = cleanCmd.match(/^(ir a|cambiar a|ver|mostrar|tab)\s+(.+)/i);
            var target = match ? match[2].trim() : '';
            var tabMap = {
                'mapa': 'map', 'map': 'map', 'noticias': 'news', 'news': 'news',
                'inteligencia': 'intel', 'intel': 'intel', 'social': 'social', 'redes': 'social',
                'alertas': 'alerts', 'alert': 'alerts', 'ciber': 'cyber', 'cyber': 'cyber',
                'cctv': 'osiris-global', 'camaras': 'osiris-global', 'recon': 'osiris-recon',
                'osiris': 'osiris-recon', 'configuracion': 'config', 'config': 'config',
                'analitica': 'analytics', 'analytics': 'analytics', 'sentimiento': 'sentiment',
                'actores': 'user-search', 'finint': 'finint', 'prediccion': 'predictive'
            };
            var tabId = tabMap[target];
            if (tabId) {
                var btn = document.querySelector('.nav-button[data-tab="' + tabId + '"]');
                if (btn) {
                    btn.click();
                    speak('Cambiando a pestaña ' + target);
                    showVoiceToast('🎙️ Navegación: ' + target.toUpperCase(), 'success');
                    return true;
                }
            }
        }

        if (/^(buscar|search)\s+(.+)/i.test(cleanCmd)) {
            var searchMatch = cleanCmd.match(/^(buscar|search)\s+(.+)/i);
            var query = searchMatch ? searchMatch[2].trim() : '';
            var searchInp = document.getElementById('search-input');
            if (searchInp && query) {
                searchInp.value = query;
                searchInp.dispatchEvent(new Event('input', { bubbles: true }));
                showVoiceToast('🎙️ Buscando: "' + query + '"', 'info');
                speak('Buscando ' + query);
                return true;
            }
        }

        if (/^(limpiar|borrar filtros|resetear)/i.test(cleanCmd)) {
            var clearBtn = document.getElementById('btn-clear-filters');
            if (clearBtn) clearBtn.click();
            showVoiceToast('🎙️ Filtros limpiados', 'info');
            speak('Filtros limpiados');
            return true;
        }

        if (/^(silenciar|apagar audio|mutear)/i.test(cleanCmd)) {
            stopSpeaking();
            autoTTS = false;
            localStorage.setItem('cobalto_voice_autotts', 'false');
            showVoiceToast('🎙️ Audio silenciado', 'warning');
            return true;
        }

        if (/^(activar audio|desmutear|voz activada)/i.test(cleanCmd)) {
            autoTTS = true;
            localStorage.setItem('cobalto_voice_autotts', 'true');
            speak('Sistema de voz reactivado');
            showVoiceToast('🎙️ Audio activado', 'success');
            return true;
        }

        if (activeInputId) {
            var targetEl = document.getElementById(activeInputId);
            if (targetEl) {
                targetEl.value = raw;
                targetEl.dispatchEvent(new Event('input', { bubbles: true }));
                if (activeInputId === 'chat-input' && window.CobaltoChat) {
                    window.CobaltoChat.sendMessage();
                    showVoiceToast('🎙️ Consulta de voz enviada a Enlace Cobalto', 'success');
                } else {
                    showVoiceToast('🎙️ Dictado ingresado: ' + raw, 'info');
                }
                return true;
            }
        }

        var chatInput = document.getElementById('chat-input');
        if (chatInput && window.CobaltoChat) {
            chatInput.value = raw;
            window.CobaltoChat.sendMessage();
            showVoiceToast('🎙️ Enviado a Enlace Cobalto: "' + raw + '"', 'info');
            return true;
        }

        return false;
    }

    function updateMicUI() {
        var micBtns = document.querySelectorAll('#btn-voice-toggle, #chat-mic-btn');
        micBtns.forEach(function(btn) {
            if (isListening) {
                btn.style.borderColor = '#FF3366';
                btn.style.color = '#FF3366';
                btn.style.boxShadow = '0 0 12px rgba(255, 51, 102, 0.5)';
                btn.setAttribute('title', 'Escuchando... Haz clic para detener');
            } else {
                btn.style.borderColor = '#00E5FF';
                btn.style.color = '#00E5FF';
                btn.style.boxShadow = 'none';
                btn.setAttribute('title', 'Comando de voz (Ctrl+Shift+V)');
            }
        });

        var statusText = document.getElementById('voice-status-text');
        if (statusText) {
            statusText.textContent = isListening ? 'ESCUCHANDO...' : 'VOZ';
        }
        var micIcon = document.getElementById('voice-mic-icon');
        if (micIcon) {
            micIcon.textContent = isListening ? '🔴' : '🎙️';
        }
    }

    function init() {
        var SpeechClass = getSpeechRecognitionClass();
        if (SpeechClass) {
            sttSupported = true;
            recognition = new SpeechClass();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'es-ES';

            recognition.onstart = function() {
                isListening = true;
                playAudioBeep(600, 100);
                updateMicUI();
                showVoiceToast('🎙️ [SISTEMA DE VOZ] Escuchando comando...', 'info');
            };

            recognition.onresult = function(e) {
                isListening = false;
                updateMicUI();
                if (e.results && e.results[0] && e.results[0][0]) {
                    var transcript = e.results[0][0].transcript;
                    playAudioBeep(880, 100);
                    processVoiceCommand(transcript);
                }
            };

            recognition.onerror = function(err) {
                isListening = false;
                updateMicUI();
                console.warn('[VOICE] Error en reconocimiento:', err.error);
                if (err.error !== 'no-speech' && err.error !== 'aborted') {
                    showVoiceToast('⚠️ Error de voz: ' + err.error, 'warning');
                }
            };

            recognition.onend = function() {
                isListening = false;
                updateMicUI();
            };
        } else {
            console.log('[VOICE] Web SpeechRecognition no disponible en este navegador/entorno.');
        }

        if (synth) {
            ttsSupported = true;
            initVoices();
            if (synth.onvoiceschanged !== undefined) {
                synth.onvoiceschanged = initVoices;
            }
        }

        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'V' || e.key === 'v')) {
                e.preventDefault();
                toggleListening();
            }
        });

        updateMicUI();
        console.log('[VOICE] Sistema de Voz Táctico inicializado. STT:', sttSupported, 'TTS:', ttsSupported);
    }

    function startListening(inputId) {
        if (!sttSupported || !recognition) {
            showVoiceToast('⚠️ Reconocimiento de voz no soportado en este navegador', 'warning');
            return;
        }
        if (isListening) {
            stopListening();
            return;
        }
        activeInputId = inputId || null;
        try {
            recognition.start();
        } catch(e) {
            console.warn('[VOICE] Error al iniciar escucha:', e);
        }
    }

    function stopListening() {
        if (recognition && isListening) {
            try {
                recognition.stop();
            } catch(e) {}
        }
        isListening = false;
        updateMicUI();
    }

    function toggleListening(inputId) {
        if (isListening) {
            stopListening();
        } else {
            startListening(inputId);
        }
    }

    function speak(text, options) {
        if (!ttsSupported || !synth || !autoTTS) return;
        var cleanText = sanitizeTextForSpeech(text);
        if (!cleanText) return;

        try {
            synth.cancel();
            var utterance = new SpeechSynthesisUtterance(cleanText);
            if (selectedVoice) utterance.voice = selectedVoice;
            utterance.rate = (options && options.rate) || 1.05;
            utterance.pitch = (options && options.pitch) || 1.0;
            utterance.volume = (options && options.volume) || 1.0;

            utterance.onstart = function() { isSpeaking = true; };
            utterance.onend = function() { isSpeaking = false; };
            utterance.onerror = function() { isSpeaking = false; };

            synth.speak(utterance);
        } catch(e) {
            console.warn('[VOICE] Error sintetizando texto:', e);
        }
    }

    function stopSpeaking() {
        if (synth) {
            try { synth.cancel(); } catch(e) {}
        }
        isSpeaking = false;
    }

    function announceCriticalAlert(alertTitle, alertDetails) {
        if (!autoTTS) return;
        var msg = 'Alerta crítica. ' + (alertTitle || '');
        if (alertDetails) {
            msg += '. ' + alertDetails;
        }
        speak(msg, { rate: 1.1, pitch: 1.05 });
    }

    return {
        init: init,
        startListening: startListening,
        stopListening: stopListening,
        toggleListening: toggleListening,
        toggleListeningForInput: function(id) { toggleListening(id); },
        speak: speak,
        stopSpeaking: stopSpeaking,
        announceCriticalAlert: announceCriticalAlert,
        isListening: function() { return isListening; },
        isSpeaking: function() { return isSpeaking; }
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    if (window.CobaltoVoice) {
        window.CobaltoVoice.init();
    }
});

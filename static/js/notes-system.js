window.CobaltoNotes = {
    _allNotes: {},
    _activeInputs: {},

    init: function() {
        this.loadAllNotes();
        this._attachGlobalListener();
    },

    loadAllNotes: function() {
        var self = this;
        fetch('/api/notes')
            .then(function(r) { return r.json(); })
            .then(function(notes) {
                self._allNotes = {};
                notes.forEach(function(n) {
                    if (n.note) {
                        self._allNotes[n.card_id] = n;
                    }
                });
                self._applyBadges();
            })
            .catch(function(e) {
                console.warn('[NOTES] Error cargando notas:', e);
            });
    },

    _applyBadges: function() {
        var self = this;
        Object.keys(this._allNotes).forEach(function(cardId) {
            var el = document.querySelector('[data-card-id="' + CSS.escape(cardId) + '"]');
            if (el && !el.querySelector('.note-badge')) {
                var badge = document.createElement('span');
                badge.className = 'note-badge';
                badge.textContent = '📝';
                badge.title = self._allNotes[cardId].note;
                el.querySelector('.news-header, .rt-source, .card-header')?.appendChild(badge);
            }
        });
    },

    _getCardId: function(card) {
        return card.getAttribute('data-card-id') ||
               card.getAttribute('data-link') ||
               card.getAttribute('data-title')?.slice(0, 80) ||
               'card_' + Math.random().toString(36).slice(2, 8);
    },

    _ensureCardId: function(card) {
        var id = this._getCardId(card);
        if (!card.hasAttribute('data-card-id')) {
            card.setAttribute('data-card-id', id);
        }
        return id;
    },

    _attachGlobalListener: function() {
        var self = this;
        document.addEventListener('dblclick', function(e) {
            var card = e.target.closest('.news-card, .rt-card, .panel-glass, .intel-card, .alert-card, .social-item');
            if (!card) return;
            if (e.target.closest('.note-input-wrapper')) return;
            self._toggleNote(card);
        });
    },

    _toggleNote: function(card) {
        var self = this;
        var existing = card.querySelector('.note-input-wrapper');
        if (existing) {
            existing.remove();
            return;
        }
        var cardId = this._ensureCardId(card);
        var noteData = this._allNotes[cardId] || { note: '' };
        var wrapper = document.createElement('div');
        wrapper.className = 'note-input-wrapper';
        wrapper.style.cssText = 'margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.06);';

        var label = document.createElement('div');
        label.style.cssText = 'font-size:0.7rem;color:var(--text-muted);font-family:Roboto Mono,monospace;margin-bottom:0.3rem;';
        label.textContent = '📝 NOTA OPERATIVA';

        var textarea = document.createElement('textarea');
        textarea.style.cssText = 'width:100%;background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.08);border-radius:4px;color:#ccd6f6;font-size:0.75rem;padding:0.4rem;font-family:Roboto Mono,monospace;resize:vertical;min-height:40px;outline:none;';
        textarea.placeholder = 'Escribe una observación táctica...';
        textarea.value = noteData.note || '';
        textarea.rows = 2;

        wrapper.appendChild(label);
        wrapper.appendChild(textarea);
        card.appendChild(wrapper);
        textarea.focus();

        var saveTimeout = null;
        textarea.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(function() {
                self._saveNote(cardId, 'news', textarea.value);
            }, 500);
        });
    },

    _saveNote: function(cardId, cardType, note) {
        var self = this;
        fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: cardId, card_type: cardType, note: note }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status === 'ok') {
                if (note) {
                    self._allNotes[cardId] = { card_id: cardId, card_type: cardType, note: note };
                } else {
                    delete self._allNotes[cardId];
                }
            }
        })
        .catch(function(e) {
            console.warn('[NOTES] Error guardando:', e);
        });
    },
};

document.addEventListener('DOMContentLoaded', function() {
    window.CobaltoNotes.init();
});


css_code = """
/* ============================================
   OSIRIS RECON TOOLKIT
   ============================================ */
.or-layout {
    display: flex;
    gap: 0;
    height: 100%;
    min-height: 0;
}
.or-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: rgba(8, 9, 14, 0.6);
    border-right: 1px solid rgba(255,255,255,0.04);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 12px 0;
}
.or-sidebar-group {
    padding: 0 10px;
    margin-bottom: 8px;
}
.or-sidebar-label {
    color: rgba(255,255,255,0.25);
    font-size: 0.55rem;
    font-family: 'Roboto Mono', monospace;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 6px 10px 4px;
    user-select: none;
}
.or-tool-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 10px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.7rem;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    letter-spacing: 0.3px;
    position: relative;
    overflow: hidden;
}
.or-tool-btn:hover {
    background: rgba(255,255,255,0.03);
    color: #fff;
    border-color: rgba(255,255,255,0.06);
}
.or-tool-btn.active {
    background: rgba(0,229,255,0.08);
    border-color: rgba(0,229,255,0.2);
    color: var(--primary);
    box-shadow: 0 0 16px rgba(0,229,255,0.06);
}
.or-tool-btn.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 15%;
    height: 70%;
    width: 2px;
    background: var(--primary);
    border-radius: 0 2px 2px 0;
    box-shadow: 0 0 6px var(--primary);
}
.or-tool-icon {
    font-size: 0.85rem;
    width: 22px;
    text-align: center;
    flex-shrink: 0;
}
.or-tool-color {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-left: auto;
    opacity: 0.6;
}

.or-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 16px 20px;
    overflow: hidden;
}

.or-search-bar {
    display: flex;
    gap: 8px;
    align-items: stretch;
    margin-bottom: 16px;
    flex-shrink: 0;
}
.or-input-wrap {
    flex: 1;
    position: relative;
    display: flex;
    align-items: center;
}
.or-search-input {
    width: 100%;
    padding: 11px 40px 11px 14px;
    background: rgba(0,0,0,0.35);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    color: #fff;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.8rem;
    outline: none;
    transition: all 0.25s ease;
}
.or-search-input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 16px rgba(0,229,255,0.1), inset 0 1px 3px rgba(0,0,0,0.3);
}
.or-search-input::placeholder {
    color: rgba(255,255,255,0.2);
    font-style: italic;
}
.or-input-hint {
    position: absolute;
    right: 12px;
    color: rgba(255,255,255,0.15);
    font-size: 0.6rem;
    font-family: 'Roboto Mono', monospace;
    pointer-events: none;
    letter-spacing: 0.5px;
}
.or-search-btn {
    padding: 0 22px;
    background: linear-gradient(135deg, rgba(0,229,255,0.15), rgba(0,229,255,0.05));
    border: 1px solid rgba(0,229,255,0.25);
    border-radius: 8px;
    color: var(--primary);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 1.5px;
    transition: all 0.25s ease;
    white-space: nowrap;
}
.or-search-btn:hover {
    background: linear-gradient(135deg, rgba(0,229,255,0.25), rgba(0,229,255,0.1));
    border-color: var(--primary);
    box-shadow: 0 0 20px rgba(0,229,255,0.15);
    transform: translateY(-1px);
}
.or-search-btn:active {
    transform: translateY(0);
}
.or-clear-btn {
    padding: 0 14px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    color: var(--text-muted);
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}
.or-clear-btn:hover {
    background: rgba(255,45,85,0.1);
    border-color: rgba(255,45,85,0.3);
    color: #FF2D55;
}

.or-results-area {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
}

.or-result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    margin-bottom: 14px;
    flex-shrink: 0;
}
.or-result-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 1px;
}
.or-result-actions {
    display: flex;
    gap: 6px;
}
.or-action-btn {
    padding: 4px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 4px;
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.6rem;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 0.5px;
}
.or-action-btn:hover {
    background: rgba(0,229,255,0.08);
    border-color: rgba(0,229,255,0.2);
    color: var(--primary);
}

.or-data-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
    margin-bottom: 16px;
}
.or-data-card {
    background: rgba(0,0,0,0.2);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
    padding: 12px 14px;
    transition: all 0.2s ease;
    position: relative;
}
.or-data-card:hover {
    border-color: rgba(255,255,255,0.08);
    background: rgba(0,0,0,0.3);
}
.or-data-card.accent-left {
    border-left: 2px solid var(--primary);
}
.or-data-label {
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.55rem;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.or-data-value {
    color: #fff;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.82rem;
    font-weight: 600;
    word-break: break-all;
}
.or-data-value.large {
    font-size: 1.4rem;
    font-weight: 700;
}
.or-data-value.success { color: #00FFAA; }
.or-data-value.danger { color: #FF3D3D; }
.or-data-value.warning { color: #FF9500; }
.or-data-value.info { color: var(--primary); }

.or-section {
    margin-bottom: 14px;
}
.or-section-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.or-section-title {
    font-family: 'Roboto Mono', monospace;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}
.or-section-count {
    background: rgba(255,255,255,0.05);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.55rem;
    font-family: 'Roboto Mono', monospace;
    color: var(--text-muted);
}

.or-record-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.02);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.72rem;
    transition: background 0.15s;
    border-radius: 3px;
}
.or-record-row:hover {
    background: rgba(255,255,255,0.02);
}
.or-record-data {
    color: #ccd6f6;
    word-break: break-all;
    flex: 1;
    margin-right: 8px;
}
.or-record-meta {
    color: var(--text-muted);
    font-size: 0.6rem;
    white-space: nowrap;
    flex-shrink: 0;
}

.or-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.65rem;
    margin: 2px;
    border: 1px solid;
}
.or-tag.port {
    background: rgba(255,61,61,0.08);
    border-color: rgba(255,61,61,0.2);
    color: #FF3D3D;
}
.or-tag.vuln {
    background: rgba(255,68,68,0.08);
    border-color: rgba(255,68,68,0.2);
    color: #FF4444;
}
.or-tag.data-type {
    background: rgba(255,0,0,0.06);
    border-color: rgba(255,0,0,0.15);
    color: #FF8888;
}
.or-tag.hostname {
    background: rgba(0,229,255,0.06);
    border-color: rgba(0,229,255,0.15);
    color: var(--primary);
}
.or-tag.subdomain {
    background: rgba(118,255,3,0.06);
    border-color: rgba(118,255,3,0.15);
    color: #76FF03;
}
.or-tag.threat {
    background: rgba(255,255,255,0.03);
    border-color: rgba(255,255,255,0.06);
    color: var(--text-muted);
}

.or-alert-box {
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.75rem;
    animation: or-alert-in 0.3s ease;
}
@keyframes or-alert-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
}
.or-alert-box.danger {
    background: rgba(255,0,0,0.08);
    border: 1px solid rgba(255,0,0,0.2);
    color: #FF4444;
}
.or-alert-box.success {
    background: rgba(0,255,170,0.06);
    border: 1px solid rgba(0,255,170,0.15);
    color: #00FFAA;
}
.or-alert-box.warning {
    background: rgba(255,150,0,0.06);
    border: 1px solid rgba(255,150,0,0.15);
    color: #FF9500;
}

.or-copy-btn {
    padding: 2px 6px;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 3px;
    color: var(--text-muted);
    font-size: 0.6rem;
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'Roboto Mono', monospace;
    opacity: 0;
}
.or-record-row:hover .or-copy-btn,
.or-data-card:hover .or-copy-btn {
    opacity: 1;
}
.or-copy-btn:hover {
    background: rgba(0,229,255,0.08);
    border-color: rgba(0,229,255,0.2);
    color: var(--primary);
}

.or-profile-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
    padding: 14px;
    background: rgba(0,0,0,0.15);
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.04);
}
.or-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.1);
    object-fit: cover;
}
.or-profile-name {
    color: #fff;
    font-size: 1rem;
    font-weight: 700;
}
.or-profile-handle {
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.72rem;
}

.or-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    gap: 14px;
}
.or-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(255,255,255,0.06);
    border-top: 3px solid var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
.or-loading-text {
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 2px;
}

.or-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 30px;
    text-align: center;
    gap: 12px;
}
.or-empty-icon {
    font-size: 2.2rem;
    opacity: 0.3;
}
.or-empty-title {
    color: var(--text-muted);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 1px;
}
.or-empty-hint {
    color: rgba(255,255,255,0.2);
    font-size: 0.7rem;
    max-width: 360px;
    line-height: 1.5;
}

.or-history-bar {
    display: flex;
    gap: 6px;
    padding: 8px 0;
    margin-bottom: 8px;
    overflow-x: auto;
    flex-shrink: 0;
}
.or-history-bar::-webkit-scrollbar { height: 2px; }
.or-hist-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 4px;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    flex-shrink: 0;
}
.or-hist-chip:hover {
    background: rgba(0,229,255,0.06);
    border-color: rgba(0,229,255,0.15);
    color: var(--primary);
}

.or-timer {
    font-family: 'Roboto Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 4px;
}

@media (max-width: 900px) {
    .or-layout {
        flex-direction: column;
    }
    .or-sidebar {
        width: 100%;
        flex-direction: row;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 8px;
        border-right: none;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        max-height: 110px;
    }
    .or-sidebar-group {
        display: flex;
        gap: 4px;
        padding: 0;
        margin-bottom: 0;
    }
    .or-sidebar-label {
        display: none;
    }
}
"""

with open("c:\\Users\\Ulianov\\Documents\\COBALTO\\COBALTO\\static\\css\\dashboard.css", "a", encoding="utf-8") as f:
    f.write("\n" + css_code)

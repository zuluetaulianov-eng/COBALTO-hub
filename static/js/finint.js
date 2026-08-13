/**
 * finint.js — Financial Intelligence & Dark Web frontend.
 * Exposes window.FinintIntel.
 */
(function () {
  "use strict";

  var state = {
    sanctionedCount: 0,
    linksCount: 0,
  };

  function init() {
    loadStats();
    // Show wallets panel by default with guidance
    switchTab("wallets");
  }

  function destroy() {
    // no polling to clean up
  }

  function loadStats() {
    // Load sanctioned wallets count
    fetch("/api/finint/sanctioned-wallets")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.sanctionedCount = (data.wallets || []).length;
        updateBadge();
      })
      .catch(function () {});
  }

  function updateBadge() {
    var el = document.getElementById("finint-badge");
    if (!el) return;
    el.textContent = state.sanctionedCount + " sancionadas · " + state.linksCount + " vinculadas";
  }

  function switchTab(tab) {
    document.querySelectorAll(".finint-panel").forEach(function (p) { p.style.display = "none"; });
    var panel = document.getElementById("finint-panel-" + tab);
    if (panel) panel.style.display = "block";
    document.querySelectorAll("[data-finint-tab]").forEach(function (btn) {
      btn.style.borderColor = btn.getAttribute("data-finint-tab") === tab ? "var(--primary)" : "var(--border-color)";
    });
  }

  function checkWallet() {
    var addr = document.getElementById("finint-wallet-input");
    var chain = document.getElementById("finint-chain-select");
    var container = document.getElementById("finint-wallet-result");
    if (!addr || !addr.value.trim()) return;

    container.innerHTML = '<div class="text-muted" style="padding:1rem;">🔄 Verificando...</div>';

    fetch("/api/finint/wallet/" + encodeURIComponent(addr.value.trim()) + "?chain=" + chain.value)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderWalletResult(data, container); })
      .catch(function () { container.innerHTML = '<div style="color:#FF2D55;">Error verificando wallet</div>'; });
  }

  function renderWalletResult(data, container) {
    var riskColor = data.risk_score >= 70 ? "#FF2D55" : data.risk_score >= 40 ? "#FF9500" : "#00FFAA";
    var sanctionsBadge = data.sanctioned
      ? '<span style="background:#FF2D5533;color:#FF2D55;border:1px solid #FF2D55;padding:2px 10px;border-radius:4px;font-weight:600;">🚫 SANCIONADA</span>'
      : '<span style="background:#00FFAA22;color:#00FFAA;border:1px solid #00FFAA44;padding:2px 10px;border-radius:4px;">✅ No sancionada</span>';

    var txsHtml = "";
    if (data.recent_tx && data.recent_tx.length > 0) {
      txsHtml = data.recent_tx
        .map(function (tx) {
          return '<div style="font-size:0.75rem;font-family:monospace;padding:2px 0;">' +
            tx.hash + " | " + (tx.value_eth !== undefined ? tx.value_eth.toFixed(4) + " ETH" : tx.total_btc !== undefined ? tx.total_btc.toFixed(6) + " BTC" : "") +
            "</div>";
        })
        .join("");
    }

    container.innerHTML =
      '<div class="panel-glass" style="padding:1rem;border-left:3px solid ' + riskColor + ';">' +
      '<div class="flex-between" style="margin-bottom:0.5rem;">' +
      '<div><span class="font-mono" style="font-size:0.8rem;">' + escapeHtml(data.address) + "</span>" +
      '<span class="text-muted" style="font-size:0.7rem;margin-left:0.5rem;">' + data.chain + "</span></div>" +
      sanctionsBadge +
      "</div>" +
      '<div style="display:flex;gap:1rem;margin:0.5rem 0;">' +
      '<div><span class="text-muted" style="font-size:0.7rem;">Riesgo</span><div style="font-size:1.2rem;font-weight:700;color:' + riskColor + ';">' + data.risk_score + "</div></div>" +
      '<div><span class="text-muted" style="font-size:0.7rem;">TXs</span><div style="font-size:1.2rem;font-weight:700;">' + (data.transaction_count || 0) + "</div></div>" +
      (data.balance_usd ? '<div><span class="text-muted" style="font-size:0.7rem;">Balance USD</span><div style="font-size:1.2rem;font-weight:700;">$' + data.balance_usd.toFixed(0) + "</div></div>" : "") +
      (data.balance_btc ? '<div><span class="text-muted" style="font-size:0.7rem;">Balance BTC</span><div style="font-size:1.2rem;font-weight:700;">' + data.balance_btc.toFixed(6) + "</div></div>" : "") +
      "</div>" +
      (txsHtml ? '<div style="margin-top:0.5rem;"><div class="text-muted" style="font-size:0.7rem;">TX Recientes</div>' + txsHtml + "</div>" : "") +
      '<div class="text-muted" style="font-size:0.65rem;margin-top:0.5rem;">Verificado: ' + (data.checked_at || "").slice(11, 19) + "</div>" +
      "</div>";
  }

  function loadSanctioned() {
    var container = document.getElementById("finint-sanctioned-list");
    if (!container) return;
    container.innerHTML = '<div class="text-muted">🔄 Cargando...</div>';

    fetch("/api/finint/sanctioned-wallets")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var wallets = data.wallets || [];
        if (wallets.length === 0) {
          container.innerHTML = '<div class="empty-state"><div style="font-size:2rem;">🛡️</div><div>Sin wallets sancionadas configuradas</div></div>';
          return;
        }
        var html = wallets
          .map(function (w) {
            return '<div class="panel-glass" style="padding:0.8rem;margin-bottom:0.3rem;border-left:3px solid #FF2D55;">' +
              '<div class="font-mono" style="font-size:0.8rem;">' + escapeHtml(w.address) + "</div>" +
              '<div style="font-size:0.75rem;color:#FF2D55;">' + escapeHtml(w.entity) + " — " + escapeHtml(w.program) + "</div>" +
              "</div>";
          })
          .join("");
        container.innerHTML = html;
      })
      .catch(function () {
        container.innerHTML = '<div style="color:#FF2D55;">Error cargando wallets sancionadas</div>';
      });
  }

  function searchDarkWeb() {
    var input = document.getElementById("finint-dw-input");
    var container = document.getElementById("finint-darkweb-results");
    if (!input || !input.value.trim()) return;

    container.innerHTML = '<div class="text-muted">🌐 Buscando en paste sites...</div>';

    fetch("/api/finint/darkweb/search?query=" + encodeURIComponent(input.value.trim()) + "&limit=20")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var results = data.results || [];
        if (results.length === 0) {
          container.innerHTML = '<div class="empty-state"><div style="font-size:2rem;">🌐</div><div>Sin resultados</div></div>';
          return;
        }
        var html = results
          .map(function (r) {
            var cryptoHtml = "";
            if (r.crypto_addresses && Object.keys(r.crypto_addresses).length > 0) {
              cryptoHtml = Object.keys(r.crypto_addresses)
                .map(function (c) {
                  return '<span style="color:#FFCC00;font-size:0.65rem;">' + c.toUpperCase() + ": " + r.crypto_addresses[c].join(", ") + "</span>";
                })
                .join(" | ");
            }
            return '<div class="panel-glass" style="padding:0.8rem;margin-bottom:0.3rem;">' +
              '<div class="flex-between"><span style="font-weight:600;font-size:0.85rem;">' + escapeHtml(r.title) + "</span>" +
              '<span style="font-size:0.65rem;color:#888;">' + escapeHtml(r.source) + "</span></div>" +
              '<div style="font-size:0.75rem;color:#ccc;margin-top:0.3rem;">' + escapeHtml(r.content).slice(0, 300) + "</div>" +
              (cryptoHtml ? '<div style="margin-top:0.3rem;">' + cryptoHtml + "</div>" : "") +
              (r.url ? '<div style="margin-top:0.3rem;"><a href="' + escapeHtml(r.url) + '" target="_blank" style="color:var(--primary);font-size:0.7rem;">' + escapeHtml(r.url) + "</a></div>" : "") +
              "</div>";
          })
          .join("");
        container.innerHTML = html;
      })
      .catch(function () {
        container.innerHTML = '<div style="color:#FF2D55;">Error en búsqueda dark web</div>';
      });
  }

  function analyzeText() {
    var input = document.getElementById("finint-analyze-input");
    var container = document.getElementById("finint-analyze-result");
    if (!input || !input.value.trim()) return;

    container.innerHTML = '<div class="text-muted">🔍 Analizando...</div>';

    fetch("/api/finint/darkweb/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input.value }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var html = '<div class="panel-glass" style="padding:1rem;">';

        if (data.crypto_addresses) {
          html += '<div style="margin-bottom:0.5rem;"><span class="heading-4">💰 Direcciones Crypto</span>';
          for (var c in data.crypto_addresses) {
            if (data.crypto_addresses[c].length > 0) {
              html += '<div style="margin:0.2rem 0;"><span style="color:#FFCC00;font-weight:600;">' + c.toUpperCase() + ":</span> " +
                data.crypto_addresses[c].map(function (a) { return '<span class="font-mono" style="font-size:0.75rem;">' + escapeHtml(a) + "</span>"; }).join(", ") + "</div>";
            }
          }
          html += "</div>";
        }

        if (data.has_sanction_keywords && data.has_sanction_keywords.length > 0) {
          html += '<div style="margin-bottom:0.5rem;"><span class="heading-4">🚫 Keywords Sanción</span>' +
            '<div>' + data.has_sanction_keywords.map(function (k) { return '<span style="background:#FF2D5533;color:#FF2D55;padding:2px 6px;border-radius:3px;font-size:0.7rem;">' + escapeHtml(k) + "</span>"; }).join(" ") + "</div></div>";
        }

        if (data.suspicious_patterns && data.suspicious_patterns.length > 0) {
          html += '<div><span class="heading-4">⚠️ Patrones Sospechosos</span>' +
            '<div>' + data.suspicious_patterns.map(function (p) { return '<span style="background:#FF950033;color:#FF9500;padding:2px 6px;border-radius:3px;font-size:0.7rem;">' + escapeHtml(p) + "</span>"; }).join(" ") + "</div></div>";
        }

        if (!data.crypto_addresses && !data.has_sanction_keywords && !data.suspicious_patterns) {
          html += '<div class="text-muted">Sin indicadores FININT detectados</div>';
        }

        html += "</div>";
        container.innerHTML = html;
      })
      .catch(function () {
        container.innerHTML = '<div style="color:#FF2D55;">Error en análisis</div>';
      });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  window.FinintIntel = {
    init: init,
    destroy: destroy,
    switchTab: switchTab,
    checkWallet: checkWallet,
    loadSanctioned: loadSanctioned,
    searchDarkWeb: searchDarkWeb,
    analyzeText: analyzeText,
  };
})();

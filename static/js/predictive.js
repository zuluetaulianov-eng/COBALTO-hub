/**
 * predictive.js — Predictive Early Warning frontend.
 * Exposes window.PredictiveIntel for threat scoring dashboard.
 */
(function () {
  "use strict";

  var state = {
    alerts: [],
    stats: {},
    filterLevel: "",
    pollInterval: null,
  };

  function init() {
    loadAlerts();
    loadStats();
    if (state.pollInterval) clearInterval(state.pollInterval);
    state.pollInterval = setInterval(loadAlerts, 15000);
  }

  function destroy() {
    if (state.pollInterval) {
      clearInterval(state.pollInterval);
      state.pollInterval = null;
    }
  }

  function loadAlerts() {
    var url = "/api/predictive/alerts?limit=100";
    if (state.filterLevel) {
      // Filter client-side after fetch
    }
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.alerts = data.alerts || [];
        render();
      })
      .catch(function () {});
  }

  function loadStats() {
    fetch("/api/predictive/stats")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.stats = data;
        renderStats();
      })
      .catch(function () {});
  }

  function filterLevel(level) {
    state.filterLevel = level;
    document.querySelectorAll("[data-pred-level]").forEach(function (btn) {
      var match = btn.getAttribute("data-pred-level") === level;
      btn.style.borderColor = match ? "var(--primary)" : "var(--border-color)";
    });
    render();
  }

  function runCycle() {
    var btn = document.querySelector('[onclick*="runCycle"]');
    if (btn) { btn.disabled = true; btn.textContent = "🔄 Preparando..."; }
    fetch("/api/predictive/run")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        loadAlerts();
        loadStats();
        if (btn) { btn.disabled = false; btn.textContent = "🔄 Ejecutar análisis"; }
        if (data.status === "no_entities") {
          showNotification("ℹ️ No hay entidades. Poblando registro...");
          // Try backfill first
          return fetch("/api/entities/backfill", { method: "POST" }).then(function () {
            if (btn) btn.textContent = "🔄 Analizando...";
            return fetch("/api/predictive/run");
          }).then(function (r2) { return r2.json(); }).then(function (data2) {
            loadAlerts();
            loadStats();
            if (btn) btn.textContent = "🔄 Ejecutar análisis";
            if (data2.new_warnings > 0) {
              showNotification(data2.new_warnings + " nuevas alertas predictivas");
            }
          });
        }
        if (data.new_warnings > 0) {
          showNotification(data.new_warnings + " nuevas alertas predictivas");
        }
      })
      .catch(function () {
        if (btn) { btn.disabled = false; btn.textContent = "🔄 Ejecutar análisis"; }
        showNotification("❌ Error en análisis predictivo");
      });
  }

  function showHistory() {
    fetch("/api/predictive/alerts?include_resolved=true&limit=200")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.alerts = data.alerts || [];
        state.filterLevel = "";
        render();
      })
      .catch(function () {});
  }

  function resolveAlert(entityId) {
    fetch("/api/predictive/resolve/" + entityId, { method: "POST" })
      .then(function () { loadAlerts(); })
      .catch(function () {});
  }

  function render() {
    var container = document.getElementById("predictive-alert-list");
    var countEl = document.getElementById("predictive-active-count");
    if (!container) return;

    var filtered = state.alerts;
    if (state.filterLevel) {
      filtered = filtered.filter(function (a) { return a.level === state.filterLevel; });
    }

    if (countEl) {
      var active = state.alerts.filter(function (a) { return a.status === "active"; }).length;
      countEl.textContent = active;
      countEl.style.color = active > 5 ? "#FF2D55" : active > 0 ? "#FF9500" : "#00FFAA";
    }

    if (filtered.length === 0) {
      container.innerHTML =
        '<div class="empty-state"><div style="font-size:2rem;">🛡️</div><div class="heading-4">Sin alertas predictivas</div>' +
        '<p class="text-muted">Ejecuta un análisis o espera al ciclo automático. Si el registro de entidades está vacío, se poblará automáticamente.</p>' +
        '<div class="flex" style="gap:0.5rem;justify-content:center;margin-top:0.8rem;">' +
        '<button class="btn-tactical" onclick="PredictiveIntel.runCycle()">🔄 Ejecutar análisis</button>' +
        '<button class="btn-tactical" onclick="PredictiveIntel.loadAlerts()" style="border-color:var(--text-muted);">🔄 Recargar</button>' +
        "</div></div>";
      return;
    }

    var html = "";
    for (var i = 0; i < filtered.length; i++) {
      var a = filtered[i];
      var levelColor = { critical: "#FF2D55", high: "#FF9500", medium: "#FFCC00" }[a.level] || "#888";
      var statusBadge =
        a.status === "active"
          ? '<span style="background:' + levelColor + "22;color:" + levelColor + ";border:1px solid " + levelColor + "44;padding:2px 8px;border-radius:4px;font-size:0.7rem;\">● ACTIVA</span>"
          : '<span style="background:#88888822;color:#888;border:1px solid #88888844;padding:2px 8px;border-radius:4px;font-size:0.7rem;\">RESUELTA</span>';

      var typeBadge = '<span style="background:var(--primary)22;color:var(--primary);border:1px solid var(--primary)44;padding:2px 8px;border-radius:4px;font-size:0.7rem;">' + escapeHtml(a.entity_type) + "</span>";

      var trendIcon = a.trend === "up" ? '📈 <span style="color:#FF2D55;">Ascendente</span>' : (a.trend === "down" ? '📉 <span style="color:#00FFAA;">Descendente</span>' : '➡️ <span style="color:#FFCC00;">Estable</span>');
      var trendBadge = '<span style="background:rgba(255,255,255,0.05);border:1px solid var(--border-color);padding:2px 8px;border-radius:4px;font-size:0.7rem;">Tendencia: ' + trendIcon + '</span>';

      var rulesHtml = "";
      if (a.rules_triggered && a.rules_triggered.length > 0) {
        rulesHtml = a.rules_triggered.map(function (r) {
          return '<span style="background:#00FFAA22;color:#00FFAA;border:1px solid #00FFAA44;padding:1px 6px;border-radius:3px;font-size:0.65rem;">' + escapeHtml(r) + "</span>";
        }).join(" ");
      }

      var scoreBar = "";
      if (a.threat_score !== undefined) {
        var sc = a.threat_score;
        var scColor = sc >= 75 ? "#FF2D55" : sc >= 50 ? "#FF9500" : "#FFCC00";
        scoreBar =
          '<div style="display:flex;align-items:center;gap:8px;margin-top:0.4rem;">' +
          '<div style="flex:1;height:6px;background:rgba(255,255,255,0.08);border-radius:3px;">' +
          '<div style="width:' + sc + "%;height:100%;background:" + scColor + ";border-radius:3px;transition:width 0.5s;\"></div></div>" +
          '<span style="font-weight:700;font-size:1rem;color:' + scColor + ';">' + sc + "/100</span></div>";
      }

      var summaryHtml = a.human_summary ? '<div style="font-size:0.82rem;color:var(--text-muted);margin:0.4rem 0;line-height:1.4;">' + escapeHtml(a.human_summary) + '</div>' : '';

      var recsHtml = "";
      if (a.recommendations && a.recommendations.length > 0) {
        recsHtml = '<div style="margin-top:0.4rem;background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.15);padding:0.5rem;border-radius:4px;font-size:0.75rem;">' +
          '<div style="color:var(--primary);font-weight:600;margin-bottom:0.2rem;">🛡️ Recomendaciones de Mitigación Táctica:</div>' +
          a.recommendations.map(function(rc) { return '<div>• ' + escapeHtml(rc) + '</div>'; }).join('') +
          '</div>';
      }

      var resolveBtn = a.status === "active"
        ? '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;" onclick="PredictiveIntel.resolveAlert(\'' + a.entity_id + '\')">✅ Resolver Alerta</button>'
        : "";

      html +=
        '<div class="panel-glass" style="padding:1rem;margin-bottom:0.8rem;border-left:4px solid ' + levelColor + ';">' +
        '<div class="flex-between" style="margin-bottom:0.3rem;">' +
        '<div class="flex" style="gap:0.5rem;align-items:center;flex-wrap:wrap;">' +
        statusBadge + " " + typeBadge + " " + trendBadge +
        '<span style="font-weight:600;font-size:0.95rem;">' + escapeHtml(a.entity_name) + "</span>" +
        "</div>" +
        '<span class="text-muted font-mono" style="font-size:0.7rem;">' + (a.created_at || "").slice(11, 19) + "</span>" +
        "</div>" +
        scoreBar +
        summaryHtml +
        (rulesHtml ? '<div class="flex flex-wrap gap-05" style="margin-top:0.3rem;">' + rulesHtml + "</div>" : "") +
        recsHtml +
        '<div class="flex-between" style="margin-top:0.6rem;">' +
        resolveBtn +
        "</div>" +
        "</div>";
    }
    container.innerHTML = html;
  }

  function renderStats() {
    var s = state.stats;
    var levelsEl = document.getElementById("pred-stats-levels");
    var typesEl = document.getElementById("pred-stats-types");
    var entsEl = document.getElementById("pred-stats-entities");

    if (levelsEl && s.by_level) {
      var html = Object.keys(s.by_level)
        .map(function (k) {
          return '<div><span style="color:var(--primary);">' + k + ":</span> " + s.by_level[k] + "</div>";
        })
        .join("");
      levelsEl.innerHTML = html || "—";
    }
    if (typesEl && s.by_type) {
      var html = Object.keys(s.by_type)
        .map(function (k) {
          return '<div><span style="color:var(--primary);">' + escapeHtml(k) + ":</span> " + s.by_type[k] + "</div>";
        })
        .join("");
      typesEl.innerHTML = html || "—";
    }
    if (entsEl && s.entities) {
      entsEl.innerHTML =
        '<div><span style="color:var(--primary);">Total:</span> ' + (s.entities.total_entities || "—") + "</div>" +
        '<div><span style="color:var(--primary);">OFAC:</span> ' + (s.entities.ofac_matched || "—") + "</div>";
    }
  }

  function showNotification(msg) {
    var el = document.getElementById("predictive-notification");
    if (!el) {
      el = document.createElement("div");
      el.id = "predictive-notification";
      el.style.cssText =
        "position:fixed;bottom:20px;right:20px;background:#FF2D55;color:#fff;padding:10px 20px;" +
        "border-radius:8px;z-index:9999;font-size:0.85rem;box-shadow:0 4px 20px rgba(255,45,85,0.4);" +
        "animation:fadeIn 0.3s;";
      document.body.appendChild(el);
    }
    el.textContent = "⚠️ " + msg;
    el.style.display = "block";
    clearTimeout(el._hide);
    el._hide = setTimeout(function () { el.style.display = "none"; }, 5000);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Add CSS animation
  var style = document.createElement("style");
  style.textContent =
    "@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }";
  document.head.appendChild(style);

  window.PredictiveIntel = {
    init: init,
    destroy: destroy,
    filterLevel: filterLevel,
    runCycle: runCycle,
    showHistory: showHistory,
    resolveAlert: resolveAlert,
  };
})();

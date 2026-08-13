/**
 * entity_explorer.js — Entity Registry frontend explorer.
 * Exposes window.EntityExplorer with search, filter, detail view.
 */
(function () {
  "use strict";

  var state = {
    entities: [],
    filtered: [],
    stats: { total_entities: 0, ofac_matches: 0, wikidata_linked: 0 },
  };

  function init() {
    if (window.EntityExplorerData) {
      state.entities = window.EntityExplorerData.entities || [];
      state.stats = window.EntityExplorerData.stats || { total_entities: 0 };
      state.filtered = state.entities.slice();
    }
    if (state.entities.length === 0) {
      fetchStats();
      searchEntities("", "", "", false);
    }
    render();
  }

  function fetchStats() {
    fetch("/api/entities/stats")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.stats = data;
        updateStats();
      })
      .catch(function () {});
  }

  function searchEntities(query, type, source, ofacOnly) {
    var params = new URLSearchParams();
    if (query) params.set("q", query);
    if (type) params.set("type", type);
    if (source) params.set("source", source);
    if (ofacOnly) params.set("ofac_only", "1");
    params.set("limit", "200");

    return fetch("/api/entities/search?" + params.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.filtered = data.entities || data || [];
        render();
        return state.filtered;
      })
      .catch(function () { return []; });
  }

  function search() {
    var query = document.getElementById("entity-search").value.trim();
    var type = document.getElementById("entity-type-filter").value;
    var source = document.getElementById("entity-source-filter").value;
    var ofacOnly = document.getElementById("entity-ofac-only").checked;

    if (!query && !type && !source && !ofacOnly) {
      state.filtered = state.entities.slice();
      render();
      return;
    }

    searchEntities(query, type, source, ofacOnly);
  }

  function filterType() { search(); }
  function filterSource() { search(); }

  function render() {
    var container = document.getElementById("entity-results");
    var totalDisplay = document.getElementById("entity-total-display");

    if (!container) return;

    if (!state.filtered || state.filtered.length === 0) {
      container.innerHTML =
        '<div class="empty-state" style="grid-column:1/-1;">' +
        '<div style="font-size:2rem;margin-bottom:0.5rem;">📦</div>' +
        '<div class="heading-4">0 entidades encontradas</div>' +
        '<p class="text-muted">No hay entidades en el registro. Puebla el registro desde OFAC SDN + históricos, o ejecuta un ciclo completo.</p>' +
        '<div class="flex" style="gap:0.5rem;justify-content:center;margin-top:0.8rem;">' +
        '<button class="btn-tactical" onclick="EntityExplorer.runBackfill()">⚡ Poblar Entidades</button>' +
        '<button class="btn-tactical" onclick="EntityExplorer.search(\'\', \'\', \'\', false)" style="border-color:var(--text-muted);">🔄 Recargar</button>' +
        "</div>" +
        "</div>";
      if (totalDisplay) totalDisplay.textContent = "0 entidades";
      updateStats();
      return;
    }

    var html = "";
    for (var i = 0; i < state.filtered.length; i++) {
      var e = state.filtered[i];
      var typeBadge = getTypeBadge(e.entity_type);
      var ofacBadge = e.ofac_match
        ? '<span class="badge-critical" style="font-size:0.7rem;">🔴 OFAC</span>'
        : "";
      var wikiBadge = e.wikidata_qid
        ? '<span class="badge-info" style="font-size:0.7rem;">🟦 Wikidata</span>'
        : "";
      var aliasText =
        e.aliases && e.aliases.length > 0
          ? e.aliases.slice(0, 3).join(", ") +
            (e.aliases.length > 3 ? "..." : "")
          : "-";

      html +=
        '<div class="panel-glass entity-card" data-entity-id="' +
        escapeHtml(e.id) +
        '" style="padding:0.8rem;cursor:pointer;" onclick="EntityExplorer.showDetail(\'' +
        escapeHtml(e.id) +
        "')\">" +
        '<div class="flex-between" style="margin-bottom:0.3rem;">' +
        '<span class="font-mono" style="font-size:0.8rem;font-weight:600;">' +
        escapeHtml(e.canonical_name || "?") +
        "</span>" +
        '<div class="flex" style="gap:0.3rem;">' +
        typeBadge +
        ofacBadge +
        wikiBadge +
        "</div>" +
        "</div>" +
        '<div class="text-muted" style="font-size:0.75rem;">Alias: ' +
        aliasText +
        "</div>" +
        '<div class="text-muted" style="font-size:0.7rem;margin-top:0.3rem;">' +
        "<span>Fuente: " +
        e.source +
        "</span> · <span>Visto: " +
        (e.last_seen || "").slice(0, 10) +
        "</span>" +
        "</div>" +
        "</div>";
    }
    container.innerHTML = html;
    if (totalDisplay)
      totalDisplay.textContent = state.filtered.length + " entidades";
    updateStats();
  }

  function showDetail(entityId) {
    fetch("/api/entities/" + encodeURIComponent(entityId))
      .then(function (r) { return r.json(); })
      .then(function (e) {
        if (!e || e.error) return;
        var container = document.getElementById("entity-results");
        var propsHtml = "";
        if (e.properties && Object.keys(e.properties).length > 0) {
          for (var key in e.properties) {
            propsHtml +=
              "<tr><td style='padding:2px 8px;font-size:0.75rem;color:var(--text-muted);'>" +
              key +
              "</td><td style='padding:2px 8px;font-size:0.8rem;'>" +
              escapeHtml(JSON.stringify(e.properties[key])) +
              "</td></tr>";
          }
        }
        container.innerHTML =
          '<div class="panel-glass" style="padding:1.5rem;grid-column:1/-1;">' +
          '<div class="flex-between" style="margin-bottom:1rem;">' +
          '<h3 class="heading-3">' +
          escapeHtml(e.canonical_name || "?") +
          "</h3>" +
          '<button class="btn-tactical" onclick="EntityExplorer.render()" style="padding:4px 12px;font-size:0.8rem;">⟵ Volver</button>' +
          "</div>" +
          '<table style="width:100%;border-collapse:collapse;">' +
          "<tr><td style='padding:4px 8px;font-weight:600;'>ID</td><td style='padding:4px 8px;font-family:monospace;font-size:0.8rem;'>" +
          e.id +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Tipo</td><td style='padding:4px 8px;'>" +
          getTypeBadge(e.entity_type) +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Fuente</td><td style='padding:4px 8px;'>" +
          e.source +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Alias</td><td style='padding:4px 8px;'>" +
          (e.aliases ? e.aliases.join(", ") : "-") +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>OFAC</td><td style='padding:4px 8px;'>" +
          (e.ofac_match
            ? '<span class="badge-critical">🔴 Sí</span> IDs: ' +
              (e.ofac_ids || []).join(", ")
            : "No") +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Wikidata</td><td style='padding:4px 8px;'>" +
          (e.wikidata_qid || "-") +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Primera vez</td><td style='padding:4px 8px;'>" +
          (e.first_seen || "-") +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Última vez</td><td style='padding:4px 8px;'>" +
          (e.last_seen || "-") +
          "</td></tr>" +
          "<tr><td style='padding:4px 8px;font-weight:600;'>Snapshots</td><td style='padding:4px 8px;'>" +
          ((e.snapshot_ids || []).length) +
          "</td></tr>" +
          propsHtml +
          "</table>" +
          '<div style="margin-top:1rem;">' +
          '<button class="btn-tactical" onclick="EntityExplorer.render()">⟵ Volver al listado</button>' +
          "</div>" +
          "</div>";
      })
      .catch(function () {});
  }

  function updateStats() {
    var el = document.getElementById("entity-total-display");
    if (!el) return;
    var s = state.stats || {};
    var ofacText = s.ofac_matches ? " · 🔴 OFAC: " + s.ofac_matches : "";
    var wikiText = s.wikidata_linked
      ? " · 🟦 Wikidata: " + s.wikidata_linked
      : "";
    el.textContent =
      "Total: " + (s.total_entities || 0) + ofacText + wikiText;
  }

  function getTypeBadge(type) {
    var colors = {
      person: "#00ffaa",
      organization: "#44aaee",
      location: "#ffaa00",
      infrastructure: "#ff5050",
      vessel: "#00ccff",
      aircraft: "#cc88ff",
      event: "#ff8844",
    };
    var color = colors[type] || "#888";
    return (
      '<span style="background:' +
      color +
      "22;color:" +
      color +
      ";border:1px solid " +
      color +
      "44;padding:1px 6px;border-radius:4px;font-size:0.7rem;font-weight:600;text-transform:uppercase;\">" +
      (type || "unknown") +
      "</span>"
    );
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function runBackfill() {
    var btn = document.querySelector('[onclick*="runBackfill"]');
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Poblando..."; }
    fetch("/api/entities/backfill", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        showToast("✅ " + (data.message || "Entidades pobladas"), "success");
        return searchEntities("", "", "", false);
      })
      .catch(function () {
        showToast("❌ Error al poblar entidades", "error");
      })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = "⚡ Poblar Entidades"; }
      });
  }

  function showToast(msg, type) {
    var el = document.createElement("div");
    el.style.cssText =
      "position:fixed;bottom:20px;right:20px;z-index:9999;padding:10px 20px;border-radius:8px;font-size:0.85rem;" +
      "box-shadow:0 4px 20px rgba(0,0,0,0.4);color:#fff;";
    if (type === "error") el.style.background = "#FF2D55";
    else el.style.background = "#00FFAA33";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () {
      if (el.parentElement) el.parentElement.removeChild(el);
    }, 4000);
  }

  // Export
  window.EntityExplorer = {
    init: init,
    search: search,
    filterType: filterType,
    filterSource: filterSource,
    render: render,
    showDetail: showDetail,
    runBackfill: runBackfill,
  };
})();

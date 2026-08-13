/**
 * humint.js — HUMINT field reports frontend.
 * Exposes window.HumintIntel.
 */
(function () {
  "use strict";

  var state = {
    reports: [],
    filterStatus: "",
    pollInterval: null,
  };

  function init() {
    loadReports();
    if (state.pollInterval) clearInterval(state.pollInterval);
    state.pollInterval = setInterval(loadReports, 20000);
  }

  function destroy() {
    if (state.pollInterval) {
      clearInterval(state.pollInterval);
      state.pollInterval = null;
    }
  }

  function loadReports() {
    var url = "/api/humint/reports?limit=100";
    if (state.filterStatus) url += "&status=" + state.filterStatus;

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.reports = data.reports || [];
        render();
      })
      .catch(function () {});
  }

  function filterStatus(status) {
    state.filterStatus = status;
    document.querySelectorAll("[data-humint-status]").forEach(function (btn) {
      btn.style.borderColor = btn.getAttribute("data-humint-status") === status ? "var(--primary)" : "var(--border-color)";
    });
    loadReports();
  }

  function submitReport() {
    var title = document.getElementById("humint-title");
    var reporter = document.getElementById("humint-reporter");
    var lat = document.getElementById("humint-lat");
    var lon = document.getElementById("humint-lon");
    var location = document.getElementById("humint-location");
    var severity = document.getElementById("humint-severity");
    var tags = document.getElementById("humint-tags");
    var desc = document.getElementById("humint-description");

    if (!title || !title.value.trim()) {
      showToast("⚠️ El título es obligatorio", "warning");
      return;
    }

    var data = {
      title: title.value.trim(),
      reporter: reporter ? reporter.value.trim() : "",
      latitude: lat && lat.value ? parseFloat(lat.value) : null,
      longitude: lon && lon.value ? parseFloat(lon.value) : null,
      location_name: location ? location.value.trim() : "",
      severity: severity ? severity.value : "info",
      tags: tags ? tags.value.split(",").map(function (t) { return t.trim(); }).filter(Boolean) : [],
      description: desc ? desc.value.trim() : "",
    };

    fetch("/api/humint/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
      .then(function (r) { return r.json(); })
      .then(function (result) {
        showToast("✅ Reporte creado: " + result.id, "success");
        // Clear form
        title.value = "";
        if (reporter) reporter.value = "";
        if (lat) lat.value = "";
        if (lon) lon.value = "";
        if (location) location.value = "";
        if (desc) desc.value = "";
        loadReports();
      })
      .catch(function () {
        showToast("❌ Error al crear reporte", "error");
      });
  }

  function addSampleReport() {
    // Pre-fill form with sample data
    var title = document.getElementById("humint-title");
    var reporter = document.getElementById("humint-reporter");
    var lat = document.getElementById("humint-lat");
    var lon = document.getElementById("humint-lon");
    var location = document.getElementById("humint-location");
    var severity = document.getElementById("humint-severity");
    var tags = document.getElementById("humint-tags");
    var desc = document.getElementById("humint-description");
    if (title) title.value = "Patrullaje rutinario sector oeste";
    if (reporter) reporter.value = "Campo-07";
    if (lat) lat.value = "10.4806";
    if (lon) lon.value = "-66.9036";
    if (location) location.value = "Caracas, Parroquia Sucre";
    if (severity) severity.value = "info";
    if (tags) tags.value = "patrullaje, caracas, rutina";
    if (desc) desc.value = "Reporte de patrullaje rutinario en el sector oeste de Caracas. Sin novedades. Tránsito normal. Comercios operando con normalidad. Sin reportes de incidentes de seguridad.";
    // Submit
    submitReport();
  }

  function updateReportStatus(reportId, status) {
    fetch("/api/humint/report/" + reportId + "/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status }),
    })
      .then(function () { loadReports(); })
      .catch(function () {});
  }

  function render() {
    var container = document.getElementById("humint-report-list");
    var countEl = document.getElementById("humint-count");
    if (!container) return;

    if (countEl) countEl.textContent = state.reports.length;

    if (state.reports.length === 0) {
      container.innerHTML =
        '<div class="empty-state"><div style="font-size:2rem;">🕵️</div><div class="heading-4">Sin reportes HUMINT</div>' +
        '<p class="text-muted">Completa el formulario superior y envía tu primer reporte de campo, o crea un reporte de ejemplo para probar.</p>' +
        '<div class="flex" style="gap:0.5rem;justify-content:center;margin-top:0.8rem;">' +
        '<button class="btn-tactical" onclick="HumintIntel.addSampleReport()">📝 Crear reporte de ejemplo</button>' +
        '<button class="btn-tactical" onclick="HumintIntel.loadReports()" style="border-color:var(--text-muted);">🔄 Recargar</button>' +
        "</div></div>";
      return;
    }

    var html = "";
    for (var i = 0; i < state.reports.length; i++) {
      var r = state.reports[i];
      var severityColor = { critical: "#FF2D55", high: "#FF9500", medium: "#FFCC00", info: "#00E5FF" }[r.severity] || "#888";

      var coords = "";
      if (r.latitude && r.longitude) {
        coords =
          '<span class="font-mono" style="font-size:0.7rem;color:var(--primary);">📍 ' +
          parseFloat(r.latitude).toFixed(4) + ", " + parseFloat(r.longitude).toFixed(4) +
          (r.location_name ? " — " + escapeHtml(r.location_name) : "") +
          "</span>";
      }

      var tagsHtml = "";
      if (r.tags) {
        try {
          var tagsArr = typeof r.tags === "string" ? JSON.parse(r.tags) : r.tags;
          tagsHtml = tagsArr.map(function (t) {
            return '<span style="background:var(--primary)22;color:var(--primary);border:1px solid var(--primary)44;padding:1px 6px;border-radius:3px;font-size:0.65rem;">' + escapeHtml(t) + "</span>";
          }).join(" ");
        } catch (e) {}
      }

      var statusBadge = {
        new: '<span style="background:#00E5FF22;color:#00E5FF;padding:2px 8px;border-radius:4px;font-size:0.7rem;">🆕 Nuevo</span>',
        published: '<span style="background:#00FFAA22;color:#00FFAA;padding:2px 8px;border-radius:4px;font-size:0.7rem;">📢 Publicado</span>',
        reviewed: '<span style="background:#88888822;color:#888;padding:2px 8px;border-radius:4px;font-size:0.7rem;">✅ Revisado</span>',
      }[r.status] || "";

      var actionBtns = "";
      if (r.status === "new") {
        actionBtns =
          '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;" onclick="HumintIntel.updateStatus(\'' + r.id + "','published')\">📢 Publicar</button>" +
          '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;" onclick="HumintIntel.updateStatus(\'' + r.id + "','reviewed')\">✅ Revisar</button>";
      }

      html +=
        '<div class="panel-glass" style="padding:0.8rem;margin-bottom:0.4rem;border-left:3px solid ' + severityColor + ';">' +
        '<div class="flex-between" style="margin-bottom:0.3rem;">' +
        '<div class="flex" style="gap:0.4rem;align-items:center;flex-wrap:wrap;">' +
        '<span style="font-weight:600;font-size:0.85rem;">' + escapeHtml(r.title || "Sin título") + "</span>" +
        statusBadge +
        "</div>" +
        '<span class="text-muted font-mono" style="font-size:0.7rem;">' + escapeHtml(r.reporter || "") +
        " " + (r.created_at || "").slice(11, 19) + "</span>" +
        "</div>" +
        (coords ? '<div style="margin-bottom:0.2rem;">' + coords + "</div>" : "") +
        (r.description ? '<div style="font-size:0.8rem;color:#ccc;margin-bottom:0.3rem;">' + escapeHtml(r.description).slice(0, 300) + "</div>" : "") +
        (tagsHtml ? '<div class="flex flex-wrap gap-05" style="margin-bottom:0.3rem;">' + tagsHtml + "</div>" : "") +
        (actionBtns ? '<div class="flex" style="gap:0.3rem;margin-top:0.3rem;">' + actionBtns + "</div>" : "") +
        "</div>";
    }
    container.innerHTML = html;
  }

  function showToast(msg, type) {
    var el = document.createElement("div");
    el.style.cssText =
      "position:fixed;bottom:20px;right:20px;z-index:9999;padding:10px 20px;border-radius:8px;font-size:0.85rem;" +
      "box-shadow:0 4px 20px rgba(0,0,0,0.4);animation:fadeIn 0.3s;color:#fff;";
    if (type === "warning") el.style.background = "#FF9500";
    else if (type === "error") el.style.background = "#FF2D55";
    else el.style.background = "#00FFAA33";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () {
      if (el.parentElement) el.parentElement.removeChild(el);
    }, 4000);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  window.HumintIntel = {
    init: init,
    destroy: destroy,
    loadReports: loadReports,
    filterStatus: filterStatus,
    submitReport: submitReport,
    updateStatus: updateReportStatus,
    addSampleReport: addSampleReport,
  };
})();

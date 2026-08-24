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
    syncOfflineQueue();
    if (state.pollInterval) clearInterval(state.pollInterval);
    state.pollInterval = setInterval(function () {
      loadReports();
      syncOfflineQueue();
    }, 20000);
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

  function jumpToMap(lat, lon, title) {
    if (window.CobaltoCore && typeof window.CobaltoCore.switchTab === "function") {
      window.CobaltoCore.switchTab("tab-map");
    }
    setTimeout(function () {
      if (window.UnifiedMap && typeof window.UnifiedMap.flyTo === "function") {
        window.UnifiedMap.flyTo(parseFloat(lat), parseFloat(lon), 15);
        showToast("📍 Enfocado en mapa: " + (title || "Reporte HUMINT"), "info");
      }
    }, 300);
  }

  function triggerRAG(reportId) {
    fetch("/api/humint/report/" + reportId + "/rag", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.hypothesis) {
          openModal("🎯 Hipótesis Táctica RAG", "<pre style='white-space:pre-wrap;font-family:monospace;color:#00E5FF;font-size:0.85rem;'>" + escapeHtml(data.hypothesis) + "</pre>");
        } else {
          showToast("🎯 Análisis RAG completado", "success");
        }
      })
      .catch(function () {
        showToast("❌ Error ejecutando análisis RAG", "error");
      });
  }

  function openPhotoModal(photoUrl, title) {
    openModal("🖼️ Evidencia Fotográfica — " + (title || "HUMINT"), '<img src="' + escapeHtml(photoUrl) + '" style="max-width:100%;max-height:75vh;object-fit:contain;border-radius:6px;border:1px solid var(--primary);" />');
  }

  function openModal(titleText, bodyHtml) {
    var modal = document.getElementById("humint-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "humint-modal";
      modal.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);z-index:99999;display:flex;align-items:center;justify-content:center;padding:1rem;";
      document.body.appendChild(modal);
    }
    modal.innerHTML =
      '<div style="position:relative;max-width:650px;width:90%;background:#0A0B10;border:1px solid var(--primary);border-radius:8px;padding:1.2rem;box-shadow:0 0 35px rgba(0,229,255,0.25);">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:0.5rem;">' +
      '<span style="font-weight:bold;color:var(--primary);font-size:1rem;">' + escapeHtml(titleText) + "</span>" +
      '<button style="background:none;border:none;color:#888;font-size:1.2rem;cursor:pointer;" onclick="document.getElementById(\'humint-modal\').style.display=\'none\'">✖</button>' +
      "</div>" +
      "<div>" + bodyHtml + "</div>" +
      "</div>";
    modal.style.display = "flex";
  }

  function submitReport() {
    var title = document.getElementById("humint-title");
    var reporter = document.getElementById("humint-reporter");
    var lat = document.getElementById("humint-lat");
    var lon = document.getElementById("humint-lon");
    var location = document.getElementById("humint-location");
    var severity = document.getElementById("humint-severity");
    var photo = document.getElementById("humint-photo");
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
      photo_url: photo ? photo.value.trim() : "",
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
        showToast("✅ Reporte de campo creado: " + result.id, "success");
        // Clear form
        title.value = "";
        if (reporter) reporter.value = "";
        if (lat) lat.value = "";
        if (lon) lon.value = "";
        if (location) location.value = "";
        if (photo) photo.value = "";
        if (tags) tags.value = "";
        if (desc) desc.value = "";
        loadReports();
      })
      .catch(function () {
        // Queue report in offline storage if fetch fails
        saveOfflineReport(data);
        showToast("📡 Red no disponible: Reporte guardado en cola Offline", "warning");
      });
  }

  function saveOfflineReport(reportData) {
    try {
      var queue = JSON.parse(localStorage.getItem("cobalto_humint_offline_queue") || "[]");
      queue.push(reportData);
      localStorage.setItem("cobalto_humint_offline_queue", JSON.stringify(queue));
      updateOfflineBadge(queue.length);
    } catch (e) {}
  }

  function syncOfflineQueue() {
    try {
      var queue = JSON.parse(localStorage.getItem("cobalto_humint_offline_queue") || "[]");
      updateOfflineBadge(queue.length);
      if (queue.length === 0) return;

      var nextReport = queue[0];
      fetch("/api/humint/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextReport),
      })
        .then(function (r) { return r.json(); })
        .then(function () {
          queue.shift();
          localStorage.setItem("cobalto_humint_offline_queue", JSON.stringify(queue));
          updateOfflineBadge(queue.length);
          showToast("📡 Sincronizado 1 reporte pendiente de cola offline", "success");
          loadReports();
        })
        .catch(function () {});
    } catch (e) {}
  }

  function updateOfflineBadge(count) {
    var badge = document.getElementById("humint-offline-badge");
    if (!badge) return;
    if (count > 0) {
      badge.style.display = "inline-block";
      badge.textContent = "📡 " + count + " Pendientes Sync";
    } else {
      badge.style.display = "none";
    }
  }

  function addSampleReport() {
    var title = document.getElementById("humint-title");
    var reporter = document.getElementById("humint-reporter");
    var lat = document.getElementById("humint-lat");
    var lon = document.getElementById("humint-lon");
    var location = document.getElementById("humint-location");
    var severity = document.getElementById("humint-severity");
    var photo = document.getElementById("humint-photo");
    var tags = document.getElementById("humint-tags");
    var desc = document.getElementById("humint-description");

    if (title) title.value = "Patrullaje táctico sector oeste — Novedad vial";
    if (reporter) reporter.value = "Agente-07";
    if (lat) lat.value = "10.4806";
    if (lon) lon.value = "-66.9036";
    if (location) location.value = "Caracas, Parroquia Sucre";
    if (severity) severity.value = "high";
    if (photo) photo.value = "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600";
    if (tags) tags.value = "patrullaje, caracas, movilizacion, vehicular";
    if (desc) desc.value = "Monitoreo en zona de interés. Detección de concentración de vehículos en arteria vial principal. Tránsito ralentizado. Se recomienda verificar en mapa y monitorear transmisiones de zona.";
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

      var coordsHtml = "";
      if (r.latitude && r.longitude) {
        coordsHtml =
          '<div style="margin-bottom:0.3rem;">' +
          '<span class="font-mono" style="font-size:0.75rem;color:var(--primary);">📍 ' +
          parseFloat(r.latitude).toFixed(4) + ", " + parseFloat(r.longitude).toFixed(4) +
          (r.location_name ? " — " + escapeHtml(r.location_name) : "") +
          "</span> " +
          '<button class="btn-tactical btn-sm" style="padding:1px 6px;font-size:0.65rem;margin-left:0.4rem;border-color:var(--primary);" onclick="HumintIntel.jumpToMap(\'' + r.latitude + "','" + r.longitude + "','" + escapeHtml(r.title).replace(/'/g, "") + "')\">📍 MAPA</button>" +
          "</div>";
      }

      var photoHtml = "";
      if (r.photo_url && r.photo_url.startsWith("http")) {
        photoHtml =
          '<div style="margin-top:0.4rem;margin-bottom:0.4rem;">' +
          '<img src="' + escapeHtml(r.photo_url) + '" style="height:70px;border-radius:4px;border:1px solid var(--primary);cursor:pointer;object-fit:cover;" title="Clic para ampliar evidencia" onclick="HumintIntel.openPhotoModal(\'' + escapeHtml(r.photo_url) + "','" + escapeHtml(r.title).replace(/'/g, "") + "')\" />" +
          "</div>";
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
        actionBtns += '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;" onclick="HumintIntel.updateStatus(\'' + r.id + "','published')\">📢 Publicar</button>";
        actionBtns += '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;" onclick="HumintIntel.updateStatus(\'' + r.id + "','reviewed')\">✅ Revisar</button>";
      }
      actionBtns += '<button class="btn-tactical" style="padding:2px 10px;font-size:0.7rem;border-color:var(--primary);" onclick="HumintIntel.triggerRAG(\'' + r.id + "')\">🎯 RAG</button>";

      html +=
        '<div class="panel-glass" style="padding:0.8rem;margin-bottom:0.5rem;border-left:3px solid ' + severityColor + ';">' +
        '<div class="flex-between" style="margin-bottom:0.3rem;">' +
        '<div class="flex" style="gap:0.4rem;align-items:center;flex-wrap:wrap;">' +
        '<span style="font-weight:600;font-size:0.85rem;">' + escapeHtml(r.title || "Sin título") + "</span>" +
        statusBadge +
        "</div>" +
        '<span class="text-muted font-mono" style="font-size:0.7rem;">' + escapeHtml(r.reporter || "") +
        " " + (r.created_at || "").slice(11, 19) + "</span>" +
        "</div>" +
        coordsHtml +
        photoHtml +
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
    else el.style.background = "#00E5FF33";
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
    jumpToMap: jumpToMap,
    triggerRAG: triggerRAG,
    openPhotoModal: openPhotoModal,
  };
})();


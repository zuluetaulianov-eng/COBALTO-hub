/**
 * agent_feed.js — Agent Activity Feed frontend.
 * Exposes window.AgentFeed for task monitoring and approval.
 */
(function () {
  "use strict";

  var state = {
    tasks: [],
    filterStatus: "",
    pollInterval: null,
  };

  function init() {
    loadTasks();
    if (state.pollInterval) clearInterval(state.pollInterval);
    state.pollInterval = setInterval(loadTasks, 10000);
    fetch("/api/agent/mode")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var sel = document.getElementById("agent-mode-select");
        if (sel && d.mode) sel.value = d.mode;
      })
      .catch(function () {});
  }

  function runCycle() {
    var btn = document.querySelector('[onclick*="runCycle"]');
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Ejecutando..."; }
    fetch("/api/agent/run-cycle", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        showToast("✅ Ciclo completado: " + (data.new_tasks || 0) + " tareas generadas", "success");
        loadTasks();
      })
      .catch(function () {
        showToast("❌ Error en ciclo de agentes", "error");
      })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = "🤖 Ejecutar Ciclo de Agentes"; }
      });
  }

  function destroy() {
    if (state.pollInterval) {
      clearInterval(state.pollInterval);
      state.pollInterval = null;
    }
  }

  function loadTasks() {
    var url = "/api/agent/tasks?limit=100";
    if (state.filterStatus) url += "&status=" + state.filterStatus;

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.tasks = data.tasks || [];
        render();
      })
      .catch(function () {});
  }

  function filterStatus(status) {
    state.filterStatus = status;
    // Highlight active button
    document.querySelectorAll('[data-agent-status]').forEach(function (btn) {
      btn.style.borderColor = btn.getAttribute("data-agent-status") === status ? "var(--primary)" : "var(--border-color)";
    });
    loadTasks();
  }

  function setMode(mode) {
    fetch("/api/agent/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode }),
    }).catch(function () {});
  }

  function approve(taskId) {
    fetch("/api/agent/approve/" + taskId, { method: "POST" })
      .then(function () { loadTasks(); })
      .catch(function () {});
  }

  function reject(taskId) {
    fetch("/api/agent/reject/" + taskId, { method: "POST" })
      .then(function () { loadTasks(); })
      .catch(function () {});
  }

  function render() {
    var container = document.getElementById("agent-task-list");
    var countEl = document.getElementById("agent-task-count");
    if (!container) return;

    if (countEl) countEl.textContent = state.tasks.length + " tareas";

    if (state.tasks.length === 0) {
      container.innerHTML =
        '<div class="empty-state"><div style="font-size:2rem;">🤖</div><div class="heading-4">Sin actividad de agentes</div>' +
        '<p class="text-muted">Los agentes autónomos investigan anomalías durante el ciclo Heavy. Ejecuta el ciclo ahora o espera al próximo ciclo automático.</p>' +
        '<div class="flex" style="gap:0.5rem;justify-content:center;margin-top:0.8rem;">' +
        '<button class="btn-tactical" onclick="AgentFeed.runCycle()">🤖 Ejecutar Ciclo de Agentes</button>' +
        '<button class="btn-tactical" onclick="AgentFeed.loadTasks()" style="border-color:var(--text-muted);">🔄 Recargar</button>' +
        "</div></div>";
      return;
    }

    var html = "";
    for (var i = 0; i < state.tasks.length; i++) {
      var t = state.tasks[i];
      var statusBadge = getStatusBadge(t.status);
      var approvalActions = "";
      if (t.status === "pending_approval") {
        approvalActions =
          '<div class="flex" style="gap:0.5rem;margin-top:0.5rem;">' +
          '<button class="btn-tactical" style="background:#00FFAA33;border-color:#00FFAA;padding:4px 12px;font-size:0.75rem;" onclick="AgentFeed.approve(\'' +
          t.id + '\')">✅ Aprobar</button>' +
          '<button class="btn-tactical" style="background:#FF2D5533;border-color:#FF2D55;padding:4px 12px;font-size:0.75rem;" onclick="AgentFeed.reject(\'' +
          t.id + '\')">❌ Rechazar</button></div>';
      }

      var toolInfo = t.tool_name
        ? '<span class="font-mono" style="font-size:0.75rem;color:var(--primary);">🔧 ' + t.tool_name + "</span>"
        : "";

      var resultPreview = "";
      if (t.result && t.result.success && t.result.result) {
        try {
          var preview = JSON.stringify(t.result.result).slice(0, 200);
          resultPreview =
            '<div class="panel-tactical" style="margin-top:0.5rem;padding:0.5rem;font-size:0.75rem;font-family:monospace;max-height:120px;overflow-y:auto;">' +
            preview +
            "</div>";
        } catch (e) {}
      }
      if (t.error) {
        resultPreview =
          '<div style="color:#FF2D55;font-size:0.75rem;margin-top:0.3rem;">Error: ' +
          escapeHtml(t.error) +
          "</div>";
      }

      html +=
        '<div class="panel-glass" style="padding:1rem;margin-bottom:0.5rem;" data-task-id="' +
        t.id +
        '">' +
        '<div class="flex-between" style="margin-bottom:0.3rem;">' +
        '<div class="flex" style="gap:0.5rem;align-items:center;flex-wrap:wrap;">' +
        statusBadge +
        '<span style="font-weight:600;font-size:0.9rem;">' +
        escapeHtml(t.title || t.task_type) +
        "</span>" +
        toolInfo +
        "</div>" +
        '<span class="text-muted font-mono" style="font-size:0.7rem;">' +
        (t.created_at || "").slice(11, 19) +
        "</span>" +
        "</div>" +
        '<div class="text-muted" style="font-size:0.8rem;">' +
        escapeHtml(t.description || "") +
        "</div>" +
        resultPreview +
        approvalActions +
        "</div>";
    }
    container.innerHTML = html;
  }

  function getStatusBadge(status) {
    var colors = {
      pending: "#FFCC00",
      pending_approval: "#FF9500",
      running: "#00E5FF",
      completed: "#00FFAA",
      failed: "#FF2D55",
      rejected: "#888",
    };
    var labels = {
      pending: "Pendiente",
      pending_approval: "⏳ Apruebe",
      running: "🔄 Ejecutando",
      completed: "✅ Completada",
      failed: "❌ Fallida",
      rejected: "Rechazada",
    };
    var color = colors[status] || "#888";
    return (
      '<span style="background:' +
      color +
      "22;color:" +
      color +
      ";border:1px solid " +
      color +
      "44;padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:600;\">" +
      (labels[status] || status) +
      "</span>"
    );
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
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

  function createTask() {
    var input = document.getElementById("agent-custom-prompt");
    var select = document.getElementById("agent-tool-select");
    if (!input || !input.value.trim()) {
      showToast("⚠️ Ingrese una instrucción u objetivo para el agente", "error");
      return;
    }
    var prompt = input.value.trim();
    var tool_name = select ? select.value : "";

    fetch("/api/agent/create-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt, tool_name: tool_name }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        showToast("🚀 Misión desplegada al agente: " + (d.tool_name || "OSINT"), "success");
        input.value = "";
        loadTasks();
      })
      .catch(function () {
        showToast("❌ Error asignando misión", "error");
      });
  }

  window.AgentFeed = {
    init: init,
    destroy: destroy,
    filterStatus: filterStatus,
    setMode: setMode,
    approve: approve,
    reject: reject,
    loadTasks: loadTasks,
    runCycle: runCycle,
    createTask: createTask,
  };
})();

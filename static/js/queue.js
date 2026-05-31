(function () {
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
  const statusLine = document.getElementById("discovery-status-line");
  const bulkResult = document.getElementById("bulk-result");

  function showMessage(text, isError) {
    if (!bulkResult) return;
    bulkResult.style.display = "block";
    bulkResult.className = isError ? "alert error" : "alert success";
    bulkResult.textContent = text;
  }

  async function postForm(url, body) {
    const headers = { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" };
    const response = await fetch(url, { method: "POST", headers, body });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  const pipelineBox = document.getElementById("pipeline-progress");

  function renderPipeline(jobs, budget) {
    if (!pipelineBox) return;
    const active = (jobs || []).filter((j) => j.status === "running" || j.status === "queued");
    if (!active.length) {
      pipelineBox.classList.remove("active");
      pipelineBox.innerHTML = "";
      return;
    }
    pipelineBox.classList.add("active");
    const lines = active
      .map(
        (j) =>
          `<div><strong>${j.kind}</strong>: ${j.message || j.status} ` +
          `(${j.progress_current || 0}/${j.progress_total || "?"}) ` +
          `<form method="post" action="/pipeline/${j.id}/cancel/" style="display:inline;margin-left:8px;">` +
          `<input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">` +
          `<button type="submit" class="btn btn-secondary btn-sm">Cancel</button></form></div>`
      )
      .join("");
    const budgetLine = budget
      ? `<div class="muted">LLM budget: $${budget.spent_usd} / $${budget.daily_limit_usd}</div>`
      : "";
    pipelineBox.innerHTML = budgetLine + lines;
  }

  async function refreshStatus() {
    const response = await fetch("/jobs/discovery-status/");
    const data = await response.json();
    if (!data.success || !statusLine) return;
    const q = data.queue || {};
    statusLine.textContent =
      `Queue: ${q.total || 0} leads  ${q.matched || 0} matched, ${q.new || 0} new. ` +
      `Last poll: ${new Date().toLocaleTimeString()}`;
    renderPipeline(data.pipeline_jobs, data.budget);
  }

  document.getElementById("btn-refresh-status")?.addEventListener("click", () => {
    refreshStatus().catch((err) => showMessage(err.message, true));
  });

  document.getElementById("btn-run-discovery")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-run-discovery");
    btn.disabled = true;
    showMessage("Discovery running this may take several minutes.", false);
    try {
      const body = new URLSearchParams({ score_limit: "20" });
      const data = await postForm("/jobs/discover/", body);
      if (data.async) {
        showMessage("Discovery queued in background. Refresh status in a minute.", false);
      } else {
        const r = data.result || {};
        showMessage(
          `Done: ${r.total_imported || 0} imported, ${r.scored || 0} scored.`,
          false
        );
      }
      await refreshStatus();
    } catch (err) {
      showMessage(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  document.querySelectorAll(".bulk-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = new FormData(form);
      try {
        showMessage("Working", false);
        const data = await postForm(form.action, body);
        if (data.result?.scored !== undefined) {
          showMessage(`Scored ${data.result.scored} lead(s).`, false);
        } else if (data.scored !== undefined) {
          showMessage(`Scored ${data.scored} lead(s).`, false);
        } else if (data.result?.generated !== undefined) {
          showMessage(`Generated ${data.result.generated} kit(s).`, false);
        } else if (data.generated !== undefined) {
          showMessage(
            `Generated ${data.generated} kit(s).` +
              (data.errors?.length ? ` Errors: ${data.errors.join("; ")}` : ""),
            data.errors?.length > 0
          );
        } else {
          showMessage("Task completed.", false);
        }
        await refreshStatus();
        setTimeout(() => window.location.reload(), 1500);
      } catch (err) {
        showMessage(err.message, true);
      }
    });
  });

  refreshStatus().catch(() => {});
  setInterval(() => refreshStatus().catch(() => {}), 30000);
})();

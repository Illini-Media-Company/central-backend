// Backend monitoring dashboard: renders /api/monitoring data and lets admins
// trigger manual runs. All server-provided strings go through esc() or
// textContent before reaching the DOM.
(function () {
    "use strict";

    const app = document.getElementById("monitoring-app");
    if (!app) return;

    const CSRF = app.dataset.csrf;
    const DASHBOARD_URL = app.dataset.dashboardUrl;
    const RUNS_URL = app.dataset.runsUrl;
    const REFRESH_MS = 60 * 1000;
    const RUNS_LIMIT = 15;
    const HISTORY_LIMIT = 50;
    const TZ = "America/Chicago";

    const STATUS = {
        healthy: { label: "Healthy", icon: "bi-check-circle" },
        degraded: { label: "Degraded", icon: "bi-exclamation-triangle" },
        failed: { label: "Failed", icon: "bi-x-octagon" },
        unknown: { label: "Unknown", icon: "bi-question-circle" },
        succeeded: { label: "Succeeded", icon: "bi-check-circle" },
        running: { label: "Running", icon: "bi-hourglass-split" },
        completed: { label: "Completed", icon: "bi-check-circle" },
        overdue: { label: "Overdue", icon: "bi-clock-history" },
    };
    const STATUS_ORDER = { failed: 0, degraded: 1, unknown: 2, healthy: 3 };

    const state = { dashboard: null, runs: [], refreshTimer: null, loading: false };

    // ——— Helpers ———

    function esc(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    const dateFmt = new Intl.DateTimeFormat("en-US", {
        timeZone: TZ, month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    });
    const fullDateFmt = new Intl.DateTimeFormat("en-US", {
        timeZone: TZ, weekday: "short", month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short",
    });

    function parseDate(iso) {
        if (!iso) return null;
        const date = new Date(iso);
        return isNaN(date) ? null : date;
    }

    function fmtDate(iso) {
        const date = parseDate(iso);
        return date ? dateFmt.format(date) : "—";
    }

    function fmtRelative(iso) {
        const date = parseDate(iso);
        if (!date) return "never";
        const seconds = Math.round((Date.now() - date.getTime()) / 1000);
        if (seconds < 45) return "just now";
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.round(minutes / 60);
        if (hours < 48) return `${hours}h ago`;
        return `${Math.round(hours / 24)}d ago`;
    }

    function timeCell(iso) {
        const date = parseDate(iso);
        if (!date) return `<span class="mon-sub">never</span>`;
        return `<span title="${esc(fullDateFmt.format(date))}">${esc(fmtRelative(iso))}</span>
                <span class="mon-sub nowrap">${esc(dateFmt.format(date))}</span>`;
    }

    function fmtMs(ms) {
        if (ms === null || ms === undefined) return "—";
        if (ms >= 10000) return `${(ms / 1000).toFixed(1)} s`;
        return `${Math.round(ms).toLocaleString()} ms`;
    }

    function fmtPct(value) {
        return value === null || value === undefined ? "—" : `${Number(value).toFixed(value >= 99.95 || value === 0 ? 0 : 1)}%`;
    }

    function durationMs(start, end) {
        const a = parseDate(start);
        const b = parseDate(end);
        return a && b ? b - a : null;
    }

    function pill(status, labelOverride) {
        const meta = STATUS[status] || STATUS.unknown;
        const cls = STATUS[status] ? status : "unknown";
        return `<span class="mon-pill ${cls}"><i class="bi ${meta.icon}" aria-hidden="true"></i>${esc(labelOverride || meta.label)}</span>`;
    }

    function titleCase(text) {
        return String(text || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\bHttp\b/g, "HTTP");
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "application/json", ...(options && options.headers) },
            ...options,
        });
        let body = null;
        try {
            body = await response.json();
        } catch (err) {
            body = null;
        }
        if (!response.ok) {
            const message = (body && body.error) ||
                (response.status === 401 || response.status === 403
                    ? "You don't have access to monitoring data. Try logging in again."
                    : `Request failed (${response.status})`);
            const error = new Error(message);
            error.status = response.status;
            throw error;
        }
        return body;
    }

    // ——— Alerts ———

    const alertsEl = document.getElementById("alerts");

    function showAlert(kind, html, { id, dismissible = true } = {}) {
        if (id) {
            const existing = alertsEl.querySelector(`[data-alert-id="${id}"]`);
            if (existing) existing.remove();
        }
        const icon = { failed: "bi-x-octagon", degraded: "bi-exclamation-triangle",
            healthy: "bi-check-circle", info: "bi-info-circle" }[kind];
        const el = document.createElement("div");
        el.className = `mon-alert ${kind}`;
        el.setAttribute("role", kind === "failed" ? "alert" : "status");
        if (id) el.dataset.alertId = id;
        el.innerHTML = `<i class="bi ${icon}" aria-hidden="true"></i>
            <div class="mon-alert-text">${html}</div>
            ${dismissible ? '<button type="button" aria-label="Dismiss"><i class="bi bi-x-lg"></i></button>' : ""}`;
        const close = el.querySelector("button");
        if (close) close.addEventListener("click", () => el.remove());
        alertsEl.appendChild(el);
        return el;
    }

    function clearAlert(id) {
        const el = alertsEl.querySelector(`[data-alert-id="${id}"]`);
        if (el) el.remove();
    }

    // ——— Rendering: hero & tiles ———

    function renderHero(data) {
        const sub = document.getElementById("hero-sub");
        const snapshot = data.snapshot;
        if (!snapshot || !snapshot.last_run_finished_at) {
            sub.textContent = "No monitoring runs yet. Start one to populate the dashboard.";
            return;
        }
        const run = data.last_run;
        const tier = run ? `${run.tier} suite` : "run";
        sub.textContent = `Last ${tier} finished ${fmtRelative(snapshot.last_run_finished_at)} · ${fmtDate(snapshot.last_run_finished_at)}`;
    }

    function tile(cls, icon, label, value, note) {
        return `<div class="mon-tile ${cls}">
            <div class="mon-tile-label"><i class="bi ${icon}" aria-hidden="true"></i>${esc(label)}</div>
            <div class="mon-tile-value">${esc(value)}</div>
            ${note ? `<div class="mon-tile-note">${esc(note)}</div>` : ""}
        </div>`;
    }

    function renderTiles(data) {
        const checks = (data.snapshot && data.snapshot.checks) || [];
        const counts = { healthy: 0, degraded: 0, failed: 0, unknown: 0 };
        let alerts = 0;
        let stale = 0;
        checks.forEach((check) => {
            counts[STATUS_ORDER[check.status] !== undefined ? check.status : "unknown"] += 1;
            if (check.alert_active) alerts += 1;
            if (check.stale) stale += 1;
        });
        const jobs = data.cron_jobs || [];
        const overdueJobs = jobs.filter((job) => job.overdue || job.last_status === "failed").length;
        const unseenJobs = jobs.filter((job) => !job.last_status).length;

        document.getElementById("summary-tiles").innerHTML = [
            tile("", STATUS.healthy.icon, "healthy", counts.healthy, `of ${checks.length} checks`),
            tile("", STATUS.degraded.icon, "degraded", counts.degraded, "slow or need attention"),
            tile(counts.failed ? "attention" : "", STATUS.failed.icon, "failed", counts.failed, stale ? `${stale} stale` : "no stale checks"),
            tile(alerts ? "attention" : "", "bi-bell", "active alerts", alerts, "sent to Slack"),
            tile(overdueJobs ? "attention" : "", "bi-clock-history", "job problems", overdueJobs, unseenJobs ? `${unseenJobs} of ${jobs.length} not seen yet` : `of ${jobs.length} scheduled jobs`),
        ].join("");
    }

    function renderStuckRuns(data) {
        const stuck = data.stuck_runs || [];
        if (!stuck.length) {
            clearAlert("stuck");
            return;
        }
        const items = stuck.map((run) => `<span class="mono">${esc(run.run_id)}</span> (${esc(run.tier)}, started ${esc(fmtRelative(run.start_time))})`).join(", ");
        showAlert("degraded", `<strong>${stuck.length} run${stuck.length > 1 ? "s" : ""} appear stuck:</strong> ${items}`, { id: "stuck", dismissible: false });
    }

    // ——— Rendering: checks table ———

    const searchEl = document.getElementById("check-search");
    const statusFilterEl = document.getElementById("filter-status");
    const tierFilterEl = document.getElementById("filter-tier");

    function filteredChecks() {
        const checks = ((state.dashboard && state.dashboard.snapshot && state.dashboard.snapshot.checks) || []).slice();
        const query = searchEl.value.trim().toLowerCase();
        const status = statusFilterEl.value;
        const tier = tierFilterEl.value;
        return checks
            .filter((check) => {
                if (tier && check.tier !== tier) return false;
                if (status === "stale" && !check.stale) return false;
                if (status && status !== "stale" && (check.status || "unknown") !== status) return false;
                if (query) {
                    const hay = `${check.name} ${check.check_id} ${check.target || ""}`.toLowerCase();
                    if (!hay.includes(query)) return false;
                }
                return true;
            })
            .sort((a, b) => {
                const byStatus = (STATUS_ORDER[a.status] ?? 2) - (STATUS_ORDER[b.status] ?? 2);
                if (byStatus) return byStatus;
                if (a.tier !== b.tier) return a.tier === "critical" ? -1 : 1;
                return String(a.name).localeCompare(String(b.name));
            });
    }

    function renderChecks() {
        const tbody = document.querySelector("#checks-table tbody");
        const all = (state.dashboard && state.dashboard.snapshot && state.dashboard.snapshot.checks) || [];
        const checks = filteredChecks();
        if (!all.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="mon-empty">No check results yet. Run a suite to get started.</td></tr>`;
            return;
        }
        if (!checks.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="mon-empty">No checks match these filters.</td></tr>`;
            return;
        }
        tbody.innerHTML = checks.map((check) => {
            const tags = [
                check.severity ? `<span class="mon-tag ${esc(check.severity)}">${esc(check.severity)}</span>` : "",
                check.alert_active ? `<span class="mon-tag alert"><i class="bi bi-bell" aria-hidden="true"></i>alerting</span>` : "",
                check.stale ? `<span class="mon-tag stale">stale</span>` : "",
            ].join("");
            const error = check.status === "failed" || check.status === "degraded"
                ? [check.error_type ? titleCase(check.error_type) : "", check.error_message || ""].filter(Boolean).join(": ")
                : "";
            return `<tr class="clickable" tabindex="0" data-check-id="${esc(check.check_id)}" aria-label="View history for ${esc(check.name)}">
                <td>${pill(check.status || "unknown")}</td>
                <td>
                    <span class="mon-check-name">${esc(check.name || check.check_id)}</span>
                    ${check.target ? `<span class="mon-sub mono">${esc(check.target)}</span>` : ""}
                    ${error ? `<span class="mon-error-text ${esc(check.status)}">${esc(error)}</span>` : ""}
                    ${tags ? `<div class="mon-tags">${tags}</div>` : ""}
                </td>
                <td>${esc(check.tier || "—")}</td>
                <td class="num">${esc(fmtMs(check.response_time_ms))}</td>
                <td class="num">${esc(fmtPct(check.uptime_24h))}</td>
                <td class="num">${esc(fmtPct(check.uptime_7d))}</td>
                <td class="num">${esc(fmtPct(check.error_rate_24h))}</td>
                <td>${timeCell(check.last_checked_at)}</td>
            </tr>`;
        }).join("");
    }

    // ——— Rendering: runs & cron jobs ———

    function stackBar(run) {
        const total = run.total || 0;
        if (!total) return `<span class="mon-stack-label">No results</span>`;
        const seg = (cls, count) => count ? `<span class="${cls}" style="flex:${count}"></span>` : "";
        const parts = [`${run.healthy || 0} ok`];
        if (run.degraded) parts.push(`${run.degraded} degraded`);
        if (run.failed) parts.push(`${run.failed} failed`);
        return `<span class="mon-stack-label">${esc(parts.join(" · "))}</span>
            <div class="mon-stack" aria-hidden="true">${seg("healthy", run.healthy)}${seg("degraded", run.degraded)}${seg("failed", run.failed)}</div>`;
    }

    function renderRuns() {
        const tbody = document.querySelector("#runs-table tbody");
        if (!state.runs.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="mon-empty">No runs recorded yet.</td></tr>`;
            return;
        }
        tbody.innerHTML = state.runs.map((run) => {
            const status = run.run_status === "running" ? pill("running") : "";
            return `<tr class="clickable" tabindex="0" data-run-id="${esc(run.run_id)}" aria-label="View run ${esc(run.run_id)}">
                <td>${timeCell(run.start_time)}</td>
                <td>${esc(run.tier)}</td>
                <td>${esc(titleCase(run.trigger))}</td>
                <td>${status || stackBar(run)}</td>
                <td class="num">${esc(fmtMs(durationMs(run.start_time, run.end_time)))}</td>
            </tr>`;
        }).join("");
    }

    function renderCron(data) {
        const tbody = document.querySelector("#cron-table tbody");
        const jobs = (data.cron_jobs || []).slice().sort((a, b) =>
            Number(b.overdue || b.last_status === "failed") - Number(a.overdue || a.last_status === "failed") ||
            String(a.display_name).localeCompare(String(b.display_name)));
        if (!jobs.length) {
            tbody.innerHTML = `<tr><td colspan="4" class="mon-empty">No scheduled jobs are reporting yet.</td></tr>`;
            return;
        }
        tbody.innerHTML = jobs.map((job) => {
            const statusPill = job.overdue ? pill("overdue") : job.last_status ? pill(job.last_status) : pill("unknown", "Not seen yet");
            const detail = [];
            if (job.last_error) detail.push(`<span class="mon-error-text">${esc(job.last_error)}</span>`);
            if (job.last_http_status && job.last_http_status >= 400) {
                detail.push(`<span class="mon-sub">HTTP ${esc(job.last_http_status)}</span>`);
            }
            return `<tr>
                <td>${statusPill}</td>
                <td><span class="mon-check-name">${esc(job.display_name || job.job_id)}</span>
                    <span class="mon-sub mono">${esc(job.job_id)}</span>${detail.join("")}</td>
                <td>${timeCell(job.last_succeeded_at)}</td>
                <td class="num">${esc(fmtMs(job.last_duration_ms))}</td>
            </tr>`;
        }).join("");
    }

    // ——— Data loading ———

    const refreshBtn = document.getElementById("refresh-now");

    async function load() {
        if (state.loading) return;
        state.loading = true;
        refreshBtn.classList.add("spinning");
        try {
            const [dashboard, runs] = await Promise.all([
                fetchJson(DASHBOARD_URL),
                fetchJson(`${RUNS_URL}?limit=${RUNS_LIMIT}`),
            ]);
            state.dashboard = dashboard || {};
            state.runs = (runs && runs.runs) || [];
            clearAlert("load-error");
            renderHero(state.dashboard);
            renderTiles(state.dashboard);
            renderStuckRuns(state.dashboard);
            renderChecks();
            renderRuns();
            renderCron(state.dashboard);
        } catch (err) {
            showAlert("failed", `Couldn't load monitoring data. ${esc(err.message)}`, { id: "load-error" });
        } finally {
            state.loading = false;
            refreshBtn.classList.remove("spinning");
        }
    }

    function scheduleRefresh() {
        clearInterval(state.refreshTimer);
        if (document.getElementById("auto-refresh").checked) {
            state.refreshTimer = setInterval(() => {
                if (!document.hidden) load();
            }, REFRESH_MS);
        }
    }

    // ——— Manual runs ———

    async function triggerRun(tier, button) {
        const buttons = app.querySelectorAll("[data-run-tier]");
        const original = button.innerHTML;
        buttons.forEach((b) => { b.disabled = true; });
        button.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Running ${esc(tier)}…`;
        showAlert("info", `Running the <strong>${esc(tier)}</strong> suite. This can take a minute…`, { id: "run", dismissible: false });
        try {
            const result = await fetchJson(RUNS_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
                body: JSON.stringify({ tier }),
            });
            const kind = result.failed ? "failed" : result.degraded ? "degraded" : "healthy";
            showAlert(kind,
                `<strong>${esc(titleCase(tier))} run complete:</strong> ${esc(result.healthy)} healthy, ${esc(result.degraded)} degraded, ${esc(result.failed)} failed of ${esc(result.total)} checks.`,
                { id: "run" });
            await load();
        } catch (err) {
            const message = err.status === 409
                ? "Another monitoring run is already in progress. Try again once it finishes."
                : `Run failed: ${esc(err.message)}`;
            showAlert(err.status === 409 ? "degraded" : "failed", message, { id: "run" });
        } finally {
            buttons.forEach((b) => { b.disabled = false; });
            button.innerHTML = original;
        }
    }

    // ——— Detail modal ———

    const modalEl = document.getElementById("detail-modal");
    const modalTitle = document.getElementById("detail-modal-title");
    const modalBody = document.getElementById("detail-modal-body");
    let modal = null;

    function openModal(title) {
        modal = modal || new window.bootstrap.Modal(modalEl);
        modalTitle.innerHTML = `<i class="imc imc-arrowhead mon-arrow" aria-hidden="true"></i>${esc(title)}`;
        modalBody.innerHTML = `<div class="mon-empty"><span class="spinner-border spinner-border-sm"></span> Loading…</div>`;
        modal.show();
    }

    function resultRows(results, { showCheck }) {
        if (!results.length) {
            return `<tr><td colspan="6" class="mon-empty">No results recorded.</td></tr>`;
        }
        return results.map((r) => {
            const error = [r.error_type ? titleCase(r.error_type) : "", r.error_message || ""].filter(Boolean).join(": ");
            const over = r.latency_threshold_ms && r.response_time_ms > r.latency_threshold_ms;
            return `<tr>
                <td>${pill(r.status)}</td>
                ${showCheck
                    ? `<td><span class="mon-check-name">${esc(r.check_name || r.check_id)}</span>${r.target ? `<span class="mon-sub mono">${esc(r.target)}</span>` : ""}</td>`
                    : `<td>${timeCell(r.checked_at)}</td>`}
                <td class="num ${over ? "mon-over" : ""}">${esc(fmtMs(r.response_time_ms))}${r.latency_threshold_ms ? `<span class="mon-sub">limit ${esc(fmtMs(r.latency_threshold_ms))}</span>` : ""}</td>
                <td class="num">${esc(r.http_status_code ?? "—")}</td>
                <td class="num">${esc(r.attempts ?? "—")}</td>
                <td>${error ? `<span class="mon-error-text ${esc(r.status)}">${esc(error)}</span>` : `<span class="mon-sub">—</span>`}
                    ${r.alert_sent ? `<span class="mon-tag alert"><i class="bi bi-bell" aria-hidden="true"></i>alert sent</span>` : ""}</td>
            </tr>`;
        }).join("");
    }

    function resultsTable(results, { showCheck }) {
        return `<div class="mon-card"><div class="mon-table-wrap"><table class="mon-table">
            <thead><tr>
                <th>Status</th><th>${showCheck ? "Check" : "Checked"}</th>
                <th class="num">Response</th><th class="num">HTTP</th><th class="num">Attempts</th><th>Error</th>
            </tr></thead>
            <tbody>${resultRows(results, { showCheck })}</tbody>
        </table></div></div>`;
    }

    function defs(pairs) {
        return `<dl class="mon-defs">${pairs
            .filter(([, v]) => v !== undefined && v !== null && v !== "")
            .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
    }

    // Response-time bar chart: one bar per result, oldest → newest, colored by
    // status, with a dashed latency-threshold line. Failed results with no
    // timing draw as a short stub so they stay visible.
    function responseChart(results, threshold) {
        const points = results.slice().reverse();
        if (!points.length) return "";
        // Match the modal-xl body width so SVG text renders near its CSS size; the
        // modal may still be animating open here, so it can't be measured yet.
        const W = Math.max(320, Math.min(window.innerWidth - 32, 1140) - 64), H = 200, PAD_L = 52, PAD_R = 8, PAD_T = 10, PAD_B = 22;
        const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B;
        const maxValue = Math.max(threshold || 0, ...points.map((p) => p.response_time_ms || 0), 1) * 1.1;
        const niceStep = (() => {
            const raw = maxValue / 4;
            const mag = Math.pow(10, Math.floor(Math.log10(raw)));
            return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
        })();
        const top = niceStep * Math.ceil(maxValue / niceStep);
        const y = (v) => PAD_T + plotH - (v / top) * plotH;
        const slot = plotW / points.length;
        const gap = Math.min(2, slot * 0.25);
        const barW = Math.max(1, Math.min(18, slot - gap));

        let grid = "";
        for (let v = 0; v <= top + 1e-9; v += niceStep) {
            grid += `<line class="grid" x1="${PAD_L}" x2="${W - PAD_R}" y1="${y(v)}" y2="${y(v)}"></line>
                <text class="axis-label" x="${PAD_L - 6}" y="${y(v) + 4}" text-anchor="end">${esc(fmtMs(v).replace(" ", ""))}</text>`;
        }

        const bars = points.map((p, i) => {
            const x = PAD_L + i * slot + (slot - barW) / 2;
            const value = p.response_time_ms;
            const h = value ? Math.max(3, (value / top) * plotH) : 4;
            const r = Math.min(4, barW / 2);
            const yTop = PAD_T + plotH - h;
            // Rounded top corners only, anchored flat on the baseline.
            const path = `M${x},${PAD_T + plotH} V${yTop + r} Q${x},${yTop} ${x + r},${yTop} H${x + barW - r} Q${x + barW},${yTop} ${x + barW},${yTop + r} V${PAD_T + plotH} Z`;
            return `<path class="bar ${esc(p.status)}" d="${path}" data-i="${i}"></path>
                <rect class="hit" x="${PAD_L + i * slot}" y="${PAD_T}" width="${slot}" height="${plotH}" data-i="${i}"></rect>`;
        }).join("");

        const thresholdLine = threshold
            ? `<line class="threshold" x1="${PAD_L}" x2="${W - PAD_R}" y1="${y(threshold)}" y2="${y(threshold)}"></line>`
            : "";

        const firstLabel = points[0] ? fmtDate(points[0].checked_at) : "";
        const lastLabel = points[points.length - 1] ? fmtDate(points[points.length - 1].checked_at) : "";

        return `<div class="mon-chart-block">
            <p class="mon-chart-title">Response time, last ${points.length} results</p>
            <svg class="mon-chart" viewBox="0 0 ${W} ${H}" role="img"
                 aria-label="Response time per result; see table below for values">
                ${grid}${thresholdLine}${bars}
                <text class="axis-label" x="${PAD_L}" y="${H - 4}">${esc(firstLabel)}</text>
                <text class="axis-label" x="${W - PAD_R}" y="${H - 4}" text-anchor="end">${esc(lastLabel)}</text>
            </svg>
            <div class="mon-chart-legend">
                <span><i class="mon-swatch" style="background:var(--mon-healthy)"></i>Healthy</span>
                <span><i class="mon-swatch" style="background:var(--mon-degraded)"></i>Degraded</span>
                <span><i class="mon-swatch" style="background:var(--mon-failed)"></i>Failed</span>
                ${threshold ? `<span><i class="mon-swatch line"></i>Latency limit (${esc(fmtMs(threshold))})</span>` : ""}
            </div>
        </div>`;
    }

    function bindChartHover(container, results) {
        const svg = container.querySelector(".mon-chart");
        if (!svg) return;
        const points = results.slice().reverse();
        const tooltip = document.getElementById("chart-tooltip");
        const barsByIndex = svg.querySelectorAll(".bar");

        svg.addEventListener("mousemove", (event) => {
            const i = event.target.dataset && event.target.dataset.i;
            if (i === undefined) return hide();
            const p = points[Number(i)];
            const meta = STATUS[p.status] || STATUS.unknown;
            tooltip.innerHTML = `<strong><i class="bi ${meta.icon}"></i> ${esc(meta.label)}</strong><br>
                ${esc(fmtMs(p.response_time_ms))}${p.http_status_code ? ` · HTTP ${esc(p.http_status_code)}` : ""}<br>
                ${esc(fmtDate(p.checked_at))}
                ${p.error_message ? `<br>${esc(p.error_message)}` : ""}`;
            tooltip.hidden = false;
            const x = Math.min(event.clientX + 12, window.innerWidth - tooltip.offsetWidth - 8);
            tooltip.style.left = `${x}px`;
            tooltip.style.top = `${event.clientY + 12}px`;
            barsByIndex.forEach((bar) => bar.classList.toggle("dim", bar.dataset.i !== i));
        });
        svg.addEventListener("mouseleave", hide);

        function hide() {
            tooltip.hidden = true;
            barsByIndex.forEach((bar) => bar.classList.remove("dim"));
        }
        modalEl.addEventListener("hide.bs.modal", hide, { once: true });
    }

    async function showCheckHistory(checkId) {
        const snapshotEntry = ((state.dashboard && state.dashboard.snapshot && state.dashboard.snapshot.checks) || [])
            .find((c) => c.check_id === checkId) || {};
        openModal(snapshotEntry.name || checkId);
        try {
            const data = await fetchJson(`/api/monitoring/checks/${encodeURIComponent(checkId)}?limit=${HISTORY_LIMIT}`);
            const def = data.check || {};
            const params = def.params || {};
            const results = data.results || [];
            modalBody.innerHTML = defs([
                ["current status", pill(snapshotEntry.status || "unknown")],
                ["target", params.target || params.job_id || params.handler ? `<span class="mono">${esc(params.target || params.job_id || params.handler)}</span>` : ""],
                ["kind", esc(def.kind)],
                ["tier", esc(def.tier)],
                ["severity", esc(def.severity)],
                ["timeout", esc(fmtMs(def.timeout_ms))],
                ["latency limit", esc(fmtMs(def.latency_threshold_ms))],
                ["uptime 24h / 7d", `${esc(fmtPct(snapshotEntry.uptime_24h))} / ${esc(fmtPct(snapshotEntry.uptime_7d))}`],
                ["enabled", def.enabled === false ? "No" : "Yes"],
            ]) + responseChart(results, def.latency_threshold_ms) + resultsTable(results, { showCheck: false });
            bindChartHover(modalBody, results);
        } catch (err) {
            modalBody.innerHTML = `<div class="mon-alert failed"><i class="bi bi-x-octagon"></i><div class="mon-alert-text">${esc(err.message)}</div></div>`;
        }
    }

    async function showRunDetail(runId) {
        openModal("run detail");
        try {
            const data = await fetchJson(`${RUNS_URL}/${encodeURIComponent(runId)}`);
            const run = data.run || {};
            const results = (data.results || []).slice().sort((a, b) =>
                (STATUS_ORDER[a.status] ?? 2) - (STATUS_ORDER[b.status] ?? 2) ||
                String(a.check_name).localeCompare(String(b.check_name)));
            modalBody.innerHTML = defs([
                ["run id", `<span class="mono">${esc(run.run_id)}</span>`],
                ["status", pill(run.run_status)],
                ["tier", esc(run.tier)],
                ["trigger", esc(titleCase(run.trigger))],
                ["started", esc(fmtDate(run.start_time))],
                ["duration", esc(fmtMs(durationMs(run.start_time, run.end_time)))],
                ["results", stackBar(run)],
            ]) + resultsTable(results, { showCheck: true });
        } catch (err) {
            modalBody.innerHTML = `<div class="mon-alert failed"><i class="bi bi-x-octagon"></i><div class="mon-alert-text">${esc(err.message)}</div></div>`;
        }
    }

    // ——— Events ———

    function onRowActivate(tableId, attr, handler) {
        const table = document.getElementById(tableId);
        const activate = (event) => {
            const row = event.target.closest(`tr[${attr}]`);
            if (row) handler(row.getAttribute(attr));
        };
        table.addEventListener("click", activate);
        table.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                activate(event);
            }
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        app.querySelectorAll("[data-run-tier]").forEach((button) => {
            button.addEventListener("click", () => triggerRun(button.dataset.runTier, button));
        });
        refreshBtn.addEventListener("click", load);
        document.getElementById("auto-refresh").addEventListener("change", scheduleRefresh);
        [searchEl, statusFilterEl, tierFilterEl].forEach((el) => el.addEventListener("input", renderChecks));
        onRowActivate("checks-table", "data-check-id", showCheckHistory);
        onRowActivate("runs-table", "data-run-id", showRunDetail);
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden && document.getElementById("auto-refresh").checked) load();
        });

        load();
        scheduleRefresh();
    });
})();

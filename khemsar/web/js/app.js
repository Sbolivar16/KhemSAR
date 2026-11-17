const state = {
  lang: "es",
  locale: {},
  projectId: null,
  lastQSAR: null,
  lastSAR: null,
  lastDeNovo: null,
};

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const err = await resp.json();
      msg = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(msg);
  }
  return resp.json();
}

function trText(es, en, pt) {
  if (state.lang === "en") return en;
  if (state.lang === "pt") return pt;
  return es;
}

async function runWithProgress(pid, btn, initialText, workFn) {
  const wrap = document.getElementById("global-progress-wrap");
  const txtEl = document.getElementById("global-progress-text");
  const pctEl = document.getElementById("global-progress-pct");
  const fillEl = document.getElementById("global-progress-fill");
  const startTs = performance.now();

  if (wrap) wrap.style.display = "block";
  if (btn) btn.disabled = true;
  if (txtEl) txtEl.textContent = initialText;
  if (pctEl) pctEl.textContent = "5%";
  if (fillEl) fillEl.style.width = "5%";

  let stopped = false;
  const poll = async () => {
    while (!stopped) {
      const elapsed = ((performance.now() - startTs) / 1000).toFixed(1);
      try {
        const st = await fetch(`/api/projects/${pid}/progress`).then((r) => r.json());
        const pct = Math.max(5, Math.min(99, st.percent || 5));
        if (txtEl) txtEl.textContent = `${st.detail || initialText} (${elapsed}s)`;
        if (pctEl) pctEl.textContent = `${pct}%`;
        if (fillEl) fillEl.style.width = `${pct}%`;
      } catch {}
      await new Promise((r) => setTimeout(r, 320));
    }
  };
  const pollPromise = poll();

  try {
    const out = await workFn();
    stopped = true;
    await pollPromise;
    const totalSec = ((performance.now() - startTs) / 1000).toFixed(1);
    if (txtEl) txtEl.textContent = `${trText("Completado", "Completed", "Concluído")} (${totalSec}s)`;
    if (pctEl) pctEl.textContent = "100%";
    if (fillEl) fillEl.style.width = "100%";
    return out;
  } catch (err) {
    stopped = true;
    await pollPromise;
    if (txtEl) txtEl.textContent = `Error: ${err.message}`;
    if (pctEl) pctEl.textContent = "0%";
    if (fillEl) fillEl.style.width = "0%";
    throw err;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function getLocaleValue(loc, dottedKey) {
  let cur = loc;
  for (const part of dottedKey.split(".")) {
    if (cur && typeof cur === "object" && part in cur) {
      cur = cur[part];
    } else {
      return null;
    }
  }
  return typeof cur === "string" ? cur : null;
}

function setActiveProject(pid) {
  state.projectId = pid;
  const lbl = getLocaleValue(state.locale, "app.project_label") || "Project";
  const none = getLocaleValue(state.locale, "app.project_none") || "None";
  document.getElementById("active-project-pill").textContent = `${lbl}: ${pid || none}`;
}

async function loadLocaleAndUI(lang) {
  state.lang = lang;
  document.documentElement.lang = lang;
  const loc = await api(`/api/locales/${lang}`);
  state.locale = loc;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const val = getLocaleValue(loc, el.dataset.i18n);
    if (val !== null) el.textContent = val;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const val = getLocaleValue(loc, el.dataset.i18nPlaceholder);
    if (val !== null) el.placeholder = val;
  });

  setActiveProject(state.projectId);
  await loadTutorCurriculum(lang);
}

async function loadTutorCurriculum(lang) {
  const data = await api(`/api/tutor/curriculum?lang=${lang}`);
  const lBox = document.getElementById("lessons-container");
  lBox.innerHTML = "";
  for (const lesson of data.lessons) {
    const div = document.createElement("div");
    div.className = "lesson-card";
    div.innerHTML = `
      <h4>${lesson.title}</h4>
      <p class="muted">${lesson.summary}</p>
      <ul>${lesson.key_points.map((kp) => `<li>${kp}</li>`).join("")}</ul>
      <div class="formula-pill">${lesson.formula}</div>
    `;
    lBox.appendChild(div);
  }

  const qBox = document.getElementById("quiz-container");
  qBox.innerHTML = "";
  data.quizzes.forEach((qz, qi) => {
    const qDiv = document.createElement("div");
    qDiv.className = "quiz-item";
    qDiv.innerHTML = `<strong>Q${qi + 1}. ${qz.question}</strong>`;
    const exp = document.createElement("p");
    exp.className = "muted";
    exp.style.display = "none";
    exp.textContent = qz.explanation;
    qz.options.forEach((opt, oi) => {
      const btn = document.createElement("button");
      btn.className = "quiz-opt";
      btn.textContent = opt;
      btn.onclick = () => {
        btn.classList.add(oi === qz.answer_index ? "correct" : "wrong");
        exp.style.display = "block";
      };
      qDiv.appendChild(btn);
    });
    qDiv.appendChild(exp);
    qBox.appendChild(qDiv);
  });
}

function appendChat(role, text) {
  const log = document.getElementById("tutor-chat-log");
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function refreshProjects() {
  const data = await api("/api/projects");
  const sel = document.getElementById("project-select");
  sel.innerHTML = "";
  for (const p of data.projects) {
    const opt = document.createElement("option");
    opt.value = p.project_id;
    opt.textContent = `${p.name} (${p.project_id})`;
    sel.appendChild(opt);
  }
  if (!state.projectId && data.projects.length > 0) {
    setActiveProject(data.projects[0].project_id);
    sel.value = state.projectId;
  }
}

async function ensureProject(defaultName = "KhemSAR_Study") {
  if (state.projectId) return state.projectId;
  const name = document.getElementById("project-name-input").value || defaultName;
  const created = await api("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, target: document.getElementById("q-target").value || "" }),
  });
  setActiveProject(created.project_id);
  await refreshProjects();
  return created.project_id;
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${tabId}`));
}

function switchStep(stepNum) {
  document.querySelectorAll(".step-pill").forEach((b) => b.classList.toggle("active", b.dataset.step === String(stepNum)));
  document.querySelectorAll(".step-panel").forEach((p) => p.classList.toggle("active", p.id === `step-${stepNum}`));
}

function molImgTag(smiles, w = 180, h = 115) {
  return `<img class="mol-thumb" src="/api/molecule/svg?smiles=${encodeURIComponent(smiles)}&width=${w}&height=${h}" alt="2D structure" />`;
}

window.inspectAtomicMap = async function (smiles) {
  const pid = await ensureProject();
  document.getElementById("atomic-smiles-input").value = smiles;
  switchStep(4);
  try {
    const res = await api(`/api/projects/${pid}/sar/atomic-map`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles }),
    });
    document.getElementById("atomic-svg-container").innerHTML = res.svg;
  } catch (err) {
    document.getElementById("atomic-svg-container").textContent = err.message;
  }
};

window.inspectDeNovo3D = async function (smiles, cid) {
  const panel = document.getElementById("denovo-3d-panel");
  const meta = document.getElementById("denovo-3d-meta");
  const el = document.getElementById("denovo-viewer-3d");
  panel.style.display = "block";
  meta.textContent = `Generando confórmero 3D (pH 7.4 + ETKDGv3 + MMFF94) para ${cid}...`;
  try {
    const res = await api(`/api/molecule/3d-pdb?smiles=${encodeURIComponent(smiles)}`);
    meta.textContent = `${cid} | Force field: ${res.force_field} | Energy: ${res.energy_kcal_mol} kcal/mol | Formal charge (pH 7.4): ${res.formal_charge_ph74}`;
    if (window.$3Dmol && el) {
      el.innerHTML = "";
      const viewer = $3Dmol.createViewer(el, { backgroundColor: "#0b1220" });
      viewer.addModel(res.pdb_block, "pdb");
      viewer.setStyle({}, { stick: { colorscheme: "cyanCarbon", radius: 0.2 }, sphere: { scale: 0.25 } });
      viewer.zoomTo();
      viewer.render();
    }
  } catch (err) {
    meta.textContent = `Error 3D: ${err.message}`;
  }
};

function renderInteractiveQSARPlots(qsar) {
  if (!window.Plotly) return;
  if (qsar.task_type === "regression") {
    const tr = qsar.predictions.train;
    const te = qsar.predictions.test;
    const allVals = [
      ...tr.map((d) => d.y_true),
      ...tr.map((d) => d.y_cv_pred),
      ...te.map((d) => d.y_true),
      ...te.map((d) => d.y_pred),
    ];
    const lo = Math.min(...allVals) - 0.35;
    const hi = Math.max(...allVals) + 0.35;

    const traces = [
      {
        x: [lo, hi, hi, lo],
        y: [lo - 1.0, hi - 1.0, hi + 1.0, lo + 1.0],
        fill: "toself",
        fillcolor: "rgba(203, 213, 225, 0.35)",
        line: { width: 0 },
        name: "±1.0 log",
        type: "scatter",
        hoverinfo: "skip",
      },
      {
        x: [lo, hi],
        y: [lo, hi],
        mode: "lines",
        name: "Ideal (y = x)",
        line: { color: "#475569", dash: "dash", width: 1.5 },
      },
      {
        x: tr.map((d) => d.y_true),
        y: tr.map((d) => d.y_cv_pred),
        text: tr.map((d) => `${d.name} (${d.compound_id})`),
        mode: "markers",
        name: `Train CV (Q²=${qsar.best_metrics.Q2_CV})`,
        marker: { color: "#0072B2", size: 8, opacity: 0.8 },
      },
      {
        x: te.map((d) => d.y_true),
        y: te.map((d) => d.y_pred),
        text: te.map((d) => `${d.name} (${d.compound_id})`),
        mode: "markers",
        name: `Test Ext (R²=${qsar.best_metrics.R2_ext})`,
        marker: { color: "#D55E00", size: 10, symbol: "triangle-up" },
      },
    ];

    const lf = qsar.linear_fit || {};
    if (lf.train_cv) {
      traces.push({
        x: [lo, hi],
        y: [lf.train_cv.slope * lo + lf.train_cv.intercept, lf.train_cv.slope * hi + lf.train_cv.intercept],
        mode: "lines",
        name: `Train OLS: y=${lf.train_cv.slope}x+${lf.train_cv.intercept}`,
        line: { color: "#0072B2", width: 1.8 },
      });
    }
    if (lf.test_ext) {
      traces.push({
        x: [lo, hi],
        y: [lf.test_ext.slope * lo + lf.test_ext.intercept, lf.test_ext.slope * hi + lf.test_ext.intercept],
        mode: "lines",
        name: `Test OLS: y=${lf.test_ext.slope}x+${lf.test_ext.intercept}`,
        line: { color: "#D55E00", width: 2.2 },
      });
    }

    Plotly.newPlot(
      "plot-parity-interactive",
      traces,
      {
        title: { text: `Linear Regression (${qsar.best_algorithm}) | Q²=${qsar.best_metrics.Q2_CV}`, font: { size: 12.5 } },
        xaxis: { title: "Experimental pActivity", range: [lo, hi] },
        yaxis: { title: "Predicted pActivity", range: [lo, hi] },
        margin: { t: 44, l: 55, r: 16, b: 45 },
        legend: { font: { size: 9.5 } },
      },
      { responsive: true }
    );
  } else if (qsar.best_metrics && qsar.best_metrics.Confusion_Matrix) {
    const cm = qsar.best_metrics.Confusion_Matrix;
    Plotly.newPlot(
      "plot-parity-interactive",
      [
        {
          z: [[cm.TN, cm.FP], [cm.FN, cm.TP]],
          x: ["Pred Inactive (0)", "Pred Active (1)"],
          y: ["True Inactive (0)", "True Active (1)"],
          type: "heatmap",
          colorscale: "Blues",
          showscale: false,
          text: [[String(cm.TN), String(cm.FP)], [String(cm.FN), String(cm.TP)]],
          texttemplate: "%{text}",
        },
      ],
      {
        title: `Confusion Matrix (${qsar.best_algorithm}) | MCC=${qsar.best_metrics.MCC_ext}`,
        margin: { t: 44, l: 95, r: 20, b: 45 },
      },
      { responsive: true }
    );
  }

  const ad = qsar.applicability_domain;
  Plotly.newPlot(
    "plot-williams-interactive",
    [
      {
        x: ad.train_points.map((d) => d.leverage),
        y: ad.train_points.map((d) => d.std_residual),
        mode: "markers",
        name: "Train",
        marker: { color: "#0072B2", size: 8 },
      },
      {
        x: ad.test_points.map((d) => d.leverage),
        y: ad.test_points.map((d) => d.std_residual),
        mode: "markers",
        name: "Test",
        marker: { color: "#D55E00", size: 10, symbol: "triangle-up" },
      },
    ],
    {
      title: { text: `Williams Plot (h*=${ad.h_star}, AD=${ad.test_coverage_pct}%)`, font: { size: 12.5 } },
      xaxis: { title: "Leverage (h)" },
      yaxis: { title: "Standardized Residual (σ)" },
      shapes: [
        { type: "line", x0: ad.h_star, x1: ad.h_star, y0: -4, y1: 4, line: { dash: "dot", color: "#111" } },
        { type: "line", x0: 0, x1: Math.max(ad.h_star * 1.4, 1), y0: 3, y1: 3, line: { dash: "dash", color: "#b91c1c" } },
        { type: "line", x0: 0, x1: Math.max(ad.h_star * 1.4, 1), y0: -3, y1: -3, line: { dash: "dash", color: "#b91c1c" } },
      ],
      margin: { t: 44, l: 55, r: 16, b: 45 },
    },
    { responsive: true }
  );

  const ys = qsar.y_scrambling || {};
  const pts = ys.points || [];
  if (pts.length > 0) {
    Plotly.newPlot(
      "plot-yscrambling-interactive",
      [
        {
          x: pts.map((p) => p.y_corr),
          y: pts.map((p) => p.r2_scrambled),
          mode: "markers",
          name: "R² scrambled",
          marker: { color: "#64748b", size: 7, opacity: 0.7 },
        },
        {
          x: pts.map((p) => p.y_corr),
          y: pts.map((p) => p.q2_scrambled),
          mode: "markers",
          name: "Q² scrambled",
          marker: { color: "#CC79A7", size: 7, symbol: "square", opacity: 0.7 },
        },
        {
          x: [1.0],
          y: [ys.original_R2_or_MCC || 0],
          mode: "markers",
          name: `Original (cRp²=${ys.cRp2})`,
          marker: { color: "#009E73", size: 15, symbol: "star" },
        },
      ],
      {
        title: { text: `Y-Scrambling Validation (cRp² = ${ys.cRp2})`, font: { size: 12.5 } },
        xaxis: { title: "|r(Y, Y_scrambled)|" },
        yaxis: { title: "Model R² / Q²" },
        margin: { t: 44, l: 55, r: 16, b: 45 },
      },
      { responsive: true }
    );
  }
}

function render3DPDB(receptorPdb, ligandPdb) {
  const el = document.getElementById("pdb-viewer-3d");
  if (!window.$3Dmol || !el) return;
  el.innerHTML = "";
  const viewer = $3Dmol.createViewer(el, { backgroundColor: "#0b1220" });
  viewer.addModel(receptorPdb, "pdb");
  viewer.setStyle({ model: 0 }, { cartoon: { color: "spectrum", opacity: 0.85 } });
  if (ligandPdb) {
    viewer.addModel(ligandPdb, "pdb");
    viewer.setStyle({ model: 1 }, { stick: { colorscheme: "greenCarbon", radius: 0.25 } });
    viewer.zoomTo({ model: 1 });
  } else {
    viewer.zoomTo();
  }
  viewer.render();
}

window.addEventListener("DOMContentLoaded", async () => {
  const settings = await api("/api/settings");
  document.getElementById("lang-select").value = settings.language;
  document.getElementById("set-ai-provider").value = settings.ai.provider;
  document.getElementById("set-ai-model").value = settings.ai.model;
  document.getElementById("set-ollama-url").value = settings.ai.ollama_url;
  document.getElementById("set-plot-lang").value = settings.plot_language;
  document.getElementById("set-sync-dir").value = settings.cloud.custom_sync_dir || "";
  document.getElementById("cloud-folder-url").value = settings.cloud.cloud_folder_url || "";
  document.getElementById("gdrive-client-id").value = settings.cloud.gdrive_client_id || "";
  document.getElementById("dropbox-app-key").value = settings.cloud.dropbox_app_key || "";

  await loadLocaleAndUI(settings.language);
  await refreshProjects();

  document.querySelectorAll(".tab-btn").forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));
  document.querySelectorAll(".step-pill").forEach((b) => (b.onclick = () => switchStep(b.dataset.step)));

  document.getElementById("lang-select").onchange = async (e) => {
    const lang = e.target.value;
    await loadLocaleAndUI(lang);
    await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: lang, plot_language: document.getElementById("set-plot-lang").value }),
    });
  };

  document.getElementById("project-select").onchange = (e) => setActiveProject(e.target.value);

  document.getElementById("btn-new-project").onclick = async () => {
    state.projectId = null;
    await ensureProject();
  };

  const runDemo = async () => {
    state.projectId = null;
    const pid = await ensureProject("COX2_Demo");
    const res = await api(`/api/projects/${pid}/demo`, { method: "POST" });
    document.getElementById("search-summary-box").innerHTML =
      `<strong>Demo cargado (${res.bioactivities.length} registros):</strong> COX-2 / PTGS2 (ChEMBL + PubChem + BindingDB), PDB de referencia <code>3LN1</code>.`;
    switchTab("studio");
    switchStep(2);
  };
  document.getElementById("btn-load-demo").onclick = runDemo;
  document.getElementById("btn-quick-demo-from-tutor").onclick = runDemo;

  document.getElementById("csv-upload-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const pid = await ensureProject(file.name.replace(".csv", ""));
    const fd = new FormData();
    fd.append("file", file);
    const res = await api(`/api/projects/${pid}/upload-csv`, { method: "POST", body: fd });
    document.getElementById("search-summary-box").innerHTML = `CSV cargado: <strong>${res.bioactivities.length}</strong> filas.`;
    switchStep(2);
  };

  document.getElementById("btn-ai-parse").onclick = async () => {
    const desc = document.getElementById("research-intent-input").value;
    const parsed = await api("/api/ai/parse-intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc }),
    });
    document.getElementById("q-target").value = parsed.target_query || "PTGS2";
    if (parsed.pdb_id) {
      document.getElementById("q-pdb").value = parsed.pdb_id;
      document.getElementById("pdb-id-input").value = parsed.pdb_id;
    }
    if (parsed.chembl_target_id) document.getElementById("q-chembl").value = parsed.chembl_target_id;
    document.getElementById("search-summary-box").innerHTML = `<strong>Copiloto (${parsed.provider}):</strong> ${parsed.rationale}`;
  };

  document.getElementById("btn-run-search").onclick = async () => {
    const box = document.getElementById("search-summary-box");
    const targetVal = document.getElementById("q-target").value.trim();
    const chemblVal = document.getElementById("q-chembl").value.trim();
    const pdbVal = document.getElementById("q-pdb").value.trim();
    if (!targetVal && !chemblVal && !pdbVal) {
      box.textContent = "Ingresa una diana/gen, un ChEMBL ID o un PDB ID (ej. 2FOM) antes de buscar.";
      return;
    }
    const btn = document.getElementById("btn-run-search");
    box.textContent = trText("Consultando 10 bases científicas en paralelo...", "Querying 10 scientific databases in parallel...", "Consultando 10 bases científicas em paralelo...");
    try {
      const pid = await ensureProject(targetVal || pdbVal || chemblVal || "Study");
      const res = await runWithProgress(pid, btn, box.textContent, () =>
        api(`/api/projects/${pid}/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_query: targetVal,
            chembl_target_id: chemblVal || null,
            pdb_id: pdbVal || null,
            max_records: Number(document.getElementById("q-limit").value || 1500),
          }),
        })
      );
      const rt = res.resolved_target || {};
      if (!targetVal && res.query) {
        document.getElementById("q-target").value = res.query;
      }
      if (!chemblVal && rt.chembl_target_id) {
        document.getElementById("q-chembl").value = rt.chembl_target_id;
      }
      const statusHtml = res.source_status.map((s) => `<li><strong>${s.source}:</strong> ${s.count} registros (${s.ok ? "OK" : s.error})</li>`).join("");
      const pdbs = (res.pdb_structures || []).slice(0, 5).map((p) => `<code>${p.pdb_id}</code> (${p.resolution_angstrom || "?"} Å)`).join(", ");
      box.innerHTML = `<p><strong>Diana resuelta:</strong> ${res.query || "N/A"} ${rt.uniprot_id ? `(UniProt: <code>${rt.uniprot_id}</code>)` : ""} ${rt.chembl_target_id ? `(ChEMBL: <code>${rt.chembl_target_id}</code>)` : ""}</p><p><strong>Total bioactividades recuperadas:</strong> ${res.bioactivities.length}</p><ul>${statusHtml}</ul><p><strong>Estructuras PDB sugeridas:</strong> ${pdbs || "N/A"}</p>`;
      if (pdbVal) {
        document.getElementById("pdb-id-input").value = pdbVal.toUpperCase();
      } else if (res.pdb_structures && res.pdb_structures.length > 0) {
        document.getElementById("pdb-id-input").value = res.pdb_structures[0].pdb_id;
      }
    } catch (err) {
      box.textContent = `Error en búsqueda: ${err.message}`;
    }
  };

  document.getElementById("btn-fetch-pdb").onclick = async () => {
    const box = document.getElementById("pdb-box-info");
    box.textContent = "Descargando y preparando receptor PDB...";
    try {
      const pid = await ensureProject();
      const res = await api(`/api/projects/${pid}/pdb/prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pdb_id: document.getElementById("pdb-id-input").value,
          chain_id: document.getElementById("pdb-chain-input").value || null,
        }),
      });
      render3DPDB(res.receptor_pdb, res.cocrystal_ligand_pdb);
      box.innerHTML = trText(
        `<strong>Receptor limpio:</strong> ${res.protein_atom_count} átomos.<br/><strong>Caja Docking sugerida:</strong> <code>${JSON.stringify(res.docking_box)}</code>`,
        `<strong>Cleaned receptor:</strong> ${res.protein_atom_count} atoms.<br/><strong>Suggested Docking Box:</strong> <code>${JSON.stringify(res.docking_box)}</code>`,
        `<strong>Receptor limpo:</strong> ${res.protein_atom_count} átomos.<br/><strong>Caixa Docking sugerida:</strong> <code>${JSON.stringify(res.docking_box)}</code>`
      );
    } catch (err) {
      box.textContent = `Error PDB: ${err.message}`;
    }
  };

  document.getElementById("btn-run-curate").onclick = async () => {
    const box = document.getElementById("curation-report-box");
    const btn = document.getElementById("btn-run-curate");
    try {
      const pid = await ensureProject();
      const res = await runWithProgress(
        pid,
        btn,
        trText("Estandarizando y curando moléculas...", "Standardizing & curating molecules...", "Padronizando e curando moléculas..."),
        () =>
          api(`/api/projects/${pid}/curate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              target_endpoint: document.getElementById("curate-endpoint").value,
              task_type: document.getElementById("curate-task").value,
              activity_cutoff_pAct: Number(document.getElementById("curate-cutoff").value),
              max_duplicate_spread: Number(document.getElementById("curate-spread").value),
            }),
          })
      );
      const r = res.report;
      box.innerHTML = trText(
        `<strong>Endpoint usado:</strong> ${res.endpoint_used} | <strong>Crudos:</strong> ${r.raw_count} → <strong>Curados finales:</strong> ${r.final_count}<br/>Duplicados fusionados: ${r.merged_duplicates} | Discordantes excluidos: ${r.excluded_discordant_duplicates} | Inválidos/mezclas/sales: ${r.excluded_invalid_or_inorganic_or_mixture}`,
        `<strong>Endpoint used:</strong> ${res.endpoint_used} | <strong>Raw:</strong> ${r.raw_count} → <strong>Final curated:</strong> ${r.final_count}<br/>Merged duplicates: ${r.merged_duplicates} | Discordant excluded: ${r.excluded_discordant_duplicates} | Invalid/mixtures/salts: ${r.excluded_invalid_or_inorganic_or_mixture}`,
        `<strong>Endpoint usado:</strong> ${res.endpoint_used} | <strong>Brutos:</strong> ${r.raw_count} → <strong>Curados finais:</strong> ${r.final_count}<br/>Duplicatas mescladas: ${r.merged_duplicates} | Discordantes excluídos: ${r.excluded_discordant_duplicates} | Inválidos/misturas/sais: ${r.excluded_invalid_or_inorganic_or_mixture}`
      );

      const recs = res.curated_records || [];
      const gal = document.getElementById("curated-2d-gallery");
      if (recs.length > 0) {
        const cards = recs.slice(0, 60).map((m) => `
          <div class="mol-card">
            ${molImgTag(m.smiles, 210, 130)}
            <strong>${m.name || m.compound_id}</strong>
            <div><code>${m.compound_id}</code> · pAct = <strong>${m.pActivity}</strong></div>
            <div class="muted">${m.standard_type} · n=${m.n_replicates || 1}</div>
          </div>
        `).join("");
        gal.innerHTML = `<p>${trText(
          `Mostrando ${Math.min(60, recs.length)} de ${recs.length} estructuras curadas:`,
          `Showing ${Math.min(60, recs.length)} of ${recs.length} curated structures:`,
          `Exibindo ${Math.min(60, recs.length)} de ${recs.length} estruturas curadas:`
        )}</p><div class="mol-grid">${cards}</div>`;
      } else {
        gal.innerHTML = "";
      }
    } catch (err) {
      box.textContent = `Error: ${err.message}`;
    }
  };

  document.getElementById("btn-train-qsar").onclick = async () => {
    const box = document.getElementById("qsar-metrics-box");
    const btn = document.getElementById("btn-train-qsar");
    box.textContent = trText(
      "Entrenando y validando modelos QSAR (Nested CV + Y-Scrambling + Williams AD)...",
      "Training and validating QSAR models (Nested CV + Y-Scrambling + Williams AD)...",
      "Treinando e validando modelos QSAR (Nested CV + Y-Scrambling + Williams AD)..."
    );
    try {
      const pid = await ensureProject();
      const res = await runWithProgress(pid, btn, box.textContent, () =>
        api(`/api/projects/${pid}/qsar/train`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_type: document.getElementById("curate-task").value,
            feature_mode: document.getElementById("qsar-features").value,
            split_method: document.getElementById("qsar-split").value,
            test_size: Number(document.getElementById("qsar-testsize").value),
            y_scrambling_permutations: Number(document.getElementById("qsar-yscram").value),
          }),
        })
      );
      state.lastQSAR = res;
      const rows = res.leaderboard
        .map((m) => `<tr><td>${m.algorithm}</td><td><code>${JSON.stringify(m.metrics)}</code></td></tr>`)
        .join("");
      box.innerHTML = `<p><strong>${trText("Mejor Modelo", "Best Model", "Melhor Modelo")}:</strong> ${res.best_algorithm} | <strong>Split:</strong> ${res.split_method_used} (Train=${res.n_train}, Test=${res.n_test}) | <strong>Y-Scrambling cRp²:</strong> ${res.y_scrambling.cRp2}</p><table class="data-table"><thead><tr><th>${trText("Algoritmo", "Algorithm", "Algoritmo")}</th><th>${trText("Métricas OCDE", "OECD Metrics", "Métricas OCDE")}</th></tr></thead><tbody>${rows}</tbody></table>`;
      renderInteractiveQSARPlots(res);

      // Render 2D structures of Train and External Test molecules
      const adTrainMap = Object.fromEntries((res.applicability_domain.train_points || []).map((p) => [p.smiles, p]));
      const adTestMap = Object.fromEntries((res.applicability_domain.test_points || []).map((p) => [p.smiles, p]));
      const mapBtnLbl = trText("Mapear Átomos", "Map Atoms", "Mapear Átomos");
      const molRows = [
        ...(res.predictions.test || []).map((m) => ({ ...m, split: "Test (Ext)", ad: adTestMap[m.smiles] })),
        ...(res.predictions.train || []).map((m) => ({ ...m, split: "Train (CV)", y_pred: m.y_cv_pred, ad: adTrainMap[m.smiles] })),
      ]
        .slice(0, 60)
        .map((m) => {
          const inAd = m.ad ? m.ad.in_ad : true;
          const escSmi = m.smiles.replace(/'/g, "\\'");
          return `<tr>
            <td>${molImgTag(m.smiles, 165, 105)}</td>
            <td><strong>${m.name || m.compound_id}</strong><br/><code>${m.compound_id}</code></td>
            <td><span class="${m.split.startsWith("Test") ? "badge-warn" : "badge-ok"}">${m.split}</span></td>
            <td>${m.y_true}</td>
            <td><strong>${m.y_pred}</strong></td>
            <td>${inAd ? '<span class="badge-ok">IN AD</span>' : '<span class="badge-warn">OUT AD</span>'}</td>
            <td><button class="btn secondary" onclick="inspectAtomicMap('${escSmi}')">${mapBtnLbl}</button></td>
          </tr>`;
        })
        .join("");
      document.getElementById("qsar-molecules-2d-box").innerHTML = `<div class="table-scroll"><table class="data-table"><thead><tr><th>2D</th><th>${trText("Compuesto", "Compound", "Composto")}</th><th>Split</th><th>Exp.</th><th>Pred.</th><th>AD</th><th>SAR 2D</th></tr></thead><tbody>${molRows}</tbody></table></div>`;

      if (res.predictions.test.length > 0) {
        document.getElementById("atomic-smiles-input").value = res.predictions.test[0].smiles;
      }
    } catch (err) {
      box.textContent = `Error QSAR: ${err.message}`;
    }
  };

  document.getElementById("btn-run-sar").onclick = async () => {
    const box = document.getElementById("sar-tables-box");
    const btn = document.getElementById("btn-run-sar");
    box.textContent = trText(
      "Calculando Activity Cliffs (SALI), MMP, R-Groups y SHAP...",
      "Computing Activity Cliffs (SALI), MMP, R-Groups & SHAP...",
      "Calculando Activity Cliffs (SALI), MMP, R-Groups e SHAP..."
    );
    try {
      const pid = await ensureProject();
      const res = await runWithProgress(pid, btn, box.textContent, () =>
        api(`/api/projects/${pid}/sar/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            similarity_cutoff: Number(document.getElementById("sar-sim").value),
            delta_p_cutoff: Number(document.getElementById("sar-dp").value),
            projection_method: document.getElementById("sar-proj").value,
            core_smarts: document.getElementById("sar-core").value || null,
          }),
        })
      );
      state.lastSAR = res;
      if (window.Plotly && res.activity_cliffs.space_points.length > 0) {
        const sp = res.activity_cliffs.space_points;
        Plotly.newPlot(
          "plot-space-interactive",
          [
            {
              x: sp.map((p) => p.x),
              y: sp.map((p) => p.y),
              text: sp.map((p) => `${p.name} (pAct=${p.pActivity})`),
              mode: "markers",
              marker: { size: 10, color: sp.map((p) => p.pActivity), colorscale: "Viridis", showscale: true },
            },
          ],
          { title: `Chemical Space (${res.activity_cliffs.projection_used.toUpperCase()})` },
          { responsive: true }
        );
      }
      const cliffsHtml = (res.activity_cliffs.cliffs || []).slice(0, 6).map((c) => `
        <tr>
          <td>
            <div class="cliff-pair">
              <div>${molImgTag(c.mol1_smiles, 140, 95)}<br/><small>${c.mol1_name} (${c.mol1_pActivity})</small></div>
              <strong>⇄</strong>
              <div>${molImgTag(c.mol2_smiles, 140, 95)}<br/><small>${c.mol2_name} (${c.mol2_pActivity})</small></div>
            </div>
          </td>
          <td>${c.tanimoto}</td>
          <td>${c.delta_pActivity}</td>
          <td><strong>${c.SALI}</strong></td>
        </tr>`).join("");
      const mmpHtml = (res.mmp.transforms || []).slice(0, 6).map((m) => `<tr><td><code>${m.transform}</code></td><td>${m.n_pairs}</td><td>${m.mean_delta_pActivity}</td></tr>`).join("");
      const shapHtml = (res.shap.top_features || []).slice(0, 8).map((f) => `<li><code>${f.feature}</code>: ${f.mean_abs_shap} (dir=${f.direction_corr})</li>`).join("");
      const rgroupCore = res.rgroup && res.rgroup.core_smiles ? `<div><strong>${trText("Core R-Group detectado", "Detected R-Group Core", "Core R-Group detectado")}:</strong> ${molImgTag(res.rgroup.core_smiles, 180, 110)} (${res.rgroup.matched_count || 0})</div>` : "";
      box.innerHTML = `<div><h4>${trText("Top Activity Cliffs (SALI) con Estructuras 2D", "Top Activity Cliffs (SALI) — 2D Pairs", "Top Activity Cliffs (SALI) em 2D")}</h4><table class="data-table"><thead><tr><th>${trText("Par Molecular 2D", "2D Molecular Pair", "Par Molecular 2D")}</th><th>Tanimoto</th><th>ΔpAct</th><th>SALI</th></tr></thead><tbody>${cliffsHtml}</tbody></table></div><div class="grid-2 mt-16"><div><h4>Top Matched Molecular Pairs (MMP)</h4><table class="data-table"><thead><tr><th>${trText("Transformación", "Transform", "Transformação")}</th><th>${trText("Pares", "Pairs", "Pares")}</th><th>${trText("Media ΔpAct", "Mean ΔpAct", "Média ΔpAct")}</th></tr></thead><tbody>${mmpHtml}</tbody></table></div><div><h4>${trText("Top Descriptores SHAP", "Top SHAP Descriptors", "Top Descritores SHAP")} (${res.shap.method})</h4><ul>${shapHtml}</ul>${rgroupCore}</div></div>`;
    } catch (err) {
      box.textContent = `Error SAR: ${err.message}`;
    }
  };

  document.getElementById("btn-atomic-map").onclick = async () => {
    const pid = await ensureProject();
    const smi = document.getElementById("atomic-smiles-input").value;
    const res = await api(`/api/projects/${pid}/sar/atomic-map`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles: smi }),
    });
    document.getElementById("atomic-svg-container").innerHTML = res.svg;
  };

  document.getElementById("btn-gen-paper-plots").onclick = async () => {
    const pid = await ensureProject();
    const res = await api(`/api/projects/${pid}/plots/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dpi: 300 }),
    });
    const links = Object.entries(res.figures)
      .map(([name, fmts]) => `<li><strong>${name}:</strong> ${Object.entries(fmts).map(([ext, fn]) => `<a href="/api/projects/${pid}/plots/file/${fn}" target="_blank">${ext.toUpperCase()}</a>`).join(" | ")}</li>`)
      .join("");
    document.getElementById("paper-plots-links").innerHTML = `<strong>${trText("Figuras Paper-Ready exportadas", "Paper-Ready Figures Exported", "Figuras Paper-Ready exportadas")} (${res.plot_lang.toUpperCase()}, ${res.dpi} DPI):</strong><ul>${links}</ul>`;
    const previews = Object.entries(res.figures)
      .filter(([, fmts]) => fmts.svg)
      .map(([name, fmts]) => `<div class="paper-preview-card"><strong>${name}</strong><img src="/api/projects/${pid}/plots/file/${fmts.svg}?t=${Date.now()}" alt="${name}" /></div>`)
      .join("");
    document.getElementById("paper-plots-preview").innerHTML = previews;
  };

  document.getElementById("btn-gen-denovo").onclick = async () => {
    const box = document.getElementById("denovo-table-box");
    const btn = document.getElementById("btn-gen-denovo");
    box.textContent = trText(
      "Generando reemplazos bioisostéricos y recombinaciones BRICS...",
      "Generating bioisosteric replacements and BRICS recombinations...",
      "Gerando substituições bioisostéricas e recombinações BRICS..."
    );
    try {
      const pid = await ensureProject();
      const res = await runWithProgress(pid, btn, box.textContent, () =>
        api(`/api/projects/${pid}/denovo/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            n_top_seeds: Number(document.getElementById("dn-seeds").value),
            n_brics_samples: Number(document.getElementById("dn-brics").value),
            max_candidates: Number(document.getElementById("dn-max").value),
          }),
        })
      );
      state.lastDeNovo = res;
      const rows = res.candidates
        .map((c) => {
          const escSmi = c.smiles.replace(/'/g, "\\'");
          return `<tr>
            <td>${c.rank}</td>
            <td>${molImgTag(c.smiles, 175, 110)}</td>
            <td><strong>${c.candidate_id}</strong><br/><small>${c.origin}</small><br/><code style="font-size:0.72rem">${c.smiles}</code></td>
            <td><strong>${c.bioisostere_rule}</strong><br/><small class="muted">${c.rationale || ""}</small></td>
            <td><strong>${c.predicted_pActivity ?? c.predicted_active_prob}</strong></td>
            <td>${c.in_ad ? '<span class="badge-ok">IN AD</span>' : '<span class="badge-warn">OUT AD</span>'}</td>
            <td>${c.QED}</td>
            <td>${c.SA_Score}</td>
            <td><strong>${c.MPO_score}</strong></td>
            <td>
              <button class="btn secondary" onclick="inspectDeNovo3D('${escSmi}','${c.candidate_id}')">3D</button>
              <button class="btn secondary" style="margin-top:4px" onclick="inspectAtomicMap('${escSmi}')">SAR</button>
            </td>
          </tr>`;
        })
        .join("");
      box.innerHTML = `<p>${trText(
        `Evaluados ${res.n_evaluated} → Top <strong>${res.n_generated}</strong> candidatos:`,
        `Evaluated ${res.n_evaluated} → Top <strong>${res.n_generated}</strong> candidates:`,
        `Avaliados ${res.n_evaluated} → Top <strong>${res.n_generated}</strong> candidatos:`
      )}</p><div class="table-scroll"><table class="data-table"><thead><tr><th>#</th><th>${trText("Estructura 2D", "2D Structure", "Estrutura 2D")}</th><th>ID / SMILES</th><th>${trText("Regla Bioisostérica / Origen", "Bioisostere Rule / Origin", "Regra Bioisostérica / Origem")}</th><th>Pred.</th><th>AD</th><th>QED</th><th>SA</th><th>MPO</th><th>${trText("Inspección", "Inspect", "Inspeção")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    } catch (err) {
      box.textContent = `Error De Novo: ${err.message}`;
    }
  };

  document.getElementById("btn-export-3d").onclick = async () => {
    const box = document.getElementById("export3d-result-box");
    const btn = document.getElementById("btn-export-3d");
    box.textContent = trText(
      "Protonando a pH 7.4, generando confórmeros 3D ETKDGv3 y minimizando energía...",
      "Protonating at pH 7.4, generating 3D ETKDGv3 conformers & minimizing energy...",
      "Protonando em pH 7.4, gerando confôrmeros 3D ETKDGv3 e minimizando energia..."
    );
    try {
      const pid = await ensureProject();
      const res = await runWithProgress(pid, btn, box.textContent, () =>
        api(`/api/projects/${pid}/export-3d`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            protonate_ph74: document.getElementById("exp-ph74").value === "true",
            force_field: document.getElementById("exp-ff").value,
            max_molecules: Number(document.getElementById("exp-max").value),
          }),
        })
      );
      box.innerHTML = `<p><strong>Confórmeros 3D generados:</strong> ${res.n_3d_embedded} / ${res.n_total}</p>
        <div class="row-actions">
          <a class="btn primary" href="/api/projects/${pid}/download/${res.download_zip}">Descargar Paquete Completo Docking/MD (.ZIP)</a>
          <a class="btn secondary" href="/api/projects/${pid}/download/${res.download_sdf}">Descargar Ligandos 3D (.SDF)</a>
          <a class="btn secondary" href="/api/projects/${pid}/download/${res.download_xlsx}">Descargar Tabla (.XLSX)</a>
        </div>`;
    } catch (err) {
      box.textContent = `Error 3D: ${err.message}`;
    }
  };

  document.getElementById("btn-ask-tutor").onclick = async () => {
    const q = document.getElementById("tutor-question").value.trim();
    if (!q) return;
    appendChat("user", q);
    document.getElementById("tutor-question").value = "";
    const res = await api("/api/tutor/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, lang: state.lang, project_id: state.projectId }),
    });
    appendChat("bot", `[${res.provider}]\n${res.answer}`);
  };

  document.getElementById("btn-interpret-study").onclick = async () => {
    const promptQ = trText(
      "Interpreta científicamente mi estudio activo.",
      "Scientifically interpret my active study.",
      "Interprete cientificamente o meu estudo ativo."
    );
    appendChat("user", promptQ);
    const res = await api("/api/tutor/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: promptQ, lang: state.lang, project_id: state.projectId }),
    });
    appendChat("bot", `[${res.provider}]\n${res.answer}`);
  };

  document.getElementById("btn-detect-cloud").onclick = async () => {
    const res = await api("/api/cloud/detect");
    document.getElementById("cloud-folders-box").innerHTML = res.folders
      .map((f) => `<div><strong>${f.label}:</strong> ${f.detected_path || "No detectada localmente (puedes instalar la app de escritorio o subir el .qsarproj.zip)"}</div>`)
      .join("");
  };

  const syncCloudFn = async () => {
    const pid = await ensureProject();
    const res = await api("/api/cloud/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: pid, target_folder: document.getElementById("set-sync-dir").value || null }),
    });
    const targetBox = document.getElementById("cloud-folders-box");
    targetBox.innerHTML = `<p>Paquete portátil creado: <code>${res.bundle_path}</code>${res.synced_path ? `<br/>Sincronizado en: <code>${res.synced_path}</code>` : ""}</p><a class="btn primary" href="/api/projects/${pid}/bundle">Descargar .qsarproj.zip</a>`;
  };
  document.getElementById("btn-cloud-backup-btn").onclick = syncCloudFn;
  document.getElementById("btn-sync-cloud-now").onclick = syncCloudFn;

  document.getElementById("btn-save-open-cloud").onclick = async () => {
    const folderUrl = document.getElementById("cloud-folder-url").value.trim();
    await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: document.getElementById("lang-select").value,
        plot_language: document.getElementById("set-plot-lang").value,
        cloud: { cloud_folder_url: folderUrl },
      }),
    });
    const pid = await ensureProject();
    const res = await api("/api/cloud/reveal-bundle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: pid, open_local: true }),
    });
    document.getElementById("cloud-link-box").innerHTML = `<p><strong>.qsarproj.zip:</strong> <code>${res.bundle_path}</code></p><div class="row-actions"><a class="btn primary" href="${res.download_url}">Descargar ${res.bundle_name}</a>${folderUrl ? `<a class="btn accent" href="${folderUrl}" target="_blank" rel="noopener">Abrir Carpeta en la Nube</a>` : ""}</div>`;
    if (folderUrl) {
      window.open(folderUrl, "_blank", "noopener");
    }
  };

  document.getElementById("btn-import-gdrive-csv").onclick = async () => {
    const box = document.getElementById("gdrive-csv-status");
    const url = document.getElementById("gdrive-csv-url").value.trim();
    if (!url) return;
    box.textContent = "Descargando CSV desde Google Drive...";
    try {
      const pid = await ensureProject("GDrive_Dataset");
      const res = await api(`/api/projects/${pid}/import-gdrive-csv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ drive_url: url }),
      });
      box.innerHTML = `CSV importado desde Google Drive: <strong>${res.bioactivities.length}</strong> filas listas en el Estudio QSAR/SAR.`;
    } catch (err) {
      box.textContent = `Error: ${err.message}`;
    }
  };

  const downloadColabFn = async () => {
    const pid = await ensureProject();
    window.open(`/api/projects/${pid}/colab-notebook`, "_blank");
  };
  document.getElementById("btn-download-colab").onclick = downloadColabFn;
  document.getElementById("btn-cloud-colab-btn").onclick = downloadColabFn;

  document.getElementById("btn-gdrive-oauth").onclick = async () => {
    const cid = document.getElementById("gdrive-client-id").value;
    if (!cid) return alert("Ingresa un Client ID de Google Cloud OAuth.");
    const res = await api("/api/cloud/oauth-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "gdrive",
        client_id: cid,
        redirect_uri: `${window.location.origin}/api/cloud/oauth-callback`,
      }),
    });
    document.getElementById("gdrive-oauth-box").innerHTML = `<a href="${res.auth_url}" target="_blank">Abrir autorización Google Drive (Gmail)</a>`;
  };

  document.getElementById("btn-dropbox-oauth").onclick = async () => {
    const cid = document.getElementById("dropbox-app-key").value;
    if (!cid) return alert("Ingresa tu App Key de Dropbox.");
    const res = await api("/api/cloud/oauth-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "dropbox",
        client_id: cid,
        redirect_uri: `${window.location.origin}/api/cloud/oauth-callback`,
      }),
    });
    document.getElementById("dropbox-oauth-box").innerHTML = `<a href="${res.auth_url}" target="_blank">Abrir autorización Dropbox</a>`;
  };

  document.getElementById("btn-save-settings").onclick = async () => {
    const res = await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: document.getElementById("lang-select").value,
        plot_language: document.getElementById("set-plot-lang").value,
        ai: {
          provider: document.getElementById("set-ai-provider").value,
          model: document.getElementById("set-ai-model").value,
          ollama_url: document.getElementById("set-ollama-url").value,
          api_key: document.getElementById("set-ai-key").value || "***",
        },
        cloud: {
          custom_sync_dir: document.getElementById("set-sync-dir").value,
          cloud_folder_url: document.getElementById("cloud-folder-url").value,
          gdrive_client_id: document.getElementById("gdrive-client-id").value,
          dropbox_app_key: document.getElementById("dropbox-app-key").value,
        },
      }),
    });
    document.getElementById("settings-status-box").textContent = `Configuración guardada localmente en ${res.saved_to}`;
  };

  document.getElementById("btn-check-ollama").onclick = async () => {
    const res = await api("/api/ai/ollama-models");
    document.getElementById("settings-status-box").textContent =
      res.models.length > 0 ? `Modelos Ollama detectados: ${res.models.join(", ")}` : "No se detectó Ollama ejecutándose en localhost:11434.";
  };
});

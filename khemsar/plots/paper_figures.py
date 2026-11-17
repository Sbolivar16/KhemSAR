"""Paper-ready QSAR, SAR, Applicability Domain, SHAP, and De Novo figures (SVG / PDF / PNG 300-600 DPI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Okabe-Ito colorblind-safe scientific palette
OKABE_BLUE = "#0072B2"
OKABE_ORANGE = "#D55E00"
OKABE_GREEN = "#009E73"
OKABE_PURPLE = "#CC79A7"
OKABE_GREY = "#595959"

PLOT_TEXT = {
    "en": {
        "exp": "Experimental pActivity",
        "pred": "Predicted pActivity",
        "train": "Training Set",
        "test": "External Test Set",
        "parity_title": "QSAR Predictive Performance",
        "williams_title": "Applicability Domain — Williams Plot",
        "leverage": "Leverage (h)",
        "std_res": "Standardized Residual (σ)",
        "yscram_title": "Y-Scrambling Robustness Validation",
        "y_corr": "|r(Y, Y_scrambled)|",
        "r2_q2": "Model R² / Q²",
        "space_title": "Chemical Space & Activity Cliffs (SALI)",
        "shap_title": "Feature Importance (SHAP)",
        "shap_x": "Mean |SHAP value|",
        "denovo_title": "De Novo & Bioisosteric Candidates vs. Known Actives",
        "sa_score": "Synthetic Accessibility (SA Score)",
    },
    "es": {
        "exp": "pActividad Experimental",
        "pred": "pActividad Predicha",
        "train": "Entrenamiento",
        "test": "Prueba Externa",
        "parity_title": "Desempeño Predictivo QSAR",
        "williams_title": "Dominio de Aplicabilidad — Williams Plot",
        "leverage": "Apalancamiento / Leverage (h)",
        "std_res": "Residuo Estandarizado (σ)",
        "yscram_title": "Validación de Robustez Y-Scrambling",
        "y_corr": "|r(Y, Y_permutada)|",
        "r2_q2": "R² / Q² del Modelo",
        "space_title": "Espacio Químico y Activity Cliffs (SALI)",
        "shap_title": "Importancia de Descriptores (SHAP)",
        "shap_x": "Media |valor SHAP|",
        "denovo_title": "Candidatos De Novo y Bioisósteros vs. Activos",
        "sa_score": "Accesibilidad Sintética (SA Score)",
    },
    "pt": {
        "exp": "pAtividade Experimental",
        "pred": "pAtividade Predita",
        "train": "Treinamento",
        "test": "Teste Externo",
        "parity_title": "Desempenho Preditivo QSAR",
        "williams_title": "Domínio de Aplicabilidade — Williams Plot",
        "leverage": "Alavancagem / Leverage (h)",
        "std_res": "Resíduo Padronizado (σ)",
        "yscram_title": "Validação de Robustez Y-Scrambling",
        "y_corr": "|r(Y, Y_permutado)|",
        "r2_q2": "R² / Q² do Modelo",
        "space_title": "Espaço Químico e Activity Cliffs (SALI)",
        "shap_title": "Importância de Descritores (SHAP)",
        "shap_x": "Média |valor SHAP|",
        "denovo_title": "Candidatos De Novo e Bioisósteros vs. Ativos",
        "sa_score": "Acessibilidade Sintética (SA Score)",
    },
}


def _configure_pub_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": True,
            "legend.framealpha": 0.92,
            "savefig.bbox": "tight",
        }
    )


def _save_multi_format(fig: plt.Figure, out_dir: Path, stem: str, dpi: int = 300) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for ext in ("svg", "pdf", "png"):
        p = out_dir / f"{stem}.{ext}"
        fig.savefig(p, format=ext, dpi=dpi if ext == "png" else None)
        paths[ext] = str(p)
    plt.close(fig)
    return paths


def generate_all_paper_figures(
    output_dir: Path | str,
    qsar_result: dict[str, Any] | None = None,
    sar_result: dict[str, Any] | None = None,
    shap_result: dict[str, Any] | None = None,
    denovo_result: dict[str, Any] | None = None,
    plot_lang: str = "en",
    dpi: int = 300,
) -> dict[str, dict[str, str]]:
    """Generate all applicable paper-ready figures in SVG, PDF, and high-DPI PNG."""
    _configure_pub_style()
    out_dir = Path(output_dir).expanduser().resolve()
    lbl = PLOT_TEXT.get(plot_lang, PLOT_TEXT["en"])
    saved: dict[str, dict[str, str]] = {}

    if qsar_result:
        # 1. Parity Plot (Regression) or Confusion/Score plot (Classification)
        preds = qsar_result.get("predictions", {})
        tr = preds.get("train", [])
        te = preds.get("test", [])
        metrics = qsar_result.get("best_metrics", {})
        if qsar_result.get("task_type") == "regression" and tr and te:
            fig, ax = plt.subplots(figsize=(5.8, 5.4))
            tr_x = np.asarray([p["y_true"] for p in tr], dtype=float)
            tr_y = np.asarray([p["y_cv_pred"] for p in tr], dtype=float)
            te_x = np.asarray([p["y_true"] for p in te], dtype=float)
            te_y = np.asarray([p["y_pred"] for p in te], dtype=float)
            all_vals = np.concatenate([tr_x, tr_y, te_x, te_y])
            lo, hi = float(np.min(all_vals)) - 0.35, float(np.max(all_vals)) + 0.35
            x_grid = np.linspace(lo, hi, 100)
            ax.plot([lo, hi], [lo, hi], "--", color=OKABE_GREY, lw=1.2, label="Ideal (y = x)")
            ax.fill_between([lo, hi], [lo - 1.0, hi - 1.0], [lo + 1.0, hi + 1.0], color="#E5E7EB", alpha=0.45, label="±1.0 log")
            ax.scatter(tr_x, tr_y, c=OKABE_BLUE, alpha=0.75, s=42, edgecolors="white", lw=0.5, label=f"{lbl['train']} (Q²_CV={metrics.get('Q2_CV', '')})")
            ax.scatter(te_x, te_y, c=OKABE_ORANGE, marker="^", alpha=0.92, s=58, edgecolors="white", lw=0.6, label=f"{lbl['test']} (R²_ext={metrics.get('R2_ext', '')})")

            if len(tr_x) >= 2 and np.std(tr_x) > 1e-8:
                m_tr, b_tr = np.polyfit(tr_x, tr_y, 1)
                ax.plot(x_grid, m_tr * x_grid + b_tr, "-", color=OKABE_BLUE, lw=1.5, alpha=0.85, label=f"Train fit: y={m_tr:.2f}x+{b_tr:.2f}")
            if len(te_x) >= 2 and np.std(te_x) > 1e-8:
                m_te, b_te = np.polyfit(te_x, te_y, 1)
                ax.plot(x_grid, m_te * x_grid + b_te, "-", color=OKABE_ORANGE, lw=1.8, label=f"Test fit: y={m_te:.2f}x+{b_te:.2f}")

            stats_txt = (
                f"R²_train = {metrics.get('R2_train', '')}\n"
                f"Q²_CV = {metrics.get('Q2_CV', '')}\n"
                f"R²_ext = {metrics.get('R2_ext', '')}\n"
                f"CCC_ext = {metrics.get('CCC_ext', '')}\n"
                f"RMSE_ext = {metrics.get('RMSE_ext', '')}"
            )
            ax.text(
                0.97,
                0.04,
                stats_txt,
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=8.2,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#CBD5E1", alpha=0.92),
            )
            ax.set_xlim(lo, hi)
            ax.set_ylim(lo, hi)
            ax.set_xlabel(lbl["exp"])
            ax.set_ylabel(lbl["pred"])
            ax.set_title(f"{lbl['parity_title']} ({qsar_result.get('best_algorithm', '')})")
            ax.legend(loc="upper left", fontsize=7.8)
            saved["qsar_parity"] = _save_multi_format(fig, out_dir, "fig1_qsar_parity", dpi=dpi)
        elif qsar_result.get("task_type") == "classification" and metrics.get("Confusion_Matrix"):
            cm = metrics["Confusion_Matrix"]
            mat = np.array([[cm["TN"], cm["FP"]], [cm["FN"], cm["TP"]]])
            fig, ax = plt.subplots(figsize=(4.8, 4.4))
            ax.imshow(mat, cmap="Blues")
            for (r, c), val in np.ndenumerate(mat):
                ax.text(c, r, str(val), ha="center", va="center", fontsize=13, fontweight="bold", color="#0f172a")
            ax.set_xticks([0, 1], ["Pred 0", "Pred 1"])
            ax.set_yticks([0, 1], ["True 0", "True 1"])
            ax.set_title(f"External Confusion Matrix (MCC={metrics.get('MCC_ext', '')}, AUC={metrics.get('ROC_AUC_ext', '')})")
            saved["qsar_parity"] = _save_multi_format(fig, out_dir, "fig1_qsar_confusion", dpi=dpi)

        # 2. Williams Plot (Applicability Domain)
        ad = qsar_result.get("applicability_domain", {})
        ad_tr = ad.get("train_points", [])
        ad_te = ad.get("test_points", [])
        if ad_tr and ad_te:
            fig, ax = plt.subplots(figsize=(6.0, 4.6))
            h_star = ad.get("h_star", 0.5)
            ax.scatter([p["leverage"] for p in ad_tr], [p["std_residual"] for p in ad_tr], c=OKABE_BLUE, alpha=0.7, s=38, label=lbl["train"])
            ax.scatter([p["leverage"] for p in ad_te], [p["std_residual"] for p in ad_te], c=OKABE_ORANGE, marker="^", alpha=0.9, s=52, label=lbl["test"])
            ax.axhline(3.0, ls="--", color="#B91C1C", lw=1.1)
            ax.axhline(-3.0, ls="--", color="#B91C1C", lw=1.1, label="±3σ")
            ax.axvline(h_star, ls=":", color="#111827", lw=1.4, label=f"h* = {h_star}")
            ax.set_xlabel(lbl["leverage"])
            ax.set_ylabel(lbl["std_res"])
            ax.set_title(lbl["williams_title"])
            ax.legend(loc="best", fontsize=8.5)
            saved["williams_plot"] = _save_multi_format(fig, out_dir, "fig2_williams_ad", dpi=dpi)

        # 3. Y-Scrambling Plot
        ys = qsar_result.get("y_scrambling", {})
        pts = ys.get("points", [])
        if pts:
            fig, ax = plt.subplots(figsize=(5.6, 4.6))
            ax.scatter([p["y_corr"] for p in pts], [p["r2_scrambled"] for p in pts], c=OKABE_GREY, alpha=0.65, s=34, label="R² scrambled")
            ax.scatter([p["y_corr"] for p in pts], [p["q2_scrambled"] for p in pts], c=OKABE_PURPLE, marker="s", alpha=0.65, s=28, label="Q² scrambled")
            ax.scatter([1.0], [ys.get("original_R2_or_MCC", 0.0)], c=OKABE_GREEN, marker="*", s=180, zorder=5, label=f"Original (cRp²={ys.get('cRp2', '')})")
            ax.set_xlabel(lbl["y_corr"])
            ax.set_ylabel(lbl["r2_q2"])
            ax.set_title(lbl["yscram_title"])
            ax.legend(loc="best", fontsize=8.5)
            saved["y_scrambling"] = _save_multi_format(fig, out_dir, "fig3_y_scrambling", dpi=dpi)

    if sar_result and sar_result.get("space_points"):
        fig, ax = plt.subplots(figsize=(6.0, 5.0))
        sp = sar_result["space_points"]
        xs = [p["x"] for p in sp]
        ys_c = [p["y"] for p in sp]
        cs = [p["pActivity"] for p in sp]
        sc = ax.scatter(xs, ys_c, c=cs, cmap="viridis", s=54, edgecolors="white", lw=0.6)
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label(lbl["exp"])

        coord_map = {p["compound_id"]: (p["x"], p["y"]) for p in sp}
        for cliff in sar_result.get("cliffs", [])[:8]:
            c1 = coord_map.get(cliff["mol1_id"])
            c2 = coord_map.get(cliff["mol2_id"])
            if c1 and c2:
                ax.plot([c1[0], c2[0]], [c1[1], c2[1]], "--", color=OKABE_ORANGE, alpha=0.65, lw=1.1)

        proj_label = sar_result.get("projection_used", "PCA").upper()
        ax.set_xlabel(f"{proj_label} 1")
        ax.set_ylabel(f"{proj_label} 2")
        ax.set_title(lbl["space_title"])
        saved["chemical_space"] = _save_multi_format(fig, out_dir, "fig4_chemical_space_cliffs", dpi=dpi)

    if shap_result and shap_result.get("top_features"):
        feats = shap_result["top_features"][:12][::-1]
        fig, ax = plt.subplots(figsize=(6.2, 4.8))
        names = [f["feature"] for f in feats]
        vals = [f["mean_abs_shap"] for f in feats]
        colors = [OKABE_GREEN if f["direction_corr"] >= 0 else OKABE_ORANGE for f in feats]
        ax.barh(names, vals, color=colors, edgecolor="none", height=0.68)
        ax.set_xlabel(lbl["shap_x"])
        ax.set_title(lbl["shap_title"])
        saved["shap_importance"] = _save_multi_format(fig, out_dir, "fig5_shap_importance", dpi=dpi)

    if denovo_result and denovo_result.get("candidates"):
        cands = denovo_result["candidates"]
        fig, ax = plt.subplots(figsize=(6.0, 4.8))
        sas = [c["SA_Score"] for c in cands]
        pacts = [c.get("predicted_pActivity") if c.get("predicted_pActivity") is not None else (c.get("predicted_active_prob") or 0.5) for c in cands]
        qeds = [max(40, c["QED"] * 220) for c in cands]
        cols = [OKABE_GREEN if c["in_ad"] else OKABE_ORANGE for c in cands]
        ax.scatter(sas, pacts, s=qeds, c=cols, alpha=0.82, edgecolors="#1F2937", lw=0.6)
        ax.set_xlabel(lbl["sa_score"])
        ax.set_ylabel(lbl["pred"])
        ax.set_title(lbl["denovo_title"])
        saved["denovo_mpo"] = _save_multi_format(fig, out_dir, "fig6_denovo_mpo", dpi=dpi)

    return saved

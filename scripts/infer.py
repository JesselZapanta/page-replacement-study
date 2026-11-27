#!/usr/bin/env python3
"""Inferential analysis of the approved experiment (v2.1 protocol).

Approved specification (2026-11-27, docs/decision-log.md):

  * Primary inference: per-condition paired analysis on the independent traces,
    one Holm family across every tested workload x frame x pair comparison.
    Sequential and looping have only one distinct trace across repetitions, so
    they are reported as boundary cells with effective n = 1 and no test.
  * Interaction test: likelihood ratio between the full 3-way mixed model and
    the additive mixed model, both fitted by ML (REML is invalid when fixed
    effects differ). REML fits are reported only as model-based supplementary
    estimates.
  * Timing is analysed on log(ns) with the same per-condition paired method.

The earlier pooled-contrast approach and REML likelihood-ratio test are retired.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import scipy.stats as st
import statsmodels
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from common import utc_now

REPO_ROOT = Path(__file__).resolve().parent.parent

RATE_FORMULA = (
    'page_fault_rate_percent ~ '
    'C(algorithm, Treatment(reference="fifo")) * '
    'C(workload, Treatment(reference="sequential")) * C(frames)'
)
ADDITIVE_FORMULA = (
    'page_fault_rate_percent ~ '
    'C(algorithm, Treatment(reference="fifo")) + '
    'C(workload, Treatment(reference="sequential")) + C(frames)'
)
TIME_FORMULA = RATE_FORMULA.replace("page_fault_rate_percent", "log_time_ns")
PAIRS = (("fifo", "lru"), ("fifo", "clock"), ("lru", "clock"))


def load_records(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("status") == "ok" and not row.get("is_demo"):
                rows.append(row)
    if not rows:
        raise ValueError(f"no usable records in {path}")
    return pd.DataFrame(rows)


def build_frame(records):
    frame = pd.DataFrame({
        "run_id": records["run_id"],
        "trace_id": records["workload"].astype(str) + "_r" + records["repetition"].astype(str),
        "trace_sha256": records["trace_sha256"],
        "workload": records["workload"],
        "frames": records["frames"].astype(int),
        "algorithm": records["algorithm"],
        "page_fault_rate_percent": records["page_fault_rate_percent"].astype(float),
        "time_ns": records["algorithm_time_ns"].astype(float),
        "algorithm_order": records.get("algorithm_order"),
        "run_order_position": records.get("run_order_position"),
    })
    frame["log_time_ns"] = np.log(frame["time_ns"].clip(lower=1.0))
    counts = frame.groupby("trace_id")["algorithm"].nunique()
    if not (counts == 3).all():
        raise ValueError("incomplete traces: all 3 algorithms per trace are required")
    return frame


def fit_model(frame, formula, reml=True):
    """Fit a mixed model; fall back to Powell if the default optimizer stalls."""
    model = smf.mixedlm(formula, data=frame, groups=frame["trace_id"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.fit(reml=reml)
        method = "default (BFGS)"
        if not result.converged:
            result = model.fit(reml=reml, method="powell")
            method = "powell (fallback)"
    return model, result, method


def paired_condition_analysis(frame, response, response_label):
    """Independent-trace paired comparisons within each workload x frame cell."""
    rows = []
    for (workload, frames), cell in frame.groupby(["workload", "frames"]):
        distinct_hashes = int(cell["trace_sha256"].nunique())
        pivot = cell.pivot_table(index="trace_id", columns="algorithm",
                                 values=response)
        for algorithm_a, algorithm_b in PAIRS:
            differences = (pivot[algorithm_b] - pivot[algorithm_a]).dropna().to_numpy()
            n = len(differences)
            row = {
                "response": response_label,
                "workload": workload,
                "frames": frames,
                "comparison": f"{algorithm_b} - {algorithm_a}",
                "n_traces": int(cell["trace_id"].nunique()),
                "distinct_trace_hashes": distinct_hashes,
                "mean_difference": float(np.mean(differences)) if n else float("nan"),
                "sd_difference": float(np.std(differences, ddof=1)) if n > 1 else float("nan"),
                "p_value": None,
                "p_holm": None,
                "significant_after_holm": None,
                "ci95_low": None,
                "ci95_high": None,
                "cohens_dz": None,
                "status": None,
                "interpretation_note": "",
            }
            if distinct_hashes < 2 or n < 2:
                row["status"] = "boundary: identical traces across repetitions (effective n=1)"
            elif np.std(differences, ddof=1) == 0:
                row["status"] = "zero variance; test undefined"
            else:
                mean = float(np.mean(differences))
                sd = float(np.std(differences, ddof=1))
                t_stat, p_value = st.ttest_1samp(differences, 0.0)
                t_crit = st.t.ppf(0.975, n - 1)
                row.update({
                    "mean_difference": mean,
                    "sd_difference": sd,
                    "t_statistic": float(t_stat),
                    "p_value": float(p_value),
                    "ci95_low": mean - t_crit * sd / np.sqrt(n),
                    "ci95_high": mean + t_crit * sd / np.sqrt(n),
                    "cohens_dz": mean / sd,
                    "status": "tested",
                })
            rows.append(row)

    table = pd.DataFrame(rows)
    valid = table["p_value"].notna()
    if valid.any():
        reject, corrected, _, _ = multipletests(table.loc[valid, "p_value"].to_numpy(),
                                                method="holm")
        table.loc[valid, "p_holm"] = corrected
        table.loc[valid, "significant_after_holm"] = reject

    if response == "page_fault_rate_percent":
        artifact = (table["workload"] == "mixed") & (table["frames"] == 15)
        table.loc[artifact, "interpretation_note"] = (
            "trace-construction artifact (path dependence); not evidence about ranking")
        trivial = ((table["workload"] == "mixed") & (table["frames"] == 3)
                   & table["significant_after_holm"].fillna(False)
                   & (table["mean_difference"].abs() < 0.05))
        table.loc[trivial, "interpretation_note"] = (
            "practically zero difference despite Holm significance")
    return table


def write_csv(path, table):
    table.to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=REPO_ROOT / "results/experiment-v2.1/raw/results.jsonl")
    parser.add_argument("--output-dir", type=Path,
                        default=REPO_ROOT / "results/experiment-v2.1/processed/inferential")
    parser.add_argument("--approval", type=Path,
                        default=REPO_ROOT / "results/experiment-v2.1/amendment.json")
    args = parser.parse_args()

    approval = json.loads(args.approval.resolve().read_text(encoding="utf-8"))
    if "approved" not in str(approval.get("status", "")).lower():
        parser.error(f"model approval not recorded in {args.approval}")

    input_path = args.input.resolve()
    frame = build_frame(load_records(input_path))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Primary inference: per-condition paired analysis with one Holm family each.
    rate_pairs = paired_condition_analysis(frame, "page_fault_rate_percent",
                                           "page_fault_rate_percent")
    time_pairs = paired_condition_analysis(frame, "log_time_ns", "log_time_ns")
    write_csv(output_dir / "paired_by_condition.csv", rate_pairs)
    write_csv(output_dir / "paired_timing_by_condition.csv", time_pairs)
    write_csv(output_dir / "boundary_cells.csv",
              rate_pairs[rate_pairs["status"] != "tested"])

    # Model-based supplementary estimates (REML) and ML-only interaction test.
    _, full_reml, reml_method = fit_model(frame, RATE_FORMULA, reml=True)
    _, timing_reml, timing_method = fit_model(frame, TIME_FORMULA, reml=True)
    (output_dir / "model_summary.txt").write_text(str(full_reml.summary()) + "\n",
                                                   encoding="utf-8")
    (output_dir / "timing_model_summary.txt").write_text(
        str(timing_reml.summary()) + "\n", encoding="utf-8")
    fixed = full_reml.params.rename("coefficient").to_frame()
    fixed["std_error"] = full_reml.bse
    fixed["z"] = full_reml.tvalues
    fixed["p_value"] = full_reml.pvalues
    ci = full_reml.conf_int()
    ci.columns = ["ci95_low", "ci95_high"]
    fixed = fixed.join(ci).reset_index().rename(columns={"index": "term"})
    write_csv(output_dir / "fixed_effects.csv", fixed)

    _, full_ml, ml_method = fit_model(frame, RATE_FORMULA, reml=False)
    _, additive_ml, additive_ml_method = fit_model(frame, ADDITIVE_FORMULA, reml=False)
    lr_stat = 2 * (full_ml.llf - additive_ml.llf)
    lr_df = len(full_ml.params) - len(additive_ml.params)
    lr_p = st.chi2.sf(lr_stat, lr_df) if lr_df > 0 else float("nan")

    shapiro_w, shapiro_p = st.shapiro(np.asarray(full_reml.resid))
    diagnostics = {
        "n_runs": int(len(frame)),
        "n_traces": int(frame["trace_id"].nunique()),
        "primary_inference": "per-condition paired t-tests on independent traces; Holm across all tested cell/pair comparisons",
        "tested_rate_comparisons": int((rate_pairs["status"] == "tested").sum()),
        "boundary_rate_comparisons": int((rate_pairs["status"] != "tested").sum()),
        "tested_timing_comparisons": int((time_pairs["status"] == "tested").sum()),
        "fit_methods": {
            "rate_model_reml": reml_method,
            "timing_model_reml": timing_method,
            "rate_model_ml": ml_method,
            "additive_model_ml": additive_ml_method,
        },
        "converged": {
            "rate_reml": bool(full_reml.converged),
            "timing_reml": bool(timing_reml.converged),
            "rate_ml": bool(full_ml.converged),
            "additive_ml": bool(additive_ml.converged),
        },
        "likelihood_ratio_interactions_ML": {
            "statistic": float(lr_stat), "df": int(lr_df), "p_value": float(lr_p),
            "note": "ML fits; REML is invalid for comparing different fixed effects",
        },
        "residual_shapiro_w": float(shapiro_w),
        "residual_shapiro_p": float(shapiro_p),
        "note": "Single-variance mixed model is a poor fit; primary inference uses per-condition variances."
    }
    (output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")

    spec = {
        "schema_version": 2,
        "generated_at_utc": utc_now(),
        "status": "approved model, executed",
        "approval_source": str(args.approval.resolve()),
        "input": str(input_path),
        "primary_method": "per-condition paired analysis on distinct traces, with Holm correction across all tested comparisons",
        "primary_formula_supplementary": RATE_FORMULA,
        "secondary_formula_supplementary": TIME_FORMULA,
        "random_effects_supplementary": "intercept by trace_id (workload x repetition)",
        "interaction_test": "likelihood ratio between full and additive ML fits",
        "boundary_rule": "cells whose repetitions share one trace hash are excluded from inference (effective n=1)",
        "algorithm_reference": "fifo",
        "workload_reference": "sequential",
        "frames_treatment": "categorical",
        "versions": {
            "numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "statsmodels": statsmodels.__version__
        },
        "interpretation": "Outputs are scoped to the approved v2.1 protocol; see docs/decision-log.md."
    }
    (output_dir / "model_spec.json").write_text(
        json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# Inferential output\n\n"
        "Primary inference is in `paired_by_condition.csv` (fault rate) and "
        "`paired_timing_by_condition.csv` (log time), each Holm-corrected across "
        "all tested comparisons. The `interpretation_note` column flags "
        "practically zero differences and the mixed/15-frame trace-construction "
        "artifact. Cells with one distinct trace across repetitions are listed in "
        "`boundary_cells.csv` and are not tested. The likelihood-ratio test in "
        "`diagnostics.json` uses ML fits; the REML model summaries are "
        "supplementary only. See `model_spec.json` for the approved specification.\n",
        encoding="utf-8")

    tested = rate_pairs[rate_pairs["status"] == "tested"]
    print(f"wrote per-condition paired results to {output_dir}")
    print(f"tested comparisons: {len(tested)}; boundary comparisons: "
          f"{len(rate_pairs) - len(tested)}")
    print(f"interaction LR (ML): chi2={lr_stat:.2f}, df={lr_df}, p={lr_p:.3g}")
    if len(tested):
        print(tested[["workload", "frames", "comparison", "mean_difference",
                      "p_holm", "significant_after_holm"]].head(10).to_string(index=False))
    return 0 if all(diagnostics["converged"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Inferential analysis of the approved v2 experiment.

Pre-specified model (approved by the researcher 2026-11-26, see
docs/decision-log.md):

    fault_rate ~ algorithm * workload * frames + (1 | trace)

`trace` is the workload x repetition identifier; all algorithms and frame
capacities see the same trace, so this is a paired/repeated design. Ordinary
one-way ANOVA on 750 independent observations is deliberately not used.

Outputs: model summaries, fixed-effect and interaction tables, Holm-corrected
pairwise algorithm contrasts, paired effect sizes, and assumption checks.
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
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices, dmatrix
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
            if row.get("status") != "ok":
                continue
            if row.get("is_demo"):
                continue
            rows.append(row)
    if not rows:
        raise ValueError(f"no usable records in {path}")
    return pd.DataFrame(rows)


def build_frame(records):
    frame = pd.DataFrame({
        "run_id": records["run_id"],
        "trace_id": records["workload"].astype(str) + "_r" + records["repetition"].astype(str),
        "workload": records["workload"],
        "frames": records["frames"].astype(int),
        "algorithm": records["algorithm"],
        "page_fault_rate_percent": records["page_fault_rate_percent"].astype(float),
        "time_ns": records["algorithm_time_ns"].astype(float),
    })
    frame["log_time_ns"] = np.log(frame["time_ns"].clip(lower=1.0))
    counts = frame.groupby("trace_id")["algorithm"].nunique()
    if not (counts == 3).all():
        raise ValueError("incomplete traces: pairwise design requires all 3 algorithms per trace")
    return frame


def fit_model(frame, formula, response):
    """Fit the mixed model, falling back to Powell if the default optimizer stalls."""
    model = smf.mixedlm(formula, data=frame, groups=frame["trace_id"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.fit(reml=True)
        method = "default (BFGS)"
        if not result.converged:
            result = model.fit(reml=True, method="powell")
            method = "powell (fallback)"
    return model, result, method


def algorithm_contrast(design_info, algorithm_a, algorithm_b, workloads, frames):
    """Mean predicted difference (b - a) over all workload x frame conditions."""
    rows = []
    for workload in workloads:
        for frame_count in frames:
            for algorithm in (algorithm_a, algorithm_b):
                rows.append({"algorithm": algorithm, "workload": workload,
                             "frames": frame_count})
    design = np.asarray(build_design_matrices([design_info], pd.DataFrame(rows))[0])
    mean_a = design[0::2].mean(axis=0)
    mean_b = design[1::2].mean(axis=0)
    return mean_b - mean_a


def paired_effect_sizes(frame, algorithm_a, algorithm_b):
    pivot = frame.pivot_table(index=["trace_id", "frames"], columns="algorithm",
                              values="page_fault_rate_percent")
    differences = (pivot[algorithm_b] - pivot[algorithm_a]).dropna().to_numpy()
    n = len(differences)
    mean = float(np.mean(differences))
    sd = float(np.std(differences, ddof=1))
    t_crit = st.t.ppf(0.975, n - 1)
    return {
        "comparison": f"{algorithm_b} - {algorithm_a}",
        "n_paired_observations": n,
        "mean_difference_pp": mean,
        "sd_difference_pp": sd,
        "ci95_low_pp": mean - t_crit * sd / np.sqrt(n),
        "ci95_high_pp": mean + t_crit * sd / np.sqrt(n),
        "cohens_dz": mean / sd if sd else float("nan"),
    }


def pairwise_table(result, frame, formula, response):
    workloads = sorted(frame["workload"].unique())
    frames = sorted(frame["frames"].unique())
    rhs = formula.split("~", 1)[1]
    design_info = dmatrix(rhs, frame, return_type="dataframe").design_info
    rows = []
    for algorithm_a, algorithm_b in PAIRS:
        contrast = algorithm_contrast(design_info, algorithm_a, algorithm_b,
                                      workloads, frames)
        test = result.t_test(np.asarray(contrast).reshape(1, -1))
        effect = float(np.asarray(test.effect).ravel()[0])
        sd = float(np.asarray(test.sd).ravel()[0])
        p_value = float(np.asarray(test.pvalue).ravel()[0])
        ci = np.asarray(test.conf_int()).ravel()
        rows.append({
            "comparison": f"{algorithm_b} - {algorithm_a}",
            "response": response,
            "mean_difference_pp" if response == "page_fault_rate_percent" else "mean_difference_log_ns": effect,
            "std_error": sd,
            "z": effect / sd if sd else float("nan"),
            "p_value": p_value,
            "ci95_low": float(ci[0]),
            "ci95_high": float(ci[1]),
        })
    p_values = [row["p_value"] for row in rows]
    reject, corrected, _, _ = multipletests(p_values, method="holm")
    for row, adjusted, significant in zip(rows, corrected, reject):
        row["p_holm"] = float(adjusted)
        row["significant_after_holm"] = bool(significant)
    return pd.DataFrame(rows)


def pairwise_by_condition(result, frame, formula, response):
    """Holm-corrected pairwise contrasts separately for each workload x frame cell."""
    rhs = formula.split("~", 1)[1]
    design_info = dmatrix(rhs, frame, return_type="dataframe").design_info
    rows = []
    for workload in sorted(frame["workload"].unique()):
        for frame_count in sorted(frame["frames"].unique()):
            cell_rows = []
            for algorithm_a, algorithm_b in PAIRS:
                newdata = pd.DataFrame([
                    {"algorithm": algorithm_a, "workload": workload, "frames": frame_count},
                    {"algorithm": algorithm_b, "workload": workload, "frames": frame_count},
                ])
                design = np.asarray(build_design_matrices([design_info], newdata)[0])
                contrast = (design[1] - design[0]).reshape(1, -1)
                test = result.t_test(contrast)
                effect = float(np.asarray(test.effect).ravel()[0])
                sd = float(np.asarray(test.sd).ravel()[0])
                ci = np.asarray(test.conf_int()).ravel()
                cell_rows.append({
                    "workload": workload,
                    "frames": frame_count,
                    "comparison": f"{algorithm_b} - {algorithm_a}",
                    "response": response,
                    "mean_difference_pp" if response == "page_fault_rate_percent" else "mean_difference_log_ns": effect,
                    "std_error": sd,
                    "z": effect / sd if sd else float("nan"),
                    "p_value": float(np.asarray(test.pvalue).ravel()[0]),
                    "ci95_low": float(ci[0]),
                    "ci95_high": float(ci[1]),
                })
            reject, corrected, _, _ = multipletests(
                [row["p_value"] for row in cell_rows], method="holm")
            for row, adjusted, significant in zip(cell_rows, corrected, reject):
                row["p_holm"] = float(adjusted)
                row["significant_after_holm"] = bool(significant)
            rows.extend(cell_rows)
    return pd.DataFrame(rows)


def write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=REPO_ROOT / "results/experiment-v2/raw/results.jsonl")
    parser.add_argument("--output-dir", type=Path,
                        default=REPO_ROOT / "results/experiment-v2/processed/inferential")
    parser.add_argument("--approval", type=Path,
                        default=REPO_ROOT / "results/experiment-v2/amendment.json")
    args = parser.parse_args()

    approval = json.loads(args.approval.resolve().read_text(encoding="utf-8"))
    if "approved" not in str(approval.get("status", "")).lower():
        parser.error(f"model approval not recorded in {args.approval}")

    input_path = args.input.resolve()
    frame = build_frame(load_records(input_path))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    full_model, full, rate_method = fit_model(frame, RATE_FORMULA,
                                              "page_fault_rate_percent")
    additive_model, additive, additive_method = fit_model(frame, ADDITIVE_FORMULA,
                                                           "page_fault_rate_percent")

    (output_dir / "model_summary.txt").write_text(str(full.summary()) + "\n", encoding="utf-8")
    (output_dir / "additive_model_summary.txt").write_text(
        str(additive.summary()) + "\n", encoding="utf-8")

    fixed = full.params.rename("coefficient").to_frame()
    fixed["std_error"] = full.bse
    fixed["z"] = full.tvalues
    fixed["p_value"] = full.pvalues
    ci = full.conf_int()
    ci.columns = ["ci95_low", "ci95_high"]
    fixed = fixed.join(ci).reset_index().rename(columns={"index": "term"})
    write_csv(output_dir / "fixed_effects.csv", fixed.to_dict("records"))

    interactions = fixed[fixed["term"].str.contains(":")].copy()
    write_csv(output_dir / "interaction_terms.csv", interactions.to_dict("records"))

    lr_stat = 2 * (full.llf - additive.llf)
    lr_df = len(full.params) - len(additive.params)
    lr_p = st.chi2.sf(lr_stat, lr_df) if lr_df > 0 else float("nan")

    rate_pairs = pairwise_table(full, frame, RATE_FORMULA, "page_fault_rate_percent")
    write_csv(output_dir / "pairwise_algorithms.csv", rate_pairs.to_dict("records"))
    condition_pairs = pairwise_by_condition(full, frame, RATE_FORMULA,
                                            "page_fault_rate_percent")
    write_csv(output_dir / "pairwise_by_condition.csv",
              condition_pairs.to_dict("records"))
    effect_rows = [paired_effect_sizes(frame, a, b) for a, b in PAIRS]
    write_csv(output_dir / "paired_effect_sizes.csv", effect_rows)

    timing_model, timing, timing_method = fit_model(frame, TIME_FORMULA, "log_time_ns")
    (output_dir / "timing_model_summary.txt").write_text(
        str(timing.summary()) + "\n", encoding="utf-8")
    timing_pairs = pairwise_table(timing, frame, TIME_FORMULA, "log_time_ns")
    write_csv(output_dir / "timing_pairwise.csv", timing_pairs.to_dict("records"))

    shapiro_w, shapiro_p = st.shapiro(np.asarray(full.resid))
    diagnostics = {
        "n_runs": int(len(frame)),
        "n_traces": int(frame["trace_id"].nunique()),
        "rate_model_converged": bool(full.converged),
        "additive_model_converged": bool(additive.converged),
        "timing_model_converged": bool(timing.converged),
        "fit_methods": {
            "rate_model": rate_method,
            "additive_model": additive_method,
            "timing_model": timing_method,
        },
        "random_effect_variance": {
            "rate_model": float(np.asarray(full.cov_re).ravel()[0]),
            "additive_model": float(np.asarray(additive.cov_re).ravel()[0]),
            "timing_model": float(np.asarray(timing.cov_re).ravel()[0]),
        },
        "boundary_fit": {
            model_name: bool(float(np.asarray(fit.cov_re).ravel()[0]) < 1e-6)
            for model_name, fit in (("rate_model", full), ("additive_model", additive),
                                    ("timing_model", timing))
        },
        "likelihood_ratio_interactions": {
            "statistic": float(lr_stat), "df": int(lr_df), "p_value": float(lr_p),
            "note": "full 3-way interaction model vs additive model"
        },
        "residual_shapiro_w": float(shapiro_w),
        "residual_shapiro_p": float(shapiro_p),
        "note": "Shapiro-Wilk is sensitive at large n; inspect residuals alongside the test."
    }
    (output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")

    spec = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "approved model, executed",
        "approval_source": str(args.approval.resolve()),
        "input": str(input_path),
        "primary_formula": RATE_FORMULA,
        "secondary_formula": TIME_FORMULA,
        "random_effects": "intercept by trace_id (workload x repetition)",
        "pairwise_method": "mean predicted contrast over all workload x frame conditions (pairwise_algorithms.csv) and within each workload x frame cell (pairwise_by_condition.csv); Holm correction across the 3 pairs in each family",
        "effect_sizes": "paired mean difference with 95% CI and Cohen's dz per matched trace/frame",
        "algorithm_reference": "fifo",
        "workload_reference": "sequential",
        "frames_treatment": "categorical",
        "versions": {
            "numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "statsmodels": statsmodels.__version__
        },
        "interpretation": "Descriptive and model outputs only within the approved v2 protocol; see docs/decision-log.md."
    }
    (output_dir / "model_spec.json").write_text(
        json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# Inferential output\n\n"
        "Produced by `scripts/infer.py` with the approved mixed-effects model "
        "in `model_spec.json`. `pairwise_algorithms.csv` gives average contrasts; "
        "`pairwise_by_condition.csv` gives contrasts within each workload x frame "
        "cell, which matter because the interaction likelihood-ratio test in "
        "`diagnostics.json` is significant. Compare p-values with "
        "`paired_effect_sizes.csv` for practical magnitude. The Shapiro-Wilk "
        "result in `diagnostics.json` indicates non-normal residuals, so these "
        "model-based p-values should be treated as approximate. "
        "All outputs are scoped to the approved v2 protocol.\n",
        encoding="utf-8")

    print(f"wrote inferential outputs to {output_dir}")
    print(rate_pairs[["comparison", "mean_difference_pp", "p_value", "p_holm",
                      "significant_after_holm"]].to_string(index=False))
    print(f"interaction LR test: chi2={lr_stat:.2f}, df={lr_df}, p={lr_p:.3g}")
    return 0 if full.converged and timing.converged else 1


if __name__ == "__main__":
    sys.exit(main())

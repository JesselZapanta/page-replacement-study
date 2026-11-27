# Inferential output

Primary inference is in `paired_by_condition.csv` (fault rate) and `paired_timing_by_condition.csv` (log time), each Holm-corrected across all tested comparisons. The `interpretation_note` column flags practically zero differences and the mixed/15-frame trace-construction artifact. Cells with one distinct trace across repetitions are listed in `boundary_cells.csv` and are not tested. The likelihood-ratio test in `diagnostics.json` uses ML fits; the REML model summaries are supplementary only. See `model_spec.json` for the approved specification.

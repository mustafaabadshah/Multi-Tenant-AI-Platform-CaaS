# M28.10 — Research Answer Quality & Scientific Forecasting Rigor

## 1. Problem Statement: Solar Irradiance Forecasting Deficiencies
In Operator Failure D, the assistant:
1. Recommended Bi-LSTM for solar forecasting definitively.
2. Asserted advantages of bidirectional sequence processing without addressing causal forecasting constraints (future target leakage).
3. Compared reported metrics (RMSE, R²) across disparate datasets as if they were directly comparable without baseline normalization.

---

## 2. Scientific Forecasting Standards Implemented
Added explicit scientific and empirical rigor guidelines into the assistant system prompt (`backend/app/assistant_runtime/context.py`):
1. **Baselines First**:
   Always establish baseline models (persistence, linear/statistical, or gradient boosted trees such as LightGBM/XGBoost) before recommending complex deep learning architectures.
2. **Metric Incomparability**:
   Never present reported metrics (RMSE, MAE, R²) from different datasets, geographic locations, or prediction horizons as directly comparable without explicitly noting differences in scale, target normalization, and evaluation protocol.
3. **Causal Constraints & Bidirectional Architectures (Bi-LSTM / Bi-GRU)**:
   Clarify that while backward passes over fully observed historical input windows do not inherently leak future targets, bidirectional processing cannot be used across future timesteps or unobserved targets. Acknowledge causal forecasting constraints and never assert that Bi-LSTM unconditionally outperforms unidirectional models.
4. **Hypothesis vs. Grounded Fact**:
   Clearly distinguish empirical findings proven in referenced sources from hypotheses or suggestions for further testing. Never fabricate experimental metrics.

---

## 3. Test Evidence
- `test_context_system_prompt_contains_forecasting_causal_leakage_guidelines`: PASSED

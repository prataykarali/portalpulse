# Team 2 — Week 1 to-do

Week 1 is **frozen**. Do not keep retraining randomly.

- [x] 1. Read `Module1_Data/data_dictionary.md` and `feature_notes.md`
- [x] 2. Load `dataset_clean.csv` and write down: X, y, rows, features, missing values, target distribution
- [x] 3. Build train / validation / test split (do not change the master CSV)
- [x] 4. Build preprocessing (fit scaler on train only)
- [x] 5. Train Linear Regression baseline — record MAE, RMSE, R²
- [x] 6. Train XGBoost (Week 1 baseline). Other candidates are Week 2+ comparison work, not a reason to unfreeze this booster.
- [x] 10. Score the finalized model once on the untouched test set
- [x] 12. Save `models/xgboost_model.pkl` + `feature_list.json` + `results/model_metrics.json` + `prediction_test.csv`
- [x] 13. Week 1 demo: input traffic → predicted capacity + risk status (dashboard)

Week 2 (do **not** start by training the model again):

- [ ] Stress-test the warning / overload region and unseen result-day-like conditions
- [ ] Threshold calibration (0.70 / 0.90)
- [ ] Robustness / generalization testing
- [ ] Turn the prediction into a traffic-decision mechanism

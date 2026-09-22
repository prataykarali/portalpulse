"""PortalPulse Module 2: Multi-Horizon Telemetry Prediction Engine."""

from backend.m2_prediction.feature_pipeline import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    compute_lag_and_rolling_features,
    construct_forecasting_targets,
    extract_features_from_live,
    load_dataset,
    prepare_supervised_splits,
)
from backend.m2_prediction.forecaster import FORECASTER, LoadForecaster
from backend.m2_prediction.schema import (
    ForecasterMetadata,
    ForecastHorizon,
    ForecastHorizonName,
    ForecastResult,
    RiskLevel,
)

__all__ = [
    "FEATURE_COLUMNS",
    "TARGET_COLUMNS",
    "compute_lag_and_rolling_features",
    "construct_forecasting_targets",
    "extract_features_from_live",
    "load_dataset",
    "prepare_supervised_splits",
    "LoadForecaster",
    "FORECASTER",
    "ForecastHorizon",
    "ForecastHorizonName",
    "ForecastResult",
    "ForecasterMetadata",
    "RiskLevel",
]

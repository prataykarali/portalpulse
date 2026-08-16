"""Create and execute EDA.ipynb for the Team 1 / Team 2 handoff."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[2]
EDA_DIR = ROOT / "team1_work" / "EDA"
FIG_DIR = EDA_DIR / "figures"
HANDOFF = ROOT / "Module1_Data"


def new_notebook() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    cells: list = []

    def md(text: str) -> None:
        cells.append(nbf.v4.new_markdown_cell(text))

    def code(text: str) -> None:
        cells.append(nbf.v4.new_code_cell(text))

    md(
        """# PortalPulse Module 1 — EDA

Team 1 analysis of the **single master table** handed to Team 2.

This notebook does **not** split train / validation / test and does **not** train a model.
It answers: *does this table actually contain a workload → performance → capacity relationship?*

**Data file:** `dataset_clean.csv` (same folder as this notebook, or `../processed/`).
"""
    )

    md(
        """## 0. Load"""
    )
    code(
        """from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams["figure.figsize"] = (8, 4.5)
plt.rcParams["figure.dpi"] = 110

candidates = [
    Path("dataset_clean.csv"),
    Path("../processed/dataset_clean.csv"),
    Path("team1_work/processed/dataset_clean.csv"),
    Path("/home/pratay-karali/Desktop/portalpulse/team1_work/processed/dataset_clean.csv"),
]
data_path = next(p for p in candidates if p.exists())
print("loading", data_path.resolve())

df = pd.read_csv(data_path, parse_dates=["timestamp"])
print(df.shape)
df.head()
"""
    )

    md(
        """## 1. Shape, types, missing values, duplicates

What we need before trusting any plot.
"""
    )
    code(
        """print("rows, cols:", df.shape)
print("time range:", df["timestamp"].min(), "→", df["timestamp"].max())
print("unique timestamps:", df["timestamp"].nunique())
print()
df.info()
print()
print("missing values")
print(df.isnull().sum())
print()
print("duplicate rows:", int(df.duplicated().sum()))
print("duplicate timestamps:", int(df["timestamp"].duplicated().sum()))
"""
    )
    code(
        """df.describe().T
"""
    )

    md(
        """## 2. What each column is

| Column | Role |
|---|---|
| `timestamp` | minute of observation |
| `hour`, `day_of_week`, `is_weekend`, `is_result_window` | calendar features |
| `concurrent_users`, `requests_per_sec` | traffic / workload |
| `cpu_usage`, `memory_usage`, `network_usage` | server metrics |
| `latency_ms`, `error_rate` | performance |
| `safe_capacity` | **primary target (regression)** |
| `risk_level` | **derived target (classification)** |

`risk_level` is computed from utilization = `concurrent_users / safe_capacity` and from SLA breaches. Team 2 can train either or both. Do **not** feed `safe_capacity` in as a feature if the task is to predict it.
"""
    )

    md("## 3. Target distributions")
    code(
        """print(df["risk_level"].value_counts())
print()
print(df["risk_level"].value_counts(normalize=True).round(3))
print()
print("safe_capacity")
print(df["safe_capacity"].describe().round(1))
"""
    )
    code(
        """fig, axes = plt.subplots(1, 2, figsize=(11, 4))
order = ["SAFE", "AT_RISK", "OVERLOADED"]
sns.countplot(data=df, x="risk_level", order=order, ax=axes[0], hue="risk_level", hue_order=order, legend=False)
axes[0].set_title("Derived target: risk_level")
sns.histplot(df["safe_capacity"], bins=40, ax=axes[1], color="#3b6d99")
axes[1].set_title("Primary target: safe_capacity")
fig.tight_layout()
plt.show()
"""
    )

    md(
        """SAFE is the majority class (~84%). That is expected: most minutes of a month are ordinary office-hour or night traffic. The minority classes are the minutes that matter on result day.

If Team 2 trains a classifier, they should **not** use raw accuracy as the only metric. Use macro-F1 / recall on `OVERLOADED`. False negatives (calling an overloaded minute SAFE) are the expensive error.
"""
    )

    md("## 4. Feature distributions")
    code(
        """feat = [
    "concurrent_users", "requests_per_sec", "cpu_usage", "memory_usage",
    "network_usage", "latency_ms", "error_rate",
]
fig, axes = plt.subplots(3, 3, figsize=(12, 9))
for ax, col in zip(axes.ravel(), feat + ["safe_capacity"]):
    sns.histplot(df[col], bins=40, ax=ax, color="#4c7c5d")
    ax.set_title(col)
axes.ravel()[-1].axis("off")
fig.tight_layout()
plt.show()
"""
    )
    md(
        """Notes from the histograms:

- `concurrent_users` and `requests_per_sec` are right-skewed — a few result-window minutes carry extreme load. That is the signal, not a bug.
- `latency_ms` and `error_rate` are *mostly* small, with a long tail. That tail **is** the degradation we need the model to see.
- `memory_usage` moves less than CPU. RAM is a softer constraint in this table.
"""
    )

    md(
        """## 5. The degradation curve (most important plot)

Conceptually we are looking for the knee:

```
latency
  │                 /
  │              __/
  │           __/
  │________ _/
  └──────────────── users
              ↑
        degradation starts
```
"""
    )
    code(
        """sample = df.sample(min(8000, len(df)), random_state=42)

fig, axes = plt.subplots(2, 2, figsize=(11, 8))
pairs = [
    ("concurrent_users", "cpu_usage", "Users → CPU"),
    ("concurrent_users", "memory_usage", "Users → RAM"),
    ("concurrent_users", "latency_ms", "Users → Latency  (look for the knee)"),
    ("concurrent_users", "error_rate", "Users → Error rate"),
]
for ax, (x, y, title) in zip(axes.ravel(), pairs):
    sns.scatterplot(
        data=sample, x=x, y=y, hue="risk_level", hue_order=order,
        s=10, alpha=0.35, ax=ax, edgecolor="none",
    )
    ax.set_title(title)
    ax.legend(markerscale=1.6, fontsize=8)
fig.tight_layout()
plt.show()
"""
    )
    code(
        """fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
sns.scatterplot(
    data=sample, x="requests_per_sec", y="latency_ms",
    hue="risk_level", hue_order=order, s=10, alpha=0.35, ax=axes[0], edgecolor="none",
)
axes[0].set_title("Requests/sec → Latency")
sns.scatterplot(
    data=sample, x="requests_per_sec", y="error_rate",
    hue="risk_level", hue_order=order, s=10, alpha=0.35, ax=axes[1], edgecolor="none",
)
axes[1].set_title("Requests/sec → Errors")
fig.tight_layout()
plt.show()
"""
    )
    code(
        """# Binned median curve makes the knee obvious
bins = pd.qcut(df["concurrent_users"], q=25, duplicates="drop")
curve = df.groupby(bins, observed=True).agg(
    users=("concurrent_users", "median"),
    latency=("latency_ms", "median"),
    p90_latency=("latency_ms", lambda s: s.quantile(0.90)),
    cpu=("cpu_usage", "median"),
    errors=("error_rate", "median"),
    n=("concurrent_users", "size"),
).reset_index(drop=True)

fig, ax1 = plt.subplots(figsize=(9, 4.6))
ax1.plot(curve["users"], curve["latency"], color="#1f4e79", lw=2.2, label="median latency")
ax1.plot(curve["users"], curve["p90_latency"], color="#1f4e79", lw=1.2, ls="--", label="p90 latency")
ax1.axhline(800, color="#a33", ls=":", lw=1.4, label="SLA 800 ms")
ax1.set_xlabel("concurrent_users (bin median)")
ax1.set_ylabel("latency_ms")
ax2 = ax1.twinx()
ax2.plot(curve["users"], curve["cpu"], color="#c47b17", lw=2.0, label="median CPU")
ax2.set_ylabel("cpu_usage %")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
ax1.set_title("Capacity knee: latency and CPU vs users")
fig.tight_layout()
plt.show()
curve.tail(8)
"""
    )

    md(
        """The scatter is noisy on purpose: the same user count can sit in SAFE or OVERLOADED depending on hidden headroom (background jobs, heavier result-day queries). That is why `safe_capacity` is **not** a trivial function of `concurrent_users`, and why a model has something to learn from the telemetry.
"""
    )

    md("## 6. Correlations — which features actually move together")
    code(
        """num = [
    "concurrent_users", "requests_per_sec", "cpu_usage", "memory_usage",
    "network_usage", "latency_ms", "error_rate", "hour",
    "is_result_window", "safe_capacity",
]
corr = df[num].corr()
fig, ax = plt.subplots(figsize=(9.5, 7.2))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax, square=True)
ax.set_title("Pearson correlation")
fig.tight_layout()
plt.show()
print("correlation with safe_capacity")
print(corr["safe_capacity"].sort_values())
print()
print("correlation with concurrent_users")
print(corr["concurrent_users"].sort_values(ascending=False))
"""
    )
    md(
        """How to read this for Team 2:

- `concurrent_users` ↔ `requests_per_sec` will be high. They are two views of the same demand. Keep both, but expect multicollinearity in linear models.
- `cpu_usage` tracks users closely. It is the strongest *observable* saturation signal.
- `latency_ms` and `error_rate` correlate more weakly in Pearson terms because the relationship is **nonlinear** (flat, then a knee). Trees / MLP will handle this better than a plain linear regressor.
- `safe_capacity` is *negatively* related to CPU and to `is_result_window`. Result windows have a heavier query mix, so the same hardware holds fewer users.
- Do not interpret a low Pearson of latency vs capacity as “latency is useless.” Look at the knee plot above.
"""
    )

    md("## 7. Calendar and result windows")
    code(
        """fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
hourly = df.groupby("hour")[["concurrent_users", "cpu_usage", "latency_ms"]].median()
hourly.plot(ax=axes[0])
axes[0].set_title("Median load by hour of day")
axes[0].set_xlabel("hour")

by_res = df.groupby("is_result_window")[["concurrent_users", "cpu_usage", "latency_ms", "error_rate", "safe_capacity"]].median()
print(by_res.round(2))
sns.boxplot(data=df, x="is_result_window", y="safe_capacity", ax=axes[1])
axes[1].set_title("safe_capacity on ordinary vs result-window minutes")
fig.tight_layout()
plt.show()
"""
    )
    code(
        """# One result-window day vs a nearby ordinary day
days = (
    df.assign(day=df["timestamp"].dt.date)
    .groupby("day")
    .agg(result=("is_result_window", "max"), users=("concurrent_users", "median"))
    .sort_values("users", ascending=False)
)
print("heaviest days")
print(days.head(6))
result_day = days[days["result"] == 1].index[0]
normal_day = days[days["result"] == 0].index[0]
print("plotting result", result_day, "vs ordinary", normal_day)

sub = df[df["timestamp"].dt.date.isin([result_day, normal_day])].copy()
sub["which"] = np.where(sub["timestamp"].dt.date == result_day, f"result {result_day}", f"ordinary {normal_day}")
fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
for ax, col in zip(axes, ["concurrent_users", "latency_ms", "cpu_usage"]):
    for name, part in sub.groupby("which"):
        ax.plot(part["timestamp"], part[col], lw=0.8, label=name)
    ax.set_ylabel(col)
    ax.legend(fontsize=8)
axes[0].set_title("Result-window day vs ordinary day (same clock, different demand)")
fig.tight_layout()
plt.show()
"""
    )

    md(
        """The diurnal shape is inherited from the **real NASA July 1995 request process** (night trough, late-morning / afternoon peak). Result windows are NASA’s three heaviest calendar days, remapped onto the 2025 observation window. Those days show higher users, higher CPU, higher latency, and **lower** `safe_capacity` — the query mix is heavier, so the SLA ceiling drops.
"""
    )

    md("## 8. Outliers and suspicious rows")
    code(
        """print("latency_ms > 2000:", int((df["latency_ms"] > 2000).sum()))
print("error_rate > 0.10:", int((df["error_rate"] > 0.10).sum()))
print("cpu_usage >= 99:", int((df["cpu_usage"] >= 99).sum()))
print("users > safe_capacity:", int((df["concurrent_users"] > df["safe_capacity"]).sum()))
print()
print("These are overload minutes, not sensor bugs. They should stay in the table.")
print()
print(df.nlargest(5, "latency_ms")[
    ["timestamp", "concurrent_users", "requests_per_sec", "cpu_usage", "latency_ms", "error_rate", "safe_capacity", "risk_level", "is_result_window"]
].to_string(index=False))
"""
    )
    md(
        """Cleaning already removed the *impossible* values (CPU = 999, negative latency, monitoring dropouts). What remains in the tail is the degradation we want Team 2’s model to predict. Do not drop `latency_ms > 2000` as outliers unless you are deliberately training a “normal-only” model — that would hide result day.
"""
    )

    md("## 9. Does the table support the PortalPulse problem?")
    code(
        """util = df["concurrent_users"] / df["safe_capacity"]
print("utilization p50/p90/p99:", util.quantile([0.5, 0.9, 0.99]).round(3).tolist())
print()
print("median telemetry by risk_level")
print(
    df.groupby("risk_level")[["concurrent_users", "cpu_usage", "latency_ms", "error_rate", "safe_capacity"]]
    .median()
    .reindex(["SAFE", "AT_RISK", "OVERLOADED"])
    .round(2)
)
"""
    )
    md(
        """**Yes — with an explicit caveat.**

| Question | Answer |
|---|---|
| Is there a workload signal? | Yes. Users and RPS follow a real 28-day web-traffic shape (NASA HTTP Jul95). |
| Do server metrics respond to that workload? | Yes. CPU tracks users; latency and errors stay flat then bend (the knee). |
| Can we define a target? | Yes. `safe_capacity` is the max users that still meet SLA (800 ms, 1% errors, 85% CPU) given current hidden headroom. `risk_level` is derived from that. |
| Is this a raw production ERP dump? | No. No public dataset we inspected had traffic **and** CPU/RAM **and** a capacity label. Telemetry and the target are produced by a documented resource + queueing model *driven by the real NASA load*. |
| Should Team 2 split now? | No. Use this one file. Fit any scaler on **train only** after they split. |

Recommended Team 2 starting point:

1. Split `dataset_clean.csv` by time (e.g. last 5 days = test) **or** a stratified random split on `risk_level`. Time split is closer to production.
2. Features = all columns except `timestamp`, `safe_capacity`, `risk_level`.
3. Train a baseline regressor on `safe_capacity` (MAE / RMSE). Derive risk at inference from `current_users / predicted_capacity`.
4. Optionally train a classifier on `risk_level` and compare.
"""
    )

    md(
        """## 10. Leakage checklist for Team 2

- Do **not** use `safe_capacity` as an input feature.
- Do **not** compute `utilization = concurrent_users / safe_capacity` and feed that in — that *is* the answer.
- `risk_level` is a label, not a feature, unless you are predicting the other target.
- `is_result_window` is a legitimate calendar feature (result dates are known in advance). It is not leakage.
- Fit StandardScaler / imputers on the training fold only.
"""
    )

    nb.cells = cells
    return nb


def main() -> None:
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    nb = new_notebook()
    src = EDA_DIR / "EDA.ipynb"
    nbf.write(nb, src)
    print("wrote", src)

    client = NotebookClient(
        nb,
        timeout=180,
        kernel_name="portalpulse",
        resources={"metadata": {"path": str(EDA_DIR)}},
    )
    client.execute()
    nbf.write(nb, src)
    print("executed", src)


if __name__ == "__main__":
    main()

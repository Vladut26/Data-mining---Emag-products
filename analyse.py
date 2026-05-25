"""
Price Manipulation Analysis
Reads analiza_preturi.csv and produces statistics + charts
testing the hypothesis that eMAG inflates prices before voucher campaigns.

"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from scipy import stats
from pathlib import Path
from matplotlib.lines import Line2D
import warnings
warnings.filterwarnings("ignore")

INPUT_CSV  = "analiza_preturi.csv"
OUTPUT_DIR = Path("charts")
OUTPUT_DIR.mkdir(exist_ok=True)

ACCENT   = "#E63946"
NEUTRAL  = "#457B9D"
BG       = "#F8F9FA"
POSITIVE = "#E63946"
NEGATIVE = "#2A9D8F"

plt.rcParams.update({
    "figure.facecolor":  BG,
    "axes.facecolor":    BG,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.family":       "DejaVu Sans",
    "axes.titlesize":    13,
    "axes.labelsize":    11,
})


def load_data(path):
    """Load CSV, filter rows with status=ok and coerce numeric columns."""
    df = pd.read_csv(path)
    df_ok = df[df["status"] == "ok"].copy()
    df_ok["price_emag_ron"]        = pd.to_numeric(df_ok["price_emag_ron"],        errors="coerce")
    df_ok["lowest_price_emag_ron"] = pd.to_numeric(df_ok["lowest_price_emag_ron"], errors="coerce")
    df_ok["price_change_pct"]      = pd.to_numeric(df_ok["price_change_pct"],      errors="coerce")
    df_ok = df_ok.dropna(subset=["price_change_pct"])
    return df, df_ok


def print_stats(df_all, df):
    """Print summary statistics and run a one-sample t-test against 0."""
    total     = len(df_all)
    found     = len(df_all[df_all["status"] == "ok"])
    not_found = len(df_all[df_all["status"] == "not_found"])
    no_data   = len(df_all[df_all["status"] == "no_data"])
    errors    = total - found - not_found - no_data

    inflated = (df["price_change_pct"] > 0).sum()
    same     = (df["price_change_pct"] == 0).sum()
    cheaper  = (df["price_change_pct"] < 0).sum()

    mean_delta   = df["price_change_pct"].mean()
    median_delta = df["price_change_pct"].median()
    t_stat, p_value = stats.ttest_1samp(df["price_change_pct"], popmean=0)

    print("=" * 55)
    print("  PRICE MANIPULATION ANALYSIS — SUMMARY")
    print("=" * 55)
    print(f"\nData coverage")
    print(f"  Total products in campaign : {total}")
    print(f"  Found on istoric-preturi   : {found}  ({found/total*100:.1f}%)")
    print(f"  Not found                  : {not_found}")
    print(f"  No eMAG data in 14 days    : {no_data}")
    print(f"  Errors                     : {errors}")
    print(f"\nPrice change vs. 14-day minimum")
    print(f"  Prices INCREASED  (>0%)    : {inflated}  ({inflated/found*100:.1f}%)")
    print(f"  Prices UNCHANGED  (=0%)    : {same}  ({same/found*100:.1f}%)")
    print(f"  Prices DECREASED  (<0%)    : {cheaper}  ({cheaper/found*100:.1f}%)")
    print(f"\nDistribution of price_change_pct")
    print(f"  Mean                       : {mean_delta:+.2f}%")
    print(f"  Median                     : {median_delta:+.2f}%")
    print(f"  Std dev                    : {df['price_change_pct'].std():.2f}%")
    print(f"  Min                        : {df['price_change_pct'].min():+.2f}%")
    print(f"  Max                        : {df['price_change_pct'].max():+.2f}%")
    print(f"\nHypothesis test (t-test: mean > 0)")
    print(f"  t-statistic                : {t_stat:.4f}")
    print(f"  p-value                    : {p_value:.4f}")
    if p_value < 0.05 and mean_delta > 0:
        print(f"  Result  → SUPPORTS hypothesis (p < 0.05, mean > 0)")
    elif p_value < 0.05 and mean_delta < 0:
        print(f"  Result  → CONTRADICTS hypothesis (p < 0.05, mean < 0)")
    else:
        print(f"  Result  → INCONCLUSIVE (p >= 0.05)")
    print("=" * 55)

    return {
        "total": total, "found": found, "not_found": not_found,
        "no_data": no_data, "errors": errors,
        "inflated": inflated, "same": same, "cheaper": cheaper,
        "mean_delta": mean_delta, "median_delta": median_delta,
        "t_stat": t_stat, "p_value": p_value
    }


def chart_coverage(s):
    """Pie chart: data coverage breakdown."""
    fig, ax = plt.subplots(figsize=(6, 5))
    labels = ["Analysed", "Not found", "No 14d data", "Errors"]
    sizes  = [s["found"], s["not_found"], s["no_data"], s["errors"]]
    colors = [NEUTRAL, "#E9C46A", "#F4A261", ACCENT]
    nonzero = [(sz, l, c) for sz, l, c in zip(sizes, labels, colors) if sz > 0]
    sizes2, labels2, colors2 = zip(*nonzero)
    wedges, texts, autotexts = ax.pie(
        sizes2, labels=labels2, colors=colors2,
        autopct="%1.1f%%", startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5}
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("Data coverage\n(all campaign products)", pad=14)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "1_coverage.png", dpi=150)
    plt.close()
    print("  Saved: 1_coverage.png")


def chart_direction(s):
    """Bar chart: count of products that went up / stayed / went down."""
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["Price\nincreased", "Price\nunchanged", "Price\ndecreased"]
    values = [s["inflated"], s["same"], s["cheaper"]]
    colors = [POSITIVE, "#ADB5BD", NEGATIVE]
    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)
    ax.bar_label(bars, fmt="%d", padding=4, fontsize=10)
    ax.set_ylabel("Number of products")
    ax.set_title("Campaign price vs. 14-day minimum\n(direction of change)")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "2_direction.png", dpi=150)
    plt.close()
    print("  Saved: 2_direction.png")


def chart_distribution(df):
    """Histogram + KDE of price_change_pct with mean and median lines."""
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(df["price_change_pct"], bins=30, kde=True,
                 color=NEUTRAL, ax=ax, line_kws={"linewidth": 2})
    ax.axvline(0, color=ACCENT, linewidth=1.5, linestyle="--", label="No change (0%)")
    ax.axvline(df["price_change_pct"].mean(), color="#E9C46A", linewidth=1.5,
               linestyle="-", label=f"Mean ({df['price_change_pct'].mean():+.2f}%)")
    ax.axvline(df["price_change_pct"].median(), color="#2A9D8F", linewidth=1.5,
               linestyle="-.", label=f"Median ({df['price_change_pct'].median():+.2f}%)")
    ax.set_xlabel("Price change (%)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of price changes\n(campaign price vs. 14-day minimum)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "3_distribution.png", dpi=150)
    plt.close()
    print("  Saved: 3_distribution.png")


def chart_by_category(df):
    """Boxplot of price_change_pct for the top 8 categories by product count."""
    top_cats = df["category"].value_counts().nlargest(8).index
    df_top   = df[df["category"].isin(top_cats)]
    order    = (df_top.groupby("category")["price_change_pct"]
                .median().sort_values(ascending=False).index)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(data=df_top, x="category", y="price_change_pct",
                order=order, palette="coolwarm", ax=ax,
                flierprops={"marker": "o", "markersize": 3, "alpha": 0.5})
    ax.axhline(0, color=ACCENT, linewidth=1.2, linestyle="--", alpha=0.7)
    ax.set_xlabel("")
    ax.set_ylabel("Price change (%)")
    ax.set_title("Price change by category\n(top 8 categories by product count)")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=25, ha="right", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "4_by_category.png", dpi=150)
    plt.close()
    print("  Saved: 4_by_category.png")


def chart_scatter(df):
    """Scatter plot: campaign price vs. 14-day minimum, coloured by direction."""
    fig, ax = plt.subplots(figsize=(7, 6))
    colors = df["price_change_pct"].apply(
        lambda x: POSITIVE if x > 0 else (NEGATIVE if x < 0 else "#ADB5BD")
    )
    ax.scatter(df["lowest_price_emag_ron"], df["price_emag_ron"],
               c=colors, alpha=0.55, s=28, zorder=3)
    lim_min = min(df["lowest_price_emag_ron"].min(), df["price_emag_ron"].min()) * 0.97
    lim_max = max(df["lowest_price_emag_ron"].max(), df["price_emag_ron"].max()) * 1.03
    ax.plot([lim_min, lim_max], [lim_min, lim_max],
            color="#555", linewidth=1, linestyle="--", label="No change")
    ax.set_xlabel("14-day minimum price (RON)")
    ax.set_ylabel("Campaign price (RON)")
    ax.set_title("Campaign price vs. 14-day minimum\n(above diagonal = inflated)")
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=POSITIVE,
               markersize=8, label="Price increased"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=NEGATIVE,
               markersize=8, label="Price decreased"),
        Line2D([0], [0], color="#555", linestyle="--", label="No change"),
    ]
    ax.legend(handles=legend_elements, fontsize=9)
    ax.grid(linestyle="--", alpha=0.3, zorder=0)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "5_scatter.png", dpi=150)
    plt.close()
    print("  Saved: 5_scatter.png")


def chart_top_inflated(df, n=15):
    """Horizontal bar: top N products with the highest % price increase."""
    top = df[df["price_change_pct"] > 0].nlargest(n, "price_change_pct").copy()
    if top.empty:
        print("  Skipped: no inflated products found")
        return
    top["label"] = top["name"].str[:45] + "…"
    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(top["label"], top["price_change_pct"], color=ACCENT, alpha=0.85)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=8)
    ax.set_xlabel("Price increase (%)")
    ax.set_title(f"Top {n} most inflated products\n(campaign price vs. 14-day minimum)")
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "6_top_inflated.png", dpi=150)
    plt.close()
    print("  Saved: 6_top_inflated.png")


def chart_absolute_increase(df, n=15):
    """Horizontal bar: top N products with the largest absolute RON increase."""
    df2 = df.copy()
    df2["abs_increase_ron"] = df2["price_emag_ron"] - df2["lowest_price_emag_ron"]
    top = df2[df2["abs_increase_ron"] > 0].nlargest(n, "abs_increase_ron")
    if top.empty:
        print("  Skipped: no absolute increases found")
        return
    top["label"] = top["name"].str[:45] + "…"
    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(top["label"], top["abs_increase_ron"], color=NEUTRAL, alpha=0.85)
    ax.bar_label(bars, fmt="%.0f RON", padding=4, fontsize=8)
    ax.set_xlabel("Absolute price increase (RON)")
    ax.set_title(f"Top {n} largest absolute price increases\n(campaign price vs. 14-day minimum)")
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "7_top_absolute.png", dpi=150)
    plt.close()
    print("  Saved: 7_top_absolute.png")


def main():
    """Entry point: load data, print stats, generate all charts."""
    if not Path(INPUT_CSV).exists():
        print(f"ERROR: '{INPUT_CSV}' not found. Run scale_scraper.py first.")
        return

    print(f"Loading {INPUT_CSV}...")
    df_all, df = load_data(INPUT_CSV)
    print(f"  {len(df_all)} total rows, {len(df)} with status=ok and valid data\n")

    if df.empty:
        print("No valid data to analyse.")
        return

    s = print_stats(df_all, df)

    print(f"\nGenerating charts → {OUTPUT_DIR}/")
    chart_coverage(s)
    chart_direction(s)
    chart_distribution(df)
    if "category" in df.columns and df["category"].nunique() > 1:
        chart_by_category(df)
    chart_scatter(df)
    chart_top_inflated(df)
    chart_absolute_increase(df)

    print(f"\nDone. All charts saved in '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
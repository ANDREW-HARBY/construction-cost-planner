"""
Module 2 - Purchase and Cost Analysis
=====================================
* pandas  : read, clean (missing values, duplicates, bad references), merge,
            filter, group.
* NumPy   : price-increase scenario on the required quantities.
* Matplotlib : four charts (line, bar, scatter, histogram) saved as PNG.

Cost = quantity x unit price. The price file has no currency, so costs are
shown in "currency units".
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # draw to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from module1_quantities import (MATERIALS, UNITS, ValidationError,
                                parse_positive)

TOLERANCE = 1e-6          # differences smaller than this are "Balanced"
CURRENCY = "currency units"


# ============================================================================
# 1. Reading and cleaning
# ============================================================================
def _flag(reasons, mask, text):
    """Write a reject reason on rows that have no reason yet."""
    reasons.loc[mask & (reasons == "")] = text


def _clean_strings(df, columns):
    """Strip spaces and turn empty strings into missing values."""
    for col in columns:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    return df


def _split_rejected(df, reasons):
    """Return (clean rows, rejected rows with a 'reason' column)."""
    keep = reasons == ""
    rejected = df[~keep].copy()
    rejected["reason"] = reasons[~keep]
    return df[keep].copy(), rejected


def load_prices(path):
    """
    Read the price file and clean it.
    Returns (prices_df, rejected_df).
    Rules: no missing values, unit_price > 0, one row per (supplier, material),
    and every material must use ONE unit only (keeps units consistent).
    """
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    cols = ["supplier_id", "material", "unit", "unit_price"]
    df = _clean_strings(df, cols)
    df["supplier_id"] = df["supplier_id"].str.upper()
    df["material"] = df["material"].str.title()
    df["unit"] = df["unit"].str.lower()

    reasons = pd.Series("", index=df.index)
    _flag(reasons, df.duplicated(), "exact duplicate row")
    _flag(reasons, df[cols].isna().any(axis=1), "missing value")
    price = pd.to_numeric(df["unit_price"], errors="coerce")
    _flag(reasons, price.isna(), "unit_price is not a number")
    _flag(reasons, price <= 0, "unit_price must be > 0")
    ok = reasons == ""
    dup_pair = pd.Series(False, index=df.index)
    dup_pair[ok] = df.loc[ok].duplicated(["supplier_id", "material"])
    _flag(reasons, dup_pair, "duplicate supplier/material price")

    clean, rejected = _split_rejected(df, reasons)
    clean["unit_price"] = price[clean.index].astype(float)

    units_per_material = clean.groupby("material")["unit"].nunique()
    mixed = units_per_material[units_per_material > 1]
    if not mixed.empty:
        raise ValidationError("Inconsistent units for: " + ", ".join(mixed.index))
    return clean.reset_index(drop=True), rejected


def load_purchases(path):
    """Read the purchase file as text (cleaning happens in clean_purchases)."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def clean_purchases(raw, valid_element_ids, prices):
    """
    Clean the purchase table. Returns (clean_df, rejected_df).

    Rejected (with a reason): exact duplicates, duplicate transaction IDs,
    missing values, quantity that is not a number or <= 0, unknown element ID,
    unknown supplier ID, supplier that has no price for the material,
    invalid date.
    """
    cols = ["transaction_id", "element_id", "supplier_id",
            "material", "date", "quantity"]
    df = _clean_strings(raw[cols].copy(), cols)
    df["transaction_id"] = df["transaction_id"].str.upper()
    df["element_id"] = df["element_id"].str.upper()
    df["supplier_id"] = df["supplier_id"].str.upper()
    df["material"] = df["material"].str.title()

    reasons = pd.Series("", index=df.index)

    # 1) exact duplicate rows (same transaction repeated)
    _flag(reasons, df.duplicated(), "exact duplicate row")
    # 2) missing values
    for col in cols:
        _flag(reasons, df[col].isna(), f"missing {col}")
    # 3) quantity must be a number > 0
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    _flag(reasons, qty.isna() & df["quantity"].notna(), "quantity is not a number")
    _flag(reasons, qty <= 0, "quantity must be > 0")
    # 4) same transaction ID but different data
    ok = reasons == ""
    dup_id = pd.Series(False, index=df.index)
    dup_id[ok] = df.loc[ok, "transaction_id"].duplicated()
    _flag(reasons, dup_id, "duplicate transaction_id")
    # 5) references to unknown IDs
    _flag(reasons, ~df["element_id"].isin(set(valid_element_ids)), "unknown element_id")
    _flag(reasons, ~df["supplier_id"].isin(set(prices["supplier_id"])), "unknown supplier_id")
    priced_pairs = set(zip(prices["supplier_id"], prices["material"]))
    no_price = [(s, m) not in priced_pairs
                for s, m in zip(df["supplier_id"], df["material"])]
    _flag(reasons, pd.Series(no_price, index=df.index), "no price for supplier/material")
    # 6) date
    dates = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    _flag(reasons, dates.isna() & df["date"].notna(), "invalid date")

    clean, rejected = _split_rejected(df, reasons)
    clean["quantity"] = qty[clean.index].astype(float)
    clean["date"] = dates[clean.index]
    return clean.reset_index(drop=True), rejected


def rejected_report(rejected, source):
    """Make a small, readable table of rejected rows for the CSV report."""
    if rejected.empty:
        return pd.DataFrame(columns=["source", "record", "reason"])
    fields = rejected.drop(columns="reason").astype("string").fillna("")
    record = fields.agg(",".join, axis=1)
    return pd.DataFrame({"source": source, "record": record.values,
                         "reason": rejected["reason"].values})


# ============================================================================
# 2. Merging and cost tables
# ============================================================================
def elements_dataframe(registry):
    """Elements of module 1 as a DataFrame (the link between the modules)."""
    rows = [e.to_dict() for e in registry.list_all()]
    return pd.DataFrame(rows)


def merge_purchases(clean, prices, elements_df):
    """Merge purchases + prices (supplier, material) + elements (element_id)."""
    merged = clean.merge(prices[["supplier_id", "material", "unit", "unit_price"]],
                         on=["supplier_id", "material"],
                         how="left", validate="many_to_one")
    merged = merged.merge(elements_df[["element_id", "element_name", "site"]],
                          on="element_id", how="left", validate="many_to_one")
    merged["cost"] = merged["quantity"] * merged["unit_price"]
    merged["month"] = merged["date"].dt.strftime("%Y-%m")
    return merged


def cost_by(merged, column):
    """Total purchase cost grouped by site, supplier or month."""
    table = (merged.groupby(column, as_index=False)
             .agg(total_cost=("cost", "sum"), transactions=("transaction_id", "count")))
    table["share_pct"] = table["total_cost"] / table["total_cost"].sum() * 100
    return table.round(2)


def cost_by_site_supplier_month(merged):
    """Detailed table: site x supplier x month."""
    table = (merged.groupby(["site", "supplier_id", "month"], as_index=False)
             .agg(total_cost=("cost", "sum"), transactions=("transaction_id", "count")))
    return table.round(2)


# ============================================================================
# 3. Required vs purchased
# ============================================================================
def required_quantities_df(registry):
    """Required quantity per element and material (long format)."""
    records = []
    for element in registry.list_all():
        for material, qty in element.material_quantities().items():
            records.append({"element_id": element.element_id,
                            "element_name": element.name,
                            "site": element.site,
                            "material": material,
                            "unit": UNITS[material],
                            "required_qty": qty})
    return pd.DataFrame(records)


def check_units(required, prices):
    """Units of module 1 and of the price file must match for every material."""
    price_units = prices.drop_duplicates("material").set_index("material")["unit"]
    for material in MATERIALS:
        if material in price_units.index and price_units[material] != UNITS[material]:
            raise ValidationError(
                f"Unit mismatch for {material}: quantities use {UNITS[material]}, "
                f"price file uses {price_units[material]}.")


def required_vs_purchased(registry, merged, prices):
    """
    Compare required (module 1) and purchased quantities per element/material.
    difference = purchased - required   (negative = shortage, positive = surplus)
    """
    required = required_quantities_df(registry)
    check_units(required, prices)
    purchased = (merged.groupby(["element_id", "material"], as_index=False)
                 ["quantity"].sum().rename(columns={"quantity": "purchased_qty"}))
    table = required.merge(purchased, on=["element_id", "material"], how="left")
    table["purchased_qty"] = table["purchased_qty"].fillna(0.0)
    table["difference"] = table["purchased_qty"] - table["required_qty"]
    table["status"] = np.select([table["difference"] < -TOLERANCE,
                                 table["difference"] > TOLERANCE],
                                ["Shortage", "Surplus"], default="Balanced")
    return table.round(4)


# ============================================================================
# 4. NumPy price scenario
# ============================================================================
def lowest_prices(prices):
    """Lowest available unit price for each material (the baseline)."""
    return prices.groupby("material")["unit_price"].min()


def price_increase_scenario(required_totals, baseline_prices, material, pct):
    """
    Compare the cost of the REQUIRED quantities before and after increasing
    the baseline (lowest) price of one material by pct percent.
    Returns (table, summary_dict). All maths uses NumPy arrays.
    """
    if material not in MATERIALS:
        raise ValidationError(f"Material must be one of: {', '.join(MATERIALS)}")
    pct = parse_positive(pct, "Price increase percentage")

    materials = np.array(MATERIALS)
    quantity = np.array([required_totals[m] for m in MATERIALS])
    old_price = np.array([baseline_prices[m] for m in MATERIALS])
    factor = np.where(materials == material, 1 + pct / 100, 1.0)
    new_price = old_price * factor

    cost_before = quantity * old_price
    cost_after = quantity * new_price

    table = pd.DataFrame({
        "material": materials,
        "unit": [UNITS[m] for m in MATERIALS],
        "required_qty": quantity,
        "lowest_price": old_price,
        "new_price": new_price,
        "cost_before": cost_before,
        "cost_after": cost_after,
        "cost_change": cost_after - cost_before,
    }).round(4)
    summary = {
        "material": material,
        "increase_pct": pct,
        "total_before": float(cost_before.sum()),
        "total_after": float(cost_after.sum()),
        "total_change": float(cost_after.sum() - cost_before.sum()),
        "change_pct": float((cost_after.sum() / cost_before.sum() - 1) * 100),
    }
    return table, summary


# ============================================================================
# 5. Charts (line, bar, scatter, histogram)
# ============================================================================
def _save(fig, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return Path(path)


def chart_line(merged, path):
    """Line: cumulative purchase cost per site over time."""
    daily = merged.groupby(["date", "site"])["cost"].sum().unstack(fill_value=0)
    cumulative = daily.sort_index().cumsum()
    fig, ax = plt.subplots(figsize=(9, 5))
    for site in cumulative.columns:
        ax.plot(cumulative.index, cumulative[site], marker="o", label=site)
    ax.set_title("Cumulative Purchase Cost per Site Over Time")
    ax.set_xlabel("Purchase date")
    ax.set_ylabel(f"Cumulative cost ({CURRENCY})")
    ax.grid(alpha=0.3)
    ax.legend(title="Site")
    fig.autofmt_xdate()
    return _save(fig, path)


def chart_bar(merged, path):
    """Bar: purchase cost per site, split by supplier."""
    table = merged.pivot_table(index="site", columns="supplier_id",
                               values="cost", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    table.plot(kind="bar", ax=ax, rot=0)
    ax.set_title("Purchase Cost per Site by Supplier")
    ax.set_xlabel("Site")
    ax.set_ylabel(f"Total cost ({CURRENCY})")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(title="Supplier")
    return _save(fig, path)


def chart_scatter(merged, quantities_df, path):
    """Scatter: concrete volume of each element vs. what was spent on it."""
    spent = merged.groupby("element_id")["cost"].sum()
    data = quantities_df.copy()
    data["cost"] = data["element_id"].map(spent).fillna(0.0)
    fig, ax = plt.subplots(figsize=(8, 5))
    for site, part in data.groupby("site"):
        ax.scatter(part["volume_with_waste_m3"], part["cost"], s=70, label=site)
    for i, (_, row) in enumerate(data.iterrows()):
        offset = (6, 4) if i % 2 == 0 else (6, -12)    # avoid overlapping labels
        ax.annotate(row["element_id"], (row["volume_with_waste_m3"], row["cost"]),
                    textcoords="offset points", xytext=offset, fontsize=8)
    ax.set_title("Purchase Cost vs. Concrete Volume per Element")
    ax.set_xlabel("Volume including waste (m³)")
    ax.set_ylabel(f"Purchase cost ({CURRENCY})")
    ax.grid(alpha=0.3)
    ax.legend(title="Site")
    return _save(fig, path)


def chart_histogram(merged, path):
    """Histogram: distribution of the cost of single transactions."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(merged["cost"], bins=8, edgecolor="black")
    ax.set_title("Distribution of Transaction Costs")
    ax.set_xlabel(f"Cost of one transaction ({CURRENCY})")
    ax.set_ylabel("Number of transactions")
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, path)


def create_charts(analysis, charts_dir):
    """Create the four PNG charts. Returns the list of file paths."""
    charts_dir = Path(charts_dir)
    merged = analysis["merged"]
    return [
        chart_line(merged, charts_dir / "1_line_cumulative_cost.png"),
        chart_bar(merged, charts_dir / "2_bar_cost_by_site_supplier.png"),
        chart_scatter(merged, analysis["quantities"], charts_dir / "3_scatter_cost_vs_volume.png"),
        chart_histogram(merged, charts_dir / "4_histogram_transaction_costs.png"),
    ]


# ============================================================================
# 6. Run everything + export
# ============================================================================
def run_analysis(registry, purchases_path, prices_path):
    """Full pipeline: load -> clean -> merge -> tables. Returns a dictionary."""
    elements_df = elements_dataframe(registry)
    prices, rejected_prices = load_prices(prices_path)
    raw = load_purchases(purchases_path)
    clean, rejected_purchases = clean_purchases(raw, set(elements_df["element_id"]), prices)
    merged = merge_purchases(clean, prices, elements_df)

    rejected = pd.concat([rejected_report(rejected_prices, "prices"),
                          rejected_report(rejected_purchases, "purchases")],
                         ignore_index=True)
    return {
        "elements": elements_df,
        "quantities": pd.DataFrame(registry.quantity_rows()),
        "prices": prices,
        "raw_rows": len(raw),
        "clean": clean,
        "rejected": rejected,
        "merged": merged,
        "cost_by_site": cost_by(merged, "site"),
        "cost_by_supplier": cost_by(merged, "supplier_id"),
        "cost_by_month": cost_by(merged, "month"),
        "cost_detail": cost_by_site_supplier_month(merged),
        "comparison": required_vs_purchased(registry, merged, prices),
    }


def export_reports(analysis, reports_dir):
    """Write all report tables to CSV. Returns the list of file paths."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    merged = analysis["merged"].copy()
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    files = {
        "cleaned_purchases.csv": merged.round(4),
        "rejected_records.csv": analysis["rejected"],
        "cost_by_site.csv": analysis["cost_by_site"],
        "cost_by_supplier.csv": analysis["cost_by_supplier"],
        "cost_by_month.csv": analysis["cost_by_month"],
        "cost_by_site_supplier_month.csv": analysis["cost_detail"],
        "required_vs_purchased.csv": analysis["comparison"],
    }
    paths = []
    for name, table in files.items():
        table.to_csv(reports_dir / name, index=False)
        paths.append(reports_dir / name)
    return paths


def export_scenario(table, summary, path):
    """Save the scenario table with a TOTAL row."""
    total = {"material": "TOTAL", "unit": "", "required_qty": np.nan,
             "lowest_price": np.nan, "new_price": np.nan,
             "cost_before": summary["total_before"],
             "cost_after": summary["total_after"],
             "cost_change": summary["total_change"]}
    out = pd.concat([table, pd.DataFrame([total])], ignore_index=True).round(4)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return Path(path)

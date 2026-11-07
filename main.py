"""
Construction Materials Cost Planner - main menu
===============================================
Connects Module 1 (quantities) and Module 2 (purchases and costs).

Run:  python main.py          -> interactive menu
      python main.py --all    -> run everything without questions
"""

import sys
from pathlib import Path

import module1_quantities as m1
import module2_costs as m2

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = BASE_DIR / "charts"

ELEMENTS_CSV = DATA_DIR / "elements.csv"
PRICES_CSV = DATA_DIR / "prices.csv"
PURCHASES_CSV = DATA_DIR / "purchases.csv"

MENU = """
=========== Construction Materials Cost Planner ===========
 MODULE 1 - Material quantities
   1. Add element
   2. List elements
   3. Search elements
   4. Update element
   5. Calculate quantities and save to CSV
 MODULE 2 - Purchases and costs
   6. Clean data, analyse costs and export reports
   7. Price-increase scenario (NumPy)
   8. Create charts (PNG)
 OTHER
   9. Run everything (5 + 6 + 8)
   0. Exit
===========================================================
"""


# ----------------------------------------------------------------------------
# Input helpers: keep asking until the value is valid
# ----------------------------------------------------------------------------
def ask(prompt, parser, keep_if_blank=None):
    """Ask until parser(value) succeeds. Blank keeps the old value if given."""
    while True:
        text = input(prompt).strip()
        if text == "" and keep_if_blank is not None:
            return keep_if_blank
        try:
            return parser(text)
        except m1.ValidationError as error:
            print(f"  ! {error}")


def print_elements(elements):
    if not elements:
        print("  (no elements found)")
        return
    print(f"  {'ID':<5} {'Name':<12} {'Site':<7} {'Dimensions (L x W x H)':<26} Waste")
    for element in elements:
        print("  " + str(element))


def print_table(df, title):
    print(f"\n--- {title} ---")
    print(df.to_string(index=False))


# ----------------------------------------------------------------------------
# Module 1 actions
# ----------------------------------------------------------------------------
def add_element(registry):
    def new_id(text):
        element_id = m1.normalize_id(text, "Element ID")
        if registry.has(element_id):
            raise m1.DuplicateIDError(f"Element ID '{element_id}' already exists.")
        return element_id

    element_id = ask("Element ID (e.g. E09): ", new_id)
    name = ask("Name: ", lambda t: m1.parse_text(t, "Name"))
    site = ask("Site: ", lambda t: m1.parse_text(t, "Site"))
    length = ask("Length (m): ", lambda t: m1.parse_positive(t, "Length"))
    width = ask("Width (m): ", lambda t: m1.parse_positive(t, "Width"))
    height = ask("Height (m): ", lambda t: m1.parse_positive(t, "Height"))
    waste = ask("Waste % (0-100): ", m1.parse_waste)
    element = registry.add(m1.ConcreteElement(element_id, name, site,
                                              length, width, height, waste))
    registry.save_csv(ELEMENTS_CSV)
    print(f"Added: {element}")


def search_elements(registry):
    keyword = ask("Search (ID, name or site): ", lambda t: m1.parse_text(t, "Keyword"))
    print_elements(registry.search(keyword))


def update_element(registry):
    element_id = ask("Element ID to update: ",
                     lambda t: registry.get(t).element_id)
    current = registry.get(element_id)
    print("Current:", current)
    print("Press Enter to keep the current value.")
    changes = {
        "name": ask(f"Name [{current.name}]: ",
                    lambda t: m1.parse_text(t, "Name"), current.name),
        "site": ask(f"Site [{current.site}]: ",
                    lambda t: m1.parse_text(t, "Site"), current.site),
        "length": ask(f"Length m [{current.length:g}]: ",
                      lambda t: m1.parse_positive(t, "Length"), current.length),
        "width": ask(f"Width m [{current.width:g}]: ",
                     lambda t: m1.parse_positive(t, "Width"), current.width),
        "height": ask(f"Height m [{current.height:g}]: ",
                      lambda t: m1.parse_positive(t, "Height"), current.height),
        "waste_pct": ask(f"Waste % [{current.waste_pct:g}]: ",
                         m1.parse_waste, current.waste_pct),
    }
    updated = registry.update(element_id, **changes)
    registry.save_csv(ELEMENTS_CSV)
    print("Updated:", updated)


def calculate_quantities(registry):
    import pandas as pd
    registry.save_quantities(REPORTS_DIR / "quantities_per_element.csv",
                             REPORTS_DIR / "quantities_per_site.csv")
    print_table(pd.DataFrame(registry.quantity_rows()), "Quantities per element")
    print_table(pd.DataFrame(registry.quantities_by_site()), "Quantities per site")
    top = registry.top_elements(3)
    print("\nLargest 3 elements:", ", ".join(e.element_id for e in top))
    print(f"Saved CSV files in: {REPORTS_DIR}")


# ----------------------------------------------------------------------------
# Module 2 actions
# ----------------------------------------------------------------------------
def get_analysis(state, registry):
    """Run the analysis once and reuse it until the elements change."""
    if state.get("analysis") is None:
        state["analysis"] = m2.run_analysis(registry, PURCHASES_CSV, PRICES_CSV)
    return state["analysis"]


def cost_analysis(state, registry):
    analysis = get_analysis(state, registry)
    print(f"\nPurchase rows read: {analysis['raw_rows']} | "
          f"kept: {len(analysis['clean'])} | "
          f"rejected: {len(analysis['rejected'])}")
    if not analysis["rejected"].empty:
        print_table(analysis["rejected"], "Rejected records (cleaning log)")
    print_table(analysis["cost_by_site"], "Cost per site")
    print_table(analysis["cost_by_supplier"], "Cost per supplier")
    print_table(analysis["cost_by_month"], "Cost per month")

    comparison = analysis["comparison"]
    summary = comparison.groupby("status").size()
    print("\n--- Required vs purchased (per element and material) ---")
    for status, count in summary.items():
        print(f"  {status}: {count}")
    print_table(comparison[comparison["status"] != "Balanced"].head(10),
                "First 10 shortages / surpluses")
    paths = m2.export_reports(analysis, REPORTS_DIR)
    print(f"\nSaved {len(paths)} CSV reports in: {REPORTS_DIR}")


def scenario(state, registry):
    prices, _ = m2.load_prices(PRICES_CSV)
    baseline = m2.lowest_prices(prices)
    print("Lowest price per material:",
          {m: float(baseline[m]) for m in m1.MATERIALS})
    material = ask(f"Material ({'/'.join(m1.MATERIALS)}): ",
                   lambda t: _choose_material(t))
    pct = ask("Price increase (%): ",
              lambda t: m1.parse_positive(t, "Price increase percentage"))
    table, summary = m2.price_increase_scenario(
        registry.total_required(), baseline, material, pct)
    print_table(table, f"{material} +{pct:g}% (required quantities, lowest prices)")
    print(f"\nTotal before: {summary['total_before']:.2f} | "
          f"after: {summary['total_after']:.2f} | "
          f"change: {summary['total_change']:+.2f} ({summary['change_pct']:+.2f}%)")
    path = m2.export_scenario(table, summary, REPORTS_DIR / "price_scenario.csv")
    print(f"Saved: {path}")


def _choose_material(text):
    name = text.strip().title()
    if name not in m1.MATERIALS:
        raise m1.ValidationError(f"Material must be one of: {', '.join(m1.MATERIALS)}")
    return name


def make_charts(state, registry):
    analysis = get_analysis(state, registry)
    for path in m2.create_charts(analysis, CHARTS_DIR):
        print("Saved:", path)


def run_everything(state, registry):
    calculate_quantities(registry)
    cost_analysis(state, registry)
    make_charts(state, registry)


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def load_registry():
    registry = m1.ElementRegistry()
    loaded, errors = registry.load_csv(ELEMENTS_CSV)
    print(f"Loaded {loaded} elements from {ELEMENTS_CSV.name}"
          f" across {len(registry.sites())} sites.")
    for message in errors:
        print("  skipped ->", message)
    return registry


def main():
    registry = load_registry()
    state = {"analysis": None}

    if "--all" in sys.argv:
        run_everything(state, registry)
        return

    # menu choice -> (function, needs_reset_of_analysis)
    actions = {
        "1": lambda: add_element(registry),
        "2": lambda: print_elements(registry.list_all()),
        "3": lambda: search_elements(registry),
        "4": lambda: update_element(registry),
        "5": lambda: calculate_quantities(registry),
        "6": lambda: cost_analysis(state, registry),
        "7": lambda: scenario(state, registry),
        "8": lambda: make_charts(state, registry),
        "9": lambda: run_everything(state, registry),
    }
    changes_elements = {"1", "4"}

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            break
        if choice not in actions:
            print("Please choose a number from 0 to 9.")
            continue
        try:
            actions[choice]()
            if choice in changes_elements:
                state["analysis"] = None      # elements changed -> re-analyse
        except (m1.ValidationError, FileNotFoundError, KeyError) as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()

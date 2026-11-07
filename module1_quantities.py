"""
Module 1 - Material Quantity Calculator
=======================================
Represents concrete elements, validates them, calculates concrete volume
and the required cement / sand / aggregate, and saves everything to CSV.

Formulas (training rates from the assignment):
    net volume (m3)        = length x width x height
    volume with waste (m3) = net volume x (1 + waste% / 100)
    cement (kg)            = 300 x volume with waste
    sand (m3)              = 0.5 x volume with waste
    aggregate (m3)         = 0.8 x volume with waste
"""

import csv
import math
from pathlib import Path

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
RATES = {"Cement": 300.0, "Sand": 0.5, "Aggregate": 0.8}   # per 1 m3 incl. waste
UNITS = {"Cement": "kg", "Sand": "m3", "Aggregate": "m3"}
MATERIALS = ("Cement", "Sand", "Aggregate")                 # tuple: fixed order

# Column order of the elements CSV file (tuple = never changes)
ELEMENT_FIELDS = ("element_id", "element_name", "site",
                  "length_m", "width_m", "height_m", "waste_pct")


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------
class ValidationError(ValueError):
    """Raised when an input value is not valid."""


class DuplicateIDError(ValidationError):
    """Raised when a record ID already exists."""


class UnknownIDError(ValidationError):
    """Raised when a record ID does not exist."""


# ----------------------------------------------------------------------------
# Small validation helpers (also used by main.py for the prompts)
# ----------------------------------------------------------------------------
def parse_text(value, label):
    """Return a stripped, non-empty string."""
    text = str(value).strip()
    if not text:
        raise ValidationError(f"{label} must not be empty.")
    return text


def parse_number(value, label):
    """Return a finite float or raise ValidationError."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number.") from None
    if not math.isfinite(number):
        raise ValidationError(f"{label} must be a finite number.")
    return number


def parse_positive(value, label):
    """Dimensions, prices and quantities must be greater than zero."""
    number = parse_number(value, label)
    if number <= 0:
        raise ValidationError(f"{label} must be greater than 0.")
    return number


def parse_waste(value):
    """Waste percentage must be between 0 and 100 (inclusive)."""
    number = parse_number(value, "Waste percentage")
    if not 0 <= number <= 100:
        raise ValidationError("Waste percentage must be between 0 and 100.")
    return number


def normalize_id(value, label="ID"):
    """IDs are stored upper-case without spaces, e.g. ' e01 ' -> 'E01'."""
    return parse_text(value, label).upper()


# ----------------------------------------------------------------------------
# Class: ConcreteElement
# ----------------------------------------------------------------------------
class ConcreteElement:
    """One concrete element (footing, column, beam, slab, wall ...)."""

    def __init__(self, element_id, name, site, length, width, height, waste_pct):
        self.element_id = normalize_id(element_id, "Element ID")
        self.name = parse_text(name, "Element name")
        self.site = parse_text(site, "Site")
        self.length = parse_positive(length, "Length")
        self.width = parse_positive(width, "Width")
        self.height = parse_positive(height, "Height")
        self.waste_pct = parse_waste(waste_pct)

    # ---- calculations ----
    @property
    def net_volume(self):
        """Net volume in m3 = length x width x height."""
        return self.length * self.width * self.height

    @property
    def volume_with_waste(self):
        """Volume in m3 including the waste percentage."""
        return self.net_volume * (1 + self.waste_pct / 100)

    def material_quantities(self):
        """Return {'Cement': kg, 'Sand': m3, 'Aggregate': m3}."""
        volume = self.volume_with_waste
        return {material: volume * RATES[material] for material in MATERIALS}

    # ---- conversion ----
    def to_dict(self):
        """Dictionary that matches the columns of the elements CSV."""
        return {
            "element_id": self.element_id,
            "element_name": self.name,
            "site": self.site,
            "length_m": self.length,
            "width_m": self.width,
            "height_m": self.height,
            "waste_pct": self.waste_pct,
        }

    def quantity_row(self):
        """One row of the quantities report (rounded to 4 decimals)."""
        qty = self.material_quantities()
        return {
            "element_id": self.element_id,
            "element_name": self.name,
            "site": self.site,
            "net_volume_m3": round(self.net_volume, 4),
            "volume_with_waste_m3": round(self.volume_with_waste, 4),
            "cement_kg": round(qty["Cement"], 4),
            "sand_m3": round(qty["Sand"], 4),
            "aggregate_m3": round(qty["Aggregate"], 4),
        }

    def __str__(self):
        return (f"{self.element_id:<5} {self.name:<12} {self.site:<7} "
                f"{self.length:>6g} x {self.width:>5g} x {self.height:>5g} m  "
                f"waste {self.waste_pct:g}%")


# ----------------------------------------------------------------------------
# Class: ElementRegistry  (add / list / search / update + CSV)
# ----------------------------------------------------------------------------
class ElementRegistry:
    """Keeps all elements in a dictionary: {element_id: ConcreteElement}."""

    def __init__(self):
        self._elements = {}

    def __len__(self):
        return len(self._elements)

    # ---- add / get / list / search / update ----
    def add(self, element):
        """Add an element. Duplicate IDs are rejected."""
        if element.element_id in self._elements:
            raise DuplicateIDError(f"Element ID '{element.element_id}' already exists.")
        self._elements[element.element_id] = element
        return element

    def has(self, element_id):
        return str(element_id).strip().upper() in self._elements

    def get(self, element_id):
        key = str(element_id).strip().upper()
        if key not in self._elements:
            raise UnknownIDError(f"Unknown element ID '{key}'.")
        return self._elements[key]

    def list_all(self):
        """All elements as a list, sorted by ID."""
        return sorted(self._elements.values(), key=lambda e: e.element_id)

    def search(self, keyword):
        """Case-insensitive search in ID, name and site."""
        keyword = parse_text(keyword, "Search keyword").lower()
        return [e for e in self.list_all()
                if keyword in e.element_id.lower()
                or keyword in e.name.lower()
                or keyword in e.site.lower()]

    def update(self, element_id, **changes):
        """
        Update fields: name, site, length, width, height, waste_pct.
        A new element is built first, so if validation fails the old
        element stays unchanged.
        """
        allowed = {"name", "site", "length", "width", "height", "waste_pct"}
        bad_keys = set(changes) - allowed
        if bad_keys:
            raise ValidationError(f"Cannot update: {', '.join(sorted(bad_keys))}")
        current = self.get(element_id)
        data = {
            "name": current.name, "site": current.site,
            "length": current.length, "width": current.width,
            "height": current.height, "waste_pct": current.waste_pct,
        }
        data.update(changes)
        updated = ConcreteElement(current.element_id, **data)
        self._elements[current.element_id] = updated
        return updated

    def sites(self):
        """Set of the different site names."""
        return {e.site for e in self._elements.values()}

    # ---- quantities ----
    def quantity_rows(self):
        """Quantities per element (list of dictionaries)."""
        return [e.quantity_row() for e in self.list_all()]

    def quantities_by_site(self):
        """Quantities per site (list of dictionaries, sorted by site)."""
        rows = []
        for site in sorted(self.sites()):
            members = [e for e in self.list_all() if e.site == site]
            rows.append({
                "site": site,
                "elements": len(members),
                "net_volume_m3": round(sum(e.net_volume for e in members), 4),
                "volume_with_waste_m3": round(sum(e.volume_with_waste for e in members), 4),
                "cement_kg": round(sum(e.material_quantities()["Cement"] for e in members), 4),
                "sand_m3": round(sum(e.material_quantities()["Sand"] for e in members), 4),
                "aggregate_m3": round(sum(e.material_quantities()["Aggregate"] for e in members), 4),
            })
        return rows

    def total_required(self):
        """Total required quantity per material for all elements."""
        totals = dict.fromkeys(MATERIALS, 0.0)
        for element in self._elements.values():
            for material, qty in element.material_quantities().items():
                totals[material] += qty
        return totals

    def top_elements(self, n=3):
        """The n elements with the largest volume (uses slicing)."""
        ranked = sorted(self._elements.values(),
                        key=lambda e: e.volume_with_waste, reverse=True)
        return ranked[:n]

    # ---- CSV ----
    def load_csv(self, path):
        """
        Load elements from a CSV file.
        Returns (number_loaded, list_of_error_messages).
        Invalid rows are skipped and reported, not silently accepted.
        """
        loaded, errors = 0, []
        with open(path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for line_no, row in enumerate(reader, start=2):
                try:
                    self.add(ConcreteElement(
                        row["element_id"], row["element_name"], row["site"],
                        row["length_m"], row["width_m"], row["height_m"],
                        row["waste_pct"]))
                    loaded += 1
                except (ValidationError, KeyError, TypeError) as error:
                    errors.append(f"Line {line_no}: {error}")
        return loaded, errors

    def save_csv(self, path):
        """Save the element data."""
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=ELEMENT_FIELDS)
            writer.writeheader()
            for element in self.list_all():
                writer.writerow(element.to_dict())

    def save_quantities(self, element_path, site_path):
        """Save calculated quantities per element and per site."""
        for path, rows in ((element_path, self.quantity_rows()),
                           (site_path, self.quantities_by_site())):
            if not rows:
                raise ValidationError("No elements to calculate.")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

"""
Product & Company Config Loader

Loads config/company.yaml and config/products.yaml, replacing the old
src/knowledge.py that loaded from JSON files.
"""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_company_config() -> dict:
    """Load company profile from config/company.yaml."""
    return _load_yaml("company.yaml")


def load_products_config() -> dict:
    """Load full product catalog from config/products.yaml."""
    return _load_yaml("products.yaml")


def get_company_profile_string(config: dict | None = None) -> str:
    """Build a human-readable company profile string."""
    if config is None:
        config = load_company_config()
    lines = [
        f"{config['name']} is a {config.get('industry', 'technology')} company "
        f"based in {config['location']}.",
    ]
    for v in config.get("stats", {}).values():
        lines.append(f"- {v}")
    contact = config.get("contact", {})
    if contact:
        lines.append(f"- Contact: {contact.get('email', '')} | {contact.get('phone', '')}")
    return "\n".join(lines)


def get_short_description(config: dict | None = None) -> str:
    """Get the ~50-token company summary for agents that don't need full context."""
    if config is None:
        config = load_company_config()
    return config.get("short_description", config["name"])


def get_full_product_context(company_config: dict | None = None, products_config: dict | None = None) -> str:
    """Returns formatted product knowledge for agent context.

    This is the equivalent of the old knowledge.get_full_product_context() but
    loads from YAML config instead of JSON data files.
    """
    if company_config is None:
        company_config = load_company_config()
    if products_config is None:
        products_config = load_products_config()

    company_profile = get_company_profile_string(company_config)
    combo = products_config["combined_solution"]
    icp = products_config["ideal_customer"]
    case_studies = products_config["case_studies"]

    sections = [
        "=== COMPANY OVERVIEW ===",
        company_profile,
        "",
    ]

    # Dynamically build sections for each product
    for i, (key, product) in enumerate(products_config["products"].items(), 1):
        category = product.get("category", "Product")
        sections.extend([
            f"=== PRODUCT {i}: {product['name']} ({category}) ===",
            f"{product['name']} — {product['tagline']}",
            product["description"].strip(),
            "",
            "Key Features:",
            *[f"- {f}" for f in product["key_features"]],
            "",
        ])

        # Key functions can be a list or dict
        if isinstance(product.get("key_functions"), list):
            sections.append("Key Functions:")
            sections.extend([f"- {f}" for f in product["key_functions"]])
        elif isinstance(product.get("key_functions"), dict):
            sections.append("Key Functions:")
            sections.extend([f"- {k}: {v}" for k, v in product["key_functions"].items()])
        sections.append("")

        if "expected_benefits" in product:
            sections.append("Expected Benefits:")
            sections.extend([f"- {b}" for b in product["expected_benefits"]])
            sections.append("")

        if "implementation_benefits" in product:
            sections.append("Implementation Benefits:")
            sections.extend([f"- {k}: {v}" for k, v in product["implementation_benefits"].items()])
            sections.append("")

        sections.append(f"Best For: {', '.join(product['best_for'])}")
        sections.append("")

        if "specs" in product:
            sections.append(f"Hardware Specs: {product['specs']}")
            sections.append("")

    sections.extend([
        f"=== COMBINED SOLUTION: {combo['name']} ===",
        combo["description"].strip(),
        "",
        "Synergies:",
        *[f"- {s}" for s in combo["synergies"]],
        "",
        "Ideal Customer Pain Points:",
        *[f"- {p}" for p in icp["pain_points"]],
        "",
        "Typical ROI:",
        *[f"- {k}: {v}" for k, v in icp["typical_roi"].items()],
        "",
        "=== CASE STUDIES ===",
        *[f"- {cs['title']}: {cs['solution']} -> {cs['result']}" for cs in case_studies],
    ])

    return "\n".join(sections)


# ── Module-level convenience (loaded on import) ──

COMPANY_CONFIG = load_company_config()
PRODUCTS_CONFIG = load_products_config()
COMPANY_PROFILE = get_company_profile_string(COMPANY_CONFIG)
SHORT_DESCRIPTION = get_short_description(COMPANY_CONFIG)

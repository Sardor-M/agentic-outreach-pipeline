"""
Extraction Schemas — Define what structured data to extract from web pages.

Used by the LangExtract extractor to pull specific facts from raw text.
Each schema defines fields and their descriptions for a specific extraction domain.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


# Default schemas (used if config/extraction_schemas.yaml is not found)
DEFAULT_SCHEMAS = {
    "company_facts": {
        "description": "General company facts from a web page",
        "fields": {
            "company_name": "The official company name",
            "industry": "What industry the company operates in",
            "products": "What products or services they offer",
            "location": "Where the company is headquartered or operates",
            "employee_count": "Number of employees if mentioned",
            "revenue": "Revenue or financial figures if mentioned",
            "key_customers": "Notable customers or clients mentioned",
            "certifications": "Any quality or industry certifications (ISO, etc.)",
        },
    },
    "manufacturing": {
        "description": "Manufacturing-specific facts",
        "fields": {
            "equipment_types": "Types of manufacturing equipment used (presses, CNC, etc.)",
            "machine_count": "Number of machines or production lines",
            "production_capacity": "Production volume or capacity figures",
            "materials": "Materials processed (metals, plastics, etc.)",
            "processes": "Manufacturing processes used (stamping, forging, molding, etc.)",
            "factory_size": "Factory floor area or number of facilities",
        },
    },
    "esg": {
        "description": "ESG and sustainability information",
        "fields": {
            "esg_initiatives": "Environmental, social, or governance initiatives",
            "carbon_reporting": "Carbon emission reporting or reduction goals",
            "certifications": "ESG-related certifications (ISO 14001, etc.)",
            "sustainability_goals": "Stated sustainability targets or commitments",
            "energy_sources": "Energy sources used (solar, grid, etc.)",
        },
    },
    "financial": {
        "description": "Financial and business information",
        "fields": {
            "revenue": "Annual revenue or sales figures",
            "growth": "Growth rates or trends",
            "investments": "Recent investments or capex",
            "market_share": "Market share or competitive position",
            "funding": "Funding rounds or financial backing",
        },
    },
}


def load_extraction_schemas() -> dict:
    """Load extraction schemas from YAML config or use defaults."""
    config_path = CONFIG_DIR / "extraction_schemas.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return DEFAULT_SCHEMAS


def get_schema(schema_name: str) -> dict | None:
    """Get a specific extraction schema by name."""
    schemas = load_extraction_schemas()
    return schemas.get(schema_name)


def get_all_field_descriptions(schema_name: str = "company_facts") -> str:
    """Get a formatted string of field descriptions for use in prompts."""
    schema = get_schema(schema_name)
    if not schema:
        return ""
    lines = [f"Extract the following from the text:"]
    for field, desc in schema.get("fields", {}).items():
        lines.append(f"- {field}: {desc}")
    return "\n".join(lines)

"""
3View Product Knowledge Base
Scoped to: Machine365.Ai + MV900 only

This module contains structured product knowledge that agents use
to map customer problems to 3View solutions.
"""

COMPANY_PROFILE = """
3View Inc. is a South Korean smart manufacturing company based in Seongnam-si, Gyeonggi-do.
- 500+ client companies worldwide
- 30+ countries served
- 100+ Smart Factory projects delivered
- 100% in-house technology
- $1M+ export value (2024)
- Contact: 3viewsales@e3view.com | +82-31-776-0677
"""

MV900_KNOWLEDGE = {
    "name": "MV900",
    "category": "Process Monitoring System (Hardware)",
    "tagline": "A New Era in Smart Process Monitoring",
    "description": (
        "The MV900 is a process monitoring system that analyzes sensor signals "
        "in real time on metal forming sites to monitor product and equipment conditions. "
        "During forming, equipment pressure is monitored to stop machines instantly when "
        "defects occur, preventing continuous errors. Combined with sensors and AI, it tracks "
        "4M, power, and equipment changes for real-time production management."
    ),
    "specs": {
        "display": "15-inch Touch Interface",
        "os": "Windows IoT 10",
        "size": "393x317x74 mm (WxHxD)",
        "power": "DC12V",
        "channels": "8 channels",
        "communication": "WiFi, 1x Ethernet, 2x USB 2.0",
        "cycle_signal": "Proximity sensor or Encoder",
        "io_ports": "Input 4 ports, Output 6 ports",
    },
    "key_features": [
        "Flexible application and expansion — adaptable to changing factory environments",
        "AI-powered detection of changes in equipment status for predictive maintenance",
        "Hyperconnectivity — cloud-connected for real-time monitoring anywhere",
        "Product-level carbon calculation for ESG reporting",
    ],
    "key_functions": [
        "Catch defective products early via real-time press force analysis",
        "Detect mold damage early through sensor signal monitoring",
        "Detect equipment abnormalities before they cause downtime",
        "Mold life management — extend mold lifespan through smart monitoring",
        "Manage production items efficiently with real-time tracking",
        "Emergency equipment shutdown when critical defects are detected",
    ],
    "expected_benefits": [
        "Cut mold costs — extend mold life through smart monitoring",
        "Predictive maintenance — instant detection of equipment issues",
        "Lower defect rate — real-time monitoring stops defects before they happen",
        "Lower energy costs — optimize electricity rates through AI power analysis",
        "Streamline ESG management — automate energy and carbon tracking",
    ],
    "best_for": [
        "Metal forming / stamping factories",
        "Press machine operations",
        "Forging operations",
        "Any factory with mechanical presses needing defect detection",
    ],
}

MACHINE365_KNOWLEDGE = {
    "name": "Machine365.Ai",
    "category": "Integrated Equipment Monitoring Platform (Software)",
    "tagline": "Integrated Equipment Monitoring Solution for Achieving ESG",
    "description": (
        "Machine365.Ai is an integrated equipment monitoring system that captures "
        "real-time production data — power usage, output, and PLC signals — to deliver "
        "complete visibility into operations. With instant alerts on anomalies, it empowers "
        "factories to act fast, minimize downtime, and maximize performance."
    ),
    "key_features": [
        "Integrated Equipment Management — manage all equipment in a single system",
        "AI & ML-Based Analysis — anomaly detection and predictive maintenance",
        "Flexible Installation & Scalability — works with older equipment via sensors/gateways",
        "Easy Accessibility — browser-based, works on PC/tablet/mobile, no software install",
        "Automatic updates — always up-to-date with zero manual work",
    ],
    "key_functions": {
        "ai_power_monitoring": (
            "Real-time and monthly cumulative power consumption by equipment or panel. "
            "Real-time peak monitoring for power management."
        ),
        "ai_electricity_cost": (
            "Real-time KEPCO electricity rates. Usage and cost trend analysis by load time periods."
        ),
        "energy_monitoring": (
            "Energy consumption per product measurement. Cross-equipment comparison."
        ),
        "carbon_emission_monitoring": (
            "Automatic carbon emission calculation to support climate change reduction efforts."
        ),
        "ai_power_quality": (
            "Real-time voltage, current, reactive power, power factor monitoring. "
            "Alerts on abnormal patterns."
        ),
        "ai_defect_detection": (
            "Defect identification with root cause analysis. Alerts on exact defect timing. "
            "Defect prediction via press force trend analysis."
        ),
        "operational_status": (
            "Operating and downtime visualization per machine. "
            "Operation/stop time tracking. Defect detection timestamps with MV integration."
        ),
        "production_monitoring": (
            "Production speed trends. Products per minute (SPM). "
            "Average SPM and energy consumption per product."
        ),
        "plc_data_monitoring": (
            "PLC data: bearing temperature, production quantity, SPM. "
            "Alerts on PLC abnormalities."
        ),
    },
    "implementation_benefits": {
        "esg": "Automatic power consumption and carbon emission calculation. ESG report indicators.",
        "downtime_reduction": "Equipment downtime notifications. Defect and anomaly alerts.",
        "cost_reduction": "Peak power advance alerts. AI-powered electricity cost forecasting.",
        "production_optimization": "Weekly/monthly production analysis reports. Equipment status history.",
        "quality_improvement": "Press force peak trend analysis. Defect detection history tracking.",
    },
    "best_for": [
        "Any manufacturing facility wanting energy cost reduction",
        "Factories needing ESG compliance and carbon tracking",
        "Operations with multiple equipment types needing unified monitoring",
        "Legacy factories wanting to retrofit smart monitoring without replacing equipment",
    ],
}

# Combined solution: MV900 + Machine365.Ai
COMBINED_SOLUTION = {
    "name": "MV900 + Machine365.Ai Bundle",
    "description": (
        "The most powerful configuration: MV900 hardware on each press/forming machine "
        "for real-time process monitoring and defect detection, feeding data into Machine365.Ai "
        "cloud platform for integrated energy management, AI analytics, and ESG reporting."
    ),
    "synergies": [
        "MV900 captures real-time sensor data → Machine365.Ai analyzes trends across all equipment",
        "MV900 detects defects at machine level → Machine365.Ai tracks defect patterns across factory",
        "MV900 monitors press force per unit → Machine365.Ai calculates energy and carbon per product",
        "MV900 enables emergency shutdown → Machine365.Ai provides predictive maintenance to prevent shutdowns",
    ],
    "ideal_customer_profile": {
        "industry": "Metal forming, stamping, forging, pressing, automotive parts, copper/brass fittings",
        "factory_size": "10+ press machines or forming equipment",
        "pain_points": [
            "High energy costs with no visibility into consumption per product",
            "Frequent defects or mold damage causing production delays",
            "ESG compliance requirements (especially EU regulations)",
            "No real-time visibility into equipment status",
            "High maintenance costs from reactive (not predictive) maintenance",
            "Manual production tracking and reporting",
        ],
        "typical_roi": {
            "energy_savings": "15-30% reduction in electricity costs",
            "defect_reduction": "Up to 40% fewer defective products",
            "downtime_reduction": "25-50% less unplanned downtime",
            "mold_life": "20-35% extension in mold lifespan",
            "maintenance": "30-40% reduction in maintenance costs",
        },
    },
}

CASE_STUDIES = [
    {
        "title": "Forging Company S",
        "solution": "MV900 + Machine365.Ai + Real-Time PLC Data System",
        "result": "Improved productivity and maintenance efficiency with smart process monitoring and equipment power management.",
        "tags": ["AI Agent", "Predictive Maintenance", "Manufacturing"],
    },
    {
        "title": "Copper Pipe and Fitting Manufacturer",
        "solution": "Machine365.Ai",
        "result": "Reduced high energy costs and inefficiencies. Real-time data-driven energy management for cost savings and stable production.",
        "tags": ["AI Agent", "Predictive Maintenance", "Manufacturing"],
    },
    {
        "title": "Plastic Manufacturing Company",
        "solution": "Machine365.Ai",
        "result": "Solved high energy costs and inefficient injection molding management. Reduced production costs and achieved sustainable manufacturing.",
        "tags": ["Predictive Analysis", "Manufacturing"],
    },
    {
        "title": "Printing Specialist Manufacturer (Europe)",
        "solution": "Machine365.Ai",
        "result": "Addressed rising energy costs and product cost calculation difficulties. Achieved sustainable growth and improved competitiveness in European market.",
        "tags": ["AI Platform", "Prediction Analysis", "Optimization", "Manufacturing"],
    },
]


def get_full_product_context() -> str:
    """Returns formatted product knowledge for agent context."""
    return f"""
=== 3VIEW COMPANY OVERVIEW ===
{COMPANY_PROFILE}

=== PRODUCT 1: MV900 (Hardware) ===
{MV900_KNOWLEDGE['name']} — {MV900_KNOWLEDGE['tagline']}
{MV900_KNOWLEDGE['description']}

Key Features:
{chr(10).join(f'- {f}' for f in MV900_KNOWLEDGE['key_features'])}

Key Functions:
{chr(10).join(f'- {f}' for f in MV900_KNOWLEDGE['key_functions'])}

Expected Benefits:
{chr(10).join(f'- {b}' for b in MV900_KNOWLEDGE['expected_benefits'])}

Best For: {', '.join(MV900_KNOWLEDGE['best_for'])}

Hardware Specs: {MV900_KNOWLEDGE['specs']}

=== PRODUCT 2: Machine365.Ai (Software Platform) ===
{MACHINE365_KNOWLEDGE['name']} — {MACHINE365_KNOWLEDGE['tagline']}
{MACHINE365_KNOWLEDGE['description']}

Key Features:
{chr(10).join(f'- {f}' for f in MACHINE365_KNOWLEDGE['key_features'])}

Key Functions:
{chr(10).join(f'- {k}: {v}' for k, v in MACHINE365_KNOWLEDGE['key_functions'].items())}

Implementation Benefits:
{chr(10).join(f'- {k}: {v}' for k, v in MACHINE365_KNOWLEDGE['implementation_benefits'].items())}

Best For: {', '.join(MACHINE365_KNOWLEDGE['best_for'])}

=== COMBINED SOLUTION: MV900 + Machine365.Ai ===
{COMBINED_SOLUTION['description']}

Synergies:
{chr(10).join(f'- {s}' for s in COMBINED_SOLUTION['synergies'])}

Ideal Customer Pain Points:
{chr(10).join(f'- {p}' for p in COMBINED_SOLUTION['ideal_customer_profile']['pain_points'])}

Typical ROI:
{chr(10).join(f'- {k}: {v}' for k, v in COMBINED_SOLUTION['ideal_customer_profile']['typical_roi'].items())}

=== CASE STUDIES ===
{chr(10).join(f'- {cs["title"]}: {cs["solution"]} → {cs["result"]}' for cs in CASE_STUDIES)}
"""

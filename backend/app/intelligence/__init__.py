"""The Intelligence Layer.

Six ordered layers, each independent, each enriching the output of the one
before it and writing only to its own result table:

1. :mod:`~app.intelligence.anomaly` — detect abnormal behaviour
2. :mod:`~app.intelligence.predictive` — forecast failure
3. :mod:`~app.intelligence.preventive` — schedule maintenance before it
4. :mod:`~app.intelligence.prescriptive` — recommend the best action
5. :mod:`~app.intelligence.apm` — measure performance and business value
6. :mod:`~app.intelligence.oee` — measure operational efficiency
"""

from app.intelligence.context import (
    AssetWindow,
    ChannelStats,
    IntelligenceContext,
    build_context,
)
from app.intelligence.runner import IntelligenceRunner, intelligence_runner
from app.intelligence.summaries import build_intelligence_summary

__all__ = [
    "AssetWindow",
    "ChannelStats",
    "IntelligenceContext",
    "IntelligenceRunner",
    "build_context",
    "build_intelligence_summary",
    "intelligence_runner",
]

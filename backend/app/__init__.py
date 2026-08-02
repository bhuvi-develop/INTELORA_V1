"""INTELORA — Enterprise AIOT Intelligence Platform (backend).

Layer map:

* :mod:`app.digital_twin` — Device Layer (virtual assets)
* :mod:`app.services.telemetry_service` — Telemetry Layer
* :mod:`app.intelligence` — Intelligence Layer (six ordered layers)
* :mod:`app.services.business_model`, :mod:`app.services.dashboard_service`
  — Business Intelligence Layer
* :mod:`app.routers`, :mod:`app.websocket` — the boundary the Presentation
  Layer talks to
"""

__version__ = "1.0.0"

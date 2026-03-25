"""Mock warehouse operations API — reference demo aligned with edge IT/OT warehouse narratives.

Not affiliated with Cisco products; synthetic data only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Warehouse Operations API",
    version="0.2.0",
    description="Mock inventory, operational events, and shipments for agent demos.",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


WAREHOUSES: list[dict[str, Any]] = [
    {
        "warehouse_id": "WH-EU-01",
        "name": "Rotterdam DC",
        "region": "EU",
        "shift": "morning",
        "tags": ["regional_hub", "cold_chain_capable"],
    },
    {
        "warehouse_id": "WH-US-W-01",
        "name": "Phoenix West FC",
        "region": "US-West",
        "shift": "night",
        "tags": ["ecommerce_fulfillment"],
    },
]

INVENTORY: list[dict[str, Any]] = [
    {
        "warehouse_id": "WH-EU-01",
        "sku": "SKU-BEV-440",
        "description": "Beverage crate 440ml",
        "quantity_on_hand": 120,
        "reorder_point": 200,
        "bin_zone": "A-12",
    },
    {
        "warehouse_id": "WH-EU-01",
        "sku": "SKU-SNACK-12P",
        "description": "Snack variety pack x12",
        "quantity_on_hand": 45,
        "reorder_point": 80,
        "bin_zone": "B-03",
    },
    {
        "warehouse_id": "WH-EU-01",
        "sku": "SKU-PALLET-STD",
        "description": "Standard shipping pallet",
        "quantity_on_hand": 8,
        "reorder_point": 15,
        "bin_zone": "YARD-1",
    },
    {
        "warehouse_id": "WH-US-W-01",
        "sku": "SKU-BEV-440",
        "description": "Beverage crate 440ml",
        "quantity_on_hand": 890,
        "reorder_point": 400,
        "bin_zone": "R-01",
    },
    {
        "warehouse_id": "WH-US-W-01",
        "sku": "SKU-LITH-9K",
        "description": "Lithium battery module 9kWh",
        "quantity_on_hand": 6,
        "reorder_point": 12,
        "bin_zone": "SECURE-C",
    },
    {
        "warehouse_id": "WH-US-W-01",
        "sku": "SKU-HVAC-FILTER",
        "description": "HVAC filter MERV-13",
        "quantity_on_hand": 22,
        "reorder_point": 40,
        "bin_zone": "M-09",
    },
]

EVENTS: list[dict[str, Any]] = [
    {
        "event_id": "EV-2041",
        "type": "stockout_risk",
        "severity": "critical",
        "title": "Pallet lane A-12 projected stockout before morning shift",
        "warehouse_id": "WH-EU-01",
        "sku": "SKU-BEV-440",
        "status": "open",
        "source": "synthetic_vision",
        "detail": "Computer-vision estimate: empty faces increasing over last 45 min.",
        "created_at": "2026-03-25T04:10:00+00:00",
        "acknowledged_at": None,
    },
    {
        "event_id": "EV-2042",
        "type": "low_stock",
        "severity": "warning",
        "title": "Snack SKU below reorder threshold",
        "warehouse_id": "WH-EU-01",
        "sku": "SKU-SNACK-12P",
        "status": "open",
        "source": "wms_feed",
        "detail": "Quantity 45 vs reorder 80.",
        "created_at": "2026-03-25T04:22:00+00:00",
        "acknowledged_at": None,
    },
    {
        "event_id": "EV-2038",
        "type": "safety_hold",
        "severity": "warning",
        "title": "Quality hold on inbound lane 4",
        "warehouse_id": "WH-US-W-01",
        "sku": None,
        "status": "acknowledged",
        "source": "floor_supervisor",
        "detail": "Awaiting QA sign-off on batch L-7781.",
        "created_at": "2026-03-24T18:00:00+00:00",
        "acknowledged_at": "2026-03-24T18:45:00+00:00",
    },
    {
        "event_id": "EV-2039",
        "type": "low_stock",
        "severity": "info",
        "title": "HVAC filters trending down",
        "warehouse_id": "WH-US-W-01",
        "sku": "SKU-HVAC-FILTER",
        "status": "open",
        "source": "erp_projection",
        "detail": "Expected breach of reorder in ~36h at current pick rate.",
        "created_at": "2026-03-25T02:00:00+00:00",
        "acknowledged_at": None,
    },
]

PENDING_SHIPMENTS: list[dict[str, Any]] = [
    {"shipment_id": "SH-99102", "warehouse_id": "WH-EU-01", "carrier": "DHL", "cutoff_utc": "2026-03-25T07:00:00+00:00", "lines": 14},
    {"shipment_id": "SH-99118", "warehouse_id": "WH-US-W-01", "carrier": "FedEx", "cutoff_utc": "2026-03-25T15:30:00+00:00", "lines": 8},
]

ACTION_LOG: list[dict[str, Any]] = []


class AckBody(BaseModel):
    note: str | None = Field(None, description="Optional operator note")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "warehouse-ops"}


def _inventory_below_reorder(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["quantity_on_hand"] < r["reorder_point"]]


@app.get("/v1/operations/summary")
def operations_summary() -> dict[str, Any]:
    open_by_severity: dict[str, int] = {}
    for e in EVENTS:
        if e["status"] != "open":
            continue
        sev = e["severity"]
        open_by_severity[sev] = open_by_severity.get(sev, 0) + 1

    inv = list(INVENTORY)
    below = _inventory_below_reorder(inv)

    return {
        "generated_at": _utc_now(),
        "warehouses": len(WAREHOUSES),
        "open_events_by_severity": open_by_severity,
        "open_events_total": sum(1 for e in EVENTS if e["status"] == "open"),
        "skus_below_reorder": len(below),
        "pending_shipments": len(PENDING_SHIPMENTS),
        "next_cutoffs": [
            {"shipment_id": s["shipment_id"], "warehouse_id": s["warehouse_id"], "cutoff_utc": s["cutoff_utc"]}
            for s in sorted(PENDING_SHIPMENTS, key=lambda x: x["cutoff_utc"])
        ],
        "recent_actions": ACTION_LOG[-5:],
    }


@app.get("/v1/events")
def list_events(
    severity: str | None = Query(None, description="critical, warning, info"),
    event_type: str | None = Query(None, alias="type", description="stockout_risk, low_stock, safety_hold"),
    warehouse_id: str | None = Query(None),
    status: str | None = Query(None, description="open, acknowledged"),
    query: str | None = Query(None, description="Free text in title, sku, event_id"),
) -> dict[str, Any]:
    rows = list(EVENTS)
    if severity:
        rows = [e for e in rows if e["severity"] == severity.lower()]
    if event_type:
        rows = [e for e in rows if e["type"] == event_type.lower()]
    if warehouse_id:
        rows = [e for e in rows if e["warehouse_id"] == warehouse_id]
    if status:
        rows = [e for e in rows if e["status"] == status.lower()]
    if query:
        q = query.lower()
        rows = [
            e
            for e in rows
            if q in e["title"].lower()
            or q in e["event_id"].lower()
            or (e.get("sku") and q in e["sku"].lower())
        ]
    return {"count": len(rows), "events": rows}


@app.get("/v1/inventory")
def list_inventory(
    warehouse_id: str | None = Query(None),
    sku: str | None = Query(None),
    below_reorder: bool | None = Query(None, description="If true, only lines under reorder_point"),
    query: str | None = Query(None, description="Matches sku or description"),
) -> dict[str, Any]:
    rows = list(INVENTORY)
    if warehouse_id:
        rows = [r for r in rows if r["warehouse_id"] == warehouse_id]
    if sku:
        rows = [r for r in rows if r["sku"] == sku]
    if below_reorder is True:
        rows = _inventory_below_reorder(rows)
    if query:
        q = query.lower()
        rows = [r for r in rows if q in r["sku"].lower() or q in r["description"].lower()]
    return {"count": len(rows), "lines": rows}


@app.get("/v1/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: str) -> dict[str, Any]:
    wh = next((w for w in WAREHOUSES if w["warehouse_id"] == warehouse_id), None)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    inv = [r for r in INVENTORY if r["warehouse_id"] == warehouse_id]
    ev = [e for e in EVENTS if e["warehouse_id"] == warehouse_id]
    ship = [s for s in PENDING_SHIPMENTS if s["warehouse_id"] == warehouse_id]
    return {
        "warehouse": wh,
        "inventory_lines": len(inv),
        "below_reorder_count": len(_inventory_below_reorder(inv)),
        "open_events": [e for e in ev if e["status"] == "open"],
        "pending_shipments": ship,
    }


@app.post("/v1/events/{event_id}/acknowledge")
def acknowledge_event(event_id: str, body: AckBody | None = None) -> dict[str, Any]:
    for e in EVENTS:
        if e["event_id"] == event_id:
            if e["status"] == "acknowledged":
                return {"ok": True, "idempotent": True, "event": e}
            e["status"] = "acknowledged"
            e["acknowledged_at"] = _utc_now()
            entry = {
                "action": "acknowledge_event",
                "event_id": event_id,
                "at": e["acknowledged_at"],
                "note": body.note if body else None,
            }
            ACTION_LOG.append(entry)
            return {"ok": True, "event": e, "detail": entry}
    raise HTTPException(status_code=404, detail="Event not found")

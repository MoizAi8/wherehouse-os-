"""Mounted application with independent dependencies for the original dashboard."""

from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from sqlalchemy import text
from fastapi.routing import APIRoute
from starlette.responses import Response

from fulfillment.api import deps
from fulfillment.api.demo_guest import require_guest, require_guest_mode
from fulfillment.api.v1 import (
    agents,
    analytics,
    carriers,
    fulfillment_centers,
    inventory,
    orders,
    shipments,
)
from fulfillment.config import settings
from fulfillment.models.user import User, UserRole
from fulfillment.services.instructor_workspace import COOLDOWN, identity, workspace
from fulfillment.tasks.instructor import instructor_run

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    dependencies=[Depends(require_guest_mode), Depends(require_guest)],
)


@app.middleware("http")
async def bounded_request(request: Request, call_next):
    if not settings.instructor_database_url:
        return Response(status_code=404)
    if request.method == "POST":
        length = request.headers.get("content-length", "")
        if (
            not length.isdecimal()
            or int(length) > 32768
            or request.headers.get("transfer-encoding")
        ):
            return Response(status_code=413)
    return await call_next(request)


async def assigned(request: Request, guest=Depends(require_guest)):
    async with workspace(identity(guest["sub"]), write=request.method == "POST") as assignment:
        yield assignment


async def database(assignment=Depends(assigned)):
    async with assignment[1].begin() as db:
        yield db


def instructor(guest=Depends(require_guest)):
    return User(
        id=identity(guest["sub"])[:32], role=UserRole.OPERATOR, name="Instructor", is_active=True
    )


app.dependency_overrides.update(
    {
        deps.get_db: database,
        deps.get_current_user: instructor,
        deps.require_operator_or_admin: instructor,
    }
)

# Only these exact registered endpoints may use the sandbox dependency overrides.
for prefix, router, paths in [
    (
        "inventory",
        inventory.router,
        {
            "GET": {
                "/products",
                "/stock",
                "/stock/{stock_id}/movements",
                "/orders/{order_id}/reservations",
            },
            "POST": {
                "/products",
                "/stock",
                "/stock/{stock_id}/movements",
                "/stock/{stock_id}/reservations",
                "/reservations/{reservation_id}/release",
                "/reservations/{reservation_id}/consume",
            },
        },
    ),
    (
        "orders",
        orders.router,
        {
            "GET": {"", "/{order_id}", "/{order_id}/lines"},
            "POST": {"", "/{order_id}/route", "/{order_id}/cancel", "/{order_id}/dispatch"},
        },
    ),
    ("fulfillment-centers", fulfillment_centers.router, {"GET": {""}}),
    ("agents", agents.router, {"GET": {"/status"}}),
    ("shipments", shipments.router, {"GET": {""}}),
    ("carriers", carriers.router, {"GET": {"/rates"}}),
    ("analytics", analytics.router, {"GET": {"/kpis", "/carriers"}}),
]:
    restricted = APIRouter()
    restricted.routes.extend(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and any(route.path in paths.get(method, set()) for method in route.methods)
    )
    app.include_router(restricted, prefix="/api/v1/" + prefix)


@app.get("/api/v1/settings")
def workspace_settings():
    return {"appName": "Warehouse OS", "theme": "dark", "apiEndpoint": "", "webhookUrl": ""}


@app.get("/api/auth/me")
def profile(user=Depends(instructor)):
    return {"id": user.id, "role": "operator", "name": "Instructor"}


@app.get("/api/evaluation/workflow")
async def read_run(assignment=Depends(assigned)):
    conn, _, slot = assignment
    if slot is None:
        return {}
    row = (
        (
            await conn.execute(
                text("""SELECT run AS id, CASE WHEN stage NOT IN ('Completed','Failed')
        AND started < now()-interval '3 minutes' THEN 'Failed' ELSE stage END AS stage,
        extract(epoch FROM started) AS updated_at,result FROM public.instructor_slots WHERE slot=:slot"""),
                {"slot": slot},
            )
        )
        .mappings()
        .one()
    )
    return dict(row) if row["id"] else {}


@app.post("/api/evaluation/workflow", status_code=202)
async def start_run(assignment=Depends(assigned), guest=Depends(require_guest)):
    conn, _, slot = assignment
    await conn.execute(text("SELECT pg_advisory_xact_lock(826413)"))
    active = await conn.scalar(
        text("""SELECT count(*) FROM public.instructor_slots WHERE
        (stage NOT IN ('Completed','Failed') AND started > now()-interval '3 minutes')
        OR started > now()-interval '15 seconds'""")
    )
    if active:
        raise HTTPException(
            409, "An evaluation is in progress or has just finished", headers=COOLDOWN
        )
    run = uuid4()
    await conn.execute(
        text("""UPDATE public.instructor_slots SET run=:id, stage='Queued', result=NULL,
        started=now() WHERE slot=:slot"""),
        {"id": run, "slot": slot},
    )
    await conn.commit()
    try:
        instructor_run.apply_async(
            args=[identity(guest["sub"])], task_id=str(run), queue="celery", expires=60, retry=False
        )
    except Exception:
        await conn.execute(
            text("UPDATE public.instructor_slots SET stage='Failed' WHERE slot=:slot AND run=:id"),
            {"slot": slot, "id": run},
        )
        await conn.commit()
        raise HTTPException(503, "Evaluation worker unavailable")
    return {"id": run, "stage": "Queued"}

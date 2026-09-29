# -*- coding: utf-8 -*-
"""
Territory_Mapping_API
---------------------
La misma logica de Territory_Mapping, expuesta como API HTTP.

Mandas el JSON de coordenadas (el mismo que usa el .exe) y te regresa la
imagen del area: el mapa de la zona con el poligono y los pines encima.

Arranque:
    python src\\api.py                      -> http://127.0.0.1:8000
    python src\\api.py --host 0.0.0.0 --port 9000

Documentacion interactiva:  http://127.0.0.1:8000/docs
"""

import argparse
import io
import os
import sys
import threading
from typing import Any, Dict, List, Optional, Union

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import territory_mapping as tm  # noqa: E402  (el motor, sin cambios)

API_VERSION = "1.0.0"

app = FastAPI(
    title="Territory_Mapping API",
    version=API_VERSION,
    description=(
        "Convierte una lista de coordenadas en la imagen del area que cubren. "
        "Mapa: (c) OpenStreetMap contributors."
    ),
)

# Permite consumirla desde una pagina web en otro dominio o puerto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Area-Ha", "X-Perimetro-M", "X-Zoom", "X-Puntos", "X-Orden"],
)

# Las teselas se bajan en serie (lo pide la politica de uso de OSM) y asi
# dos solicitudes simultaneas no escriben el mismo archivo de cache a la vez.
_teselas = threading.Lock()

CLAVES_ENVOLTURA = ("coordenadas", "coordinates", "puntos", "points", "vertices")

EJEMPLO = [
    {"lat": 20.650872, "lng": -103.436386},
    {"lat": 20.650639, "lng": -103.432531},
    {"lat": 20.646900, "lng": -103.432741},
    {"lat": 20.647579, "lng": -103.436573},
]


# --------------------------------------------------------------------------
# Opciones: los mismos parametros y defaults que el .exe
# --------------------------------------------------------------------------

class Opciones(BaseModel):
    ancho: int = Field(1280, ge=200, le=4000, description="Ancho en pixeles")
    alto: int = Field(1024, ge=200, le=4000, description="Alto en pixeles")
    margen: float = Field(8.0, ge=0, le=45, description="Porcentaje de aire alrededor del poligono")
    color: str = Field(tm.PIN_BODY, pattern=r"^#?[0-9A-Fa-f]{6}$", description="Contorno en RRGGBB")
    grosor: int = Field(4, ge=1, le=50, description="Grosor del contorno en px")
    opacidad: float = Field(8.0, ge=0, le=100, description="Opacidad del relleno, 0 a 100")
    pin: int = Field(34, ge=8, le=200, description="Alto del pin en px")
    sin_pines: bool = Field(False, description="No dibuja los marcadores")
    sin_ordenar: bool = Field(False, description="Respeta el orden del JSON aunque se cruce")
    formato: str = Field("png", pattern=r"^(png|jpg|jpeg)$", description="png o jpg")


def _mezclar_opciones(query: Dict[str, Any], data: Any) -> Opciones:
    """Opciones por query string; si el cuerpo trae "opciones", esas ganan."""
    valores = {k: v for k, v in query.items()
               if k in Opciones.model_fields and v is not None}
    if isinstance(data, dict) and isinstance(data.get("opciones"), dict):
        valores.update(data["opciones"])
    try:
        return Opciones(**valores)
    except ValidationError as exc:
        raise HTTPException(422, detail=[
            {"campo": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
            for e in exc.errors()
        ])


# --------------------------------------------------------------------------
# Lectura de puntos: mismas reglas que load_points() del .exe
# --------------------------------------------------------------------------

def _puntos(data: Any):
    if isinstance(data, dict):
        for clave in CLAVES_ENVOLTURA:
            if isinstance(data.get(clave), list):
                data = data[clave]
                break
    if not isinstance(data, list):
        raise HTTPException(422, "El cuerpo debe ser una lista de puntos {lat, lng}, "
                                 "o un objeto con 'coordenadas'.")
    try:
        pts = [tm.parse_point(p, i) for i, p in enumerate(data)]
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if len(pts) > 3 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        raise HTTPException(422, "Se necesitan al menos 3 puntos para dibujar un area "
                                 "(llegaron %d)." % len(pts))
    return pts


def _ordenar(pts, sin_ordenar: bool):
    """Devuelve (puntos, orden, cruce), igual que el flujo del .exe."""
    cruce = tm.find_crossing(pts)
    orden = "original"
    if cruce and not sin_ordenar:
        pts = tm.order_by_shortest_tour(pts)
        cruce = tm.find_crossing(pts)
        orden = "corregido"
    return pts, orden, cruce


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

CUERPO = Body(
    ...,
    description="La lista de coordenadas, igual que el JSON del .exe. "
                "Tambien acepta {\"coordenadas\": [...], \"opciones\": {...}}.",
    examples=[EJEMPLO],
)


@app.get("/salud", summary="Verifica que la API este arriba")
def salud():
    return {"estado": "ok", "version": API_VERSION, "motor": tm.VERSION}


@app.post(
    "/imagen",
    summary="Genera la imagen del area",
    response_class=Response,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}},
                     "description": "La imagen del territorio"}},
)
def imagen(
    data: Union[List[Any], Dict[str, Any]] = CUERPO,
    ancho: Optional[int] = Query(None, description="default 1280"),
    alto: Optional[int] = Query(None, description="default 1024"),
    margen: Optional[float] = Query(None, description="default 8"),
    color: Optional[str] = Query(None, description="default E94235"),
    grosor: Optional[int] = Query(None, description="default 4"),
    opacidad: Optional[float] = Query(None, description="default 8"),
    pin: Optional[int] = Query(None, description="default 34"),
    sin_pines: Optional[bool] = Query(None),
    sin_ordenar: Optional[bool] = Query(None),
    formato: Optional[str] = Query(None, description="png (default) o jpg"),
):
    op = _mezclar_opciones(locals(), data)
    pts, orden, cruce = _ordenar(_puntos(data), op.sin_ordenar)

    try:
        with _teselas:
            canvas, to_canvas, zoom = tm.build_basemap(
                pts, op.ancho, op.alto, op.margen, verbose=False)
        tm.draw_polygon(canvas, pts, to_canvas, op.color, op.grosor,
                        op.opacidad, not op.sin_pines, op.pin)
        ha = tm.area_hectares(pts)
        per = tm.perimeter_meters(pts)
        tm.stamp_attribution(canvas, "%.2f ha  |  perimetro %.0f m" % (ha, per))
    except SystemExit as exc:  # el motor avisa errores de uso con SystemExit
        raise HTTPException(400, str(exc).replace("ERROR: ", ""))

    buf = io.BytesIO()
    if op.formato == "png":
        canvas.convert("RGB").save(buf, format="PNG", optimize=True)
        media = "image/png"
    else:
        canvas.convert("RGB").save(buf, format="JPEG", quality=95)
        media = "image/jpeg"

    headers = {
        "X-Area-Ha": "%.2f" % ha,
        "X-Perimetro-M": "%.0f" % per,
        "X-Zoom": str(zoom),
        "X-Puntos": str(len(pts)),
        "X-Orden": orden + ("; aviso: lados %d y %d se cruzan" % cruce if cruce else ""),
    }
    return Response(content=buf.getvalue(), media_type=media, headers=headers)


@app.post("/area", summary="Calcula area y perimetro sin generar imagen")
def area(
    data: Union[List[Any], Dict[str, Any]] = CUERPO,
    sin_ordenar: bool = Query(False, description="Respeta el orden del JSON"),
):
    pts, orden, cruce = _ordenar(_puntos(data), sin_ordenar)
    return {
        "puntos": [{"lat": la, "lng": lo} for la, lo in pts],
        "area_ha": round(tm.area_hectares(pts), 4),
        "perimetro_m": round(tm.perimeter_meters(pts), 1),
        "orden": orden,
        "cruce": list(cruce) if cruce else None,
    }


# --------------------------------------------------------------------------
# Arranque
# --------------------------------------------------------------------------

def main(argv=None):
    import uvicorn

    parser = argparse.ArgumentParser(prog="Territory_Mapping_API")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                        help="interfaz (default 127.0.0.1; usa 0.0.0.0 para la red local)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)),
                        help="puerto (default 8000)")
    parser.add_argument("--version", action="version",
                        version="Territory_Mapping_API " + API_VERSION)
    args = parser.parse_args(argv)

    print("Territory_Mapping_API %s" % API_VERSION)
    print("  escuchando en  http://%s:%d" % (args.host, args.port))
    print("  documentacion  http://%s:%d/docs" % (args.host, args.port))
    print("  Ctrl+C para detener\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

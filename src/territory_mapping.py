# -*- coding: utf-8 -*-
"""
Territory_Mapping
-----------------
Recibe un JSON con una lista de coordenadas y genera una imagen del area
cubierta: el mapa de la zona con el poligono dibujado encima.

Uso:
    Territory_Mapping.exe --input coords.json --output salida\\
    Territory_Mapping.exe -i coords.json -o mapa.png --relleno --ancho 1600

Fuente del mapa: teselas de OpenStreetMap (sin API key, sin cuenta).
"""

import argparse
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.stderr.write(
        "ERROR: falta Pillow.\n"
        "       Instalalo con:  pip install pillow\n"
    )
    sys.exit(2)

VERSION = "1.0.0"
TILE_SIZE = 256
MAX_ZOOM = 19
MIN_ZOOM = 2
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "Territory_Mapping/%s (+https://github.com/EliseoMx/Territory_Mapping)" % VERSION
ATTRIBUTION = "(c) OpenStreetMap contributors"
PIN_BODY = "E94235"   # cuerpo del pin
PIN_CORE = "B20D0D"   # circulo interior del pin
SS_MAX = 4            # supersampling para dibujar con bordes suaves


# --------------------------------------------------------------------------
# Lectura y validacion del JSON
# --------------------------------------------------------------------------

def _num(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("'%s' debe ser un numero, llego: %r" % (name, value))
    return float(value)


def parse_point(raw, idx):
    """Acepta {lat,lng} / {lat,lon} / {lat,long} / [lat, lng]."""
    if isinstance(raw, dict):
        keys = {k.lower(): k for k in raw}
        if "lat" not in keys:
            raise ValueError("el punto %d no tiene 'lat'" % (idx + 1))
        lon_key = None
        for cand in ("lng", "lon", "long", "longitude"):
            if cand in keys:
                lon_key = keys[cand]
                break
        if lon_key is None:
            raise ValueError("el punto %d no tiene 'lng' (ni 'lon')" % (idx + 1))
        lat = _num(raw[keys["lat"]], "lat")
        lon = _num(raw[lon_key], "lng")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lat = _num(raw[0], "lat")
        lon = _num(raw[1], "lng")
    else:
        raise ValueError("el punto %d no es un objeto {lat,lng} ni un par [lat,lng]" % (idx + 1))

    if not -90.0 <= lat <= 90.0:
        raise ValueError("el punto %d tiene lat fuera de rango: %s" % (idx + 1, lat))
    if not -180.0 <= lon <= 180.0:
        raise ValueError("el punto %d tiene lng fuera de rango: %s" % (idx + 1, lon))
    return (lat, lon)


def load_points(path):
    if not os.path.isfile(path):
        raise SystemExit("ERROR: no existe el archivo de entrada: %s" % path)
    try:
        with io.open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except ValueError as exc:
        raise SystemExit("ERROR: el JSON no es valido (%s)" % exc)

    # Tolera que venga envuelto en un objeto.
    if isinstance(data, dict):
        for key in ("coordenadas", "coordinates", "puntos", "points", "vertices"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise SystemExit("ERROR: el JSON debe ser una lista de puntos {lat, lng}.")

    try:
        pts = [parse_point(p, i) for i, p in enumerate(data)]
    except ValueError as exc:
        raise SystemExit("ERROR: %s" % exc)

    # Quita el punto de cierre si repitieron el primero al final.
    if len(pts) > 3 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        raise SystemExit("ERROR: se necesitan al menos 3 puntos para dibujar un area (llegaron %d)." % len(pts))
    return pts


# --------------------------------------------------------------------------
# Proyeccion Web Mercator
# --------------------------------------------------------------------------

def project(lat, lon, zoom):
    """lat/lon -> pixel global en ese zoom."""
    siny = math.sin(math.radians(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    scale = TILE_SIZE * (2 ** zoom)
    x = scale * (lon + 180.0) / 360.0
    y = scale * (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi))
    return x, y


def pick_zoom(points, width, height, margin_pct):
    usable_w = width * (1.0 - 2.0 * margin_pct / 100.0)
    usable_h = height * (1.0 - 2.0 * margin_pct / 100.0)
    if usable_w <= 0 or usable_h <= 0:
        raise SystemExit("ERROR: el margen deja el lienzo en cero. Baja --margen.")
    for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        xs, ys = zip(*[project(la, lo, zoom) for la, lo in points])
        if (max(xs) - min(xs)) <= usable_w and (max(ys) - min(ys)) <= usable_h:
            return zoom
    return MIN_ZOOM


# --------------------------------------------------------------------------
# Descarga de teselas, con cache en disco
# --------------------------------------------------------------------------

def cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "Territory_Mapping", "tiles")
    try:
        os.makedirs(path)
    except OSError:
        pass
    return path


def fetch_tile(zoom, x, y, cache, retries=3):
    local = os.path.join(cache, "%d_%d_%d.png" % (zoom, x, y))
    if os.path.isfile(local) and os.path.getsize(local) > 0:
        try:
            return Image.open(local).convert("RGBA")
        except Exception:
            pass

    url = TILE_URL.format(z=zoom, x=x, y=y)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                blob = resp.read()
            with open(local, "wb") as fh:
                fh.write(blob)
            return Image.open(io.BytesIO(blob)).convert("RGBA")
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(1.0 + attempt)
    sys.stderr.write("  aviso: no se pudo bajar la tesela %d/%d/%d (%s)\n" % (zoom, x, y, last))
    return Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (242, 239, 233, 255))


def build_basemap(points, width, height, margin_pct, verbose=True):
    zoom = pick_zoom(points, width, height, margin_pct)
    projected = [project(la, lo, zoom) for la, lo in points]
    xs, ys = zip(*projected)
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    origin_x = cx - width / 2.0
    origin_y = cy - height / 2.0

    x0 = int(math.floor(origin_x / TILE_SIZE))
    x1 = int(math.floor((origin_x + width) / TILE_SIZE))
    y0 = int(math.floor(origin_y / TILE_SIZE))
    y1 = int(math.floor((origin_y + height) / TILE_SIZE))

    total = (x1 - x0 + 1) * (y1 - y0 + 1)
    if verbose:
        print("  zoom %d, %d teselas" % (zoom, total))

    canvas = Image.new("RGBA", (width, height), (242, 239, 233, 255))
    cache = cache_dir()
    n_max = 2 ** zoom
    done = 0
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            done += 1
            if ty < 0 or ty >= n_max:
                continue
            tile = fetch_tile(zoom, tx % n_max, ty, cache)
            canvas.paste(
                tile,
                (int(round(tx * TILE_SIZE - origin_x)), int(round(ty * TILE_SIZE - origin_y))),
                tile,
            )
            if verbose and total > 8 and done % 10 == 0:
                print("  %d/%d teselas" % (done, total))

    def to_canvas(lat, lon):
        px, py = project(lat, lon, zoom)
        return (px - origin_x, py - origin_y)

    return canvas, to_canvas, zoom


# --------------------------------------------------------------------------
# Dibujo
# --------------------------------------------------------------------------

def hex_to_rgb(text):
    t = text.strip().lstrip("#").lstrip("0x").lstrip("0X")
    if len(t) != 6:
        raise SystemExit("ERROR: color invalido: %s (usa formato RRGGBB, por ejemplo FF0000)" % text)
    try:
        return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise SystemExit("ERROR: color invalido: %s" % text)


def load_font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def draw_pin(layer, x, y, alto, body_rgb, core_rgb):
    """Dibuja un pin de mapa con la punta exactamente en (x, y).

    Se dibuja sobre un lienzo supersampleado; el llamador lo reduce despues,
    que es lo que le da el borde suave (Pillow no tiene antialiasing).
    """
    d = ImageDraw.Draw(layer)
    h = float(alto)
    r = h * 0.35                 # radio de la cabeza
    cy = y - (h - r)             # centro de la cabeza
    dist = h - r

    # sombra en el piso
    sw, sh = r * 0.80, r * 0.22
    d.ellipse([x - sw, y - sh, x + sw, y + sh], fill=(70, 50, 50, 38))

    # cola: triangulo tangente a la cabeza
    if dist > r:
        theta = math.acos(r / dist)
        tx = r * math.sin(theta)
        ty = r * math.cos(theta)
        d.polygon([(x, y), (x - tx, cy + ty), (x + tx, cy + ty)], fill=body_rgb + (255,))

    # cabeza y circulo interior
    d.ellipse([x - r, cy - r, x + r, cy + r], fill=body_rgb + (255,))
    ir = r * 0.42
    d.ellipse([x - ir, cy - ir, x + ir, cy + ir], fill=core_rgb + (255,))


def draw_polygon(canvas, points, to_canvas, color, grosor, opacidad, pines, pin_alto):
    coords = [to_canvas(la, lo) for la, lo in points]
    rgb = hex_to_rgb(color)

    # relleno tenue
    if opacidad > 0:
        alpha = int(round(255 * opacidad / 100.0))
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).polygon(coords, fill=rgb + (alpha,))
        canvas.alpha_composite(overlay)

    # contorno, dibujado supersampleado para que no quede escalonado.
    # El factor baja en lienzos grandes para no disparar la memoria.
    px = canvas.size[0] * canvas.size[1]
    SS = SS_MAX if px <= 2200000 else (3 if px <= 6000000 else 2)
    big = Image.new("RGBA", (canvas.size[0] * SS, canvas.size[1] * SS), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    big_coords = [(cx * SS, cy * SS) for cx, cy in coords]
    bd.line(big_coords + [big_coords[0]], fill=rgb + (255,), width=grosor * SS, joint="curve")

    if pines:
        body = hex_to_rgb(PIN_BODY)
        core = hex_to_rgb(PIN_CORE)
        for cx, cy in big_coords:
            draw_pin(big, cx, cy, pin_alto * SS, body, core)

    canvas.alpha_composite(big.resize(canvas.size, Image.LANCZOS))
    return canvas


def stamp_attribution(canvas, extra=""):
    text = ATTRIBUTION + ("  |  " + extra if extra else "")
    font = load_font(13)
    draw = ImageDraw.Draw(canvas)
    try:
        box = draw.textbbox((0, 0), text, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
    pad = 5
    x = canvas.size[0] - tw - 2 * pad
    y = canvas.size[1] - th - 2 * pad
    draw.rectangle([x - pad, y - pad, canvas.size[0], canvas.size[1]], fill=(255, 255, 255, 205))
    draw.text((x, y), text, fill=(60, 60, 60, 255), font=font)
    return canvas


# --------------------------------------------------------------------------
# Geometria de apoyo
# --------------------------------------------------------------------------

def metros_por_grado(lat):
    """Cuantos metros mide un grado de latitud y uno de longitud, en `lat`.

    La Tierra no es una esfera: un grado de latitud mide ~110574 m en el ecuador
    y ~111694 m en el polo, y uno de longitud se acorta con el coseno. Estas son
    las series estandar sobre WGS84; dan precision de centimetros, y evitan el
    sesgo de usar una constante fija (que subestimaba el area 0.2% en Guadalajara
    y 1.1% a 65 grados de latitud).
    """
    f = math.radians(lat)
    m_lat = (111132.92
             - 559.82 * math.cos(2 * f)
             + 1.175 * math.cos(4 * f)
             - 0.0023 * math.cos(6 * f))
    m_lon = (111412.84 * math.cos(f)
             - 93.5 * math.cos(3 * f)
             + 0.118 * math.cos(5 * f))
    return m_lat, m_lon


def area_hectares(points):
    """Area aproximada por proyeccion equirectangular local."""
    lat0 = sum(p[0] for p in points) / len(points)
    m_lat, m_lon = metros_por_grado(lat0)
    xs = [(lo * m_lon) for _, lo in points]
    ys = [(la * m_lat) for la, _ in points]
    total = 0.0
    for i in range(len(points)):
        j = (i + 1) % len(points)
        total += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(total) / 2.0 / 10000.0


def perimeter_meters(points):
    total = 0.0
    for i in range(len(points)):
        la1, lo1 = points[i]
        la2, lo2 = points[(i + 1) % len(points)]
        m_lat, m_lon = metros_por_grado((la1 + la2) / 2.0)
        dx = (lo2 - lo1) * m_lon
        dy = (la2 - la1) * m_lat
        total += math.hypot(dx, dy)
    return total


def _orient(a, b, c):
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(v) < 1e-14:
        return 0
    return 1 if v > 0 else -1


def _on_segment(a, b, c):
    """c colineal con ab: cae dentro del segmento?"""
    return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))


def _segments_cross(p1, p2, p3, p4):
    o1, o2 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    o3, o4 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(p1, p2, p3):
        return True
    if o2 == 0 and _on_segment(p1, p2, p4):
        return True
    if o3 == 0 and _on_segment(p3, p4, p1):
        return True
    if o4 == 0 and _on_segment(p3, p4, p2):
        return True
    return False


def find_crossing(points):
    """Devuelve (i, j) del primer par de lados que se cruzan, o None.

    Un poligono cuyos lados se cruzan es señal de que los puntos no vienen en
    orden de recorrido: el area y el dibujo saldrian mal.
    """
    xy = [(lo, la) for la, lo in points]
    n = len(xy)
    for i in range(n):
        a1, a2 = xy[i], xy[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            b1, b2 = xy[j], xy[(j + 1) % n]
            if _segments_cross(a1, a2, b1, b2):
                return (i + 1, j + 1)
    return None


def _local_meters(points):
    """Proyecta a metros planos alrededor del centro del conjunto.

    A escala de un territorio la distorsion es despreciable, y trabajar en
    metros evita que la longitud "pese" distinto que la latitud al medir.
    """
    lat0 = sum(p[0] for p in points) / len(points)
    lon0 = sum(p[1] for p in points) / len(points)
    m_lat, m_lon = metros_por_grado(lat0)
    return [((lo - lon0) * m_lon, (la - lat0) * m_lat) for la, lo in points]


def _distances(xy):
    n = len(xy)
    return [[math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1]) for j in range(n)]
            for i in range(n)]


def _tour_length(order, dist):
    return sum(dist[order[i]][order[(i + 1) % len(order)]] for i in range(len(order)))


def _held_karp(dist):
    """Circuito mas corto exacto por programacion dinamica. O(n^2 * 2^n)."""
    n = len(dist)
    full = 1 << (n - 1)                      # el nodo 0 queda fijo como inicio
    INF = float("inf")
    best = [[INF] * (n - 1) for _ in range(full)]
    prev = [[-1] * (n - 1) for _ in range(full)]
    for j in range(n - 1):
        best[1 << j][j] = dist[0][j + 1]
    for mask in range(full):
        row = best[mask]
        for j in range(n - 1):
            cur = row[j]
            if cur == INF or not (mask >> j) & 1:
                continue
            for k in range(n - 1):
                if (mask >> k) & 1:
                    continue
                nm = mask | (1 << k)
                cand = cur + dist[j + 1][k + 1]
                if cand < best[nm][k]:
                    best[nm][k] = cand
                    prev[nm][k] = j
    last, total = -1, INF
    for j in range(n - 1):
        cand = best[full - 1][j] + dist[j + 1][0]
        if cand < total:
            total, last = cand, j
    order, mask = [], full - 1
    while last != -1:
        order.append(last + 1)
        nxt = prev[mask][last]
        mask ^= (1 << last)
        last = nxt
    order.reverse()
    return [0] + order


def _two_opt(order, dist):
    """Descruza el recorrido hasta que ningun intercambio lo acorte.

    En distancias euclidianas, un optimo local de 2-opt no tiene cruces: si dos
    tramos se cruzaran, intercambiarlos acortaria el recorrido. Por eso al
    terminar el poligono es simple.
    """
    n = len(order)
    mejorado = True
    while mejorado:
        mejorado = False
        for i in range(n - 1):
            a, b = order[i], order[(i + 1) % n]
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                c, d = order[j], order[(j + 1) % n]
                delta = (dist[a][c] + dist[b][d]) - (dist[a][b] + dist[c][d])
                if delta < -1e-9:
                    order[i + 1:j + 1] = reversed(order[i + 1:j + 1])
                    mejorado = True
                    a, b = order[i], order[(i + 1) % n]
    return order


def _nearest_neighbor(dist, inicio):
    n = len(dist)
    visto = [False] * n
    order = [inicio]
    visto[inicio] = True
    for _ in range(n - 1):
        u = order[-1]
        mejor, md = -1, float("inf")
        for v in range(n):
            if not visto[v] and dist[u][v] < md:
                mejor, md = v, dist[u][v]
        order.append(mejor)
        visto[mejor] = True
    return order


def order_by_shortest_tour(points):
    """Reordena los puntos como el circuito cerrado mas corto que los recorre.

    El recorrido mas corto que pasa por todos los puntos es, por desigualdad
    triangular, un poligono que no se cruza: el de menor perimetro posible
    sobre ese conjunto. Para un territorio real ese es el perimetro que se
    quiso capturar.

    Hasta 12 puntos se resuelve exacto (Held-Karp). De ahi en adelante se usa
    vecino mas cercano desde cada arranque mas 2-opt, que en estos tamanos
    llega al optimo o a un pelo de el, y que de todos modos garantiza que no
    queden cruces.
    """
    n = len(points)
    if n < 4:
        return list(points)
    dist = _distances(_local_meters(points))

    if n <= 12:
        order = _held_karp(dist)
    else:
        arranques = range(n) if n <= 60 else range(0, n, max(1, n // 60))
        order, mejor = None, float("inf")
        for ini in arranques:
            cand = _two_opt(_nearest_neighbor(dist, ini), dist)
            largo = _tour_length(cand, dist)
            if largo < mejor:
                order, mejor = cand, largo
    order = _two_opt(order, dist)
    return [points[i] for i in order]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def base_dir():
    """Carpeta donde vive el programa.

    Compilado con PyInstaller en modo --onefile, `sys.executable` es el .exe
    real; `__file__` apuntaria a la carpeta temporal donde se descomprime, que
    desaparece al terminar. Por eso se distingue un caso del otro.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resolve_output(output, input_path):
    base = os.path.splitext(os.path.basename(input_path))[0]
    if not output:
        # Sin --output: junto al ejecutable.
        return os.path.join(base_dir(), base + "_area.png")
    if output.lower().endswith((".png", ".jpg", ".jpeg")):
        parent = os.path.dirname(os.path.abspath(output))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        return output
    if not os.path.isdir(output):
        os.makedirs(output)
    return os.path.join(output, base + "_area.png")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="Territory_Mapping",
        description="Genera la imagen del area cubierta a partir de un JSON de coordenadas.",
    )
    parser.add_argument("-i", "--input", required=True, metavar="RUTA",
                        help="JSON con la lista de coordenadas {lat, lng}")
    parser.add_argument("-o", "--output", metavar="RUTA", default=None,
                        help="archivo .png de salida, o carpeta donde guardarlo. "
                             "Si no lo pones, la imagen se guarda junto al ejecutable")
    parser.add_argument("--ancho", type=int, default=1280, help="ancho en pixeles (default 1280)")
    parser.add_argument("--alto", type=int, default=1024, help="alto en pixeles (default 1024)")
    parser.add_argument("--margen", type=float, default=8.0,
                        help="porcentaje de aire alrededor del poligono (default 8)")
    parser.add_argument("--color", default=PIN_BODY,
                        help="color del contorno en RRGGBB (default %s, el rojo del pin)" % PIN_BODY)
    parser.add_argument("--grosor", type=int, default=4, help="grosor del contorno en px (default 4)")
    parser.add_argument("--opacidad", type=float, default=8.0,
                        help="opacidad del relleno, 0 a 100 (default 8; usa 0 para no rellenar)")
    parser.add_argument("--sin-pines", dest="sin_pines", action="store_true",
                        help="no dibuja el pin en cada vertice")
    parser.add_argument("--pin", type=int, default=34,
                        help="alto del pin en px (default 34)")
    parser.add_argument("--sin-ordenar", dest="sin_ordenar", action="store_true",
                        help="no corrige el orden de los puntos aunque el poligono "
                             "se cruce; respeta el orden del JSON tal cual")
    parser.add_argument("--silencioso", action="store_true", help="no imprime el avance")
    parser.add_argument("--version", action="version", version="Territory_Mapping " + VERSION)
    args = parser.parse_args(argv)

    if args.ancho < 200 or args.alto < 200:
        raise SystemExit("ERROR: --ancho y --alto deben ser de al menos 200 px.")
    if args.grosor < 1:
        raise SystemExit("ERROR: --grosor debe ser 1 o mas.")
    if not 0.0 <= args.opacidad <= 100.0:
        raise SystemExit("ERROR: --opacidad debe estar entre 0 y 100.")
    if args.pin < 8:
        raise SystemExit("ERROR: --pin debe ser de al menos 8 px.")

    verbose = not args.silencioso
    points = load_points(args.input)
    destino = resolve_output(args.output, args.input)

    if verbose:
        print("Territory_Mapping %s" % VERSION)
        print("  entrada : %s (%d puntos)" % (args.input, len(points)))

    cruce = find_crossing(points)
    if cruce and not args.sin_ordenar:
        antes = perimeter_meters(points)
        points = order_by_shortest_tour(points)
        cruce = find_crossing(points)
        if verbose:
            print("  orden   : corregido, circuito mas corto (%.0f m vs %.0f m)"
                  % (perimeter_meters(points), antes))

    if cruce:
        sys.stderr.write(
            "\n"
            "  AVISO: los lados %d y %d del poligono se cruzan.\n"
            "         Los puntos no estan en orden de recorrido del perimetro,\n"
            "         asi que el area y el dibujo van a salir mal.\n"
            "         Quita --sin-ordenar para que el programa lo corrija solo.\n"
            "\n" % cruce
        )

    canvas, to_canvas, zoom = build_basemap(points, args.ancho, args.alto, args.margen, verbose)
    draw_polygon(canvas, points, to_canvas, args.color, args.grosor,
                 args.opacidad, not args.sin_pines, args.pin)

    ha = area_hectares(points)
    per = perimeter_meters(points)
    stamp_attribution(canvas, "%.2f ha  |  perimetro %.0f m" % (ha, per))

    reemplazo = os.path.isfile(destino)
    try:
        canvas.convert("RGB").save(destino, quality=95)
    except (OSError, IOError) as exc:
        if args.output:
            raise SystemExit("ERROR: no se pudo escribir %s\n       %s" % (destino, exc))
        # Sin --output se intento junto al ejecutable; si esa carpeta es de
        # solo lectura (Program Files, una unidad de red), cae a la actual.
        alterno = os.path.join(os.getcwd(), os.path.basename(destino))
        sys.stderr.write(
            "\n  AVISO: no se pudo escribir junto al ejecutable.\n"
            "         %s\n"
            "         La imagen se guarda en la carpeta actual.\n\n" % exc
        )
        reemplazo = os.path.isfile(alterno)
        canvas.convert("RGB").save(alterno, quality=95)
        destino = alterno

    if verbose:
        print("  area    : %.2f ha" % ha)
        print("  perim.  : %.0f m" % per)
        print("  salida  : %s%s" % (os.path.abspath(destino),
                                    "  (reemplazado)" if reemplazo else ""))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nCancelado.\n")
        sys.exit(130)

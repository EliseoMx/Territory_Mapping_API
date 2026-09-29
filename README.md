# Territory_Mapping_API

La version API de [Territory_Mapping](../Territory_Mapping): mandas el JSON de
coordenadas por HTTP y te regresa la imagen del area, con el mapa de la zona,
el poligono encima y un pin en cada vertice.

![Ejemplo de salida](docs/ejemplo.png)

> Territorio de ejemplo en Zapopan, Jalisco, delimitado por Av. Moctezuma,
> Av. Nicolas Copernico, Av. El Colli y C. Paseo de los Volcanes. 15.70 ha.

---

## Que cambia respecto al .exe

Nada del resultado. `src/territory_mapping.py` es el mismo motor, sin tocar:
misma proyeccion, mismo ordenamiento automatico, mismos pines, misma paleta y
el mismo cache de teselas. `src/api.py` solo lo envuelve en HTTP.

| | Territory_Mapping | Territory_Mapping_API |
|---|---|---|
| Entrada | Archivo `.json` con `-i` | Cuerpo del `POST` (el mismo JSON) |
| Opciones | `--ancho 1600 --sin-pines` | `?ancho=1600&sin_pines=true` |
| Salida | Archivo `.png` en disco | La imagen en la respuesta |
| Area y perimetro | Impresos en consola | Encabezados `X-Area-Ha`, `X-Perimetro-M` |
| Quien lo usa | Una persona, a mano | Otra app, una pagina web, Postman |

---

## Arranque rapido

### 1. Instala Python

Descarga Python 3 de <https://www.python.org/downloads/> y **marca la casilla
"Add python.exe to PATH"** durante la instalacion.

### 2. Levanta la API

Doble clic en **`iniciar.bat`**. La primera vez crea el entorno virtual e
instala FastAPI, Uvicorn y Pillow. Luego queda escuchando:

```
Territory_Mapping_API 1.0.0
  escuchando en  http://127.0.0.1:8000
  documentacion  http://127.0.0.1:8000/docs
```

**Deja esa ventana abierta**: si la cierras, la API se apaga.

### 3. Pruebala

Con la API arriba, doble clic en **`probar.bat`**. Manda el territorio de
ejemplo, guarda la imagen en `salida\` y la abre.

O entra a <http://127.0.0.1:8000/docs>, abre `POST /imagen`, clic en
**Try it out** y **Execute**. Ahi mismo ves la imagen.

---

## Endpoints

| Metodo | Ruta | Que hace |
|---|---|---|
| `POST` | `/imagen` | Recibe las coordenadas y regresa la imagen (PNG o JPG) |
| `POST` | `/area` | Recibe las coordenadas y regresa area, perimetro y el orden final, sin imagen |
| `GET` | `/salud` | Responde `{"estado": "ok"}` si la API esta arriba |
| `GET` | `/docs` | Documentacion interactiva para probar desde el navegador |

### Cuerpo

El mismo JSON que usa el `.exe`: la lista de ubicaciones en el orden en que se
recorre el perimetro.

```json
[
  { "lat": 20.650872, "lng": -103.436386 },
  { "lat": 20.650639, "lng": -103.432531 },
  { "lat": 20.646900, "lng": -103.432741 },
  { "lat": 20.647579, "lng": -103.436573 }
]
```

Aplican las mismas reglas: minimo 3 puntos, cierre implicito, acepta `lon` y
`long`, pares `[lat, lng]`, y si los puntos vienen revueltos se reordenan
solos. Detalle en [`docs/formato-json.md`](docs/formato-json.md).

Si prefieres mandar las opciones dentro del cuerpo en vez de la URL, envuelve
la lista:

```json
{
  "coordenadas": [ { "lat": 20.650872, "lng": -103.436386 }, "..." ],
  "opciones": { "ancho": 1600, "sin_pines": true }
}
```

Si una opcion viene en la URL y en `opciones`, gana la del cuerpo.

### Opciones

Mismos parametros y defaults que el `.exe`, con guion bajo en vez de guion:

| Parametro | Default | Que hace |
|---|---|---|
| `ancho` / `alto` | `1280` / `1024` | Tamano de la imagen en pixeles (200 a 4000) |
| `margen` | `8` | Porcentaje de aire alrededor del poligono (0 a 45) |
| `color` | `E94235` | Color del contorno, en RRGGBB |
| `grosor` | `4` | Grosor del contorno en pixeles |
| `opacidad` | `8` | Opacidad del relleno, 0 a 100. `0` deja solo el contorno |
| `pin` | `34` | Alto del pin en pixeles |
| `sin_pines` | `false` | No dibuja los marcadores |
| `sin_ordenar` | `false` | No corrige el orden aunque el poligono se cruce |
| `formato` | `png` | `png` o `jpg` |

### Respuesta de `/imagen`

El cuerpo es la imagen. Los datos del territorio viajan en encabezados:

| Encabezado | Ejemplo | Que es |
|---|---|---|
| `X-Area-Ha` | `15.70` | Area en hectareas |
| `X-Perimetro-M` | `1589` | Perimetro en metros |
| `X-Zoom` | `17` | Zoom de OpenStreetMap usado |
| `X-Puntos` | `4` | Vertices dibujados |
| `X-Orden` | `corregido` | `original` o `corregido`; con `sin_ordenar` avisa si hay cruces |

### Errores

| Codigo | Cuando |
|---|---|
| `422` | JSON mal formado, menos de 3 puntos, `lat`/`lng` fuera de rango, opcion invalida |
| `400` | Combinacion que el motor no puede dibujar |

El mensaje viene en `detail`, en espanol, con el mismo texto que imprime el
`.exe`. Por ejemplo:

```json
{ "detail": "el punto 1 tiene lat fuera de rango: -103.0" }
```

---

## Como consumirla

### curl (viene con Windows 10 y 11)

```bat
curl.exe -X POST "http://127.0.0.1:8000/imagen?opacidad=0" ^
     -H "Content-Type: application/json" ^
     --data-binary "@samples\territorio_ejemplo.json" ^
     -o mapa.png
```

### Python

```python
import json, requests

coords = json.load(open("samples/territorio_ejemplo.json"))
r = requests.post("http://127.0.0.1:8000/imagen",
                  params={"ancho": 1600, "color": "1A73E8"},
                  json=coords)
r.raise_for_status()
open("mapa.png", "wb").write(r.content)
print(r.headers["X-Area-Ha"], "ha")
```

### JavaScript (navegador o Node)

```js
const r = await fetch("http://127.0.0.1:8000/imagen", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(coordenadas),
});
const blob = await r.blob();
document.querySelector("img").src = URL.createObjectURL(blob);
console.log(r.headers.get("X-Area-Ha"), "ha");
```

CORS esta abierto, asi que una pagina en otro puerto o dominio puede llamarla.

### Postman

`POST http://127.0.0.1:8000/imagen`, pestana **Body** > **raw** > **JSON**,
pega las coordenadas y **Send**. Postman muestra la imagen en la respuesta.

---

## Usarla desde otra computadora

Por default solo escucha en tu equipo (`127.0.0.1`). Para abrirla a tu red
local:

```bat
iniciar.bat --host 0.0.0.0 --port 8000
```

Desde otra maquina usa la IP de la tuya (`ipconfig` te la dice), por ejemplo
`http://192.168.1.50:8000/docs`. Windows te va a pedir permiso en el firewall
la primera vez.

No tiene autenticacion: no la expongas a internet tal cual.

---

## Como ejecutable

Si prefieres un solo archivo sin instalar Python en cada maquina, doble clic
en **`build.bat`**. Genera `dist\Territory_Mapping_API.exe`, que al abrirlo
levanta la API igual que `iniciar.bat` y acepta los mismos `--host` y `--port`.

---

## Cache de teselas

Es el mismo del `.exe`: `%LOCALAPPDATA%\Territory_Mapping\tiles`. Si ya
generaste un territorio con uno, el otro no vuelve a descargar esa zona.

Las teselas se bajan una solicitud a la vez, como pide la politica de uso de
OpenStreetMap. Si llegan dos solicitudes juntas sobre una zona nueva, la
segunda espera a que termine la primera; sobre una zona en cache, ambas
responden al instante.

---

## Estructura

```
Territory_Mapping_API/
├── src/api.py                  la API (FastAPI)
├── src/territory_mapping.py    el motor, identico al del .exe
├── samples/                    los mismos JSON de ejemplo
│   └── formas/                 los cinco casos de ordenamiento
├── docs/                       formato, arquitectura, diagrama
├── iniciar.bat                 instala lo necesario y levanta la API
├── probar.bat                  manda el ejemplo y abre la imagen
├── build.bat                   genera dist\Territory_Mapping_API.exe
└── requirements.txt
```

Si cambias el motor en `Territory_Mapping`, copia `src\territory_mapping.py`
aqui para que la API lo tome.

---

## Problemas comunes

| Sintoma | Causa y solucion |
|---|---|
| `iniciar.bat` dice que no encuentra Python | No marcaste "Add python.exe to PATH". Reinstala Python marcando la casilla |
| `probar.bat` dice que la API no responde | Abre `iniciar.bat` primero y deja la ventana abierta |
| `[Errno 10048]` al iniciar | El puerto 8000 ya esta ocupado. Usa `iniciar.bat --port 8001` |
| El mapa sale gris sin calles | No hubo conexion al bajar las teselas. Revisa internet y vuelve a pedirla |
| La primera solicitud tarda varios segundos | Esta bajando las teselas de esa zona. Las siguientes salen del cache |
| `422` con `lat fuera de rango` | Invertiste `lat` y `lng`. En Mexico la latitud ronda 20 y la longitud -103 |

---

## Creditos

Datos y teselas del mapa: **(c) OpenStreetMap contributors**, bajo
[ODbL](https://www.openstreetmap.org/copyright). La atribucion va estampada en
cada imagen que genera la API.

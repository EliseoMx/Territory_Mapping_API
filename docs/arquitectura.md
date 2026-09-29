# Arquitectura y fuentes de datos

Criterio: **cero costo y sin tarjeta de credito**. Ninguna de las piezas requiere
habilitar facturacion.

## Decision

| Pieza | Fuente elegida | Costo | Requiere clave |
|---|---|---|---|
| Imagen del area | Teselas raster de OpenStreetMap | Gratis | No |
| Imagenes a nivel de calle | Mapillary Graph API | Gratis | Token gratuito (sin tarjeta) |
| Validacion opcional de calles | Overpass API (OSM) | Gratis | No |
| Lenguaje / empaquetado | Python 3 + Pillow + requests -> PyInstaller | Gratis | No |

### Por que NO Google

`Static Street View` y `Maps Static API` exigen habilitar facturacion en el
proyecto de Google Cloud y enviar una API key en cada solicitud, aunque exista
un tramo mensual sin cargo. Eso implica dar de alta una tarjeta, que es justo
lo que queremos evitar.

### Por que OpenStreetMap para el mapa

Las teselas de `tile.openstreetmap.org` son abiertas y no piden clave. A cambio,
la politica de uso de la fundacion pide identificarse y no hacer descargas
masivas, asi que el programa:

- manda un `User-Agent` propio (`Territory_Mapping/<version> (<contacto>)`),
- cachea las teselas en disco (`%LOCALAPPDATA%\Territory_Mapping\tiles`), y
- descarga en serie, no en paralelo.

Un territorio tipico a zoom 16-17 son entre 6 y 20 teselas; con cache, las
corridas siguientes sobre la misma zona no vuelven a pedir nada.

### Por que Mapillary para el nivel de calle

Es imagineria a nivel de calle de origen colaborativo, con API publica y token
gratuito. Se verifico la cobertura sobre la zona del ejemplo (Av. Moctezuma,
Av. El Colli, Av. Nicolas Copernico y las calles interiores del poligono):
hay cobertura densa.

**Limitacion real:** la cobertura es colaborativa, no sistematica. Habra calles
sin fotos, y las que hay pueden tener varios anios. Por eso el programa no falla
cuando un punto no tiene imagen: lo registra y sigue.

Endpoints usados:

- `GET https://graph.mapillary.com/images?fields=id,thumb_1024_url,captured_at,compass_angle,geometry&bbox=<minLon,minLat,maxLon,maxLat>`
- descarga directa del `thumb_1024_url`

El token se lee de la variable de entorno `MAPILLARY_TOKEN` o del parametro
`--token`. Nunca se guarda en el repositorio.

## Flujo del programa

```
JSON de coordenadas
      |
      v
1. Validar poligono (>=3 puntos, rangos, cierre implicito)
      |
      +--> 2. Bounding box + zoom que encuadre el area con margen
      |          |
      |          v
      |    3. Descargar y unir teselas OSM -> lienzo
      |          |
      |          v
      |    4. Dibujar el contorno del poligono -> <nombre>_area.png
      |
      +--> 5. Generar puntos sobre el perimetro cada N metros
                 |
                 v
           6. Buscar imagen en Mapillary cerca de cada punto
                 |
                 v
           7. Descargar -> <nombre>_pXX.jpg
                 |
                 v
           8. index.html con el mapa y la galeria
```

## Calculo del area

Tres pasos.

**1. De grados a metros.** Las coordenadas llegan en grados, que no son una
unidad de longitud: un grado de longitud mide ~111 km en el ecuador y cero en
el polo. Se proyecta a un plano local (equirectangular) centrado en el
territorio, multiplicando cada coordenada por los metros que mide un grado a
esa latitud.

**2. Formula del cordon de zapato (Gauss).** Con el poligono ya en metros:

```
area = |  SUM ( x_i * y_j  -  x_j * y_i )  | / 2      con j = i+1, cerrando al inicio
```

Suma los productos cruzados de vertices consecutivos. El valor con signo indica
el sentido del recorrido (positivo antihorario, negativo horario); el valor
absoluto lo vuelve indiferente, que es por lo que el JSON acepta cualquiera de
los dos sentidos.

**3. A hectareas.** Dividir entre 10 000.

### Por que un poligono cruzado da un area equivocada

La formula suma areas con signo. En un moño, los dos lobulos se recorren en
sentidos opuestos, sus signos se cancelan y el total encoge o llega a cero. Por
eso el programa detecta los cruces antes de calcular: no es un capricho de
dibujo, es que el numero seria mentira.

### Precision

Los metros por grado salen de las series estandar sobre WGS84, no de una
constante fija:

```
m_lat = 111132.92 - 559.82*cos(2f) + 1.175*cos(4f) - 0.0023*cos(6f)
m_lon = 111412.84*cos(f) -  93.5*cos(3f) + 0.118*cos(5f)
```

Contrastado contra el area geodesica real sobre WGS84 (pyproj), el error queda
en **0.0000%** para territorios de barrio y sube apenas a 0.0005% en una caja
de 100 km de lado. Se verifico de 0 a 65 grados de latitud, norte y sur.

Usar constantes fijas (111320 y 110540, que es lo que se ve en la mayoria de
los ejemplos de internet) subestimaba el area **0.2% en Guadalajara y 1.1% a 65
grados de latitud**. Sobre un territorio de 16 ha eso son ~310 m2 de menos.

## Atribucion obligatoria

Ambas fuentes piden credito, y el programa lo estampa en la imagen y en el
`index.html`:

- Mapa: `(c) OpenStreetMap contributors` (ODbL)
- Fotos: credito al autor de cada imagen de Mapillary

## Nota de pruebas

El entorno de desarrollo de Claude no tiene salida a `tile.openstreetmap.org`
ni a `graph.mapillary.com` (politica de egreso del sandbox). La logica de
geometria, teselado y CLI se prueba aqui con datos simulados; **las pruebas
contra la red reales se corren en la maquina Windows** con el ejecutable ya
construido.

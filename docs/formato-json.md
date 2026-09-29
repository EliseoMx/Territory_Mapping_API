# Formato del JSON de entrada

El archivo contiene **unicamente las ubicaciones**: un arreglo de puntos en el
orden en que se recorre el perimetro del territorio.

```json
[
  { "lat": 20.650546, "lng": -103.436033 },
  { "lat": 20.650546, "lng": -103.432361 },
  { "lat": 20.646729, "lng": -103.432361 },
  { "lat": 20.646729, "lng": -103.436033 }
]
```

## Reglas

| Regla | Detalle |
|---|---|
| Raiz | Arreglo JSON. Nada mas. |
| Campos por punto | Solo `lat` y `lng`, numeros decimales (WGS84). |
| Minimo | 3 puntos. Con menos no hay area que dibujar. |
| Orden | El del arreglo. Define el trazo del perimetro. |
| Cierre | Implicito: el ultimo punto se une al primero. No repetir el primero al final. |
| Sentido | Indistinto (horario o antihorario). |
| Desorden | Si los lados se cruzan, la API reordena sola por circuito mas corto. |
| Rangos | `lat` entre -90 y 90; `lng` entre -180 y 180. |

Se aceptan tambien `lon` y `lng` como nombre de la longitud.

## Ejemplos

| Archivo | Que es |
|---|---|
| `samples/territorio_ejemplo.json` | Cuadrilatero de 4 puntos: Av. Moctezuma, Av. Nicolas Copernico, Av. El Colli y C. Paseo de los Volcanes (Zapopan). |
| `samples/territorio_subzona.json` | Mitad norte del mismo territorio, cortada en Calle Playa de Santiago. |

## Todo lo demas va en la URL

Como el JSON solo lleva coordenadas, la configuracion viaja como parametros de
la URL, con los mismos defaults que el ejecutable:

```
POST /imagen?ancho=1600&opacidad=0&sin_pines=true
```

| Parametro | Default | Descripcion |
|---|---|---|
| `ancho` / `alto` | `1280` / `1024` | Tamano de la imagen en pixeles (200 a 4000). |
| `margen` | `8` | Porcentaje de aire alrededor del poligono (0 a 45). |
| `color` | `E94235` | Color del contorno en RRGGBB. Es el rojo del pin. |
| `grosor` | `4` | Grosor del contorno en pixeles. |
| `opacidad` | `8` | Opacidad del relleno, 0 a 100. Con `0` no rellena. |
| `pin` | `34` | Alto del pin en pixeles. |
| `sin_pines` | `false` | No dibuja el pin en cada vertice. |
| `sin_ordenar` | `false` | Respeta el orden del JSON tal cual, aunque el poligono se cruce. Por defecto se corrige solo. |
| `formato` | `png` | `png` o `jpg`. |

Tambien pueden ir dentro del cuerpo, envolviendo la lista:

```json
{ "coordenadas": [ ... ], "opciones": { "ancho": 1600 } }
```

## Paleta

| Elemento | Color |
|---|---|
| Cuerpo del pin y contorno | `#E94235` |
| Circulo interior del pin | `#B20D0D` |
| Relleno del area | `#E94235` al 8% |

El relleno usa el mismo rojo que el contorno y los pines, a muy baja opacidad:
el area se lee como un solo objeto y las calles, los nombres y los parques del
mapa siguen siendo legibles por debajo. Si lo quieres aun mas tenue, `opacidad=5`;
si lo quieres solo con contorno, `opacidad=0`.

## De donde salen las coordenadas de los ejemplos

No son estimadas a ojo: se calcularon como la **interseccion real** de los ejes
de las calles, usando la geometria de OpenStreetMap consultada via Overpass API.
Donde la avenida tiene cuerpos separados se promedian los cruces de ambos.

| Vertice | Cruce |
|---|---|
| 1 | Av. Moctezuma x C. Paseo de los Volcanes |
| 2 | Av. Moctezuma x Av. Nicolas Copernico |
| 3 | Av. El Colli x Av. Nicolas Copernico |
| 4 | Av. El Colli x C. Paseo de los Volcanes |

El poligono **no es un rectangulo**: Av. El Colli corre en diagonal, asi que el
lado sur esta inclinado respecto al norte. Es un buen caso de prueba.

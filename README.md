# Cartagra ~Affliction of the Soul~ — Traducción al Español

Parche de traducción al español del juego **Cartagra ~Affliction of the Soul~**
(Innocent Grey / MangaGamer).

Este repositorio contiene **las herramientas, la documentación y el guion
traducido** (`script.pac`). No se distribuyen assets gráficos del juego.

> ⚠️ Compra el juego original para apoyar a sus creadores. Este es un proyecto
> de traducción por afición.

## Contenido

| Archivo | Descripción |
|---|---|
| `script.pac` | Guion del juego traducido al español (texto). Reemplaza el de tu instalación. |
| `herramientas/cartagra_tool.py` | Descifra / cifra / extrae / inserta texto del guion. |
| `herramientas/mgpk.py` | Extractor / reempaquetador del contenedor MGPK (`.pac`). |
| `herramientas/translate_big.py` | Traductor MT (Marian OPUS en→es) usado para generar la traducción. |
| `herramientas/patch_atlas.py` | Redibuja labels de la interfaz sobre los atlas de Unity. |
| `herramientas/pack_bundle.py` | Reempaqueta los atlas editados en `sharedassets0.assets`. |
| `fuentes/` | Bitstream Vera Sans Mono (fuente del juego, para el redibujado). |

## Qué está traducido

- **19.825 cadenas**: todo el diálogo, narración, monólogos, textos del prólogo
  y las opciones de menú de decisiones (por ejemplo "Aceptar" / "Rechazar").
- **Menú e interfaz** (etiquetas que son imágenes dentro de atlas de Unity):
  - `MainUI`: Q.SAVE→G.RÁPIDO, Q.LOAD→C.RÁPIDO, SKIP→SALTAR, SYSTEM→SISTEMA, AUTO→AUTO
  - `SystemMenu`: Backlog→Historial, Config Menu→Configuración, Exit→Salir, Save→Guardar, Load→Cargar
  - `SaveLoad`: NO DATA→SIN DATOS, Date→Fecha, Scene→Escena, comment→comentario, QUICK SAVE→GUARDADO RÁPIDO
  - `ConfigScreen`: títulos y valores (Ventana, Pant. completa, Vol. SFX, Vol. música,
    Vel. texto, Lenta/Rápida, SÍ/NO, Restaurar, Cancelar, Probar voz, etc.)
- Los **nombres de personaje** y honoríficos se conservan tal cual.
- El símbolo `■■` (nombre censurado por MangaGamer) se mantiene literal.

## Correcciones aplicadas

- **Gritos del traductor MT recortados.** El modelo convertía gritos cortos
  (`"Nooooooo!"`) en cadenas de 40–160 caracteres sin espacios, y el motor de
  ajuste de línea por palabras se colgaba (imagen congelada). Se limitaron esas
  palabras repetidas a ≤12 caracteres. Afectó a 73 líneas.
- **Compresor CLZF2 exacto.** El `.pac` se reempaqueta con un port puro de
  **CLZF2** (byte-exacto), no con `liblzf`.

## Qué NO está traducido

- Textos que el juego dibuja desde otros recursos de Unity (no cubiertos por
  `script.pac` ni por los atlas `MainUI`/`SystemMenu`/`SaveLoad`/`ConfigScreen`).

## Instalación

### 1. Guion (`script.pac`)

Copia `script.pac` sobre el original:

- **Windows:** `<Instalación>\GameData\script.pac`
- **Linux/Wine:** `<prefix>/drive_c/.../GameData/script.pac`

Respalda el original antes de nada.

### 2. Interfaz (atlas de Unity)

Las etiquetas del menú son imágenes dentro de `main_Data/sharedassets0.assets`.
Para traducirlas, usa las herramientas incluidas (necesitas tu copia del juego):

```bash
# 1) Extrae los atlas del bundle del juego (ver pack_bundle.py / patch_atlas.py)
# 2) Edita/redibuja los labels con patch_atlas.py (fuente en fuentes/)
# 3) Reempaqueta con pack_bundle.py y reemplaza sharedassets0.assets
```

Respalda `sharedassets0.assets` antes de reemplazarlo.

## Cómo revertir

Copia tu respaldo original sobre `script.pac` y `sharedassets0.assets`.

## Notas técnicas (para curiosos)

El juego **no** guarda el texto en claro: cada `.txt` dentro de `script.pac`
está comprimido con LZF y luego cifrado con un XOR de clave rodante de 11 bytes.

```
disco  ->  XOR rolling (clave de 11 bytes)  ->  LZF decompress  ->  texto claro
texto  ->  LZF compress  ->  XOR rolling     ->  disco
```

Clave XOR (11 bytes):

```
E5 65 BA 1A 3D C6 7F 9E 46 15 89
```

El contenedor `.pac` usa el formato **MGPK**:

```
magic "MGPK" + u32 version(1) + u32 count
por cada entrada: u8 len(name) + name + ... + u32 offset + u32 size
```

Los atlas de la interfaz son texturas **DXT5** dentro de `sharedassets0.assets`.
**Detalle importante:** al reempaquetar con UnityPy, los canales RGBA se rotan
(el bundle lee `(R,G,B,A)` como `(G,B,A,R)`). Hay que inyectar con
`inj = (A,R,G,B)` del color objetivo o los colores saldrán alterados en el juego.
Ver `pack_bundle.py`.

Herramientas para reproducir todo el proceso:

```bash
# Descifrar los .txt de un .pac
python3 mgpk.py x script.pac carpeta_extraida
python3 cartagra_tool.py dec carpeta_extraida carpeta_texto

# ...traducir los .txt...

# Cifrar, empaquetar e insertar en el .pac
python3 cartagra_tool.py enc carpeta_texto carpeta_cifrada
python3 mgpk.py r script.pac.original_backup nuevo.pac carpeta_cifrada
```

## Créditos

- Juego original: © Innocent Grey / MangaGamer.
- Traducción automática al español: modelo `Helsinki-NLP/opus-mt-tc-big-en-es`
  con revisión de formato.
- Fuente: Bitstream Vera Sans Mono (ver `fuentes/LICENSE`).

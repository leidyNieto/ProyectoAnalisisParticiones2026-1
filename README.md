# Proyecto-20261

Este repositorio contiene tres implementaciones principales para el analisis de MIP/IIT:

1. `QNodes` (base clasica, antes referida como Proyecto-2025A)
2. `GeoMIP/src/Method2_Dynamic_Programming_Reformulation`

## Requisitos

- Linux (probado en Ubuntu)
- Python 3.11+ (hay entornos locales con 3.12)
- `uv` instalado

Instalacion de `uv` (si no lo tienes):

```bash
pip install uv
```

## Estructura Rapida

- `QNodes/`: ejecucion directa de un caso de prueba (`exec.py`).
- `GeoMIP/src/Method1_GPU_Accelerated/`: procesamiento por lotes desde Excel.
- `GeoMIP/src/Method2_Dynamic_Programming_Reformulation/`: procesamiento por lotes desde Excel.
- `GeoMIP/data/samples/`: datasets TPM `N*.csv` usados por Method1/Method2.
- `GeoMIP/results/`: archivos Excel de entrada/salida para Method1/Method2.

## 1) Ejecutar QNodes

### Dependencias

Desde `QNodes/`:

```bash
cd QNodes
uv sync
```

### Ejecucion

```bash
uv run exec.py
```

### Que hace

- Carga una red desde `QNodes/src/.samples/` (segun el estado inicial y pagina configurada).
- Ejecuta estrategia `BruteForce` desde `QNodes/src/main.py`.
- Imprime la solucion en consola.

### Ajustes comunes

Edita `QNodes/src/main.py`:

- `estado_inicial`
- `condiciones`
- `alcance`
- `mecanismo`

Si termina muy rapido, no necesariamente es error: puede ser un caso pequeno o corte temprano cuando `phi = 0`.

## 3) Ejecutar Method2_Dynamic_Programming_Reformulation

### Dependencias

Desde `GeoMIP/src/Method2_Dynamic_Programming_Reformulation/`:

```bash
cd GeoMIP/src/Method2_Dynamic_Programming_Reformulation
uv sync
```

### Ejecucion

```bash
uv run exec.py
```

### Entrada por defecto

- Excel entrada: `GeoMIP/results/PruebasIniciales.xlsx`
- Columnas esperadas:
  - `Sistema` — mascara binaria o letras (condicionamiento completo)
  - `Sistema candidato` — variables que permanecen tras condicionar
  - `Estado inicial` — cadena binaria (ej. `100` para 3 nodos)
  - `Subcandidato` — subsistema como `alcance|mecanismo` en letras o binario (ej. `ABC|abc`)

Tambien acepta el formato legado (`Subsistema` con `alcance|mecanismo` en columna B).

Variables de entorno opcionales:

- `GEOMIP_INPUT_XLSX` — ruta al Excel de pruebas
- `GEOMIP_OUTPUT_XLSX` — ruta de salida
- `GEOMIP_STRATEGY` — `Geometric` (default, GeoMIP k=2..5 sin fuerza bruta) o `KPartition` (solo validacion exhaustiva)
- `GEOMIP_SHEET` — indice de hoja (default `0`)

### Salida por defecto

- Excel salida: `GeoMIP/results/resultados_Geometric.xlsx`
- Columnas: k optimo, particion, perdida (φ), tiempo de ejecucion

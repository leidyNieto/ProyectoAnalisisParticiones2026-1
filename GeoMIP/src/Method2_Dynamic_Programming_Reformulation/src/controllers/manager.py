from dataclasses import dataclass
from pathlib import Path
import time
import os

import numpy as np

from src.models.base.application import aplicacion
from src.constants.base import (
    ABC_START,
    COLON_DELIM,
    CSV_EXTENSION,
    SAMPLES_PATH,
    RESOLVER_PATH,
)


@dataclass
class Manager:
    """
    El gestor es el encargado de en función al tamaño del estado inicial y la página asociada 
    traer el fichero de formato CSV con las TPM's almacenadas en `.samples/` para hacer una 
    rápida depuración de los datos para la creación de sistemas.

    Args:
    ----
        - `estado_inicial` (str): Dado se manejan sistemas binarios es un número base dos de tamaño asociado a la red que 
          se quiera cargar.
        - `pagina` (str): En la ruta de samples se tiene un literal asociado al tamaño de las redes por si se necesita
          añadir varias de un mismo tamaño.ruta_base (Path): Ruta donde se encuentran las muestras de TPMs en 
          representación estado-nodo-on (TPM estado-nodo simplificada).

    Returns:
    -------
        Manager: Así mismo se encarga de asociar el directorio donde se mostrarán análisis de las ejecuciones, donde sea el programador haga uso del módulo de logging y profilling.
    """

    estado_inicial: str
    ruta_base: Path = Path(SAMPLES_PATH)

    def __post_init__(self) -> None:
        """Resolve sample path across legacy and current repository layouts."""
        env_samples_dir = os.getenv("GEOMIP_SAMPLES_DIR")
        if env_samples_dir:
            env_path = Path(env_samples_dir).expanduser().resolve()
            if env_path.exists():
                self.ruta_base = env_path
                return

        method2_root = Path(__file__).resolve().parents[2]
        geomip_root = Path(__file__).resolve().parents[4]
        candidates = (
            method2_root / "src" / ".samples",
            method2_root / ".samples",
            geomip_root / "data" / "samples",
        )

        for candidate in candidates:
            if candidate.exists():
                self.ruta_base = candidate
                return

        # Keep the configured default but as an absolute path from Method2 root.
        self.ruta_base = (method2_root / self.ruta_base).resolve()

    @property
    def pagina(self) -> str:
        return aplicacion.pagina_sample_network

    @property
    def tpm_filename(self) -> Path:
        return (
            self.ruta_base / f"N{len(self.estado_inicial)}{self.pagina}.{CSV_EXTENSION}"
        )

    @property
    def output_dir(self) -> Path:
        return Path(
            f"{RESOLVER_PATH}/N{len(self.estado_inicial)}{self.pagina}/{self.estado_inicial}"
        )

    def generar_red(self, dimensiones: int, datos_discretos: bool = True) -> str:
        """
        Se encarga de generar una red (TPM) en notación little endian para un sistema determinista o no determinista 
        (esto en función a si contiene datos discretos o no respectivamente. Nunca confundir con un "Sistema continuo" 
        puesto apela a otra definición totalmente diferente).
        La red generada se almacenará en el "output_dir", un atributo dinámico en función a que si generaste una red de 
        un tamaño X por primera vez, estará etiquetada como "A", si deseas generar otra red del mismo tamaño se generará
        automáticamente con etiqueta "B", "C", etc., cada una con datos diferentes basados en variaciones de la semilla.

        Args:
            dimensiones (int): Número de nodos/elementos/variables/canales que se desea maneje la red, obteniendo un Sistema que para cada estado en $(t)$ tendrá un canal en $(t+1)$.
            datos_discretos (bool, optional): Selecciona si se quiere que la red generada sea no determinista, con el valor de probabilidad como siempre, un real positivo entre 0 y 1 inclusivo. Por defecto es True.

        Raises:
            ValueError: Si las dimensiones son menores a 1.

        Returns:
            str: El nombre del archivo generado (ej: N20A.csv, N20B.csv, etc.)
        """
        if dimensiones < 1:
            raise ValueError("Las dimensiones deben ser positivas")

        # Calcular tamaño y tiempo estimado
        num_estados = 1 << dimensiones
        total_size_gb = (num_estados * dimensiones*4) / (1024**3)
        estimated_time = total_size_gb * 2

        print(f"Tamaño estimado: {total_size_gb:.6f} GB")
        print(f"Tiempo estimado: {estimated_time:.1f} segundos")

        if total_size_gb > 1:
            if (
                input("El sistema ocupará más de 1GB. ¿Continuar? (s/n): ").lower()
                != "s"
            ):
                return None

        # Verificar archivos existentes y generar nuevo nombre
        base_path = Path(SAMPLES_PATH)
        base_path.mkdir(parents=True, exist_ok=True)

        suffix = ABC_START
        variant_number = 0
        while (base_path / f"N{dimensiones}{suffix}.{CSV_EXTENSION}").exists():
            variant_number += 1
            suffix = chr(ord(ABC_START) + variant_number)
            if variant_number > 25:
                raise RuntimeError(f"Se alcanzó el límite de variantes (26) para N{dimensiones}")

        filename = f"N{dimensiones}{suffix}.{CSV_EXTENSION}"
        filepath = base_path / filename

        # Generar estados
        print("Generando estados...")
        start_time = time.time()

        # Variar la semilla según el número de variante para generar TPMs diferentes
        seed = aplicacion.semilla_numpy + variant_number * 1000
        np.random.seed(seed)

            # 1. Probabilidades base en [0.2, 0.8] — evita ruido blanco puro (0.5)
        states = np.random.uniform(
                0.2, 0.8, size=(num_estados, dimensiones)
            ).astype(np.float32)
            # 2. Representación binaria de cada índice de fila
            #    Permite introducir dependencia causal entre nodos según el estado
        state_indices = np.arange(num_estados)[:, np.newaxis]
        shifts        = np.arange(dimensiones - 1, -1, -1)
        binary_states = (state_indices >> shifts) & 1
 
            # 3. Vecinos circulares — cada nodo depende de sus adyacentes en la cadena
        left_neighbors  = np.roll(binary_states, shift=1,  axis=1)
        right_neighbors = np.roll(binary_states, shift=-1, axis=1)
 
            # 4. Ajuste de probabilidades según vecindad activa
            #    Crea alta integración φ: cualquier partición pierde información causal
        states += 0.15 * left_neighbors    # vecino izquierdo sube probabilidad
        states -= 0.10 * right_neighbors   # vecino derecho baja probabilidad
 
            # 5. Clamp estricto — EMD necesita probabilidades en (0, 1) abierto
        states = np.clip(states, 0.000001, 0.999999)

        print(f"Generación completada en {time.time() - start_time:.2f} segundos")

        # Guardar archivo
        print(f"Guardando en {filepath}...")
        start_time = time.time()
        # np.savetxt(
        #     filepath, states, delimiter=COLON_DELIM, fmt="%d" if datos_discretos else "%.6f"
        # )
        CHUNK_ROWS = 65_536
        fmt        = "%.6f"
 
        with open(filepath, "w") as f:
            for start in range(0, num_estados, CHUNK_ROWS):
                end = min(start + CHUNK_ROWS, num_estados)
                np.savetxt(f, states[start:end], delimiter=COLON_DELIM, fmt=fmt)
                pct = end / num_estados * 100
                print(f"  [{pct:5.1f}%] {end:,}/{num_estados:,} filas escritas", end="\r")
        print()

        file_size_gb = os.path.getsize(filepath) / (1024**3)
        print(f"Archivo guardado: {file_size_gb:.6f} GB")
        print(f"Tiempo de guardado: {time.time() - start_time:.2f} segundos")

        return filename

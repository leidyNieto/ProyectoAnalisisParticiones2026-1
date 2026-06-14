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
        PROJECT_ROOT = Path(__file__).resolve().parents[4]
        candidates = (
            method2_root / "src" / ".samples",
            method2_root / ".samples",
            PROJECT_ROOT / "data" / "samples",
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

    def generar_red(
        self,
        dimensiones: int,
        datos_discretos: bool = True,
        pagina: str | None = None,
        auto_confirm: bool = False,
    ) -> str | None:
        """
        Genera una TPM en ``self.ruta_base``. Si ``pagina`` se indica (ej. ``A``),
        crea ``N{dimensiones}{pagina}.csv``; si no, usa la primera letra libre (A, B, …).
        """
        if dimensiones < 1:
            raise ValueError("Las dimensiones deben ser positivas")

        if pagina is None:
            suffix = ABC_START
            variant_number = 0
            while (self.ruta_base / f"N{dimensiones}{suffix}.{CSV_EXTENSION}").exists():
                variant_number += 1
                suffix = chr(ord(ABC_START) + variant_number)
                if variant_number > 25:
                    raise RuntimeError(
                        f"Se alcanzo el limite de variantes (26) para N{dimensiones}"
                    )
        else:
            suffix = pagina.upper()
            variant_number = ord(suffix) - ord(ABC_START)

        return self._escribir_tpm(
            dimensiones, suffix, variant_number, datos_discretos, auto_confirm
        )

    def _escribir_tpm(
        self,
        dimensiones: int,
        suffix: str,
        variant_number: int,
        datos_discretos: bool,
        auto_confirm: bool,
    ) -> str | None:
        num_estados = 1 << dimensiones
        total_size_gb = (num_estados * dimensiones * 4) / (1024**3)
        estimated_time = total_size_gb * 2

        filename = f"N{dimensiones}{suffix}.{CSV_EXTENSION}"
        filepath = self.ruta_base / filename

        if filepath.exists():
            print(f"TPM ya existe: {filepath}")
            return filename

        print(f"Generando TPM {filename} ...")
        print(f"Tamaño estimado: {total_size_gb:.6f} GB")
        print(f"Tiempo estimado: {estimated_time:.1f} segundos")

        if total_size_gb > 1 and not auto_confirm:
            if os.getenv("GEOMIP_AUTO_TPM", "").lower() not in ("1", "true", "si", "s"):
                print(
                    f"TPM {filename} supera 1 GB. "
                    "Defina GEOMIP_AUTO_TPM=1 para generar sin confirmacion."
                )
                return None
            print("GEOMIP_AUTO_TPM=1: generando sin confirmacion interactiva.")

        self.ruta_base.mkdir(parents=True, exist_ok=True)

        print("Generando estados...")
        start_time = time.time()

        seed = aplicacion.semilla_numpy + variant_number * 1000
        np.random.seed(seed)

        states = np.random.uniform(0.2, 0.8, size=(num_estados, dimensiones)).astype(
            np.float32
        )
        state_indices = np.arange(num_estados)[:, np.newaxis]
        shifts = np.arange(dimensiones - 1, -1, -1)
        binary_states = (state_indices >> shifts) & 1

        left_neighbors = np.roll(binary_states, shift=1, axis=1)
        right_neighbors = np.roll(binary_states, shift=-1, axis=1)

        states += 0.15 * left_neighbors
        states -= 0.10 * right_neighbors
        states = np.clip(states, 0.000001, 0.999999)

        print(f"Generacion completada en {time.time() - start_time:.2f} segundos")

        print(f"Guardando en {filepath}...")
        start_time = time.time()
        chunk_rows = 65_536
        fmt = "%.6f"

        with open(filepath, "w") as f:
            for start in range(0, num_estados, chunk_rows):
                end = min(start + chunk_rows, num_estados)
                np.savetxt(f, states[start:end], delimiter=COLON_DELIM, fmt=fmt)
                pct = end / num_estados * 100
                print(f"  [{pct:5.1f}%] {end:,}/{num_estados:,} filas escritas", end="\r")
        print()

        file_size_gb = os.path.getsize(filepath) / (1024**3)
        print(f"Archivo guardado: {file_size_gb:.6f} GB")
        print(f"Tiempo de guardado: {time.time() - start_time:.2f} segundos")

        return filename

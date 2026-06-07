"""Generación de k-particiones para mecanismo y purview."""

from itertools import product
from typing import Generator, Iterator

import numpy as np
from numpy.typing import NDArray


def _asignacion_a_partes(
    indices: NDArray[np.int8],
    asignacion: tuple[int, ...],
    k: int,
) -> list[NDArray[np.int8]]:
    partes: list[list[int]] = [[] for _ in range(k)]
    for idx, parte in zip(indices, asignacion):
        partes[parte].append(int(idx))
    return [np.array(p, dtype=np.int8) for p in partes]


def es_particion_trivial(
    partes_purview: list[NDArray[np.int8]],
    partes_mecanismo: list[NDArray[np.int8]],
) -> bool:
    """Descarta cortes donde una sola parte concentra todo el sistema."""
    n_purview = sum(p.size for p in partes_purview)
    n_mecanismo = sum(p.size for p in partes_mecanismo)
    if n_purview == 0 and n_mecanismo == 0:
        return True

    for j in range(len(partes_purview)):
        if partes_purview[j].size == n_purview and partes_mecanismo[j].size == n_mecanismo:
            return True
    return False


def enumerar_k_particiones(
    dims_mecanismo: NDArray[np.int8],
    indices_purview: NDArray[np.int8],
    k: int,
) -> Generator[tuple[list[NDArray[np.int8]], list[NDArray[np.int8]]], None, None]:
    """
    Enumera asignaciones de mecanismo y purview en exactamente k partes no triviales.

    Yields:
        Tuplas (partes_purview, partes_mecanismo) con k arreglos cada una.
    """
    m = dims_mecanismo.size
    v = indices_purview.size

    if k < 2 or m + v < k:
        return

    mech_assignments: Iterator[tuple[int, ...]]
    purv_assignments: Iterator[tuple[int, ...]]

    if m == 0:
        mech_assignments = iter([tuple()])
    else:
        mech_assignments = (
            a for a in product(range(k), repeat=m) if len(set(a)) == k
        )

    if v == 0:
        purv_assignments = iter([tuple()])
    else:
        purv_assignments = (
            a for a in product(range(k), repeat=v) if len(set(a)) == k
        )

    for mech_a in mech_assignments:
        partes_mec = _asignacion_a_partes(dims_mecanismo, mech_a, k) if m else [np.array([], dtype=np.int8)] * k
        for purv_a in purv_assignments:
            partes_pur = _asignacion_a_partes(indices_purview, purv_a, k) if v else [np.array([], dtype=np.int8)] * k
            if es_particion_trivial(partes_pur, partes_mec):
                continue
            yield partes_pur, partes_mec


def enumerar_biparticiones_binarias(
    dims_mecanismo: NDArray[np.int8],
    indices_purview: NDArray[np.int8],
) -> Generator[tuple[list[NDArray[np.int8]], list[NDArray[np.int8]]], None, None]:
    """
    Biparticiones mediante ``generar_particiones`` (más eficiente para k=2).
    """
    from src.funcs.system import generar_particiones

    m = dims_mecanismo.size
    v = indices_purview.size
    if m < 1 and v < 1:
        return

    if m >= 1 and v >= 1:
        for mech_bits, purv_bits in generar_particiones(m, v, as_generator=True):
            partes_mec = [
                dims_mecanismo[np.where(mech_bits)[0].astype(np.int8)],
                dims_mecanismo[np.where(1 - mech_bits)[0].astype(np.int8)],
            ]
            partes_pur = [
                indices_purview[np.where(purv_bits)[0].astype(np.int8)],
                indices_purview[np.where(1 - purv_bits)[0].astype(np.int8)],
            ]
            if not es_particion_trivial(partes_pur, partes_mec):
                yield partes_pur, partes_mec
        return

    yield from enumerar_k_particiones(dims_mecanismo, indices_purview, 2)

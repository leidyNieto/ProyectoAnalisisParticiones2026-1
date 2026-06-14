"""Estrategia geométrica GeoMIP: k-particiones via tabla de costos (sin fuerza bruta)."""

#from math import dist
import time
from typing import Dict, List, Tuple

import numpy as np

COST_DTYPE = np.float32  # tabla de costos en float32 (mitad de memoria que float64)

from src.constants.base import ACTUAL, EFECTO, NET_LABEL, TYPE_TAG
from src.constants.models import (
    GEOMETRIC_ANALYSIS_TAG,
    GEOMETRIC_LABEL,
    GEOMETRIC_STRAREGY_TAG,
)
from src.controllers.manager import Manager
from src.funcs.base import emd_efecto
from src.funcs.format import fmt_biparte_q, fmt_k_particion, partes_a_clave
from src.middlewares.profile import profile, profiler_manager
from src.middlewares.slogger import SafeLogger
from src.models.base.sia import SIA
from src.models.core.solution import Solution


class GeometricSIA(SIA):
    """Encuentra la k-partición óptima (k=2..5) usando únicamente el enfoque geométrico."""

    K_MIN = 2
    K_MAX = 5

    def __init__(self, gestor: Manager):
        super().__init__(gestor)
        profiler_manager.start_session(
            f"{NET_LABEL}{len(gestor.estado_inicial)}{gestor.pagina}"
        )
        self.logger = SafeLogger(GEOMETRIC_STRAREGY_TAG)
        self.sia_logger = self.logger
        self.tabla_transiciones: dict = {}
        self.vertices: set[tuple] = set()
        self.memoria_particiones: dict = {}
        self._flat_data: list = []
        self.idx_ncubos: list[int] = []
        self.caminos: Dict[int, List[List[int]]] = {}
        self.estado_inicial: np.ndarray = np.array([])
        self.estado_final: np.ndarray = np.array([])

    @profile(context={TYPE_TAG: GEOMETRIC_ANALYSIS_TAG})
    def aplicar_estrategia(
        self,
        condicion: str,
        alcance: str,
        mecanismo: str,
        tpm: np.ndarray,
    ) -> Solution:
        self.sia_preparar_subsistema(condicion, alcance, mecanismo, tpm) #! COMENTAR PARA UN SOLO ESTADO INICIAL
        # self.sia_preparar_subsistema(condicion, alcance, mecanismo) #! DESCOMENTAR PARA UN SOLO ESTADO INICIAL

        futuro = tuple(
            (EFECTO, efecto) for efecto in self.sia_subsistema.indices_ncubos
        )
        presente = tuple(
            (ACTUAL, actual) for actual in self.sia_subsistema.dims_ncubos
        )


        self._flat_data = []
        for idx, ncubo in enumerate(self.sia_subsistema.ncubos):
            # garantías: ncubo.data.shape == (2,2,...,2)
            # np.ravel() lo aplana. El orden ‘C’ equivale 
            # a little-endian si tus tuples están invertidas.
            self._flat_data.append(ncubo.data.ravel())

        self.vertices = set(presente + futuro)
        dims = self.sia_subsistema.dims_ncubos
        self.estado_inicial = self.sia_subsistema.estado_inicial[dims]
        self.estado_final = 1 - self.estado_inicial
        # print(mip)
        mejor_k, mejor_clave, mejor_perdida, mejor_dist = self.find_mip()

        return Solution(
            estrategia=GEOMETRIC_LABEL,
            perdida=mejor_perdida,
            distribucion_subsistema=self.sia_dists_marginales,
            distribucion_particion=mejor_dist,
            tiempo_total=time.time() - self.sia_tiempo_inicio,
            particion=fmt_k_particion(mejor_clave),
            k_particiones=mejor_k,
            resultados_por_k=self.resultados_por_k,
        )

    def find_mip(self) -> tuple[int, list, float, np.ndarray]:
        """Evalúa k=2..5; guarda el mejor de cada k en ``resultados_por_k``."""
        self.sia_logger.critic("empieza.")
        self._construir_tabla_costos()
        self.resultados_por_k: dict[int, dict] = {}

        mejor_k = self.K_MIN
        mejor_perdida = float("inf")
        mejor_clave: list = []
        mejor_dist = self.sia_dists_marginales.copy()

        n_elem = len(self.idx_ncubos) + len(self.estado_inicial)
        max_k = min(self.K_MAX, n_elem)

        for k in range(self.K_MIN, max_k + 1):
            t_k = time.time()
            perdida_k = float("inf")
            clave_k: list = []
            dist_k = self.sia_dists_marginales.copy()

            for partes_pur_idx, partes_mec_idx in self.identificar_candidatos_k(k):
                partes_pur = [
                    self.sia_subsistema.indices_ncubos[np.array(p, dtype=np.int8)]
                    for p in partes_pur_idx
                ]
                partes_mec = [
                    self.sia_subsistema.dims_ncubos[np.array(p, dtype=np.int8)]
                    for p in partes_mec_idx
                ]
                # dist = self.sia_subsistema.particionar_k(
                #     partes_pur, partes_mec
                # ).distribucion_marginal()
                # emd = emd_efecto(dist, self.sia_dists_marginales)
                clave = partes_a_clave(
                partes_pur,partes_mec)
                if clave in self.memoria_particiones:
                    emd, dist = self.memoria_particiones[clave]
                else:
                    dist = (
                        self.sia_subsistema
                        .particionar_k(
                        partes_pur,
                        partes_mec
                 )
                        .distribucion_marginal())
                    emd = emd_efecto(
                        dist,
                        self.sia_dists_marginales )

                    self.memoria_particiones[clave] = (
                        emd,dist)

                if emd < perdida_k:
                    perdida_k = emd
                    dist_k = dist
                    clave_k = clave

            if clave_k:

                self.resultados_por_k[k] = {
                    "particion": fmt_k_particion(clave_k),
                    "perdida": perdida_k,
                    "tiempo": time.time() - t_k,
                    "clave": clave_k,
                }
                if perdida_k < mejor_perdida:
                    mejor_perdida = perdida_k
                    mejor_dist = dist_k
                    mejor_clave = clave_k
                    mejor_k = k

        if not mejor_clave:
            mejor_perdida = 0.0

        return mejor_k, mejor_clave, mejor_perdida, mejor_dist

   
    def _construir_tabla_costos(self) -> None:
        """
        Construye la tabla de costos T[i,j] mediante BFS desde el estado inicial
        del subsistema hacia su estado complementario, nivel por nivel (Hamming
        1, 2, ..., n), aplicando la función de costo recursiva de la guía
        (Algoritmo 1).

        Complejidad O(n · 2^n): se explora el hipercubo UNA sola vez desde el
        estado inicial. (Antes se reconstruía la tabla desde los 2^n estados
        origen, lo que elevaba el costo a ~O(n · 4^n) — inviable para los
        tamaños de prueba de 15..25 nodos y, en la práctica, una exploración
        exhaustiva del espacio de estados que contradice el enfoque geométrico.)
        """
        n = len(self.estado_inicial)
        self.idx_ncubos = list(range(len(self.sia_subsistema.indices_ncubos)))
        n_fut = len(self.idx_ncubos)
        size = 1 << n
        self.full = size - 1

        ini = [int(b) for b in self.estado_inicial]
        self.base = sum(b << i for i, b in enumerate(ini))
        base = self.base

        # F[m, f]: valor X_f en el estado de mascara absoluta m (mismo indexado
        # que _flat_data: bit i con peso 2^i).
        F = np.empty((size, n_fut), dtype=COST_DTYPE)
        for f, flat in enumerate(self._flat_data):
            F[:, f] = np.asarray(flat, dtype=COST_DTYPE).ravel()

        # Tabla de costos como UN arreglo indexado por entero (reemplaza el dict
        # de 2^n claves-tupla -> menor complejidad espacial, sin parseo de str).
        self.Tcost = np.zeros((size, n_fut), dtype=COST_DTYPE)
        self.caminos = {0: [base]}

        prev = [base]
        for nivel in range(1, n + 1):
            seen: set = set()
            nivel_masks: List[int] = []
            factor = 1.0 / (1 << nivel)
            for m in prev:
                for i in range(n):
                    if ((m >> i) & 1) == ini[i]:          # bit i aun sin voltear
                        nm = m ^ (1 << i)                  # voltear hacia el final
                        if nm in seen:
                            continue
                        seen.add(nm)
                        nivel_masks.append(nm)
                        # |X[i]-X[j]| vectorizado sobre TODAS las variables futuras
                        acc = np.abs(F[base] - F[nm])
                        if nivel > 1:                      # + costos de vecinos
                            for j in range(n):
                                if ((nm >> j) & 1) != ini[j]:
                                    acc = acc + self.Tcost[nm ^ (1 << j)]
                        self.Tcost[nm] = factor * acc
            self.caminos[nivel] = nivel_masks
            prev = nivel_masks

        # Costo agregado por variable (lo que consumen los generadores de
        # candidatos): se calcula UNA vez en vez de re-sumar la tabla por llamada.
        self.costo_agregado = self.Tcost.sum(axis=0)
        self.tabla_transiciones = {}

    def identificar_candidatos_k(
        self, k: int
    ) -> List[Tuple[List[List[int]], List[List[int]]]]:
        """
        Genera candidatos geométricos para k partes sin búsqueda exhaustiva.
        Combina: marginalización simple, complementariedad por niveles Hamming,
        clustering por estados ancla y división recursiva geométrica.
        """
        vistos: set = set()
        candidatos: List[Tuple[List[List[int]], List[List[int]]]] = []

        def agregar(partes_pur: List[List[int]], partes_mec: List[List[int]]) -> None:
            partes_pur, partes_mec = self._normalizar_k_partes(partes_pur, partes_mec, k)
            if not self._particion_valida(partes_pur, partes_mec, k):
                return
            key = self._clave_candidato(partes_pur, partes_mec)
            if key not in vistos:
                vistos.add(key)
                candidatos.append((partes_pur, partes_mec))

        if k == 2:
            for presentes, futuros in self._candidatos_biparticion():
                agregar(*self._biparticion_a_k_partes(presentes, futuros))
            for pur, mec in self._candidatos_afinidad(2):
                agregar(pur, mec)
            # Mejor corte: prueba TODOS los cortes sobre las futuras ordenadas
            # por costo; find_mip se queda con el de menor pérdida exacta.
            for pur, mec in self._candidatos_corte_optimo(2):
                agregar(pur, mec)
            return candidatos

        for presentes, futuros in self._candidatos_biparticion():
            agregar(*self._expandir_a_k_partes(presentes, futuros, k))

        # anclas = self._seleccionar_ancoras(k)
        # if anclas:
        #     agregar(*self._asignar_por_ancoras(anclas, k))

        recursivo = self._division_recursiva(k)
        if recursivo:
            agregar(*recursivo)


        # Candidatos geométricos por afinidad (aislamiento + clustering +
        # división), los que alcanzan el óptimo en la validación contra fuerza
        # bruta para k >= 3.
        for pur, mec in self._candidatos_afinidad(k):
            agregar(pur, mec)

        # Mejor corte: segmenta las futuras (ordenadas por costo geométrico) en
        # k grupos contiguos probando todas las posiciones de corte (acotado).
        # Como find_mip evalúa la pérdida exacta y se queda con la mínima, esto
        # garantiza que se elige el mejor corte y no uno fijo "a la mitad".
        for pur, mec in self._candidatos_corte_optimo(k):
            agregar(pur, mec)

        return candidatos

    def _segmentaciones(self, n_items: int, k: int, cap: int) -> List[List[int]]:
        """k-1 fronteras crecientes en 1..n_items-1 (segmentos contiguos),
        en orden lexicográfico (aísla primero los grupos pequeños), hasta ``cap``
        combinaciones. Polinómico y acotado; no enumera particiones del sistema."""
        res: List[List[int]] = []

        def rec(start: int, fronteras: List[int]) -> None:
            if len(res) >= cap:
                return
            if len(fronteras) == k - 1:
                res.append(list(fronteras))
                return
            for b in range(start, n_items):
                if len(res) >= cap:
                    return
                rec(b + 1, fronteras + [b])

        if k - 1 <= n_items - 1:
            rec(1, [])
        return res

    def _candidatos_corte_optimo(
        self, k: int
    ) -> List[Tuple[List[List[int]], List[List[int]]]]:
        """Ordena las futuras por costo geométrico acumulado (las más
        independientes primero) y las parte en k segmentos contiguos, probando
        TODAS las posiciones de corte (acotadas). El mecanismo de cada segmento
        se asigna por afinidad. find_mip evalúa la pérdida exacta de cada corte y
        conserva el menor: así el corte elegido es el de mínima pérdida, no uno
        fijo a la mitad."""
        n_fut = len(self.idx_ncubos)
        n_mec = len(self.estado_inicial)
        if not (2 <= k <= n_fut):
            return []

        costo = self.costo_agregado
        orden = sorted(range(n_fut), key=lambda f: costo[f])

        if not hasattr(self, "_aff"):
            self._preparar_afinidad()

        CAP = 600
        out: List[Tuple[List[List[int]], List[List[int]]]] = []
        for fronteras in self._segmentaciones(n_fut, k, CAP):
            cortes = [0] + list(fronteras) + [n_fut]
            grupos = [orden[cortes[i]:cortes[i + 1]] for i in range(k)]
            if any(len(g) == 0 for g in grupos):
                continue
            partes_mec: List[List[int]] = [[] for _ in range(k)]
            for mp in range(n_mec):
                mejor, afin = 0, -1.0
                for g in range(k):
                    a = sum(self._aff[f][mp] for f in grupos[g])
                    if a > afin:
                        afin, mejor = a, g
                partes_mec[mejor].append(mp)
            out.append(([list(g) for g in grupos], partes_mec))
        return out

    def _candidatos_biparticion(self) -> List[Tuple[List[int], List[int]]]:
        """Candidatos k=2 por complementariedad (GeoMIP secc. 4.2.4)."""
        candidatos: List[Tuple[List[int], List[int]]] = []
        n_vars = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)

        for idx in range(n_vars):
            presentes = list(range(n_mech))
            futuros = [i for i in range(n_vars) if i != idx]
            candidatos.append((presentes, futuros))
        ranking = []

        for idx in range(n_vars):
            ranking.append((idx, float(self.costo_agregado[idx])))

        ranking.sort(key=lambda x: x[1])

        ordenados = [x[0] for x in ranking]

        for corte in range(1, n_vars):

            futuros = ordenados[:corte]
            presentes = list(range(len(self.estado_inicial)))[:max(1, min(corte, len(self.estado_inicial)-1))]
            candidatos.append(
                (presentes, futuros)
    )

        es_par = len(self.caminos) % 2 == 0
        mitad = len(self.caminos) // 2 if es_par else (len(self.caminos) // 2) + 1
        s0 = self.base
        n_mech = len(self.estado_inicial)

        for nivel in range(1, mitad):
            costo_min = float("inf")
            mejor: Tuple[List[int], List[int]] = ([], [])
            for m in self.caminos[nivel]:
                actual = self.Tcost[m]
                complementario = self.Tcost[m ^ self.full]
                presentes = [
                    idx for idx in range(n_mech)
                    if ((m >> idx) & 1) == ((s0 >> idx) & 1)
                ]
                futuros: List[int] = []
                costo = 0.0
                for idx in range(n_vars):
                    if actual[idx] <= complementario[idx]:
                        futuros.append(idx)
                        costo += actual[idx]
                    else:
                        costo += complementario[idx]
                if costo < costo_min:
                    costo_min = costo
                    mejor = (presentes, futuros)
            if mejor[0] or mejor[1]:
                candidatos.append(mejor)

        return candidatos

    def _biparticion_a_k_partes(
        self, presentes: List[int], futuros: List[int]
    ) -> Tuple[List[List[int]], List[List[int]]]:
        return self._expandir_a_k_partes(presentes, futuros, 2)

  
    def _expandir_a_k_partes(
        self,
        presentes: List[int],
        futuros: List[int],
        k: int
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """
        Expande una bipartición a k-particiones usando la tabla de costos.
        En cada iteración se divide el bloque más grande según el costo
        acumulado de las variables futuras.
        """

        n_fut = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)

        bloques = [
            (
                futuros,
                presentes
            ),
            (
                [i for i in range(n_fut) if i not in futuros],
                [i for i in range(n_mech) if i not in presentes]
            )
        ]

        while len(bloques) < k:

            idx_bloque = max(
                range(len(bloques)),
                key=lambda i: len(bloques[i][0]) + len(bloques[i][1])
            )

            fut, mec = bloques.pop(idx_bloque)

            # No se puede dividir más
            if len(fut) + len(mec) <= 1:
                bloques.append((fut, mec))
                break

            # ==========================
            # Ranking geométrico por costo
            # ==========================
            ranking_fut = []

            for variable in fut:
                ranking_fut.append((variable, float(self.costo_agregado[variable])))

            ranking_fut.sort(key=lambda x: x[1])

            futuros_ordenados = [x[0] for x in ranking_fut]

            # ==========================
            # División de variables futuras
            # ==========================
            corte_fut = max(1, len(futuros_ordenados) // 2)

            fut1 = futuros_ordenados[:corte_fut]
            fut2 = futuros_ordenados[corte_fut:]

            # ==========================
            # División de mecanismos
            # ==========================
            corte_mec = max(1, len(mec) // 2)

            mec1 = mec[:corte_mec]
            mec2 = mec[corte_mec:]

            # Evitar bloques vacíos
            if len(fut1) + len(mec1) == 0:
                fut1 = fut2[:1]
                fut2 = fut2[1:]

            if len(fut2) + len(mec2) == 0:
                fut2 = fut1[-1:]
                fut1 = fut1[:-1]

            bloques.append((fut1, mec1))
            bloques.append((fut2, mec2))

        partes_pur = [b[0] for b in bloques]
        partes_mec = [b[1] for b in bloques]

        while len(partes_pur) < k:
            partes_pur.append([])
            partes_mec.append([])

        return partes_pur[:k], partes_mec[:k]

    @staticmethod
    def _normalizar_k_partes(
        partes_pur: List[List[int]], partes_mec: List[List[int]], k: int
    ) -> Tuple[List[List[int]], List[List[int]]]:
        while len(partes_pur) < k:
            partes_pur.append([])
        while len(partes_mec) < k:
            partes_mec.append([])
        return partes_pur[:k], partes_mec[:k]


    def _division_recursiva(self, k: int) -> Tuple[List[List[int]], List[List[int]]] | None:
        """Divide recursivamente con biparticiones geométricas hasta obtener k partes."""
        n_fut = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)
        pur_labels = [0] * n_fut
        mec_labels = [0] * n_mech
        next_label = 1

        for _ in range(k - 1):
            if next_label >= k:
                break
            label_counts = {}
            for l in pur_labels:
                label_counts[l] = label_counts.get(l, 0) + 1
            for l in mec_labels:
                label_counts[l] = label_counts.get(l, 0) + 1
            target = max(label_counts, key=label_counts.get)

            idxs_fut = [i for i, l in enumerate(pur_labels) if l == target]
            idxs_mec = [i for i, l in enumerate(mec_labels) if l == target]
            if len(idxs_fut) + len(idxs_mec) < 2:
                break

            presentes, futuros = self._mejor_biparticion_local(idxs_mec, idxs_fut)
            for i in idxs_fut:
                pur_labels[i] = next_label if i not in futuros else target
            for i in idxs_mec:
                mec_labels[i] = next_label if i not in presentes else target
            next_label += 1

        partes_pur = [[] for _ in range(k)]
        partes_mec = [[] for _ in range(k)]
        for i, l in enumerate(pur_labels):
            if l < k:
                partes_pur[l].append(i)
        for i, l in enumerate(mec_labels):
            if l < k:
                partes_mec[l].append(i)
        return partes_pur, partes_mec

    def _mejor_biparticion_local(
        self, idxs_mec: List[int], idxs_fut: List[int]
    ) -> Tuple[List[int], List[int]]:
        s0 = self.base
        mitad = max(1, len(self.caminos) // 2)
        costo_min = float("inf")
        mejor_presentes: List[int] = list(idxs_mec)
        mejor_futuros: List[int] = idxs_fut[: max(1, len(idxs_fut) // 2)]

        for nivel in range(1, mitad + 1):
            for m in self.caminos.get(nivel, []):
                actual = self.Tcost[m]
                comp = self.Tcost[m ^ self.full]
                presentes = [i for i in idxs_mec if ((m >> i) & 1) == ((s0 >> i) & 1)]
                futuros: List[int] = []
                costo = 0.0
                for i in idxs_fut:
                    if actual[i] <= comp[i]:
                        futuros.append(i)
                        costo += actual[i]
                    else:
                        costo += comp[i]
                if costo < costo_min and futuros:
                    costo_min = costo
                    mejor_presentes = presentes
                    mejor_futuros = futuros

        if not mejor_futuros and idxs_fut:
            mejor_futuros = idxs_fut[:1]
        return mejor_presentes, mejor_futuros


   
    def _particion_valida(self, partes_pur, partes_mec, k):
        """Una k-partición válida cumple:
        - exactamente ``k`` bloques en purview y en mecanismo;
        - cada bloque tiene al menos una variable futura (el mecanismo puede ser
          vacío: aislar una futura sin presentes es una partición legítima y, de
          hecho, suele ser la óptima según la guía);
        - **cobertura completa y sin duplicados**: cada variable futura y cada
          dimensión presente aparece en exactamente un bloque.
        """
        if len(partes_pur) != k or len(partes_mec) != k:
            return False
        for i in range(k):
            if len(partes_pur[i]) == 0:
                return False
        n_fut = len(self.idx_ncubos)
        n_mec = len(self.estado_inicial)
        todos_fut = [x for grupo in partes_pur for x in grupo]
        todos_mec = [x for grupo in partes_mec for x in grupo]
        # sorted(...) == range(n) garantiza, a la vez, cobertura total
        # (no falta ninguna) y ausencia de duplicados (ninguna repetida).
        if sorted(todos_fut) != list(range(n_fut)):
            return False
        if sorted(todos_mec) != list(range(n_mec)):
            return False
        return True
    
    # def _particion_valida(self, partes_pur, partes_mec, k):
    #     """Una k-partición válida cumple:
    #     - exactamente ``k`` bloques en purview y en mecanismo;
    #     - cada bloque tiene al menos una variable futura Y al menos una dimensión
    #       presente: NO se consideran bloques vacíos ni en futuro ni en presente
    #       al generar las particiones;
    #     - **cobertura completa y sin duplicados**: cada variable futura y cada
    #       dimensión presente aparece en exactamente un bloque.
    #     """
    #     if len(partes_pur) != k or len(partes_mec) != k:
    #         return False
    #     for i in range(k):
    #         if len(partes_pur[i]) == 0 or len(partes_mec[i]) == 0:
    #             return False
    #     n_fut = len(self.idx_ncubos)
    #     n_mec = len(self.estado_inicial)
    #     todos_fut = [x for grupo in partes_pur for x in grupo]
    #     todos_mec = [x for grupo in partes_mec for x in grupo]
    #     # sorted(...) == range(n) garantiza, a la vez, cobertura total
    #     # (no falta ninguna) y ausencia de duplicados (ninguna repetida).
    #     if sorted(todos_fut) != list(range(n_fut)):
    #         return False
    #     if sorted(todos_mec) != list(range(n_mec)):
    #         return False
    #     return True
    
    @staticmethod
    def _clave_candidato(partes_pur: List[List[int]], partes_mec: List[List[int]]) -> tuple:
        return (
            tuple(tuple(sorted(p)) for p in partes_pur),
            tuple(tuple(sorted(p)) for p in partes_mec),
        )

    def calcular_costos_nivel(self,estado_final: np.ndarray, nivel):
        n = len(estado_final)      
        visitados:set[tuple] = set()
        self.caminos[nivel] = []
        for estado_anterior in self.caminos[nivel - 1]:
            estado_actual = np.array(estado_anterior)
            for i in range(n):
                if estado_actual[i] != estado_final[i]:
                    nuevo_estado = estado_actual.copy()
                    nuevo_estado[i] = estado_final[i]
                    nuevo_estado_tuple = tuple(nuevo_estado)
                    if nuevo_estado_tuple not in visitados:
                        self.caminos[nivel].append(nuevo_estado.tolist())
                        self.calcular_costo(self.caminos[0][0],nuevo_estado.tolist(),self.idx_ncubos)
                        visitados.add(nuevo_estado_tuple)

    def calcular_costo(self, estado_inicial:tuple, estado_final:tuple, ncubos:list[int]):
        """
            Funcion encargada de calcular el costo de transicion de transicion del estado inicial al estado final
            para las variables futuras definidas en ncubos
            aplica la funcion de costo tx(i,j)= y(|X[i]-X[j]|+ sum(tx(k,j)))
            donde:
                - y es el factor de decrecimiento 1/2^(dh(i,j))
                - dh(i,j) es la distancia hamming entre i y j
                - X[i] es el valor de probabilida de transicion de un estado para cada variable futura
                - sum(tx(i,k)) son todos costos de transicion de los vecinos de j que estan en un 
                  camino optimo desde i
        """
        key = tuple(estado_inicial), tuple(estado_final)
        if key not in self.tabla_transiciones:
            self.tabla_transiciones[key] = [None]*len(self.sia_subsistema.indices_ncubos)
        distancia_hamming = self.hamming(estado_inicial, estado_final)
        factor = 1/(2**distancia_hamming)
        # index_inicial = tuple(np.array(estado_inicial)[::-1])
        # index_final = tuple(np.array(estado_final)[::-1])


        estado_ini_int = int("".join(map(str, estado_inicial[::-1])), 2)
        estado_fin_int = int("".join(map(str, estado_final[::-1])), 2)

        # Con eso, cada flat_data[idx][...] ya te da directamente X[i] o X[j].
        diffs = np.abs(
            np.array([flat[estado_ini_int] for flat in self._flat_data])
        - np.array([flat[estado_fin_int] for flat in self._flat_data])
        )
        self.tabla_transiciones[key] = diffs.tolist()
        # for idx in ncubos:
        #     self.tabla_transiciones[key][idx] = (abs(self.sia_subsistema.ncubos[idx].data[index_inicial]-self.sia_subsistema.ncubos[idx].data[index_final]))
        
        if distancia_hamming > 1:
            for i in range(len(estado_inicial)):
                if estado_inicial[i] != estado_final[i]:
                    # Vecinos del estado FINAL revertidos un bit hacia el inicial
                    # (estados a distancia d-1 de i sobre caminos óptimos hacia j),
                    # tal como define la función de costo de la guía:
                    #   t(i,j) = γ·(|X[i]-X[j]| + Σ_{k∈N(i,j)} t(i,k))
                    nuevo_estado = estado_final.copy()
                    nuevo_estado[i] = estado_inicial[i]
                    nuevo_estado_tuple = tuple(nuevo_estado)
                    temp_key = tuple(estado_inicial), nuevo_estado_tuple
                    for n in ncubos:
                        self.tabla_transiciones[key][n] = self.tabla_transiciones[key][n] + self.tabla_transiciones[temp_key][n]
        tmp =[]
        for i,n in enumerate(self.tabla_transiciones[key]):
            if n is not None:
                tmp.append(factor * n)
            else:
                tmp.append(n)
        self.tabla_transiciones[key] = tmp

    # ------------------------------------------------------------------ #
    #  Candidatos geométricos por AFINIDAD futuro↔presente (sin fuerza     #
    #  bruta). La pérdida es separable por variable futura: la contribución #
    #  de cada n-cubo depende sólo de qué presentes comparten su bloque.    #
    #  Esto permite generar pocas candidatas de alta calidad y evaluarlas   #
    #  con la pérdida exacta (vía particionar_k) en tiempo polinómico.      #
    # ------------------------------------------------------------------ #

    def _preparar_afinidad(self) -> None:
        """Precalcula la sensibilidad de cada variable futura al invertir cada
        dimensión presente desde el estado inicial, y el costo de aislar cada
        variable futura (marginalizar todas sus presentes). Índices POSICIONALES
        consistentes con ``find_mip`` (posición en ``indices_ncubos`` /
        ``dims_ncubos``)."""
        from src.funcs.base import seleccionar_subestado

        sub = self.sia_subsistema
        self._aff_F = list(range(len(sub.indices_ncubos)))
        self._aff_P = list(range(len(sub.dims_ncubos)))
        self._aff_dim = [int(d) for d in sub.dims_ncubos]
        self._aff_cubes = list(sub.ncubos)
        s0 = {int(d): int(sub.estado_inicial[int(d)]) for d in sub.dims_ncubos}
        self._aff_s0 = s0

        def val(cube, est):
            if cube.dims.size:
                sel = tuple(est[int(j)] for j in cube.dims)
                return 1.0 - float(cube.data[seleccionar_subestado(sel)])
            return 1.0 - float(cube.data)

        self._aff = {}
        for fp in self._aff_F:
            cube = self._aff_cubes[fp]
            dims_cube = [int(x) for x in cube.dims]
            base = val(cube, s0)
            fila = {}
            for mp in self._aff_P:
                d = self._aff_dim[mp]
                if d in dims_cube:
                    flip = dict(s0)
                    flip[d] = 1 - flip[d]
                    fila[mp] = abs(base - val(cube, flip))
                else:
                    fila[mp] = 0.0
            self._aff[fp] = fila

        self._aff_iso = {
            fp: abs(
                float(self.sia_dists_marginales[fp])
                - (1.0 - float(self._aff_cubes[fp].marginalizar(self._aff_cubes[fp].dims).data))
            )
            for fp in self._aff_F
        }

    def _aff_agrupar(self, F: List[int], k: int):
        """Clustering aglomerativo (average linkage) de variables futuras según
        el perfil de afinidad sobre las presentes. Devuelve ``k`` grupos."""
        if k >= len(F):
            return [[f] for f in F][:k]
        perfil = {
            f: np.array([self._aff[f][mp] for mp in self._aff_P], dtype=np.float64)
            if self._aff_P
            else np.zeros(1)
            for f in F
        }
        clusters = [[f] for f in F]

        def dist(a, b):
            return float(
                np.mean([np.linalg.norm(perfil[x] - perfil[y]) for x in a for y in b])
            )

        while len(clusters) > k:
            bi, bj, bd = 0, 1, float("inf")
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    d = dist(clusters[i], clusters[j])
                    if d < bd:
                        bd, bi, bj = d, i, j
            nuevo = clusters[bi] + clusters[bj]
            clusters = [c for x, c in enumerate(clusters) if x not in (bi, bj)]
            clusters.append(nuevo)
        return clusters

    def _aff_asignar_presentes(self, grupos: List[List[int]]):
        """Asigna cada presente al grupo de futuras con mayor afinidad total."""
        pm = [[] for _ in grupos]
        for mp in self._aff_P:
            best, ba = 0, -1.0
            for g, fut in enumerate(grupos):
                a = sum(self._aff[f][mp] for f in fut)
                if a > ba or (a == ba and len(fut) > len(grupos[best])):
                    ba, best = a, g
            pm[best].append(mp)
        return [list(grupos[g]) for g in range(len(grupos))], pm

    def _candidatos_afinidad(
        self, k: int
    ) -> List[Tuple[List[List[int]], List[List[int]]]]:
        """Genera candidatas de k partes por afinidad geométrica: aislamiento
        (dos variantes), clustering aglomerativo y división recursiva."""
        if not hasattr(self, "_aff"):
            self._preparar_afinidad()
        F = list(self._aff_F)
        P = list(self._aff_P)
        out: List[Tuple[List[List[int]], List[List[int]]]] = []
        if not (2 <= k <= len(F)):
            return out

        # --- Aislamiento: las (k-1) futuras más baratas de aislar ---
        orden = sorted(F, key=lambda f: self._aff_iso[f])
        aislados = orden[: k - 1]
        principal = [f for f in F if f not in aislados]
        # Variante A: aisladas sin presentes; principal con TODAS las presentes.
        out.append(([principal] + [[f] for f in aislados],
                    [list(P)] + [[] for _ in aislados]))
        # Variante B: cada aislada conserva su presente más afín.
        if P:
            tomadas: set = set()
            mec_ais = []
            for f in aislados:
                d_best = max(P, key=lambda m: self._aff[f][m])
                if self._aff[f][d_best] > 0 and d_best not in tomadas:
                    mec_ais.append([d_best])
                    tomadas.add(d_best)
                else:
                    mec_ais.append([])
            pur = [principal] + [[f] for f in aislados]
            mec = [[m for m in P if m not in tomadas]] + mec_ais
            out.append((pur, mec))

        # --- Clustering aglomerativo ---
        g = self._aff_agrupar(F, k)
        if g:
            out.append(self._aff_asignar_presentes(g))

        # --- División recursiva geométrica ---
        grupos = [list(F)]
        while len(grupos) < k:
            idx, mejor = -1, -1.0
            for i, gg in enumerate(grupos):
                if len(gg) < 2:
                    continue
                sc = (
                    sum(self._aff[a][m] for a in gg for m in P) if P else float(len(gg))
                )
                if sc > mejor:
                    mejor, idx = sc, i
            if idx == -1:
                break
            sub_g = self._aff_agrupar(grupos[idx], 2)
            if not sub_g or len(sub_g) < 2:
                break
            grupos = grupos[:idx] + sub_g + grupos[idx + 1 :]
        if len(grupos) == k:
            out.append(self._aff_asignar_presentes(grupos))

        return out

    @staticmethod
    def hamming(a: List[int], b: List[int]) -> int:
       return sum(x != y for x, y in zip(a, b))
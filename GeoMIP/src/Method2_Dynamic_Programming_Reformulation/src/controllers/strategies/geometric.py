"""Estrategia geométrica GeoMIP: k-particiones via tabla de costos (sin fuerza bruta)."""

from math import dist
import time
from typing import Dict, List, Tuple

import numpy as np

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
        estado_inicial = self.estado_inicial
        estado_final = self.estado_final
        self.idx_ncubos = list(range(len(self.sia_subsistema.indices_ncubos)))
        self.caminos = {0: [estado_inicial.tolist()]}
        self.tabla_transiciones.clear()
        self.tabla_transiciones[
            tuple(self.caminos[0][0]), tuple(self.caminos[0][0])
        ] = [0.0] * len(self.idx_ncubos)
        for nivel in range(1, len(estado_inicial) + 1):
            self.calcular_costos_nivel(estado_final, nivel)

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
            return candidatos

        for presentes, futuros in self._candidatos_biparticion():
            agregar(*self._expandir_a_k_partes(presentes, futuros, k))

        anclas = self._seleccionar_ancoras(k)
        if anclas:
            agregar(*self._asignar_por_ancoras(anclas, k))

        recursivo = self._division_recursiva(k)
        if recursivo:
            agregar(*recursivo)

        por_cero = self._agrupar_por_costo_cero(k)
        if por_cero:
            agregar(*por_cero)

        return candidatos

    def _candidatos_biparticion(self) -> List[Tuple[List[int], List[int]]]:
        """Candidatos k=2 por complementariedad (GeoMIP secc. 4.2.4)."""
        candidatos: List[Tuple[List[int], List[int]]] = []
        n_vars = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)

        for idx in range(n_vars):
            presentes = list(range(n_mech))
            futuros = [i for i in range(n_vars) if i != idx]
            candidatos.append((presentes, futuros))

        es_par = len(self.caminos) % 2 == 0
        mitad = len(self.caminos) // 2 if es_par else (len(self.caminos) // 2) + 1
        s0 = tuple(self.caminos[0][0])

        for nivel in range(1, mitad):
            costo_min = float("inf")
            mejor: Tuple[List[int], List[int]] = ([], [])
            for estado in self.caminos[nivel]:
                actual = self.tabla_transiciones.get((s0, tuple(estado)))
                complementario = self.tabla_transiciones.get(
                    (s0, tuple((1 - np.array(estado)).tolist()))
                )
                if actual is None or complementario is None:
                    continue
                presentes = [
                    idx for idx, bit in enumerate(estado) if bit == s0[idx]
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
        self, presentes: List[int], futuros: List[int], k: int
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """Convierte una bipartición en k partes (las restantes quedan vacías)."""
        n_fut = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)
        futuros2 = [i for i in range(n_fut) if i not in futuros]
        presentes2 = [i for i in range(n_mech) if i not in presentes]
        partes_pur = [futuros, futuros2]
        partes_mec = [presentes, presentes2]
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

    def _seleccionar_ancoras(self, k: int) -> List[List[int]]:
        """Selecciona k estados ancla con costo agregado bajo y separación Hamming."""
        s0 = tuple(self.caminos[0][0])
        estados: List[Tuple[float, List[int]]] = []

        for nivel, lista in self.caminos.items():
            for estado in lista:
                key = (s0, tuple(estado))
                costos = self.tabla_transiciones.get(key)
                if costos is None:
                    continue
                estados.append((sum(costos), estado))

        estados.sort(key=lambda x: x[0])
        anclas: List[List[int]] = []
        for _, estado in estados:
            if len(anclas) >= k:
                break
            if not anclas:
                anclas.append(estado)
                continue
            if all(self.hamming(estado, a) >= 1 for a in anclas):
                anclas.append(estado)

        if len(anclas) < k and estados:
            for _, estado in estados:
                if estado not in anclas:
                    anclas.append(estado)
                if len(anclas) >= k:
                    break
        return anclas[:k]

    def _asignar_por_ancoras(
        self, anclas: List[List[int]], k: int
    ) -> Tuple[List[List[int]], List[List[int]]]:
        """Asigna variables al ancla con menor costo de transición (proyección geométrica)."""
        s0 = tuple(self.caminos[0][0])
        n_fut = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)
        partes_pur: List[List[int]] = [[] for _ in range(k)]
        partes_mec: List[List[int]] = [[] for _ in range(k)]

        for fi in range(n_fut):
            costos = []
            for ancla in anclas:
                c = self.tabla_transiciones.get((s0, tuple(ancla)), [float("inf")] * n_fut)
                costos.append(c[fi] if fi < len(c) else float("inf"))
            partes_pur[int(np.argmin(costos))].append(fi)

        for mi in range(n_mech):
            asignado = False
            for j, ancla in enumerate(anclas):
                if ancla[mi] == s0[mi]:
                    partes_mec[j].append(mi)
                    asignado = True
                    break
            if not asignado:
                partes_mec[int(np.argmin([self.hamming(s0, a) for a in anclas]))].append(mi)

        return partes_pur, partes_mec

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
        s0 = tuple(self.caminos[0][0])
        mitad = max(1, len(self.caminos) // 2)
        costo_min = float("inf")
        mejor_presentes: List[int] = list(idxs_mec)
        mejor_futuros: List[int] = idxs_fut[: max(1, len(idxs_fut) // 2)]

        for nivel in range(1, mitad + 1):
            for estado in self.caminos.get(nivel, []):
                actual = self.tabla_transiciones.get((s0, tuple(estado)))
                comp = self.tabla_transiciones.get(
                    (s0, tuple((1 - np.array(estado)).tolist()))
                )
                if actual is None or comp is None:
                    continue
                presentes = [i for i in idxs_mec if estado[i] == s0[i]]
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

    def _agrupar_por_costo_cero(
        self, k: int
    ) -> Tuple[List[List[int]], List[List[int]]] | None:
        """Agrupa variables por transiciones de costo mínimo hacia el estado final."""
        s0 = tuple(self.caminos[0][0])
        s_f = tuple(self.estado_final.tolist())
        costos = self.tabla_transiciones.get((s0, s_f))
        if costos is None:
            return None

        n_fut = len(self.idx_ncubos)
        n_mech = len(self.estado_inicial)
        orden = sorted(range(n_fut), key=lambda i: costos[i])
        partes_pur: List[List[int]] = [[] for _ in range(k)]
        for rank, fi in enumerate(orden):
            partes_pur[rank % k].append(fi)

        partes_mec: List[List[int]] = [[] for _ in range(k)]
        for mi in range(n_mech):
            partes_mec[mi % k].append(mi)

        return partes_pur, partes_mec

    def _particion_valida(
        self, partes_pur: List[List[int]], partes_mec: List[List[int]], k: int
    ) -> bool:
        if len(partes_pur) < k or len(partes_mec) < k:
            return False
        total_pur = sum(len(p) for p in partes_pur)
        total_mec = sum(len(p) for p in partes_mec)
        if total_pur == 0 and total_mec == 0:
            return False
        # Descartar partición trivial: todo en una sola parte
        no_vacias = [i for i in range(k) if partes_pur[i] or partes_mec[i]]
        if len(no_vacias) < 2:
            return False
        if len(no_vacias) == 1:
            return False
        if total_pur > 0 and any(len(partes_pur[i]) == total_pur for i in no_vacias):
            if total_mec == 0 or any(len(partes_mec[i]) == total_mec for i in no_vacias):
                return False
        return True

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
                    nuevo_estado = estado_inicial.copy()
                    nuevo_estado[i] = estado_final[i] 
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

    @staticmethod
    def hamming(a: List[int], b: List[int]) -> int:
       return sum(x != y for x, y in zip(a, b))
       
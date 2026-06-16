import time
from typing import Union

import numpy as np

from src.middlewares.slogger import SafeLogger
from src.middlewares.profile import gestor_perfilado, profile
from src.funcs.iit import ABECEDARY
from src.funcs.format import fmt_k_particion_q, fmt_geomip_k_particion
from src.models.base.sia import SIA
from src.models.core.solution import Solution
from src.constants.models import (
    QNODES_ANALYSIS_TAG,
    QNODES_LABEL,
    QNODES_STRAREGY_TAG,
)
from src.constants.base import (
    COLS_IDX,
    INT_ZERO,
    TYPE_TAG,
    NET_LABEL,
    INFTY_POS,
    LAST_IDX,
    EFFECT,
    ACTUAL,
)
from src.models.base.application import aplicacion

# Un vértice es (tiempo, indice): tiempo == EFFECT (1) -> nodo en t+1,
#                                  tiempo == ACTUAL (0) -> nodo en t.
Vertice = tuple[int, int]


class QNodes(SIA):
    """
    Estrategia QNodes (algoritmo Q) — k-particiones (k = 2 … 5).

    Conserva el algoritmo Q original (ordenamiento submodular omega/delta y
    formación de pares candidatos) como MOTOR DE BIPARTICIÓN, y lo extiende a
    k-particiones por recursión divisiva (top-down).

    Diferencias respecto a la versión bipartición original:

      1. CORRECCIÓN DE PÉRDIDA. Antes, la partición candidata almacenada se
         guardaba con la EMD del último delta agregado a omega (penúltimo del
         ordenamiento), no con la EMD de separar el delta sobrante. Aquí cada
         partición candidata se guarda con SU pérdida real (la de separar ese
         delta del resto), por lo que `algorithm` ya devuelve la mejor
         bipartición correcta.

      2. EVALUACIÓN k-aria. `funcion_submodular` mide g con `sia_calcular_perdida_k`
         (vía `k_partir`) en vez de `bipartir`. Para k = 2 da exactamente la
         misma EMD que `bipartir`, pero permite medir la pérdida cuando hay más
         de dos bloques (necesario para k > 2 y para el contexto divisivo).

      3. k-PARTICIONES. `aplicar_estrategia` aplica `algorithm` de forma
         divisiva: k = 2 biparte todo V; para pasar de k a k+1 se biparte (con
         el algoritmo Q) la parte que produzca la k-partición de menor pérdida.

    g(X) = EMD( ⊗ P(parteᵢ) , P(V) ) con EMD-efecto marginal: la misma métrica
    que usa GeoMIP, por lo que la comparación entre ambos es válida.
    """

    def __init__(self, tpm: np.ndarray):
        super().__init__(tpm)
        gestor_perfilado.start_session(
            f"{NET_LABEL}{len(tpm[COLS_IDX])}{aplicacion.pagina_red_muestra}"
        )
        self.m: int  # número de nodos del purview (futuros)
        self.n: int  # número de dims del mecanismo (presentes)
        self.etiquetas = [tuple(s.lower() for s in ABECEDARY), ABECEDARY]

        self.vertices: list[Vertice] = []
        self.clave_submodular: tuple[list[int], list[int]] = ([], [])

        # Memoización: g de particiones completas (clave = firma de la partición).
        self.memoria_delta: dict = {}
        # Particiones candidatas generadas por `algorithm` en la bipartición actual.
        self.memoria_grupo_candidato: dict = {}

        # Contexto de la bipartición en curso (parte a dividir + partes fijas).
        self._parte_vertices: set = set()
        self._otras: list[list[Vertice]] = []

        self.indices_alcance: np.ndarray
        self.indices_mecanismo: np.ndarray

        self.logger = SafeLogger(QNODES_STRAREGY_TAG)

    # ------------------------------------------------------------------ #
    #  Entrada principal                                                  #
    # ------------------------------------------------------------------ #

    def aplicar_estrategia(
        self,
        estado_inicial: str,
        condicion: str,
        alcance: str,
        mecanismo: str,
        mostrar_tabla: bool = True,
    ):
        self.sia_preparar_subsistema(estado_inicial, condicion, alcance, mecanismo)

        self.memoria_delta = {}

        # Conjunto de vértices V = {presente} ∪ {futuro}.
        # e.g. (0,0)=a (0,2)=c (presente)   (1,0)=A (1,1)=B (futuro)
        presente = tuple(
            (ACTUAL, idx_actual) for idx_actual in self.sia_subsistema.dims_ncubos
        )
        futuro = tuple(
            (EFFECT, idx_efecto) for idx_efecto in self.sia_subsistema.indices_ncubos
        )

        self.m = self.sia_subsistema.indices_ncubos.size
        self.n = self.sia_subsistema.dims_ncubos.size
        self.indices_alcance = self.sia_subsistema.indices_ncubos
        self.indices_mecanismo = self.sia_subsistema.dims_ncubos

        self.vertices = [(int(t), int(i)) for (t, i) in (presente + futuro)]
        nv = len(self.vertices)

        # Resolución divisiva k = 2 … 5.
        resultados_por_k = self._resolver_divisivo(nv)

        # Mejor global = menor φ (MIP).
        mejor_k = min(
            resultados_por_k, key=lambda k: resultados_por_k[k]["perdida"]
        )
        mejor = resultados_por_k[mejor_k]

        if mostrar_tabla:
            self.sia_imprimir_resultados_k(resultados_por_k, mejor_k, QNODES_LABEL)

        fmt_mip = (
            fmt_k_particion_q(mejor["particion"])
            if mejor["particion"] is not None
            else "—"
        )

        resultados_excel = {
            k: {
                "particion": (
                    fmt_geomip_k_particion(res["particion"]).replace("\n", " | ")
                    if res["particion"]
                    else None
                ),
                "perdida": None if res.get("inviable") else res["perdida"],
                "tiempo": res["tiempo"],
            }
            for k, res in resultados_por_k.items()
        }

        sol = Solution(
            estrategia=QNODES_LABEL,
            perdida=mejor["perdida"],
            distribucion_subsistema=self.sia_dists_marginales,
            distribucion_particion=mejor["dist"]
            if mejor["dist"] is not None
            else self.sia_dists_marginales,
            tiempo_total=time.time() - self.sia_tiempo_inicio,
            particion=fmt_mip,
        )
        sol.k_particiones = mejor_k
        sol.resultados_por_k = resultados_excel
        return sol

    # ------------------------------------------------------------------ #
    #  Driver divisivo: construye k = 2 … 5 refinando el k anterior       #
    # ------------------------------------------------------------------ #

    @profile(context={TYPE_TAG: QNODES_ANALYSIS_TAG})
    def _resolver_divisivo(self, nv: int) -> dict:
        resultados_por_k: dict = {}

        # Partición de partida: un único grupo con todo V (k = 1).
        particion_actual: list[list[Vertice]] = [list(self.vertices)]

        for k in range(2, 6):
            t0 = time.time()

            if k > nv:
                resultados_por_k[k] = {
                    "perdida": INFTY_POS,
                    "particion": None,
                    "dist": None,
                    "tiempo": time.time() - t0,
                    "inviable": True,
                }
                continue

            # Elegir la parte cuya bipartición (con el algoritmo Q) produce la
            # k-partición de menor pérdida global.
            mejor = None  # (perdida, nueva_particion, dist)
            for i, parte in enumerate(particion_actual):
                if len(parte) < 2:
                    continue  # una parte de un solo vértice no se puede dividir
                otras = [
                    particion_actual[j]
                    for j in range(len(particion_actual))
                    if j != i
                ]
                perdida, A, B, dist = self._bipartir_parte(parte, otras)
                if mejor is None or perdida < mejor[0] - 1e-12:
                    nueva = otras + [list(A), list(B)]
                    mejor = (perdida, nueva, dist)

            if mejor is None:
                resultados_por_k[k] = {
                    "perdida": INFTY_POS,
                    "particion": None,
                    "dist": None,
                    "tiempo": time.time() - t0,
                    "inviable": True,
                }
                continue

            perdida, nueva_particion, dist = mejor
            particion_actual = nueva_particion
            resultados_por_k[k] = {
                "perdida": perdida,
                "particion": [list(g) for g in nueva_particion],
                "dist": dist,
                "tiempo": time.time() - t0,
            }

        return resultados_por_k

    def _bipartir_parte(
        self,
        parte: list[Vertice],
        otras: list[list[Vertice]],
    ) -> tuple[float, list[Vertice], list[Vertice], np.ndarray]:
        """Fija el contexto (parte a dividir + partes fijas) y corre el algoritmo Q."""
        self._parte_vertices = set(parte)
        self._otras = otras
        self.memoria_grupo_candidato = {}
        return self.algorithm(list(parte))

    # ------------------------------------------------------------------ #
    #  Algoritmo Q: mejor bipartición de la parte (ordenamiento omega/delta)#
    # ------------------------------------------------------------------ #

    @profile(context={TYPE_TAG: QNODES_ANALYSIS_TAG})
    def algorithm(
        self, vertices: list[Vertice]
    ) -> tuple[float, list[Vertice], list[Vertice], np.ndarray]:
        """
        Algoritmo Q sobre la parte representada por `vertices`: construye el
        ordenamiento submodular (omega crece eligiendo en cada paso el delta que
        minimiza  g(omega ∪ delta) − g(delta)), forma los pares candidatos y, en
        cada fase, registra la partición candidata = separar el delta sobrante.

        Devuelve (perdida, A, B, dist) de la MEJOR bipartición candidata, donde
        cada candidata se evalúa con su pérdida real (corrección respecto a la
        versión original) y `B = parte ∖ A`.
        """
        parte_total = set(vertices)

        # Cada "elemento" es una lista de vértices (singletons al inicio; los
        # pares candidatos fusionados se concatenan en pasos posteriores).
        vertices = [self._como_lista(v) for v in vertices]

        while len(vertices) > 2:
            omegas_ciclo = [vertices[INT_ZERO]]
            deltas_ciclo = vertices[1:]

            for j in range(len(deltas_ciclo) - 1):
                emd_local = INFTY_POS
                indice_mip = INT_ZERO

                for k in range(len(deltas_ciclo)):
                    emd_union, emd_delta, dist_delta = self.funcion_submodular(
                        deltas_ciclo[k], omegas_ciclo
                    )
                    emd_iteracion = emd_union - emd_delta

                    # Atajo: separar un delta con pérdida nula es óptimo global
                    # para una bipartición (φ ≥ 0); se devuelve de inmediato.
                    if emd_delta == INT_ZERO:
                        A = set(self._vertices_de(deltas_ciclo[k]))
                        B = parte_total - A
                        return 0.0, sorted(A), sorted(B), dist_delta

                    if emd_iteracion < emd_local:
                        emd_local = emd_iteracion
                        indice_mip = k

                omegas_ciclo.append(deltas_ciclo[indice_mip])
                deltas_ciclo.pop(indice_mip)

            # Delta sobrante = último del ordenamiento -> partición candidata.
            sobrante = deltas_ciclo[LAST_IDX]
            A = set(self._vertices_de(sobrante))
            B = parte_total - A
            perdida, dist = self._g_biparte(A)
            self.memoria_grupo_candidato[frozenset(A)] = (perdida, sorted(B), dist)

            # Fusionar el par candidato (último omega + delta sobrante) y recurrir.
            par_candidato = omegas_ciclo[LAST_IDX] + sobrante
            omegas_ciclo.pop()
            omegas_ciclo.append(par_candidato)
            vertices = omegas_ciclo

        # Caso base |V'| = 2: la última partición candidata es (e0, e1).
        A = set(self._vertices_de(vertices[1]))
        B = parte_total - A
        perdida, dist = self._g_biparte(A)
        self.memoria_grupo_candidato[frozenset(A)] = (perdida, sorted(B), dist)

        # Mejor bipartición candidata = menor pérdida real.
        clave_mip = min(
            self.memoria_grupo_candidato,
            key=lambda c: self.memoria_grupo_candidato[c][INT_ZERO],
        )
        perdida, B, dist = self.memoria_grupo_candidato[clave_mip]
        return perdida, sorted(clave_mip), B, dist

    # ------------------------------------------------------------------ #
    #  Función submodular: g(omega ∪ delta) y g(delta) en el contexto      #
    # ------------------------------------------------------------------ #

    def funcion_submodular(
        self,
        deltas: Union[Vertice, list[Vertice]],
        omegas: list[Union[Vertice, list[Vertice]]],
    ):
        """
        Evalúa el delta individual y su unión con omega dentro del contexto de
        bipartición actual (parte a dividir + partes fijas):

          emd_delta = g( separar delta del resto de la parte )
          emd_union = g( separar (omega ∪ delta) del resto de la parte )

        Devuelve (emd_union, emd_delta, dist_delta). El criterio del algoritmo Q
        es minimizar  emd_union − emd_delta.
        """
        self.clave_submodular = ([], [])

        # Delta individual.
        v_delta = self.definir_clave(deltas)
        emd_delta, dist_delta = self._g_biparte(set(v_delta))

        # Unión omega ∪ delta (se acumulan los vértices de cada omega).
        v_union = set(v_delta)
        for omega in omegas:
            v_union |= set(self.definir_clave(omega))
        emd_union, _ = self._g_biparte(v_union)

        return emd_union, emd_delta, dist_delta

    def definir_clave(
        self,
        conjunto: Union[Vertice, list[Vertice]],
    ) -> list[Vertice]:
        """
        Acumula en `clave_submodular` los índices (presente/futuro) del conjunto
        y devuelve la lista de vértices (tiempo, índice) que lo componen. Acepta
        un vértice suelto o un grupo (lista de vértices).
        """
        vertices = self._vertices_de(conjunto)
        for tiempo, indice in vertices:
            self.clave_submodular[tiempo].append(indice)
        self.clave_submodular[ACTUAL].sort()
        self.clave_submodular[EFFECT].sort()
        return vertices

    # ------------------------------------------------------------------ #
    #  g de una partición / bipartición  (EMD-efecto, igual que GeoMIP)    #
    # ------------------------------------------------------------------ #

    def _g_biparte(self, X: set) -> tuple[float, np.ndarray]:
        """Pérdida de la partición { X, parte∖X } ∪ otras  (X ⊆ parte actual)."""
        resto = self._parte_vertices - set(X)
        grupos = [list(X)]
        if resto:
            grupos.append(list(resto))
        grupos.extend(list(o) for o in self._otras)
        return self._perdida_particion(grupos)

    def _perdida_particion(
        self, grupos: list[list[Vertice]]
    ) -> tuple[float, np.ndarray]:
        """g de una partición completa de V, memoizada por la firma de la partición."""
        grupos = [g for g in grupos if g]
        firma = frozenset(frozenset(g) for g in grupos)
        if firma not in self.memoria_delta:
            perdida, dist = self.sia_calcular_perdida_k(grupos)
            self.memoria_delta[firma] = (float(perdida), dist)
        return self.memoria_delta[firma]

    # ------------------------------------------------------------------ #
    #  Utilidades                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _como_lista(elem: Union[Vertice, list[Vertice]]) -> list[Vertice]:
        """Normaliza un elemento a lista de vértices."""
        if isinstance(elem, tuple):
            return [elem]
        return list(elem)

    @staticmethod
    def _vertices_de(elem: Union[Vertice, list[Vertice]]) -> list[Vertice]:
        """Devuelve los vértices (tiempo, índice) que componen un elemento."""
        if isinstance(elem, tuple):
            return [elem]
        return list(elem)

    def nodes_complement(self, nodes: list[Vertice]) -> list[Vertice]:
        return list(set(self.vertices) - set(nodes))
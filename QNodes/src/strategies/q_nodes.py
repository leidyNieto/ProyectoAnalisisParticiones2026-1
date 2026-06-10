# import time
# from typing import Union
# import numpy as np
# from colorama import Fore, Style
# from src.middlewares.slogger import SafeLogger
# from src.funcs.iit import emd_efecto, ABECEDARY
# from src.middlewares.profile import gestor_perfilado, profile
# from src.funcs.format import fmt_biparticion_q, fmt_k_particion_q, fmt_geomip_k_particion
# from src.models.base.sia import SIA

# from src.models.core.solution import Solution
# from src.constants.models import (
#     QNODES_ANALYSIS_TAG,
#     QNODES_LABEL,
#     QNODES_STRAREGY_TAG,
# )
# from src.constants.base import (
#     COLS_IDX,
#     INT_ZERO,
#     TYPE_TAG,
#     NET_LABEL,
#     INFTY_POS,
#     LAST_IDX,
#     EFFECT,
#     ACTUAL,
# )
# from src.models.base.application import aplicacion


# class QNodes(SIA):
#     """
#     Clase QNodes para el análisis de redes mediante el algoritmo Q.

#     Esta clase implementa un gestor principal para el análisis de redes que utiliza
#     el algoritmo Q para encontrar la partición óptima que minimiza la
#     pérdida de información en el sistema. Hereda de la clase base SIA (Sistema de
#     Información Activo) y proporciona funcionalidades para analizar la estructura
#     y dinámica de la red.

#     Args:
#     ----
#         config (Loader):
#             Instancia de la clase Loader que contiene la configuración del sistema
#             y los parámetros necesarios para el análisis.

#     Attributes:
#     ----------
#         m (int):
#             Número de elementos en el conjunto de purview (vista).

#         n (int):
#             Número de elementos en el conjunto de mecanismos.

#         tiempos (tuple[np.ndarray, np.ndarray]):
#             Tupla de dos arrays que representan los tiempos para los estados
#             actual y efecto del sistema.

#         etiquetas (list[tuple]):
#             Lista de tuplas conteniendo las etiquetas para los nodos,
#             con versiones en minúsculas y mayúsculas del abecedario.

#         vertices (set[tuple]):
#             Conjunto de vértices que representan los nodos de la red,
#             donde cada vértice es una tupla (tiempo, índice).

#         memoria (dict):
#             Diccionario para almacenar resultados intermedios y finales
#             del análisis (memoización).

#         logger:
#             Instancia del logger configurada para el análisis Q.

#     Methods:
#     -------
#         run(condicion, purview, mechanism):
#             Ejecuta el análisis principal de la red con las condiciones,
#             purview y mecanismo especificados.

#         algorithm(vertices):
#             Implementa el algoritmo Q para encontrar la partición
#             óptima del sistema.

#         funcion_submodular(deltas, omegas):
#             Calcula la función submodular para evaluar particiones candidatas.

#         view_solution(mip):
#             Visualiza la solución encontrada en términos de las particiones
#             y sus valores asociados.

#         nodes_complement(nodes):
#             Obtiene el complemento de un conjunto de nodos respecto a todos
#             los vértices del sistema.

#     Notes:
#     -----
#     - La clase implementa una versión secuencial del algoritmo Q para encontrar la partición que minimiza la pérdida de información.
#     - Utiliza memoización para evitar recálculos innecesarios durante el proceso.
#     - El análisis se realiza considerando dos tiempos: actual (presente) y
#       efecto (futuro).
#     """

#     def __init__(self, tpm: np.ndarray):
#         super().__init__(tpm)
#         gestor_perfilado.start_session(
#             f"{NET_LABEL}{len(tpm[COLS_IDX])}{aplicacion.pagina_red_muestra}"
#         )
#         self.m: int
#         self.n: int
#         self.tiempos: tuple[np.ndarray, np.ndarray]
#         self.etiquetas = [tuple(s.lower() for s in ABECEDARY), ABECEDARY]
#         self.vertices: set[tuple]
#         self.clave_submodular = [], []
#         self.memoria_union = {}
#         self.memoria_delta = {}
#         self.memoria_grupo_candidato = {}
#         mip_local = self.algorithm(grupo)

#         self.indices_alcance: np.ndarray
#         self.indices_mecanismo: np.ndarray

#         self.logger = SafeLogger(QNODES_STRAREGY_TAG)

#     def aplicar_estrategia(
#         self,
#         estado_inicial: str,
#         condicion: str,
#         alcance: str,
#         mecanismo: str,
#     ):
#         self.sia_preparar_subsistema(estado_inicial, condicion, alcance, mecanismo)

#         futuro = tuple(
#             (EFFECT, idx_efecto) for idx_efecto in self.sia_subsistema.indices_ncubos
#         )
#         presente = tuple(
#             (ACTUAL, idx_actual) for idx_actual in self.sia_subsistema.dims_ncubos
#         )

#         self.m = self.sia_subsistema.indices_ncubos.size
#         self.n = self.sia_subsistema.dims_ncubos.size
#         self.indices_alcance = self.sia_subsistema.indices_ncubos
#         self.indices_mecanismo = self.sia_subsistema.dims_ncubos
#         self.tiempos = (
#             np.zeros(self.n, dtype=np.int8),
#             np.zeros(self.m, dtype=np.int8),
#         )

#         vertices = list(presente + futuro)
#         self.vertices = set(presente + futuro)

#         resultados_por_k: dict = {}

#         # k=2: algoritmo Queyranne (óptimo) #
#         t0 = time.time()
#         self.memoria_grupo_candidato = {}
#         self.memoria_delta = {}
#         mip = self.algorithm(vertices)
#         perdida_2, dist_2 = self.memoria_grupo_candidato[mip]
#         resultados_por_k[2] = {
#             "perdida": perdida_2,
#             "particion": [list(mip), self.nodes_complement(mip)],
#             "dist": dist_2,
#             "tiempo": time.time() - t0,
#         }

#         # k=3,4,5: enumeración exhaustiva #
#         for k in range(3, 6):
#             if k > len(vertices):
#                 break
#             t0 = time.time()
#             perdida_k, particion_k, dist_k = self.buscar_mejor_k_particion_qnodes(vertices, k)
#             resultados_por_k[k] = {
#                 "perdida": perdida_k,
#                 "particion": particion_k,
#                 "dist": dist_k,
#                 "tiempo": time.time() - t0,
#             }

#         # Mejor global #
#         mejor_k = min(resultados_por_k, key=lambda k: resultados_por_k[k]["perdida"])
#         mejor = resultados_por_k[mejor_k]

#         # Tabla por-k en consola (k = 2 … 5)
#         self.sia_imprimir_resultados_k(resultados_por_k, mejor_k, QNODES_LABEL)

#         fmt_mip = fmt_k_particion_q(mejor["particion"])

#         sol = Solution(
#             estrategia=QNODES_LABEL,
#             perdida=mejor["perdida"],
#             distribucion_subsistema=self.sia_dists_marginales,
#             distribucion_particion=mejor["dist"],
#             tiempo_total=time.time() - self.sia_tiempo_inicio,
#             particion=fmt_mip,
#         )
#         sol.k_particiones = mejor_k
#         sol.resultados_por_k = resultados_por_k
#         return sol


#     @profile(context={TYPE_TAG: QNODES_ANALYSIS_TAG})
#     def algorithm(self, vertices: list[tuple[int, int]]):
#         """
#         Implementa el algoritmo Q para encontrar la partición óptima de un sistema que minimiza la pérdida de información, basándose en principios de submodularidad dentro de la teoría de lainformación.

#         El algoritmo opera sobre un conjunto de vértices que representan nodos en diferentes tiempos del sistema (presente y futuro). La idea fundamental es construir incrementalmente grupos de nodos que, cuando se particionan, producen la menor pérdida posible de información en el sistema.

#         Proceso Principal:
#         -----------------
#         El algoritmo comienza estableciendo dos conjuntos fundamentales: omega (W) y delta.
#         Omega siempre inicia con el primer vértice del sistema, mientras que delta contiene todos los vértices restantes. Esta decisión no es arbitraria - al comenzar con un
#         solo elemento en omega, podemos construir grupos de manera incremental evaluando cómo cada adición afecta la pérdida de información.

#         La ejecución se desarrolla en fases, ciclos e iteraciones, donde cada fase representa un nivel diferente y conlleva a la formación de una partición candidata, cada ciclo representa un incremento de elementos al conjunto W y cada iteración determina al final cuál es el mejor elemento/cambio/delta para añadir en W.
#         Fase >> Ciclo >> Iteración.

#         1. Formación Incremental de Grupos:
#         El algoritmo mantiene un conjunto omega que crece gradualmente en cada j-iteración. En cada paso, evalúa todos los deltas restantes para encontrar cuál, al unirse con omega produce la menor pérdida de información. Este proceso utiliza la función submodular para calcular la diferencia entre la EMD (Earth Mover's Distance) de la combinación y la EMD individual del delta evaluado.

#         2. Evaluación de deltas:
#         Para cada delta candidato el algoritmo:
#         - Calcula su EMD individual si no está en memoria.
#         - Calcula la EMD de su combinación con el conjunto omega actual
#         - Determina la diferencia entre estas EMDs (el "costo" de la combinación)
#         El delta que produce el menor costo se selecciona y se añade a omega.

#         3. Formación de Nuevos Grupos:
#         Al final de cada fase cuando omega crezca lo suficiente, el algoritmo:
#         - Toma los últimos elementos de omega y delta (par candidato).
#         - Los combina en un nuevo grupo
#         - Actualiza la lista de vértices para la siguiente fase
#         Este proceso de agrupamiento permite que el algoritmo construya particiones
#         cada vez más complejas y reutilice estos "pares candidatos" para particiones en conjunto.

#         Optimización y Memoria:
#         ----------------------
#         El algoritmo utiliza dos estructuras de memoria clave:
#         - individual_memory: Almacena las EMDs y distribuciones de nodos individuales, evitando recálculos muy costosos.
#         - partition_memory: Guarda las EMDs y distribuciones de las particiones completas, permitiendo comparar diferentes combinaciones de grupos teniendo en cuenta que su valor real está asociado al valor individual de su formación delta.

#         La memoización es relevante puesto muchos cálculos de EMD son computacionalmente costosos y se repiten durante la ejecución del algoritmo.

#         Resultado:
#         ---------------
#         Al terminar todas las fases, el algoritmo selecciona la partición que produjo la menor EMD global, representando la división del sistema que mejor preserva su información causal.

#         Args:
#             vertices (list[tuple[int, int]]): Lista de vértices donde cada uno es una
#                 tupla (tiempo, índice). tiempo=0 para presente (t_0), tiempo=1 para futuro (t_1).

#         Returns:
#             tuple[float, tuple[tuple[int, int], ...]]: El valor de pérdida en la primera posición, asociado con la partición óptima encontrada, identificada por la clave en partition_memory que produce la menor EMD.
#         """
#         indice_emd = INT_ZERO

#         for i in range(len(vertices) - 1):
#             # self.logger.debug(f"total: {len(vertices) - i}")
#             omegas_ciclo = [vertices[0]]
#             deltas_ciclo = vertices[1:]

#             emd_particion_candidata = INFTY_POS
#             dist_particion_candidata = None

#             for j in range(len(deltas_ciclo) - 1):
#                 # self.logger.critic(f"   {j=}")
#                 emd_local = 1e5
#                 indice_mip: int

#                 for k in range(len(deltas_ciclo)):
#                     emd_union, emd_delta, dist_marginal_delta = self.funcion_submodular(
#                         deltas_ciclo[k], omegas_ciclo
#                     )

#                     emd_iteracion = emd_union - emd_delta

#                     if emd_iteracion < emd_local:
#                         if emd_delta == INT_ZERO:
#                             clave = (
#                                 tuple(deltas_ciclo[k])
#                                 if isinstance(deltas_ciclo[k], list)
#                                 else (deltas_ciclo[k],)
#                             )
#                             self.memoria_grupo_candidato[clave] = (
#                                 emd_delta,
#                                 dist_marginal_delta,
#                             )
#                             return clave

#                         emd_local = emd_iteracion
#                         indice_mip = k
#                         emd_particion_candidata = emd_delta
#                         dist_particion_candidata = dist_marginal_delta
#                 # self.logger.critic(f"       [k]: {indice_mip}")

#                 omegas_ciclo.append(deltas_ciclo[indice_mip])
#                 deltas_ciclo.pop(indice_mip)
#             self.memoria_grupo_candidato[
#                 tuple(
#                     deltas_ciclo[LAST_IDX]
#                     if isinstance(deltas_ciclo[LAST_IDX], list)
#                     else deltas_ciclo
#                 )
#             ] = emd_particion_candidata, dist_particion_candidata

#             par_candidato = (
#                 [omegas_ciclo[LAST_IDX]]
#                 if isinstance(omegas_ciclo[LAST_IDX], tuple)
#                 else omegas_ciclo[LAST_IDX]
#             ) + (
#                 deltas_ciclo[LAST_IDX]
#                 if isinstance(deltas_ciclo[LAST_IDX], list)
#                 else deltas_ciclo
#             )

#             omegas_ciclo.pop()
#             omegas_ciclo.append(par_candidato)

#             vertices = omegas_ciclo

#         return min(
#             self.memoria_grupo_candidato,
#             key=lambda k: self.memoria_grupo_candidato[k][indice_emd],
#         )
#     def buscar_mejor_k_particion_qnodes(self, vertices, k):
#         """
#         Extiende QNodes de forma recursiva.

#         k=2 -> Queyranne normal
#         k>2 -> divide sucesivamente el grupo más costoso
#         """

#         if k < 2:
#             raise ValueError("k debe ser >= 2")

#         # Primera bipartición
#         mip = self.algorithm(vertices)

#         grupos = [
#             list(mip),
#             self.nodes_complement(mip),
#         ]

#         while len(grupos) < k:

#             peor_idx = None
#             peor_phi = -1

#             for idx, grupo in enumerate(grupos):

#                 if len(grupo) <= 1:
#                     continue

#                 try:
#                     phi_grupo, _ = self.calcular_phi_grupo(grupo)

#                     if phi_grupo > peor_phi:
#                         peor_phi = phi_grupo
#                         peor_idx = idx

#                 except Exception:
#                     continue

#             if peor_idx is None:
#                 break

#             grupo = grupos.pop(peor_idx)

#             mip_local = self.algorithm(grupo)

#             grupo_a = list(mip_local)
#             grupo_b = list(set(grupo) - set(grupo_a))

#             grupos.append(grupo_a)
#             grupos.append(grupo_b)

#         perdida_total, dist_total = self.sia_calcular_perdida_k(grupos)

#         return perdida_total, grupos, dist_total
#     def calcular_phi_grupo(self, grupo):

#         if len(grupo) <= 1:
#             return 0.0, None

#         mip = self.algorithm(grupo)

#         phi, dist = self.memoria_grupo_candidato[mip]

#         return phi, dist

#     def funcion_submodular(
#         self, deltas: Union[tuple, list[tuple]], omegas: list[Union[tuple, list[tuple]]]
#     ):
#         """
#         Evalúa el impacto de combinar el conjunto de nodos individual delta y su agrupación con el conjunto omega, calculando la diferencia entre EMD (Earth Mover's Distance) de las configuraciones, en conclusión los nodos delta evaluados individualmente y su combinación con el conjunto omega.

#         El proceso se realiza en dos fases principales:

#         1. Evaluación Individual:
#            - Crea una copia del estado temporal del subsistema.
#            - Activa los nodos delta en su tiempo correspondiente (presente/futuro).
#            - Si el delta ya fue evaluado antes, recupera su EMD y distribución marginal de memoria
#            - Si no, ha de:
#              * Identificar dimensiones activas en presente y futuro.
#              * Realiza bipartición del subsistema con esas dimensiones.
#              * Calcular la distribución marginal y EMD respecto al subsistema.
#              * Guarda resultados en memoria para seguro un uso futuro.

#         2. Evaluación Combinada:
#            - Sobre la misma copia temporal, activa también los nodos omega.
#            - Calcula dimensiones activas totales (delta + omega).
#            - Realiza bipartición del subsistema completo.
#            - Obtiene EMD de la combinación.

#         Args:
#             deltas: Un nodo individual (tupla) o grupo de nodos (lista de tuplas)
#                    donde cada tupla está identificada por su (tiempo, índice), sea el tiempo t_0 identificado como 0, t_1 como 1 y, el índice hace referencia a las variables/dimensiones habilitadas para operaciones de substracción/marginalización sobre el subsistema, tal que genere la partición.
#             omegas: Lista de nodos ya agrupados, puede contener tuplas individuales
#                    o listas de tuplas para grupos formados por los pares candidatos o más uniones entre sí (grupos candidatos).

#         Returns:
#             tuple: (
#                 EMD de la combinación omega y delta,
#                 EMD del delta individual,
#                 Distribución marginal del delta individual
#             )
#             Esto lo hice así para hacer almacenamiento externo de la emd individual y su distribución marginal en las particiones candidatas.
#         """
#         vector_delta_marginal = None
#         self.clave_submodular = [], []

#         # Delta #

#         clave_delta_actual, clave_delta_efecto = self.definir_clave(deltas)
#         clave_delta = tuple(clave_delta_actual), tuple(clave_delta_efecto)

#         idxs_alcance_delta = self.clave_submodular[EFFECT]
#         dims_mecanismo_delta = self.clave_submodular[ACTUAL]
        

#         if clave_delta not in self.memoria_delta:
#             particion_delta = self.sia_subsistema.bipartir(
#                 np.array(idxs_alcance_delta, dtype=np.int8),
#                 np.array(dims_mecanismo_delta, dtype=np.int8),
#             )
#             vector_delta_marginal = particion_delta.distribucion_marginal()
#             emd_delta = emd_efecto(vector_delta_marginal, self.sia_dists_marginales)
#             self.memoria_delta[clave_delta] = emd_delta, vector_delta_marginal

#         else:
#             emd_delta, vector_delta_marginal = self.memoria_delta[clave_delta]
      

#         # Unión #

#         for omega in omegas:
#             self.definir_clave(omega)

#         idxs_alcance_union = self.clave_submodular[EFFECT]
#         dims_mecanismo_union = self.clave_submodular[ACTUAL]
#         clave_union = (
#         tuple(sorted(idxs_alcance_union)),
#         tuple(sorted(dims_mecanismo_union)),
#         )
#         if clave_union in self.memoria_union:

#             emd_union, vector_union_marginal = (
#                 self.memoria_union[clave_union]
#             )

#         else:

#             particion_union = self.sia_subsistema.bipartir(
#                 np.array(idxs_alcance_union, dtype=np.int8),
#                 np.array(dims_mecanismo_union, dtype=np.int8),
#             )

#             vector_union_marginal = (
#                 particion_union.distribucion_marginal()
#             )

#             emd_union = emd_efecto(
#                 vector_union_marginal,
#                 self.sia_dists_marginales,
#             )

#             self.memoria_union[clave_union] = (
#                 emd_union,
#                 vector_union_marginal,
#     )
#         # particion_union = self.sia_subsistema.bipartir(
#         #     np.array(idxs_alcance_union, dtype=np.int8),
#         #     np.array(dims_mecanismo_union, dtype=np.int8),
#         # )
#         # vector_union_marginal = particion_union.distribucion_marginal()
#         # emd_union = emd_efecto(vector_union_marginal, self.sia_dists_marginales)

#         return emd_union, emd_delta, vector_delta_marginal

#     def definir_clave(
#         self,
#         conjunto: Union[tuple[int, int], list[tuple[int, int]]],
#     ):
#         if isinstance(conjunto, tuple):
#             tiempo, indice = conjunto
#             self.clave_submodular[tiempo].append(indice)
#         else:
#             for tiempo, indice in conjunto:
#                 self.clave_submodular[tiempo].append(indice)
#         self.clave_submodular[ACTUAL].sort()
#         self.clave_submodular[EFFECT].sort()
#         return self.clave_submodular

#     def nodes_complement(self, nodes: list[tuple[int, int]]):
#         return list(set(self.vertices) - set(nodes))
import time
from typing import Union

import numpy as np

from src.constants.base import (
    ACTUAL,
    COLS_IDX,
    EFFECT,
    INFTY_POS,
    INT_ZERO,
    LAST_IDX,
    NET_LABEL,
    TYPE_TAG,
)
from src.constants.models import (
    QNODES_ANALYSIS_TAG,
    QNODES_LABEL,
    QNODES_STRAREGY_TAG,
)
from src.funcs.format import (
    fmt_biparticion_q,
    fmt_geomip_k_particion,
    fmt_k_particion,
    partes_a_clave,
)
from src.funcs.iit import ABECEDARY, emd_efecto
from src.middlewares.profile import gestor_perfilado, profile
from src.middlewares.slogger import SafeLogger
from src.models.base.application import aplicacion
from src.models.base.sia import SIA
from src.models.core.solution import Solution


class QNodes(SIA):
    """Algoritmo Q para bipartición y k-particiones (k=2..5)."""

    K_MIN = 2
    K_MAX = 5

    def __init__(self, tpm: np.ndarray):
        super().__init__(tpm)
        gestor_perfilado.start_session(
            f"{NET_LABEL}{len(tpm[COLS_IDX])}{aplicacion.pagina_red_muestra}"
        )
        self.m: int
        self.n: int
        self.tiempos: tuple[np.ndarray, np.ndarray]
        self.etiquetas = [tuple(s.lower() for s in ABECEDARY), ABECEDARY]
        self.vertices: set[tuple]
        self.clave_submodular: list[list[int]] = [[], []]
        self.memoria_delta: dict = {}
        self.memoria_union: dict = {}
        self.memoria_grupo_candidato: dict = {}
        self.memoria_k_particion: dict = {}
        self.cortes_dendrograma: dict[int, list] = {}

        self.indices_alcance: np.ndarray
        self.indices_mecanismo: np.ndarray

        self.logger = SafeLogger(QNODES_STRAREGY_TAG)

    def aplicar_estrategia(
        self,
        estado_inicial: str,
        condicion: str,
        alcance: str,
        mecanismo: str,
    ):
        self.sia_preparar_subsistema(estado_inicial, condicion, alcance, mecanismo)

        futuro = tuple(
            (EFFECT, idx_efecto) for idx_efecto in self.sia_subsistema.indices_ncubos
        )
        presente = tuple(
            (ACTUAL, idx_actual) for idx_actual in self.sia_subsistema.dims_ncubos
        )

        self.m = self.sia_subsistema.indices_ncubos.size
        self.n = self.sia_subsistema.dims_ncubos.size
        self.indices_alcance = self.sia_subsistema.indices_ncubos
        self.indices_mecanismo = self.sia_subsistema.dims_ncubos
        self.tiempos = (
            np.zeros(self.n, dtype=np.int8),
            np.zeros(self.m, dtype=np.int8),
        )

        vertices = list(presente + futuro)
        self.vertices = set(presente + futuro)

        self.memoria_delta.clear()
        self.memoria_union.clear()
        self.memoria_grupo_candidato.clear()
        self.memoria_k_particion.clear()
        self.cortes_dendrograma.clear()

        t_algo = time.time()
        mip = self.algorithm(vertices)
        tiempo_algo = time.time() - t_algo

        self._mip_k2 = mip
        resultados_por_k: dict[int, dict] = {}
        n_vertices = len(vertices)
        k_maximo = min(self.K_MAX, n_vertices)

        for k in range(self.K_MIN, k_maximo + 1):
            t_k = time.time()
            if k == 2:
                perdida, dist, partes = self._resultado_biparticion(mip)
            else:
                perdida, dist, partes = self._mejor_k_particion(k)
            tiempo_k = time.time() - t_k
            if partes is None:
                continue
            resultados_por_k[k] = {
                "particion": fmt_geomip_k_particion(partes),
                "particion_fmt": fmt_k_particion(partes),
                "perdida": perdida,
                "tiempo": tiempo_k,
                "distribucion": dist,
            }

        if not resultados_por_k:
            raise RuntimeError("No se encontró ninguna partición válida.")

        mejor_k = min(resultados_por_k, key=lambda k: resultados_por_k[k]["perdida"])
        mejor = resultados_por_k[mejor_k]

        return Solution(
            estrategia=QNODES_LABEL,
            perdida=mejor["perdida"],
            distribucion_subsistema=self.sia_dists_marginales,
            distribucion_particion=mejor["distribucion"],
            tiempo_total=tiempo_algo,
            particion=mejor["particion_fmt"],
            k_particiones=mejor_k,
            resultados_por_k=resultados_por_k,
            quiere_hablar=False,
        )

    def _resultado_biparticion(self, mip):
        perdida, dist = self.memoria_grupo_candidato[mip]
        prim = self._nodos_de_clave(mip)
        dual = self.nodes_complement(prim)
        partes = [prim, dual]
        return perdida, dist, partes

    def _nodos_de_clave(self, clave) -> list[tuple[int, int]]:
        if isinstance(clave, tuple) and clave and isinstance(clave[0], tuple):
            return list(clave)
        return self._aplanar_grupo(clave)

    def _mejor_k_particion(self, k: int):
        mejor = (INFTY_POS, None, None)
        candidatos = list(self.cortes_dendrograma.get(k, []))
        candidatos.extend(self._refinar_cortes_hacia_k(k))

        vistos: set = set()
        for grupos in candidatos:
            clave = tuple(
                tuple(sorted(self._aplanar_grupo(g), key=lambda x: (x[0], x[1])))
                for g in grupos
            )
            if clave in vistos:
                continue
            vistos.add(clave)

            if clave in self.memoria_k_particion:
                perdida, dist, partes = self.memoria_k_particion[clave]
            else:
                perdida, dist, partes = self._evaluar_grupos_k(grupos)
                self.memoria_k_particion[clave] = (perdida, dist, partes)
            if perdida < mejor[0]:
                mejor = (perdida, dist, partes)
        return mejor

    def _refinar_cortes_hacia_k(self, k: int) -> list[list]:
        """Genera cortes adicionales dividiendo el grupo más grande de particiones menores."""
        extra: list[list] = []
        bases: list[list] = []
        if hasattr(self, "_mip_k2") and self._mip_k2 is not None:
            prim = self._nodos_de_clave(self._mip_k2)
            dual = self.nodes_complement(prim)
            bases.append([prim, dual])
        for k_base in range(2, k):
            bases.extend(self.cortes_dendrograma.get(k_base, []))

        for grupos in bases:
            refinado = [list(self._aplanar_grupo(g)) for g in grupos]
            while len(refinado) < k:
                idx_grande = max(
                    range(len(refinado)),
                    key=lambda i: len(refinado[i]),
                )
                grupo = refinado[idx_grande]
                if len(grupo) < 2:
                    break
                sub_a, sub_b = self._dividir_grupo_greedy(grupo)
                refinado = (
                    refinado[:idx_grande]
                    + [sub_a, sub_b]
                    + refinado[idx_grande + 1 :]
                )
            if len(refinado) == k:
                extra.append(refinado)
        return extra

    def _dividir_grupo_greedy(
        self, nodos: list[tuple[int, int]]
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        if len(nodos) < 2:
            return nodos, []
        ordenados = sorted(nodos, key=lambda x: (x[0], x[1]))
        omega = [ordenados[0]]
        delta = ordenados[1:]
        while len(delta) > 1:
            mejor_idx = 0
            mejor_costo = INFTY_POS
            for i, d in enumerate(delta):
                emd_union, emd_delta, _ = self.funcion_submodular(d, omega)
                costo = emd_union - emd_delta
                if costo < mejor_costo:
                    mejor_costo = costo
                    mejor_idx = i
            omega.append(delta.pop(mejor_idx))
        return omega, delta

    def _evaluar_grupos_k(self, grupos):
        partes_pur, partes_mec = self._grupos_a_partes(grupos)
        particion = self.sia_subsistema.particionar_k(partes_pur, partes_mec)
        dist = particion.distribucion_marginal()
        perdida = emd_efecto(dist, self.sia_dists_marginales)
        partes = partes_a_clave(partes_pur, partes_mec)
        return perdida, dist, partes

    def _grupos_a_partes(self, grupos):
        partes_purview: list[np.ndarray] = []
        partes_mecanismo: list[np.ndarray] = []
        for grupo in grupos:
            purv, mech = [], []
            for tiempo, idx in self._aplanar_grupo(grupo):
                if tiempo == EFFECT:
                    purv.append(idx)
                else:
                    mech.append(idx)
            partes_purview.append(np.array(purv, dtype=np.int8))
            partes_mecanismo.append(np.array(mech, dtype=np.int8))
        return partes_purview, partes_mecanismo

    @staticmethod
    def _aplanar_grupo(item) -> list[tuple[int, int]]:
        if isinstance(item, tuple):
            return [item]
        return list(item)

    def _registrar_corte(self, vertices_fase: list, k: int):
        if k < self.K_MIN or k > self.K_MAX:
            return
        copia = [v for v in vertices_fase]
        if copia not in self.cortes_dendrograma.setdefault(k, []):
            self.cortes_dendrograma[k].append(copia)

    @profile(context={TYPE_TAG: QNODES_ANALYSIS_TAG})
    def algorithm(self, vertices: list[tuple[int, int]]):
        indice_emd = INT_ZERO
        n = len(vertices)
        self._registrar_corte(vertices, n)

        for _ in range(n - 1):
            omegas_ciclo = [vertices[0]]
            deltas_ciclo = vertices[1:]

            emd_particion_candidata = INFTY_POS
            dist_particion_candidata = None

            for _j in range(len(deltas_ciclo) - 1):
                emd_local = 1e5
                indice_mip = 0

                for k_idx in range(len(deltas_ciclo)):
                    emd_union, emd_delta, dist_marginal_delta = self.funcion_submodular(
                        deltas_ciclo[k_idx], omegas_ciclo
                    )
                    emd_iteracion = emd_union - emd_delta

                    if emd_iteracion < emd_local:
                        if emd_delta == INT_ZERO:
                            clave = self._clave_grupo(deltas_ciclo[k_idx])
                            self.memoria_grupo_candidato[clave] = (
                                emd_delta,
                                dist_marginal_delta,
                            )
                            return clave

                        emd_local = emd_iteracion
                        indice_mip = k_idx
                        emd_particion_candidata = emd_delta
                        dist_particion_candidata = dist_marginal_delta

                omegas_ciclo.append(deltas_ciclo[indice_mip])
                deltas_ciclo.pop(indice_mip)

            clave_final = self._clave_grupo(deltas_ciclo[LAST_IDX])
            self.memoria_grupo_candidato[clave_final] = (
                emd_particion_candidata,
                dist_particion_candidata,
            )

            par_candidato = (
                [omegas_ciclo[LAST_IDX]]
                if isinstance(omegas_ciclo[LAST_IDX], tuple)
                else omegas_ciclo[LAST_IDX]
            ) + (
                deltas_ciclo[LAST_IDX]
                if isinstance(deltas_ciclo[LAST_IDX], list)
                else [deltas_ciclo[LAST_IDX]]
            )

            omegas_ciclo.pop()
            omegas_ciclo.append(par_candidato)
            vertices = omegas_ciclo
            self._registrar_corte(vertices, len(vertices))

        return min(
            self.memoria_grupo_candidato,
            key=lambda k: self.memoria_grupo_candidato[k][indice_emd],
        )

    @staticmethod
    def _clave_grupo(item):
        if isinstance(item, list):
            return tuple(item)
        return (item,)

    def funcion_submodular(
        self, deltas: Union[tuple, list[tuple]], omegas: list[Union[tuple, list[tuple]]]
    ):
        self.clave_submodular = [[], []]

        self.definir_clave(deltas)
        clave_delta = (
            tuple(self.clave_submodular[ACTUAL]),
            tuple(self.clave_submodular[EFFECT]),
        )

        if clave_delta not in self.memoria_delta:
            particion_delta = self.sia_subsistema.bipartir(
                np.array(self.clave_submodular[EFFECT], dtype=np.int8),
                np.array(self.clave_submodular[ACTUAL], dtype=np.int8),
            )
            vector_delta_marginal = particion_delta.distribucion_marginal()
            emd_delta = emd_efecto(vector_delta_marginal, self.sia_dists_marginales)
            self.memoria_delta[clave_delta] = (emd_delta, vector_delta_marginal)
        else:
            emd_delta, vector_delta_marginal = self.memoria_delta[clave_delta]

        clave_omega: list[tuple[int, ...]] = []
        for omega in omegas:
            clave_omega.append(tuple(self._indices_de_conjunto(omega)))

        clave_union = (clave_delta, tuple(clave_omega))
        if clave_union in self.memoria_union:
            return self.memoria_union[clave_union][0], emd_delta, vector_delta_marginal

        self.clave_submodular = [[], []]
        self.definir_clave(deltas)
        for omega in omegas:
            self.definir_clave(omega)

        particion_union = self.sia_subsistema.bipartir(
            np.array(self.clave_submodular[EFFECT], dtype=np.int8),
            np.array(self.clave_submodular[ACTUAL], dtype=np.int8),
        )
        vector_union_marginal = particion_union.distribucion_marginal()
        emd_union = emd_efecto(vector_union_marginal, self.sia_dists_marginales)
        self.memoria_union[clave_union] = (emd_union, vector_union_marginal)

        return emd_union, emd_delta, vector_delta_marginal

    def _indices_de_conjunto(
        self, conjunto: Union[tuple[int, int], list[tuple[int, int]]]
    ) -> list[int]:
        if isinstance(conjunto, tuple):
            return [conjunto[1]]
        return [idx for _, idx in conjunto]

    def definir_clave(
        self,
        conjunto: Union[tuple[int, int], list[tuple[int, int]]],
    ):
        if isinstance(conjunto, tuple):
            tiempo, indice = conjunto
            self.clave_submodular[tiempo].append(indice)
        else:
            for tiempo, indice in conjunto:
                self.clave_submodular[tiempo].append(indice)
        self.clave_submodular[ACTUAL].sort()
        self.clave_submodular[EFFECT].sort()
        return self.clave_submodular

    def nodes_complement(self, nodes: list[tuple[int, int]]):
        return list(self.vertices - set(nodes))

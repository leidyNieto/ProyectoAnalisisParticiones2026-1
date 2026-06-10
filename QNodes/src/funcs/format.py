# from src.funcs.iit import ABECEDARY, LOWER_ABECEDARY
# from src.constants.base import BASE_TWO, COLON_DELIM, VOID_STR

# '''
# Métodos para formatear particiones resultantes de estrategias específicas.
# Este fichero tiene el objetivo de hacer estándar y presentable la salida de resultados al hallarse una bipartición. Es importante aclarar cómo aunque cada función puede ser reutilizada para un nuevo algoritmo si se adaptan sus argumentos, es preferible crear una nueva función si se aprecia mayor dificultad en dicha adaptación.
# '''

# def fmt_biparticion_fuerza_bruta(
#     parte_uno: list[tuple[int, ...], tuple[int, ...]],
#     parte_dos: list[tuple[int, ...], tuple[int, ...]],
# ) -> str:
#     '''
#     Formatea una bipartición de una estrategia de fuerza bruta.

#     Args:
#         parte_uno: Mecanismo y purview de la primera parte.
#     '''
#     mech_p, pur_p = parte_uno
#     mech_d, purv_d = parte_dos

#     # Convertir índices a letras o símbolo vacío si no hay elementos
#     purv_prim = COLON_DELIM.join(ABECEDARY[j] for j in pur_p) if pur_p else VOID_STR
#     mech_prim = (
#         COLON_DELIM.join(LOWER_ABECEDARY[i] for i in mech_p) if mech_p else VOID_STR
#     )

#     purv_dual = COLON_DELIM.join(ABECEDARY[i] for i in purv_d) if purv_d else VOID_STR
#     mech_dual = (
#         COLON_DELIM.join(LOWER_ABECEDARY[j] for j in mech_d) if mech_d else VOID_STR
#     )

#     width_prim = max(len(purv_prim), len(mech_prim)) + BASE_TWO
#     width_dual = max(len(purv_dual), len(mech_dual)) + BASE_TWO

#     return (
#         f"⎛{purv_prim:^{width_prim}}⎞⎛{purv_dual:^{width_dual}}⎞\n"
#         f"⎝{mech_prim:^{width_prim}}⎠⎝{mech_dual:^{width_dual}}⎠\n"
#     )


# def fmt_biparticion_q(
#     prim: list[tuple[int, int]],
#     dual: list[tuple[int, int]],
#     to_sort: bool = True,
# ) -> str:
#     top_prim, bottom_prim = fmt_parte_q(prim, to_sort)
#     top_dual, bottom_dual = fmt_parte_q(dual, to_sort)

#     return f"{top_prim}{top_dual}\n{bottom_prim}{bottom_dual}\n"


# def fmt_k_particion_q(grupos_vertices: list[list[tuple[int, int]]]) -> str:
#     """Formatea una k-partición (k >= 2) en la misma notación fraccionaria."""
#     partes = sorted(grupos_vertices, key=lambda g: min(v[1] for v in g))
#     tops, bottoms = [], []
#     for grupo in partes:
#         top, bottom = fmt_parte_q(list(grupo))
#         tops.append(top)
#         bottoms.append(bottom)
#     return "".join(tops) + "\n" + "".join(bottoms) + "\n"


# def fmt_geomip_k_particion(grupos_vertices: list[list[tuple[int, int]]]) -> str:
#     """
#     Formatea una k-partición en el estilo de GeoMIP:
#         | G1_futuro || G2_futuro || G3_futuro |
#         | G1_presente || G2_presente || G3_presente |
#     """
#     partes = sorted(grupos_vertices, key=lambda g: min(v[1] for v in g))

#     segmentos_top, segmentos_bot = [], []
#     for grupo in partes:
#         futuros = sorted(
#             [ABECEDARY[idx] for t, idx in grupo if t == 1],
#         )
#         presentes = sorted(
#             [LOWER_ABECEDARY[idx] for t, idx in grupo if t == 0],
#         )
#         segmentos_top.append(COLON_DELIM.join(futuros) if futuros else VOID_STR)
#         segmentos_bot.append(COLON_DELIM.join(presentes) if presentes else VOID_STR)

#     sep = " || "
#     linea_top = "| " + sep.join(segmentos_top) + " |"
#     linea_bot = "| " + sep.join(segmentos_bot) + " |"
#     return f"{linea_top}\n{linea_bot}"


# def fmt_parte_q(
#     parte: list[tuple[int, int]], a_ordenar: bool = True
# ) -> tuple[str, str]:
#     if a_ordenar:
#         # Ordenar por índice #
#         parte.sort(key=lambda x: x[1])

#     purv, mech = [], []
#     for time, idx in parte:
#         purv.append(ABECEDARY[idx]) if time else mech.append(LOWER_ABECEDARY[idx])

#     str_purv = COLON_DELIM.join(purv) if purv else VOID_STR
#     str_mech = COLON_DELIM.join(mech) if mech else VOID_STR
#     width = max(len(str_purv), len(str_mech)) + 2

#     return f"⎛{str_purv:^{width}}⎞", f"⎝{str_mech:^{width}}⎠"
from src.funcs.iit import ABECEDARY, LOWER_ABECEDARY
from src.constants.base import ACTUAL, BASE_TWO, COLON_DELIM, EFFECT, VOID_STR

'''
Métodos para formatear particiones resultantes de estrategias específicas.
Este fichero tiene el objetivo de hacer estándar y presentable la salida de resultados al hallarse una bipartición. Es importante aclarar cómo aunque cada función puede ser reutilizada para un nuevo algoritmo si se adaptan sus argumentos, es preferible crear una nueva función si se aprecia mayor dificultad en dicha adaptación.
'''

def fmt_biparticion_fuerza_bruta(
    parte_uno: list[tuple[int, ...], tuple[int, ...]],
    parte_dos: list[tuple[int, ...], tuple[int, ...]],
) -> str:
    '''
    Formatea una bipartición de una estrategia de fuerza bruta.

    Args:
        parte_uno: Mecanismo y purview de la primera parte.
    '''
    mech_p, pur_p = parte_uno
    mech_d, purv_d = parte_dos

    # Convertir índices a letras o símbolo vacío si no hay elementos
    purv_prim = COLON_DELIM.join(ABECEDARY[j] for j in pur_p) if pur_p else VOID_STR
    mech_prim = (
        COLON_DELIM.join(LOWER_ABECEDARY[i] for i in mech_p) if mech_p else VOID_STR
    )

    purv_dual = COLON_DELIM.join(ABECEDARY[i] for i in purv_d) if purv_d else VOID_STR
    mech_dual = (
        COLON_DELIM.join(LOWER_ABECEDARY[j] for j in mech_d) if mech_d else VOID_STR
    )

    width_prim = max(len(purv_prim), len(mech_prim)) + BASE_TWO
    width_dual = max(len(purv_dual), len(mech_dual)) + BASE_TWO

    return (
        f"⎛{purv_prim:^{width_prim}}⎞⎛{purv_dual:^{width_dual}}⎞\n"
        f"⎝{mech_prim:^{width_prim}}⎠⎝{mech_dual:^{width_dual}}⎠\n"
    )


def fmt_biparticion_q(
    prim: list[tuple[int, int]],
    dual: list[tuple[int, int]],
    to_sort: bool = True,
) -> str:
    top_prim, bottom_prim = fmt_parte_q(prim, to_sort)
    top_dual, bottom_dual = fmt_parte_q(dual, to_sort)

    return f"{top_prim}{top_dual}\n{bottom_prim}{bottom_dual}\n"


def fmt_parte_q(
    parte: list[tuple[int, int]], a_ordenar: bool = True
) -> tuple[str, str]:
    if a_ordenar:
        # Ordenar por índice #
        parte.sort(key=lambda x: x[1])

    purv, mech = [], []
    for time, idx in parte:
        purv.append(ABECEDARY[idx]) if time else mech.append(LOWER_ABECEDARY[idx])

    str_purv = COLON_DELIM.join(purv) if purv else VOID_STR
    str_mech = COLON_DELIM.join(mech) if mech else VOID_STR
    width = max(len(str_purv), len(str_mech)) + 2

    return f"⎛{str_purv:^{width}}⎞", f"⎝{str_mech:^{width}}⎠"


def partes_a_clave(
    partes_purview: list,
    partes_mecanismo: list,
) -> list[list[tuple[int, int]]]:
    """Convierte partes purview/mecanismo en claves para formateo."""
    k = max(len(partes_purview), len(partes_mecanismo))
    clave: list[list[tuple[int, int]]] = []
    for j in range(k):
        parte: list[tuple[int, int]] = []
        for idx in partes_mecanismo[j] if j < len(partes_mecanismo) else []:
            parte.append((ACTUAL, int(idx)))
        for idx in partes_purview[j] if j < len(partes_purview) else []:
            parte.append((EFFECT, int(idx)))
        clave.append(parte)
    return clave


def fmt_k_particion(partes: list[list[tuple[int, int]]]) -> str:
    """Formatea una k-partición con k bloques horizontales."""
    if not partes:
        return "∅\n"
    tops, bottoms = [], []
    for parte in partes:
        top, bottom = fmt_parte_q(list(parte))
        tops.append(top)
        bottoms.append(bottom)
    return "".join(tops) + "\n" + "".join(bottoms)


def fmt_geomip_k_particion(partes: list[list[tuple[int, int]]]) -> str:
    """Formato plano para Excel (sin caracteres Unicode de cajas)."""
    if not partes:
        return VOID_STR

    bloques = []
    for parte in partes:
        purv, mech = [], []
        for time, idx in sorted(parte, key=lambda x: x[1]):
            if time:
                purv.append(ABECEDARY[idx])
            else:
                mech.append(LOWER_ABECEDARY[idx])
        str_purv = COLON_DELIM.join(purv) if purv else VOID_STR
        str_mech = COLON_DELIM.join(mech) if mech else VOID_STR
        width = max(len(str_purv), len(str_mech)) + 2
        bloques.append(
            f"|{str_purv:^{width}}|\n|{str_mech:^{width}}|"
        )
    return "\n".join(bloques)

from src.controllers.manager import Manager

# Importación de estrategias
from src.strategies.q_nodes import QNodes


def iniciar():
    """Punto de entrada"""

    # ABCD #
    estado_inicial = "1000"
    condiciones =    "1110"
    alcance =        "1110"
    mecanismo =      "1110"

    gestor_redes = Manager(estado_inicial)
    mpt = gestor_redes.cargar_red()

    analizador = QNodes(mpt)

    # La tabla por-k (k = 2 … 5) se imprime dentro de aplicar_estrategia.
    analizador.aplicar_estrategia(
        estado_inicial,
        condiciones,
        alcance,
        mecanismo
    )
    
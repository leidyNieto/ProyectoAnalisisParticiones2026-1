import sys

# Forzar UTF-8 en la salida para evitar UnicodeEncodeError con caracteres
# especiales (φ, ⎛, ∅, ≡, ...) en terminales Windows con codificación cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.models.base.application import aplicacion

from src.main import iniciar


def main():
    """Inicialización del aplicativo"""

    # 👇 Investiga en la clase `aplicación` para más configuraciones 👇 #
    aplicacion.activar_profiling()
    aplicacion.set_pagina_red_muestra("A")

    iniciar()


if __name__ == "__main__":
    main()

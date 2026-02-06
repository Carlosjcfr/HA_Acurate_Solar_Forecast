Accurate Forecast (Solar Simulator)

Integración personalizada para Home Assistant que estima la producción fotovoltaica con alta precisión mediante modelos físicos y geométricos.

Características Principales:

    Motor de Transposición: Calcula la irradiancia incidente en múltiples orientaciones e inclinaciones partiendo de un único sensor de referencia (Piranómetro), utilizando geometría solar en tiempo real.

    Base de Datos de Paneles: Sistema de gestión interno para crear, almacenar y reutilizar modelos de módulos FV (Potencia, Coeficientes, NOCT).

    Física Térmica Avanzada: Cálculo dinámico de pérdidas por temperatura (Derating) usando tres estrategias automáticas:

        Medición Directa (Sonda en panel).

        Modelo Faiman (Temp. Ambiente + Viento).

        Modelo NOCT (Temp. Ambiente).

    Multi-String: Soporte para ilimitados strings virtuales con configuraciones geométricas independientes.

    Configuración UI: Gestión completa (Paneles y Strings) mediante Flujo de Configuración (Config Flow) nativo.

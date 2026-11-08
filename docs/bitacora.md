# Bitácora de desarrollo: Mesa de ayuda EdgeAI

Proyecto II - Taller de Sistemas Embebidos, Tecnológico de Costa Rica.
Periodo documentado: 19 de octubre al 5 de noviembre de 2026.

## Registro de tareas

| Tarea | Integrante | Fecha |
|---|---|---|
| Inicialización del repositorio y creación del README de partida. | Álvaro Chacón | 19/10/2026 |
| Implementación de la carga de configuración para desarrollo y despliegue. | Denzel Lynch | 25/10/2026 |
| Definición de categorías de consulta, base de conocimiento y casos de demostración. | Denzel Lynch | 25/10/2026 |
| Implementación del cliente HTTP para comunicarse con Ollama. | Denzel Lynch | 25/10/2026 |
| Implementación de la clasificación de consultas y las políticas de decisión. | Denzel Lynch | 25/10/2026 |
| Implementación de la redacción de respuestas con el modelo de lenguaje local. | Denzel Lynch | 25/10/2026 |
| Implementación del almacenamiento y la gestión de tiquetes en SQLite. | Denzel Lynch | 25/10/2026 |
| Integración del servicio de atención y del procesamiento de respuestas. | Denzel Lynch | 25/10/2026 |
| Implementación del servidor HTTP y documentación de la API. | Denzel Lynch | 25/10/2026 |
| Creación de la interfaz web para ingresar consultas y consultar respuestas. | Denzel Lynch | 25/10/2026 |
| Creación del panel web para gestionar la cola de atención. | Denzel Lynch | 25/10/2026 |
| Implementación del kiosco de texto para uso local. | Denzel Lynch | 25/10/2026 |
| Implementación del control de indicadores LED. | Denzel Lynch | 25/10/2026 |
| Creación de herramientas de administración y medición de rendimiento. | Denzel Lynch | 25/10/2026 |
| Definición de servicios systemd, reglas udev y ajustes del sistema. | Denzel Lynch | 25/10/2026 |
| Creación del simulador de Ollama para desarrollo sin Raspberry Pi ni modelos reales. | Denzel Lynch | 25/10/2026 |
| Creación del exportador de modelos para preparar su distribución. | Denzel Lynch | 25/10/2026 |
| Incorporación de pruebas de decisión, API, almacenamiento, indicadores y herramientas. | Denzel Lynch | 25/10/2026 |
| Incorporación de comandos Makefile para pruebas y desarrollo local. | Denzel Lynch | 25/10/2026 |
| Creación de la capa meta-edgeai y de la distribución Yocto wrynose. | Álvaro Chacón | 25/10/2026 |
| Preparación de plantillas de construcción y fijación de revisiones de las capas. | Álvaro Chacón | 25/10/2026 |
| Creación de la receta de Ollama ARM64 y de su servicio systemd. | Álvaro Chacón | 25/10/2026 |
| Creación de la receta de la aplicación para instalarla en la imagen Yocto. | Álvaro Chacón | 25/10/2026 |
| Creación de la receta de modelos precargados y del archivo de versiones de modelos. | Álvaro Chacón | 25/10/2026 |
| Configuración de Ethernet, Wi-Fi y descubrimiento de red mediante mDNS. | Álvaro Chacón | 25/10/2026 |
| Configuración de arranque de Raspberry Pi y definición del grupo de paquetes y la imagen. | Álvaro Chacón | 25/10/2026 |
| Creación de scripts para verificar el host y preparar el entorno de construcción. | Álvaro Chacón | 25/10/2026 |
| Creación de scripts para construir la imagen y grabarla en una microSD. | Álvaro Chacón | 25/10/2026 |
| Creación de scripts para preparar modelos, actualizar Ollama y desplegar la aplicación. | Álvaro Chacón | 25/10/2026 |
| Incorporación de herramientas para generar y filtrar el grafo de dependencias. | Álvaro Chacón | 25/10/2026 |
| Adaptación de la configuración de construcción para la máquina qemuarm64. | Denzel Lynch | 25/10/2026 |
| Incorporación de la receta de pruebas de la aplicación en QEMU. | Denzel Lynch | 25/10/2026 |
| Incorporación de pruebas de ejecución de la imagen mediante OEQA. | Denzel Lynch | 25/10/2026 |
| Creación de scripts para iniciar QEMU y ejecutar sus pruebas. | Denzel Lynch | 25/10/2026 |
| Configuración del flujo de integración continua en GitHub Actions. | Álvaro Chacón | 25/10/2026 |
| Automatización del registro del runner propio para construcciones Yocto. | Álvaro Chacón | 25/10/2026 |
| Integración del flujo de construcción de modelos, QEMU y Raspberry Pi. | Álvaro Chacón | 25/10/2026 |
| Automatización de la recolección de imágenes, reportes y artefactos de construcción. | Álvaro Chacón | 25/10/2026 |
| Documentación de la arquitectura operacional, funcional y física. | Álvaro Chacón | 25/10/2026 |
| Elaboración de la guía de generación e instalación y de la documentación de recetas y dependencias. | Álvaro Chacón | 25/10/2026 |
| Documentación de hardware, conexiones, demostración y propuesta de diseño. | Álvaro Chacón | 25/10/2026 |
| Corrección de la habilitación automática del kiosco mediante un preset de systemd. | Álvaro Chacón | 26/10/2026 |
| Ajuste de la herramienta de administración para manejar archivos comprimidos. | Denzel Lynch | 26/10/2026 |
| Incorporación de una prueba de API relacionada con la importación de modelos comprimidos. | Denzel Lynch | 26/10/2026 |
| Ajuste de las pruebas de QEMU para operar sin indicadores físicos y actualización de la guía. | Denzel Lynch | 26/10/2026 |
| Incorporación de una red Wi-Fi de respaldo en la configuración y la receta de red. | Denzel Lynch | 28/10/2026 |
| Documentación de la configuración y el uso de la red Wi-Fi alternativa. | Denzel Lynch | 28/10/2026 |
| Incorporación de la propuesta de diseño en formato PDF. | Denzel Lynch | 01/11/2026 |
| Ajuste de categorías, configuración y lógica de clasificación de urgencia. | Álvaro Chacón | 05/11/2026 |
| Incorporación de una regla de riesgo y actualización de la arquitectura documentada. | Álvaro Chacón | 05/11/2026 |
| Ajuste de los indicadores para reflejar los cambios en la clasificación. | Álvaro Chacón | 05/11/2026 |
| Incorporación de módulos Wi-Fi al grupo de paquetes de la imagen. | Álvaro Chacón | 05/11/2026 |

## Respaldo en el historial

Las actividades de cada bloque se derivan de los archivos incorporados o
modificados en estos commits. No representan un registro diario de horas.

| Commit | Autor registrado | Fecha | Bloque de trabajo |
|---|---|---|---|
| 5d53c26 | Álvaro Chacón | 19/10/2026 | Inicialización del repositorio. |
| 902a37b | dlynchr | 25/10/2026 | Aplicación, interfaces, servicios, simulador y pruebas. |
| ba853fd | Álvaro Chacón | 25/10/2026 | Capa Yocto, recetas, red, modelos y scripts. |
| 599f178 | DlynchR | 25/10/2026 | Soporte de QEMU y pruebas de la imagen. |
| ecc6047 | Álvaro Chacón | 25/10/2026 | Integración continua, artefactos y documentación. |
| 8086f6f | Álvaro Chacón | 26/10/2026 | Habilitación del kiosco. |
| a4f7e94 | DlynchR | 26/10/2026 | Archivos comprimidos y pruebas sin hardware. |
| 3f32189 | DlynchR | 28/10/2026 | Red Wi-Fi de respaldo. |
| 5e09745 | Denzel Lynch | 01/11/2026 | Propuesta de diseño en PDF. |
| 15162e1 | Álvaro Chacón | 05/11/2026 | Urgencia, categorías, riesgo, indicadores y módulos Wi-Fi. |
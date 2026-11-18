# Verificación de esta versión

Revisión local del 18 de noviembre de 2026, con Python 3.14 en Windows.

| Comprobación | Resultado |
| --- | --- |
| Suite Python completa en entorno recién instalado | 64 pruebas correctas, incluida compatibilidad del cambio de nombre |
| Composición y comportamiento JavaScript con servicios simulados | 6 pruebas correctas |
| Formato Python | Black correcto |
| Formato JavaScript, CSS e índice HTML | Prettier correcto |
| Arranque del paquete extraído con datos aislados | Correcto |
| Recursos de la página y rechazo de API sin sesión | Correcto |
| Exclusión de datos privados del conjunto publicable | Comprobada |
| Primer arranque Windows PowerShell 5, sin pip ni librerías preinstaladas | Instalación, arranque, reapertura y cierre correctos |
| Dependencias de producción | 15 versiones comprobadas; cero vulnerabilidades conocidas detectadas tras actualizar pypdf a 6.21.4 |

Se cubren acceso, sesiones, aislamiento entre empresas, importación, copias, informes, conversiones, clasificación por alcance y selección de factores. La migración se prueba con un libro antiguo que contiene credenciales, actividad calculada e informes, verificando conservación e integridad de relaciones.

La revisión visual en navegador queda pendiente de comprobación manual. Esta evidencia corresponde a la versión local preparada: no acredita un despliegue de esta versión en un servidor ni una ejecución de los trabajos de GitHub Actions.

La prueba numérica usa exclusivamente factores ficticios. Valida el funcionamiento del cálculo; no valida factores reales ni certifica la metodología particular de una empresa.

Consulta los hallazgos y las correcciones en la [revisión final](REVISION_FINAL.md). Las comprobaciones de dependencias reflejan los avisos disponibles en la fecha de revisión; no garantizan ausencia de vulnerabilidades futuras.

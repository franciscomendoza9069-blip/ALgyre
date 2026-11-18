# Revisión de publicación · 18 de noviembre de 2026

## Hallazgos corregidos

### Primer arranque en Windows

La comprobación anterior importaba librerías que podían no estar instaladas. En Windows PowerShell 5, el error de Python podía detener el acceso directo antes de instalar las dependencias.

Se comprueba su presencia sin producir una excepción. El acceso prepara pip si falta, instala las versiones fijadas y guarda la huella del archivo de requisitos para actualizar las librerías cuando ese archivo cambie. El acceso de Windows configura expresamente el modo local y la carpeta de datos de esa instalación.

Se comprobó con un ZIP extraído, un entorno sin pip ni librerías y valores de modo servidor heredados: instalación, arranque local, reapertura y cierre correctos.

### Dependencia de lectura de PDF

La comprobación encontró siete avisos conocidos para pypdf 6.21.2. Los requisitos se actualizaron a 6.21.4, que incorpora [correcciones de seguridad del mantenedor](https://github.com/py-pdf/pypdf/releases/tag/6.21.4). Tras repetir la consulta con pip-audit, las 15 dependencias fijadas no presentaron vulnerabilidades conocidas detectadas.

Esto se refiere a esta versión preparada. No confirma que otras instalaciones o servidores ya estén actualizados.

### Actividades distintas que comparten fecha

Los controles de suministros solapados también bloqueaban viajes o entregas de residuos que coincidían en fecha. Las actividades puntuales permiten ahora registros distintos con referencias propias. Se conserva la detección de referencias repetidas y de actividades idénticas sin referencias distintas. Los suministros continuos mantienen el control de solapamientos.

La suite incluye pruebas tanto de entrada manual como de importación de varias actividades en un mismo día. El panel aclara que la cobertura temporal solo mide suministros continuos.

## Comprobaciones completadas

- Instalación de las dependencias en un entorno limpio y comprobación de sus requisitos.
- 64 pruebas de Python y 6 de JavaScript correctas.
- Formato Python, JavaScript, CSS e índice HTML comprobado.
- Arranque local desde el paquete de distribución y protección de las rutas que requieren sesión.
- Compatibilidad con bases, contraseñas y copias de versiones anteriores.
- Archivos publicables revisados para excluir datos empresariales, direcciones operativas y credenciales privadas.
- Enlaces locales de la documentación comprobados.

## Licencia y comprobaciones pendientes

Se incorpora PolyForm Internal Use 1.0.0 en LICENSE, según la decisión del titular: uso empresarial interno y modificaciones internas permitidos; la redistribución y el servicio a terceros quedan fuera de los permisos. No se presenta como una licencia de código abierto.

La revisión visual en navegador queda pendiente de comprobación manual. Las pruebas de JavaScript utilizan servicios simulados y no demuestran por sí solas que todos los estados visuales funcionen correctamente.

El entorno limpio se verificó en Windows con Python 3.14. La ejecución de GitHub Actions en Windows/Linux, la prueba en macOS y la instalación de esta versión en Debian no se han realizado en esta revisión. La publicación en GitHub tampoco se ha realizado.

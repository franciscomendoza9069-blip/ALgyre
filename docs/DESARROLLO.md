# Organización y mantenimiento del código

## Estructura

| Archivo o carpeta | Responsabilidad |
| --- | --- |
| `app.py` | Composición Flask, conexión autorizada al espacio y rutas HTTP |
| `tenancy.py` | Cuentas, sesiones, empresas, correo opcional y administración |
| `manage.py` | Operaciones administrativas desde el servidor |
| `algyre_core/environment.py` | Catálogo de actividades, alcances y unidades |
| `algyre_core/ledger.py` | Validación, selección de factores, cálculo y estado del inventario |
| `algyre_core/common.py` | Valores, identificadores y operaciones SQL comunes |
| `algyre_core/reporting.py` | PDF de instantáneas de informes |
| `algyre_core/documents.py` | Lectura acotada de texto PDF |
| `algyre_core/migrations.py` | Actualización transaccional de bases anteriores |
| `import_workflow.py` | Lectura de Excel/CSV, columnas y plantilla |
| `static/core.js` | Estado, primitivas y cliente HTTP |
| `static/views.js` | Pantallas del inventario y acceso local |
| `static/forms.js` | Formularios y selección de archivos |
| `static/actions.js` | Acciones del inventario |
| `static/accounts.js` | Acceso multiempresa y administración |
| `static/intake.js` | Asistente de importación y calidad |
| `static/app.js` | Eventos globales y único punto de arranque |
| `tests/` | Pruebas aisladas con datos ficticios |
| `deploy/` | Instalación, empaquetado, copias y supervisión |

La interfaz recibe catálogo y unidades en `/api/state`. No mantiene una segunda lista manual. Los scripts se cargan en el orden declarado en `static/index.html`; las funciones de acceso y renderizado se componen explícitamente, sin sustituir funciones ya definidas. No hay compilación frontend obligatoria.

## Pruebas

Instala las dependencias de `requirements-lock.txt` y ejecuta desde la raíz:

```bash
python -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

Usa el Python del entorno virtual. En Windows es `.venv/Scripts/python.exe`; en Linux, `.venv/bin/python`. Node solo es necesario para las comprobaciones de la interfaz, no para servir la aplicación.

Las pruebas crean bases ficticias en `work/`. Nunca deben utilizar `data/` ni una base de producción. Se comprueban aislamiento entre empresas, sesiones, importación, informes, restauración, migración y totales por alcance. Las pruebas de JavaScript comprueban composición y comportamiento con servicios simulados; no sustituyen la revisión visual en un navegador.

## Estilo

Python sigue Black, configuración en `pyproject.toml`. JavaScript sigue Prettier, configuración en `.prettierrc.json`. Las herramientas de formato son de desarrollo, no dependencias del servidor. Versiones usadas para esta reorganización: Black 25.1.0 y Prettier 3.6.2.

Mantén las reglas ambientales en `algyre_core/environment.py`. Si añades una categoría, actualiza restricciones SQL, migración, metodología y pruebas de compatibilidad. Un factor nunca debe asignarse por mera coincidencia de unidades si la actividad necesita una elección específica.

## Actualizar datos anteriores

Al inicializar un libro antiguo se guarda `antes-alcance-v2-NOMBRE.sqlite` junto a la base. La ampliación de restricciones ocurre en una transacción con comprobación de claves foráneas. No cambia identificadores ni elimina informes anteriores. El arranque público actualiza las bases de las empresas existentes.

Detén el servicio y conserva una copia general antes de actualizar. No abras simultáneamente la base con versiones diferentes del programa. Revertir solo el código después de registrar categorías nuevas no es compatible: conserva la pareja código/base de la versión anterior.

## Preparación del repositorio

No incluyas bases, facturas, secretos, copias, historial operativo privado ni herramientas descargadas. `.gitignore` excluye esas ubicaciones. `deploy/package.py` genera un paquete por lista explícita de archivos; no empaqueta toda la carpeta.

El código propio se ofrece bajo PolyForm Internal Use 1.0.0, texto completo en LICENSE y atribución en NOTICE. Permite operaciones internas y cambios para ese fin; no concede permiso de redistribución ni explotación como servicio externo. Las dependencias conservan sus licencias.

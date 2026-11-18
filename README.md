# ALgyre

**Consumos, documentos y emisiones de tu empresa en un espacio privado.**

ALgyre es un software creado por Paco a partir de una necesidad de su propia empresa: reunir información ambiental dispersa, conservar las evidencias y convertir los datos en resultados que se puedan revisar y explicar. Este proyecto permite que otras empresas organicen ese trabajo en su propia infraestructura.

**Descarga el código y ejecútalo en tu propio ordenador para las operaciones internas de tu empresa. No necesitas registrarte, facilitar un correo ni solicitar acceso.** Cada instalación es independiente y guarda sus datos en ese equipo. La contraseña que eliges al abrirlo por primera vez solo protege tu espacio local.

## Descargar y abrir

1. En este repositorio, pulsa **Code → Download ZIP**.
2. Descomprime el ZIP en una carpeta donde tengas permiso para guardar archivos. No lo ejecutes dentro del ZIP.
3. Instala Python 3.11 o posterior si todavía no lo tienes. En Windows, activa la opción para añadir Python al PATH durante la instalación.
4. En Windows, abre **Abrir ALgyre.cmd**. La primera vez se descargan las librerías necesarias; después se abrirá ALgyre en tu navegador.
5. Elige una contraseña local o explora los datos ficticios de demostración.

Para detenerlo en Windows, abre **Cerrar ALgyre.cmd**. Más abajo encontrarás los comandos para Linux, macOS y la instalación manual.

La instalación de dependencias requiere Internet. Una vez instaladas, el uso local no necesita una cuenta externa ni conexión a un servicio de ALgyre. Las actualizaciones del programa y la consulta de fuentes de factores sí pueden necesitar conexión.

## Qué puedes hacer

- Crear instalaciones y definir las actividades que quieres medir.
- Registrar actividades manualmente o importar Excel y CSV con revisión previa.
- Adjuntar PDF y comprobar las propuestas extraídas de su texto.
- Mantener factores con fuente, versión, año, país y condiciones de uso.
- Consultar emisiones por alcance, pendientes y calidad de datos.
- Generar informes PDF, exportaciones CSV e historial de correcciones.
- Conservar copias recuperables de los datos de tu empresa.

## Alcance ambiental

| Alcance | Actividades disponibles |
| --- | --- |
| 1 · Emisiones directas | Gas natural, diésel, gasolina y fugas de refrigerantes en fuentes propias o controladas |
| 2 · Energía comprada | Electricidad por método territorial, calor/vapor y frío comprados |
| 3 · Actividades indirectas seleccionadas | Bienes y servicios comprados, suministro de agua, transporte contratado, residuos tratados por terceros, viajes de trabajo y desplazamiento al trabajo |

Cada actividad necesita un factor apropiado. **Sin factor, los datos quedan pendientes; no cuentan como emisiones cero.** Las nuevas actividades exigen elegir expresamente el factor y describir la actividad en las notas.

No se cubren todas las fuentes e impactos ambientales posibles. No hay cálculo por gasto, huella de producto, inventario completo de las 15 categorías indirectas ni certificación automática. Consulta la [metodología y los límites](docs/METODOLOGIA.md).

## Incorporar ALgyre a tu empresa

1. Designa una persona responsable del perímetro y los factores.
2. Instala ALgyre en el ordenador donde vas a trabajar y guardar los datos.
3. Configura empresa e instalaciones. Empieza por un periodo pequeño.
4. Añade factores documentados y actividades. Comprueba los resultados.
5. Guarda la contraseña local y establece una rutina de copias de seguridad.

La [guía para empresas](docs/GUIA_EMPRESA.md) explica el recorrido sin requerir conocimientos de programación.

## Instalación manual

Necesitas Python 3.11 o posterior. No se incluye un entorno preparado ni datos reales.

Windows, desde PowerShell en la carpeta del proyecto:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe app.py
```

Linux y macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python app.py
```

En Debian, si falta soporte para entornos, instala `python3-venv`.

Abre **http://127.0.0.1:8765** y crea la contraseña local. Puedes explorar un ejemplo ficticio en una base independiente. Windows también incluye `Abrir ALgyre.cmd` y `Cerrar ALgyre.cmd`.

`127.0.0.1` significa **tu propio ordenador**. El navegador muestra una página servida por el programa que acabas de abrir en ese mismo equipo. Cada persona que descargue el proyecto tendrá su propia instalación independiente.

No necesitas crear un archivo `.env` para este modo. Arranca con la configuración local por defecto. Si usas la terminal, mantenla abierta mientras trabajas y pulsa Ctrl+C para cerrar el programa.

## Datos y mantenimiento

La instalación local guarda datos y documentos en `data/`, dentro de la carpeta del programa. Bases, documentos, claves y copias privadas no forman parte del repositorio. El cálculo y la lectura PDF ocurren en tu instalación. La lectura usa texto y reglas, sin OCR ni agentes de IA.

Desde **Configuración**, descarga una copia ZIP para proteger tu trabajo. Antes de cambiar de ordenador o actualizar, guarda esa copia. Cada instalación tiene sus propios datos: copiar solo el código no traslada el inventario empresarial.

- [Guía de uso para tu empresa](docs/GUIA_EMPRESA.md)
- [Organización del código y pruebas](docs/DESARROLLO.md)
- [Novedades](CHANGELOG.md)

Los informes conservan fuentes y supuestos. No sustituyen la validación de una persona competente ni la verificación externa cuando corresponda.

## Opción avanzada: servidor propio

Si más adelante tu empresa quiere compartir una instalación entre varios equipos, puede alojarla en su propia infraestructura siguiendo la [guía Debian](deploy/LEEME.md). Ese modo tiene cuentas y administración, y se configura por separado. La descarga y el uso en tu ordenador funcionan sin activarlo.

## Licencia

ALgyre se ofrece gratuitamente para las operaciones internas de tu empresa bajo [PolyForm Internal Use 1.0.0](LICENSE). Puedes usarlo y modificarlo para ese fin. La licencia no permite redistribuirlo, revenderlo ni ofrecerlo como servicio a terceros. Para usos fuera de esos permisos necesitas autorización del titular.

Copyright © 2026 Paco ([franciscomendoza9069-blip](https://github.com/franciscomendoza9069-blip)). El texto vinculante es el de LICENSE. Las dependencias conservan sus propias licencias.

# Instalar ALgyre en tu ordenador

[English](install.md) · [Castellano](install.es.md) · [Portada](../../README.es.md)

No necesitas registrarte, facilitar un correo ni utilizar un servidor externo de ALgyre. Elegirás una contraseña que protege la aplicación en tu ordenador.

## Windows: abrir con doble clic

1. Descarga el proyecto en GitHub con **Code → Download ZIP**.
2. Descomprime el ZIP en una carpeta donde puedas guardar archivos. No ejecutes el programa desde dentro del ZIP.
3. Instala **Python 3.11 o posterior** desde [python.org](https://www.python.org/downloads/). Marca **Add Python to PATH** durante la instalación.
4. Haz doble clic en **Abrir ALgyre.cmd**. La primera vez prepara el entorno Python y descarga las librerías necesarias.
5. En el navegador, elige una contraseña local de al menos diez caracteres o pulsa **Explorar con datos de ejemplo** para probarlo con datos ficticios.

El acceso abre **http://127.0.0.1:8765**. `127.0.0.1` significa tu propio ordenador. Para detener el programa, utiliza **Cerrar ALgyre.cmd**. Cerrar solo la pestaña no lo detiene.

Los archivos de `scripts/` implementan los accesos; normalmente solo necesitas los dos botones `.cmd` de la carpeta principal.

## Instalación manual

Abre una terminal en la carpeta descomprimida del proyecto.

### Windows PowerShell

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe app.py
```

### Linux y macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python app.py
```

En Debian, instala `python3-venv` con el gestor de paquetes si falta soporte para crear el entorno. Las pruebas automáticas comprueban Windows y Linux; macOS no se ha verificado por separado.

Abre **http://127.0.0.1:8765**. Mantén la terminal abierta mientras trabajas; pulsa **Ctrl+C** para detener el programa. El modo local no necesita un archivo `.env`.

## Datos, actualizaciones y cambio de ordenador

- La primera instalación de librerías necesita Internet. Después puedes trabajar sin un servicio externo de ALgyre.
- Los registros y documentos se guardan en `data/`. El espacio real y el ejemplo utilizan bases separadas.
- Antes de actualizar o cambiar de equipo, descarga una copia ZIP desde **Configuración**. Es privada: guarda otra copia fuera de la carpeta de la aplicación.
- En el destino, instala el programa, elige su contraseña local y restaura el ZIP desde **Configuración**. Se recuperan inventario y documentos; no se traslada la contraseña anterior.
- Guarda la contraseña en tu gestor de contraseñas. El modo local no envía correos de recuperación.

## Problemas habituales

| Problema | Qué comprobar |
| --- | --- |
| No encuentra Python | Vuelve a abrir la terminal y comprueba que Python esté añadido al PATH. |
| No abre la página | Arranca primero el programa. En Windows, consulta `data/server-error.log`; en modo manual, lee el mensaje de la terminal. |
| Falta una librería | Ejecuta la instalación de requisitos con el Python situado dentro de `.venv`. |
| El puerto está ocupado | Detén la otra aplicación que utiliza el puerto 8765 antes de abrir esta copia. |
| El inventario aparece vacío | Cada instalación tiene sus propios datos. Restaura tu copia si vienes de otro equipo. |

Si tu empresa quiere compartir una instalación, puede utilizar [su propio servidor Debian](../../deploy/LEEME.md). Es una configuración opcional distinta del uso local.

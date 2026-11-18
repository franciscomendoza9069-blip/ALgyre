# ALgyre en Debian

El acceso público se hace por HTTPS con una IP. No necesita Tailscale ni SSH para sus usuarios.

## Instalación

Con los archivos extraídos en una carpeta, ejecuta como administrador:

```bash
sudo bash deploy/install-debian.sh IP_PUBLICA
sudo bash /opt/algyre/deploy/publish-ip.sh IP_PUBLICA
```

El primer archivo instala una copia en `/opt/algyre`, crea el usuario de servicio `algyre`, guarda los datos en `/var/lib/algyre` y arranca automáticamente. Su conexión interna usa `127.0.0.1:8766`. Los datos se guardan fuera del código para conservarlos al actualizar.

El segundo añade un sitio de Apache para la IP y un certificado de Let's Encrypt. Los puertos públicos 80 y 443 deben llegar al servidor. Una dirección de red privada o de VPN no sustituye a una IP pública accesible por los usuarios. El script respalda las configuraciones de Apache y comprueba su sintaxis antes de recargarlo; conserva los sitios por dominio.

Los navegadores que entran por IP no siempre envían el nombre del sitio durante la conexión HTTPS. Por eso ALgyre pasa a ser el sitio predeterminado para conexiones sin nombre. Las webs con sus dominios siguen seleccionando sus propios certificados. Comprueba los sitios existentes después del cambio. Para revertir solo ALgyre: `sudo a2dissite 000-000-algyre-ip && sudo apache2ctl configtest && sudo systemctl reload apache2`.

## Crear tu cuenta de administrador

Genera un enlace de instalación de un solo uso, válido durante una hora:

```bash
sudo bash -c 'set -a; source /etc/algyre.env; set +a; runuser -u algyre -- /opt/algyre/.venv/bin/python /opt/algyre/manage.py prepare-admin'
```

Abre el enlace en tu navegador y elige tu correo y contraseña. Indica también el nombre del responsable y su correo público de contacto, que aparecerán en Privacidad. Elige una contraseña exclusiva y guárdala en tu gestor de contraseñas. El enlace no puede crear otro administrador una vez creado el primero.

## Dar acceso a las empresas

- Puedes crear cuentas desde Administración, con una contraseña inicial que entregarás por un medio privado.
- Las empresas también pueden pulsar «Registrar mi empresa». Sin correo configurado, aparecerán pendientes y debes pulsar «Aprobar» antes de que puedan entrar.
- Cada empresa tiene una sola cuenta compartida y su propia base de datos. Los empleados no tienen permisos de administración general.
- Puedes abrir el espacio de una empresa, suspenderla, restablecer su contraseña o eliminarla. Suspender y restablecer la contraseña cierra sus sesiones.
- La contraseña de ALgyre es independiente de la contraseña SSH del servidor.

## Correo opcional

Edita `/etc/algyre.env` con `sudoedit` y añade las variables SMTP de `.env.example`; reinicia con `sudo systemctl restart algyre`. Introduce las claves directamente en el servidor. Con SMTP se envían los enlaces para confirmar el correo y recuperar la contraseña. Sin SMTP la recuperación la realiza el administrador. El envío exige TLS en 587 o 465.

## Datos anteriores

Para copiar una instalación local anterior a una cuenta nueva, sustituye `/ruta/a/algyre.sqlite` por su ubicación. El archivo de origen se conserva:

```bash
sudo bash -c 'set -a; source /etc/algyre.env; set +a; /opt/algyre/.venv/bin/python /opt/algyre/manage.py import-legacy --source /ruta/a/algyre.sqlite; chown -R algyre:algyre /var/lib/algyre'
```

El comando pide el correo y contraseña de esa empresa. No vuelve a usar la contraseña local antigua ni da a los registros anteriores acceso a otras empresas.

## Mantenimiento

- Estado: `sudo systemctl status algyre`.
- Reiniciar: `sudo systemctl restart algyre`.
- Errores: `sudo journalctl -u algyre --since today` y `/var/log/apache2/algyre-error.log`.
- Comprobación de HTTPS y servicio cada cinco minutos: `algyre-health.timer`. Los fallos quedan en `journalctl -u algyre-health`; no se envían avisos externos sin configurar un canal de notificación.
- Copia diaria de todos los datos: `algyre-backup.timer`, guardada en `/var/backups/algyre`, con retención de 14 días. Durante la copia ALgyre se detiene unos segundos.
- Copia manual: `sudo bash /opt/algyre/deploy/backup.sh`.
- Los certificados de IP duran aproximadamente seis días. `algyre-cert-renew.timer` comprueba cada hora su renovación, sin alterar el Certbot de las otras webs.
- Comprobar renovación: `sudo /opt/algyre-certbot/bin/certbot renew --dry-run --config-dir /etc/algyre-acme --work-dir /var/lib/algyre-acme --logs-dir /var/log/algyre-acme`.
- Recuperar el administrador desde el servidor: carga `/etc/algyre.env` como en los comandos anteriores y ejecuta `manage.py reset-admin`.
- Las copias en el mismo disco protegen de errores de uso; conviene mantener también una copia externa bajo tu control. El sistema no transmite copias a servicios externos.
- Si cambia la IP pública, habrá que actualizar `ALGYRE_PUBLIC_URL`, Apache y el certificado antes de compartir la dirección nueva.

## Actualizar una instalación existente

1. Descarga la nueva versión en una carpeta distinta de `/opt/algyre`.
2. Programa una pausa de uso y confirma que dispones de una copia recuperable.
3. Ejecuta desde la nueva carpeta `sudo bash deploy/install-debian.sh IP_PUBLICA`.
4. Comprueba `sudo systemctl status algyre`, entra con una cuenta de prueba y revisa un informe.

El instalador guarda una copia general de los datos y del código anterior, detiene ALgyre y copia la versión nueva. La migración amplía categorías sin cambiar los registros existentes; conserva además una copia por base afectada. El servicio arranca cuando termina. Si el proceso falla, revisa el error antes de reabrir el acceso: no se debe ejecutar código viejo con datos que ya usan categorías nuevas.

No necesitas volver a emitir el certificado para una actualización ordinaria. `publish-ip.sh` es para preparar HTTPS o cambiar la IP, no para cada cambio de código.

## Recuperar una copia general

La recuperación completa corresponde al administrador del servidor. Conserva juntos el archivo de código anterior y la copia de datos de la misma fecha. Detén `algyre.service`, aparta el directorio actual de datos para poder deshacer la recuperación y restaura el contenido de la copia bajo `/var/lib/algyre`, con propietario `algyre:algyre` y acceso privado. Restaura también el código compatible si vuelves a una versión anterior y conserva `/etc/algyre.env`, necesario para el servicio. Arranca ALgyre y comprueba cuentas e informes antes de permitir nuevas entradas.

Para recuperar solamente los datos de una empresa, utiliza su copia ZIP desde Configuración dentro del espacio correcto. Esa copia no cambia cuentas ni contraseñas.

## Qué entrega el paquete

`python deploy/package.py` genera `work/algyre-publica.tar.gz` con código, módulos, recursos, pruebas y guías. No contiene cuentas, datos empresariales ni secretos. Descomprímelo en una carpeta de preparación y sigue los pasos de instalación.

# Documentation / Documentación

[Project home](../README.md) · [Portada en castellano](../README.es.md)

## For your company / Para tu empresa

| Guide | Language | Purpose |
| --- | --- | --- |
| [Install](guides/install.md) | English | Local setup, updates and troubleshooting |
| [Instalar](guides/install.es.md) | Castellano | Instalación local, actualizaciones y problemas habituales |
| [Uso diario](guides/usage.es.md) | Castellano | Primer inventario, actividades, factores e informes |
| [Metodología](guides/methodology.es.md) | Castellano | Categorías, unidades y límites ambientales |
| [Gallery / Galería](gallery.md) | Both | Real screens with fictional data |

## For maintainers / Para mantenimiento

- [Code structure and tests](technical/development.es.md)
- [Verification results](technical/verification.es.md)
- [Publication review](technical/review.es.md)
- [Optional deployment on your own Debian server](../deploy/LEEME.md)

## Repository map

```text
ALgyre/
├── README.md / README.es.md    Short project introductions
├── Abrir ALgyre.cmd            Open on Windows
├── Cerrar ALgyre.cmd           Close on Windows
├── app.py                     Application entry point and HTTP routes
├── manage.py                  Optional server administration
├── algyre_core/               Accounting, accounts, imports and database schema
├── static/                    Application interface and visual assets
├── scripts/                   Windows launcher implementation
├── docs/
│   ├── guides/                Installation, use and methodology
│   ├── technical/             Development and verification
│   └── images/                Screenshots using fictional data
├── deploy/                    Packaging and optional server installation
└── tests/                     Isolated tests using fictional data
```

`data/` and `work/` are created locally and excluded from Git. The application entry point, default local URL and storage location are unchanged by this organisation.

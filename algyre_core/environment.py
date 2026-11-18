"""Activity taxonomy and unit rules shared by calculation, import and UI.

No production emission factors are bundled. Each organisation supplies and
reviews factors appropriate to its reporting boundary and activity.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Activity:
    label: str
    scope: int
    units: tuple[str, ...]
    guidance: str
    scope3_category: int | None = None
    continuous: bool = False
    explicit_factor: bool = True


ACTIVITIES = {
    "electricity": Activity(
        "Electricidad",
        2,
        ("kWh", "MWh"),
        "Electricidad comprada y consumida. Factor territorial de generación; no ciclo de vida.",
        continuous=True,
        explicit_factor=False,
    ),
    "gas": Activity(
        "Gas natural",
        1,
        ("kWh", "MWh", "L", "kg", "m3"),
        "Combustión en fuentes propias o controladas; excluye emisiones previas del combustible.",
        continuous=True,
        explicit_factor=False,
    ),
    "diesel": Activity(
        "Diésel",
        1,
        ("kWh", "MWh", "L", "kg", "m3"),
        "Combustión en instalaciones o vehículos propios o controlados. Documenta el uso.",
        continuous=True,
        explicit_factor=False,
    ),
    "petrol": Activity(
        "Gasolina",
        1,
        ("kWh", "MWh", "L", "kg", "m3"),
        "Combustión en fuentes propias o controladas; no incluir viajes de terceros.",
        continuous=True,
        explicit_factor=False,
    ),
    "refrigerant": Activity(
        "Fugas de refrigerantes",
        1,
        ("kg",),
        "Registra kg de gas emitido, no la carga total del equipo. Identifica el gas y la edición del potencial de calentamiento global a 100 años en el factor y las notas.",
    ),
    "heat": Activity(
        "Calor y vapor comprados",
        2,
        ("kWh", "MWh"),
        "Energía térmica comprada y consumida; factor de generación de calor o vapor. Identifica la red o proveedor.",
        continuous=True,
    ),
    "cooling": Activity(
        "Frío comprado",
        2,
        ("kWh", "MWh"),
        "Energía de refrigeración comprada; no electricidad de un equipo propio ni fugas de refrigerante.",
        continuous=True,
    ),
    "purchased_goods": Activity(
        "Bienes y servicios comprados",
        3,
        ("kg", "t", "unit"),
        "Categoría 1. Identifica producto o servicio y factor de cuna a puerta por unidad física. No incluye bienes de capital ni cálculo por gasto.",
        1,
    ),
    "upstream_transport": Activity(
        "Transporte contratado de mercancías",
        3,
        ("tkm",),
        "Categoría 4. Transporte de terceros contratado por la empresa: toneladas transportadas × kilómetros. Identifica vehículo, ruta y límites del factor.",
        4,
    ),
    "waste": Activity(
        "Residuos tratados por terceros",
        3,
        ("kg", "t"),
        "Categoría 5. Identifica residuo y tratamiento externo. No restes emisiones evitadas ni créditos de reciclaje.",
        5,
    ),
    "business_travel": Activity(
        "Viajes de trabajo",
        3,
        ("pkm", "km", "night"),
        "Categoría 6. Transporte de terceros u hotel. Identifica modo, ocupación y si km son de vehículo o pasajero. No dupliques combustibles de vehículos propios.",
        6,
    ),
    "commuting": Activity(
        "Desplazamiento al trabajo",
        3,
        ("pkm", "km"),
        "Categoría 7. Trayectos domicilio-trabajo en transporte no controlado por la empresa. Documenta modo, ocupación y base de la distancia.",
        7,
    ),
    "water": Activity(
        "Agua suministrada",
        3,
        ("m3",),
        "Categoría 1. Emisiones del suministro de agua. Los m³ son actividad, no huella hídrica. No dupliques agua ya incluida en compras.",
        1,
    ),
}
CAT = {key: value.label for key, value in ACTIVITIES.items()}
UNIT_LABELS = {
    "kWh": "kWh",
    "MWh": "MWh",
    "L": "Litros",
    "kg": "kg",
    "m3": "m³",
    "t": "Toneladas",
    "unit": "Unidades",
    "tkm": "Tonelada·km",
    "pkm": "Pasajero·km",
    "km": "km",
    "night": "Noches",
}


def valid_unit(category, unit, *, factor=False):
    activity = ACTIVITIES.get(category)
    return bool(
        activity and unit in activity.units and (not factor or unit not in ("MWh", "t"))
    )


def normalize_quantity(quantity, unit):
    """Only exact physical conversions; never infer occupancy or fuel energy."""
    if unit == "MWh":
        return Decimal(quantity) * 1000, "kWh"
    if unit == "t":
        return Decimal(quantity) * 1000, "kg"
    return Decimal(quantity), unit


def catalog():
    return {key: asdict(value) for key, value in ACTIVITIES.items()}

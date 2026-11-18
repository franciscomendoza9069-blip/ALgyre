# Metodología ambiental

**Cantidad normalizada × factor documentado = kg CO₂e.** El total suma fuentes registradas y calculadas; no declara cobertura completa.

La clasificación distingue fuentes propias/controladas (alcance 1), generación de energía comprada (alcance 2) y actividades indirectas (alcance 3), tomando como referencia el [GHG Protocol](https://ghgprotocol.org/scope-3-calculation-guidance-2). No implica certificación ni conformidad automática.

| Código | Alcance / categoría indirecta | Unidades | Revisión |
| --- | --- | --- | --- |
| `electricity` | 2 | kWh, MWh | Generación eléctrica territorial |
| `gas` | 1 | kWh, MWh, L, kg, m3 | Combustión propia/controlada |
| `diesel` | 1 | kWh, MWh, L, kg, m3 | Combustión de instalación o vehículo propio/controlado |
| `petrol` | 1 | kWh, MWh, L, kg, m3 | Combustión directa, sin emisiones previas |
| `refrigerant` | 1 | kg | Masa emitida, gas concreto y potencial de calentamiento global a 100 años con edición |
| `heat` | 2 | kWh, MWh | Generación de calor/vapor comprado |
| `cooling` | 2 | kWh, MWh | Frío comprado, no electricidad propia |
| `purchased_goods` | 3 / 1 | kg, t, unit | Producto/servicio concreto, cuna a puerta |
| `water` | 3 / 1 | m3 | Suministro, no huella hídrica ni depuración |
| `upstream_transport` | 3 / 4 | tkm | Transporte de terceros contratado |
| `waste` | 3 / 5 | kg, t | Residuo y tratamiento externo |
| `business_travel` | 3 / 6 | pkm, km, night | Modo, base de distancia u hotel |
| `commuting` | 3 / 7 | pkm, km | Domicilio-trabajo y ocupación |

`unit`: unidad física de producto/servicio; `night`: noche según la base del factor; `pkm`: pasajero·km; `tkm`: tonelada·km. Diez toneladas transportadas cien kilómetros son 1.000 tkm. ALgyre no deduce distancias ni ocupación.

## Factores

Categoría, país, año y unidad normalizada deben coincidir. Electricidad usa método territorial. Los cuatro tipos iniciales de energía/combustible admiten selección automática de un único factor compatible. Si hay varias versiones, debes elegir.

Refrigerantes, calor, frío y actividades indirectas exigen selección explícita y notas, aunque exista un único factor. La adecuación a cada gas, producto, viaje o residuo sigue siendo responsabilidad de quien lo revisa.

No se incluyen factores reales precargados. Registra fuente, versión, licencia, unidad y ámbito. Documenta la aplicabilidad de fuentes internacionales al país. No cambies artificialmente país o año para forzar coincidencias.

## Conversiones y calidad

- 1 MWh = 1.000 kWh; 1 t = 1.000 kg. Registra los factores por kWh o kg.
- No se convierte gas en m3 a energía, ni km a pasajero·km o tonelada·km.
- Sin factor, el registro queda pendiente; no se considera emisión cero.
- Las estimaciones necesitan explicación. Divide periodos entre años y documenta el reparto.
- Los totales mensuales se distribuyen por días; pueden diferir de lecturas mensuales reales.
- La cobertura temporal comprueba suministros continuos. Contrasta actividades puntuales con registros de origen.

## Duplicidades y límites

Las actividades puntuales pueden compartir fecha si son registros distintos. Usa referencias propias de factura, viaje o albarán. Las referencias repetidas y los registros idénticos sin referencias distintas se marcan para revisión. Los suministros continuos mantienen el control de periodos solapados.


No registres combustible propio y el mismo trayecto como viaje externo. No sumes agua o transporte ya incluidos en otro factor. No atribuyas un factor de ciclo de vida entero a combustión directa. No restes créditos de reciclaje, emisiones evitadas ni compensaciones al inventario bruto.

Declara el perímetro de control y clasifica las actividades: el programa no lo deduce automáticamente.

No cubre las 15 categorías indirectas, procesos industriales, separación de carbono biogénico, electricidad contractual, ciclo de vida de producto, biodiversidad ni huella hídrica. No calcula automáticamente incertidumbre, materialidad o calidad del factor. No genera certificaciones ni reportes regulatorios completos.

Identifica fuentes ausentes y documenta su importancia. Consulta el [detalle de categorías y límites](https://ghgprotocol.org/sites/default/files/ghgp/standards/Scope3_Calculation_Guidance_0.pdf) antes de utilizar resultados externamente.

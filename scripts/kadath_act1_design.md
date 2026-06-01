# Acto 1 Rework — Diseño Narrativo

## Concepto
Edyssey es un soñador atrapado en el Umbral. Lleva "eones" aquí, incapaz de cruzar.
Cree que es el mejor explorador de las Dreamlands pero nadie lo reconoce.
Obsesionado con "documentar" todo (su "contenido"). El Payaso lo persigue como sombra.

## Personajes
- **Edyssey**: Guía → Traidor. Muletillas: "es que", "osea", "la gente", "xd", "no sé", "qué quieres que diga", "vaya". Pasivo-agresivo, victimista, egocéntrico.
- **El Payaso del Umbral**: Entidad que acecha. Siempre busca a Edyssey. Silencioso al principio, luego ríe. Emoji 🤡 como marca.
- **Nasht y Kaman-Thah**: Guardianes de la Puerta de Bronce (se mantienen del acto original).

## Estructura (57 nodos)

### Sección A — El Descenso (nodos 1-15)
El jugador desciende, encuentra señales de alguien más, y conoce a Edyssey.

1. `act1_descenso_inicio` — Despertar en la escalera (mantiene conexión con prólogo)
2. `act1_descenso_ecos` — Ecos de alguien hablando solo
3. `act1_descenso_marcas` — Marcas en las paredes (Edyssey estuvo aquí)
4. `act1_descenso_glifos` — Muro de glifos (adaptado del original)
5. `act1_descenso_glifos_leidos` — Leer los glifos
6. `act1_descenso_mirada_atras` — Mirar atrás (figura larga = el payaso?)
7. `act1_descenso_caida` — Caída libre lateral
8. `act1_descenso_vision` — Visión de Kadath
9. `act1_encuentro_voz` — Escuchas una voz quejándose
10. `act1_encuentro_edyssey` — Primer encuentro con Edyssey
11. `act1_edyssey_desconfia` — Edyssey desconfía del jugador
12. `act1_edyssey_acepta` — Edyssey acepta guiarte (a regañadientes)
13. `act1_edyssey_historia` — Edyssey cuenta su historia
14. `act1_edyssey_campamento` — El campamento de Edyssey
15. `act1_edyssey_mapa` — Edyssey muestra su "mapa" del Umbral

### Sección B — El Guía (nodos 16-30)
Edyssey guía al jugador. El payaso aparece en sombras. Tensión creciente.

16. `act1_guia_sendero` — Edyssey te lleva por un sendero lateral
17. `act1_guia_advertencia` — "No mires las sombras, osea en serio"
18. `act1_guia_gato` — El gato de Ulthar aparece
19. `act1_guia_gato_sigue` — Seguir al gato (ruta alternativa)
20. `act1_guia_ulthar_consejo` — Consejo de gatos (adaptado)
21. `act1_guia_ulthar_respuesta` — Respuesta al acertijo
22. `act1_payaso_primera_senal` — Primera señal del payaso (emoji en la pared)
23. `act1_edyssey_nervioso` — Edyssey se pone nervioso
24. `act1_guia_bifurcacion` — Bifurcación: izquierda (mar) o derecha (frío)
25. `act1_guia_escalera_media` — Estrato medio de la escalera
26. `act1_edyssey_queja` — Edyssey se queja de "la gente"
27. `act1_payaso_risa` — Se escucha una risa lejana
28. `act1_edyssey_panico` — Edyssey entra en pánico breve
29. `act1_guia_refugio` — Refugio temporal
30. `act1_edyssey_confesion` — Edyssey confiesa que lleva mucho tiempo aquí

### Sección C — La Tensión (nodos 31-45)
El payaso se acerca. Edyssey se vuelve más errático. Pistas de la traición.

31. `act1_tension_avance` — Seguir avanzando pese al miedo
32. `act1_tension_payaso_cerca` — El payaso está más cerca (sombra visible)
33. `act1_tension_edyssey_plan` — Edyssey menciona "un plan para salir"
34. `act1_tension_puerta_vista` — Se ve la Puerta de Bronce a lo lejos
35. `act1_tension_edyssey_desesperado` — Edyssey se desespera
36. `act1_tension_payaso_cara` — El payaso muestra su cara por primera vez
37. `act1_tension_huida` — Huir del payaso
38. `act1_tension_edyssey_propuesta` — Edyssey propone "un trato"
39. `act1_tension_pista_traicion` — Pistas de que Edyssey miente
40. `act1_tension_gato_aviso` — El gato intenta avisar
41. `act1_tension_puerta_cerca` — La puerta está cerca
42. `act1_tension_edyssey_ritual` — Edyssey prepara algo
43. `act1_tension_payaso_acorrala` — El payaso los acorrala
44. `act1_tension_decision` — Momento de decisión crucial
45. `act1_tension_confrontar_edyssey` — Confrontar a Edyssey

### Sección D — El Desenlace (nodos 46-57)
Tres caminos: payaso devora a Edyssey / Edyssey traiciona / escape limpio.

46. `act1_final_payaso_ataca` — El payaso ataca
47. `act1_final_payaso_devora` — El payaso devora a Edyssey (33% endings)
48. `act1_final_edyssey_grita` — Edyssey grita sus frases mientras es devorado
49. `act1_final_trauma` — El jugador queda traumatizado (flag permanente)
50. `act1_final_traicion_ritual` — Edyssey ejecuta su traición
51. `act1_final_traicion_lucha` — Luchar contra Edyssey
52. `act1_final_traicion_matar` — Matar a Edyssey
53. `act1_final_escape_juntos` — Escapar juntos (ruta difícil)
54. `act1_final_puerta_bronce` — Llegar a la Puerta de Bronce
55. `act1_final_puerta_hueso` — Puerta de Hueso alternativa
56. `act1_final_cruce_yermos` — Cruzar hacia Dylath-Leen (→ act2_hub_yermos)
57. `act1_final_cruce_bosque` — Cruzar al bosque (→ act2_bosque_zoog_entrada)

## Salidas al Acto 2 (se mantienen las 3 originales)
- `act2_hub_yermos` — Via Puerta de Bronce (con o sin Edyssey muerto)
- `act2_bosque_zoog_entrada` — Via Puerta de Hueso

## Flags que se setean
- `edyssey_muerto` — Si el payaso lo devora o lo matamos
- `edyssey_devorado_por_payaso` — Específico: el payaso lo mató
- `edyssey_traiciono` — Si intentó traicionarnos
- `vio_al_payaso` — Flag permanente de haber visto al payaso
- `trauma_edyssey` — Memoria del trauma (afecta sanidad futura)
- `edyssey_aliado` — Si escapamos juntos (ruta difícil)
- `payaso_suelto` — El payaso sigue ahí para actos futuros

## Stats del sistema (voluntad/lucidez/memoria/corrupcion/lore/favor)
- Edyssey da +lore pero -lucidez (te confunde con sus quejas)
- El payaso da -voluntad y -lucidez
- Confrontar a Edyssey da +voluntad
- La traición da +corrupcion
- Escapar juntos da +favor y +memoria

"""
Detector de Género y Pronombres para Destilación de Personalidades.

Analiza el historial de mensajes para inferir los pronombres preferidos del usuario.
Usa múltiples señales: auto-referencias, análisis lingüístico, y contexto social.
"""

from typing import Optional
import re


# Patrones de auto-referencia en español
PATRONES_PRONOMBRES = {
    "él": [
        r'\byo\b', r'\bme\b', r'\bmi\b', r'\bconmigo\b',  # Pronombres subjects
        r'\bmi\b', r'\bmis\b',  # Possessives
    ],
    "ella": [
        r'\byo\b', r'\bme\b', r'\bmi\b', r'\bconmigo\b',
        r'\bmi\b', r'\bmis\b',
    ],
    "elle": [
        r'\byo\b', r'\bme\b', r'\bmi\b', r'\bconmigo\b',
        r'\bmi\b', r'\bmis\b',
    ],
}

# Palabras que indican género gramatical (contexto)
INDICADORES_MASCULINOS = [
    "chico", "chavo", "wey", "compadre", "carnal", "hermano",
    "tío", "unai", "maño", "pibe", "rapaz", "maje", "parce",
]

INDICADORES_FEMENINOS = [
    "chica", "china", "comadre", "hermana", "tía", "nya",
    "piba", "rapaza", "maja", "parsia",
]

# Patrones de escritura que correlacionan con género
PATRONES_ESCULTURA_GENERO = {
    "masculino": [
        r'\b JAJAJA+\b', r'\b jajaja+\b',  # Risa más extendida
        r'\bwey\b', r'\bmano\b', r'\bva?\b',
        r'\bgg\b', r'\blol\b', r'\blmao\b',
    ],
    "femenino": [
        r'\bbesos?\b', r'\b<3\b', r':3\b', r'\buwu\b',
        r'\bholii\b', r'\b甚\b',  # Japanese-influenced
    ],
}


def detectar_pronombres_desde_mensajes(mensajes: list) -> dict:
    """
    Analiza una lista de mensajes y determina pronombres y señales de género.
    
    Returns:
        dict con:
            - pronombres: str como "él/ella/elle/they"
            - genero_inferido: "masculino" | "femenino" | "neutro" | "unknown"
            - confianza: 0.0 - 1.0
            - señales: list de las señales encontradas
    """
    if not mensajes:
        return {
            "pronombres": "él/ella",
            "genero_inferido": "unknown",
            "confianza": 0.0,
            "señales": []
        }
    
    # Concatenar todos los mensajes para análisis
    texto_total = " ".join(m.get("content", "").lower() for m in mensajes)
    
    señales = []
    cuenta_masculino = 0
    cuenta_femenino = 0
    
    # 1. Detectar auto-referencias (uso de "yo")
    yo_count = len(re.findall(r'\byo\b', texto_total))
    if yo_count > 0:
        señales.append(f"Auto-referencia 'yo' ({yo_count}x)")
    
    # 2. Detectar indicativos de género en contexto
    for palabra in INDICADORES_MASCULINOS:
        if re.search(rf'\b{palabra}\b', texto_total):
            cuenta_masculino += 1
            señales.append(f"Indicador masculino: '{palabra}'")
    
    for palabra in INDICADORES_FEMENINOS:
        if re.search(rf'\b{palabra}\b', texto_total):
            cuenta_femenino += 1
            señales.append(f"Indicador femenino: '{palabra}'")
    
    # 3. Detectar patrones de escritura por género
    for patron in PATRONES_ESCULTURA_GENERO["masculino"]:
        if re.search(patron, texto_total):
            cuenta_masculino += 0.5
            señales.append(f"Patrón escritura masculino: {patron}")
    
    for patron in PATRONES_ESCULTURA_GENERO["femenino"]:
        if re.search(patron, texto_total):
            cuenta_femenino += 0.5
            señales.append(f"Patrón escritura femenino: {patron}")
    
    # 4. Analizar uso de emoji (proxy de expresión emocional)
    emoji_femeninos = len(re.findall(r'[😘💕🥺😢😭😡🥰😍😎]', texto_total))
    emoji_generales = len(re.findall(r'[😀😃😄😁😆😅😂🤣😊🙂😉😌😍🤔👍❤️🧡💛💚💙💜]', texto_total))
    
    if emoji_generales > 0:
        proporcion_femenina = emoji_femeninos / emoji_generales
        if proporcion_femenina > 0.3:
            cuenta_femenino += 1
            señales.append(f"Alta proporción emoji 'femeninos' ({proporcion_femenina:.1%})")
    
    # 5. Detectar uso de "elles" o lenguaje inclusivo
    if re.search(r'\belles\b', texto_total) or re.search(r'\be\b\b(?!x\b)', texto_total):
        señales.append("Lenguaje inclusivo detectado")
        return {
            "pronombres": "elle",
            "genero_inferido": "neutro",
            "confianza": 0.8,
            "señales": señales + ["Usa lenguaje inclusivo"]
        }
    
    # 6. Determinar género basado en señales
    diferencia = cuenta_masculino - cuenta_femenino
    
    if abs(diferencia) < 0.5:
        genero = "neutro"
        pronombres = "él/ella"
        confianza = 0.3
    elif diferencia > 0:
        genero = "masculino"
        pronombres = "él"
        confianza = min(0.7, 0.4 + diferencia * 0.1)
    else:
        genero = "femenino"
        pronombres = "ella"
        confianza = min(0.7, 0.4 + abs(diferencia) * 0.1)
    
    return {
        "pronombres": pronombres,
        "genero_inferido": genero,
        "confianza": confianza,
        "señales": señales
    }


def generar_pronombres_contexto(user_name: str, guild_name: str = None, mensajes: list = None) -> str:
    """
    Genera una estimación de pronombres considerando el contexto del servidor.
    
    Args:
        user_name: Nombre de display del usuario
        guild_name: Nombre del servidor (puede dar pistas)
        mensajes: Lista de mensajes para análisis
        
    Returns:
        String de pronombres como "él/ella/elle"
    """
    # Si hay mensajes, usar análisis
    if mensajes:
        resultado = detectar_pronombres_desde_mensajes(mensajes)
        if resultado["confianza"] >= 0.5:
            return resultado["pronombres"]
    
    # Si no, usar heurísticas del nombre
    # (Esto es menos preciso pero da algo cuando no hay historial)
    
    # Nombres que son obviously gendered
    nombres_masculinos = [
        "ar", "as", "os", "er", "ir",  # Endings comunes
    ]
    nombres_femeninos = [
        "a", "e", "i",  # Endings comunes
    ]
    
    # No hacer suposiciones basadas solo en el nombre - es muy poco confiable
    # Mejor devolver el default
    return "él/ella"


def integrar_detector_en_perfil(perfil: dict, mensajes: list) -> dict:
    """
    Actualiza un perfil con los pronombres detectados.
    Se llama después de destilar el perfil base.
    
    Args:
        perfil: El perfil ya destilado (puede tener pronombres o no)
        mensajes: Lista de mensajes para análisis
        
    Returns:
        Perfil actualizado con campo pronombres optimizado
    """
    # Si ya tiene pronombres específicos (no el default), no cambiar
    if perfil.get("pronombres") not in ("él/ella", None, ""):
        # Verificar que no sea el default
        if perfil.get("pronombres") not in ("él/ella",):
            return perfil
    
    # Detectar desde mensajes
    resultado = detectar_pronombres_desde_mensajes(mensajes)
    
    # Solo actualizar si tenemos confianza razonable
    if resultado["confianza"] >= 0.4:
        perfil["pronombres"] = resultado["pronombres"]
        perfil["_genero_detectado"] = {
            "valor": resultado["genero_inferido"],
            "confianza": resultado["confianza"],
            "señales": resultado["señales"][:5]  # Máximo 5 señales para guardar
        }
    else:
        # Mantener default pero guardar el análisis
        perfil["_genero_detectado"] = {
            "valor": resultado["genero_inferido"],
            "confianza": resultado["confianza"],
            "señales": resultado["señales"][:3]
        }
    
    return perfil


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test con mensajes de ejemplo
    mensajes_test_masc = [
        {"content": "wey qué onda", "role": "user"},
        {"content": "órale va", "role": "user"},
        {"content": "jajajaJAJAJAJA está buenardo", "role": "user"},
        {"content": "ni modo wey", "role": "user"},
    ]
    
    mensajes_test_fem = [
        {"content": "holii~ qué tal?", "role": "user"},
        {"content": "besitos 💕", "role": "user"},
        {"content": "estoy algo triste...", "role": "user"},
        {"content": "uwu gracias!!", "role": "user"},
    ]
    
    print("=== Test Masculino ===")
    resultado = detectar_pronombres_desde_mensajes(mensajes_test_masc)
    print(f"Pronombres: {resultado['pronombres']}")
    print(f"Género: {resultado['genero_inferido']}")
    print(f"Confianza: {resultado['confianza']}")
    print(f"Señales: {resultado['señales']}")
    
    print("\\n=== Test Femenino ===")
    resultado = detectar_pronombres_desde_mensajes(mensajes_test_fem)
    print(f"Pronombres: {resultado['pronombres']}")
    print(f"Género: {resultado['genero_inferido']}")
    print(f"Confianza: {resultado['confianza']}")
    print(f"Señales: {resultado['señales']}")
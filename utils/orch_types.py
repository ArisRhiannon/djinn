"""
Tipos internos del Orchestrator — abstracción sobre google.genai.types.

Si se cambia de provider, solo se modifica este archivo.
"""
from google.genai import types

# Re-exports usados por el orchestrator
Content = types.Content
Part = types.Part
Tool = types.Tool

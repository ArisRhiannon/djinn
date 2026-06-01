"""Tests del guard de tools terminales (bug 'continue' del 2026-05-16).

Bug histórico: Claude Sonnet 4.6 vía proxy llamó send_message 6 veces
seguidas a un "hola" de Law, alucinando 4 mensajes "continue" del usuario.
El loop agentic no tenía noción de "tool terminal" — simplemente seguía
mientras hubiera tool_calls.

Fix: TERMINAL_TOOLS = {send_message, send_embed, send_dm}. Si el modelo
llama una y luego intenta otra, el loop aborta retornando "" (vacío).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: la constante existe y contiene las tools esperadas
# ─────────────────────────────────────────────────────────────────────────────


def test_terminal_tools_set_exists_and_complete():
    from utils.llm_client import TERMINAL_TOOLS

    assert isinstance(TERMINAL_TOOLS, frozenset)
    assert "send_message" in TERMINAL_TOOLS
    assert "send_embed" in TERMINAL_TOOLS
    assert "send_dm" in TERMINAL_TOOLS
    # No debe contener tools que NO sean de output final
    assert "list_morosos" not in TERMINAL_TOOLS
    assert "get_treasury_balance" not in TERMINAL_TOOLS


def test_terminal_tools_is_immutable():
    """frozenset garantiza que nadie lo muta accidentalmente."""
    from utils.llm_client import TERMINAL_TOOLS

    with pytest.raises((AttributeError, TypeError)):
        TERMINAL_TOOLS.add("ban_user")  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: simulación del bug — modelo emite send_message dos veces seguidas
# ─────────────────────────────────────────────────────────────────────────────


def _make_tool_call_response(call_name: str, args: str = '{"text":"x"}') -> MagicMock:
    """Mock de response de OpenAI con un solo tool_call."""
    tc = MagicMock()
    tc.id = f"call_{call_name}_1"
    tc.function = MagicMock()
    tc.function.name = call_name
    tc.function.arguments = args

    msg = MagicMock()
    msg.tool_calls = [tc]
    msg.content = None

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"

    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)
    return response


def _make_text_response(text: str) -> MagicMock:
    """Mock de response de OpenAI con solo texto (sin tool_calls)."""
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = text

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"

    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=10)
    return response


@pytest.mark.asyncio
async def test_customllm_aborts_on_second_terminal_tool():
    """
    Reproducción del bug: el modelo emite send_message 3 veces seguidas.
    El guard debe abortar el loop tras la segunda y retornar "".
    """
    from utils.llm_client import CustomLLM

    # Mock config mínimo
    config = MagicMock()
    config.custom_api_key = "test"
    config.custom_base_url = "http://test"
    config.custom_model_name = "claude-test"
    config.llm_provider = "kiro"
    config.owner_user_id = 0

    llm = CustomLLM.__new__(CustomLLM)
    llm.config = config

    # Mock del cliente OpenAI: cada call retorna un send_message
    llm._client = MagicMock()
    llm._client.chat = MagicMock()
    llm._client.chat.completions = MagicMock()
    llm._client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_tool_call_response("send_message"),  # round 1
            _make_tool_call_response("send_message"),  # round 2 → guard debe disparar
            _make_text_response("nunca debería llegar"),  # round 3
        ]
    )

    # _sampling_for retorna config dummy
    llm._sampling_for = MagicMock(return_value=({"temperature": 0.7}, None))

    # Executor mock que dice "ok"
    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"success": True, "message_id": "1"})

    # Tool list mínimo
    tools = MagicMock()
    tools.function_declarations = []

    # Patch métodos estáticos auxiliares
    from utils.llm_client import OpenRouterLLM
    OpenRouterLLM._convert_fairy_tool_to_openai = MagicMock(
        return_value=[{"function": {"name": "send_message"}}]
    )
    OpenRouterLLM._genai_to_openai = MagicMock(return_value=[])
    OpenRouterLLM._make_google_fc = MagicMock(return_value=MagicMock(name="send_message"))

    result = await llm.generate_with_tools(
        system_prompt="test",
        contents=[],
        tools=tools,
        executor=executor,
        max_rounds=5,
    )

    # El guard debe haber abortado en round 2 → retorno vacío
    assert result == ""
    # Solo 2 calls al modelo: round 1 (que disparó el guard al verificar round 2)
    # En realidad: round 1 ejecutó 1 send_message, round 2 detectó terminal repetido
    # y retornó sin ejecutar más. Por eso solo se llamó al cliente 2 veces.
    assert llm._client.chat.completions.create.await_count == 2
    # El executor SOLO ejecutó la primera tool (la segunda fue abortada)
    assert executor.execute.await_count == 1


@pytest.mark.asyncio
async def test_customllm_allows_normal_flow_with_one_terminal():
    """
    Flujo normal: round 1 = get_data, round 2 = send_embed, round 3 = texto final.
    El guard NO debe disparar — solo hay UN terminal tool.
    """
    from utils.llm_client import CustomLLM, OpenRouterLLM

    config = MagicMock()
    config.custom_api_key = "test"
    config.custom_base_url = "http://test"
    config.custom_model_name = "claude-test"
    config.llm_provider = "kiro"
    config.owner_user_id = 0

    llm = CustomLLM.__new__(CustomLLM)
    llm.config = config
    llm._client = MagicMock()
    llm._client.chat = MagicMock()
    llm._client.chat.completions = MagicMock()
    llm._client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_tool_call_response("get_treasury_balance"),  # round 1: data
            _make_tool_call_response("send_embed"),            # round 2: terminal
            _make_text_response("Banco sano. Comentario."),    # round 3: texto final
        ]
    )
    llm._sampling_for = MagicMock(return_value=({"temperature": 0.7}, None))

    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"success": True})

    tools = MagicMock()
    tools.function_declarations = []

    OpenRouterLLM._convert_fairy_tool_to_openai = MagicMock(return_value=[{"function": {"name": "x"}}])
    OpenRouterLLM._genai_to_openai = MagicMock(return_value=[])
    OpenRouterLLM._make_google_fc = MagicMock(return_value=MagicMock())

    result = await llm.generate_with_tools(
        system_prompt="test",
        contents=[],
        tools=tools,
        executor=executor,
        max_rounds=5,
    )

    # El flujo completó normalmente: round 1 + round 2 + round 3 (texto final)
    assert result == "Banco sano. Comentario."
    assert llm._client.chat.completions.create.await_count == 3
    # Las 2 tools se ejecutaron (get_treasury + send_embed)
    assert executor.execute.await_count == 2

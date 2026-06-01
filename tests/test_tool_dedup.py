"""Tests del dedup de tool calls (caso real 2026-05-16 06:19:33).

Bug reportado: Claude Sonnet 4.6 llamó list_listeners 2 veces seguidas
con (probablemente) los mismos args, en rounds 1 y 2 del mismo turn.
La data era idéntica entre rounds. El loop NO lo detectaba porque
list_listeners no es una tool terminal.

Fix: dedup por (tool_name + args_normalizados) — la segunda llamada
recibe un payload short-circuit con _duplicate_call=True en lugar de
re-ejecutar.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _tc(call_id: str, name: str, args_dict: dict) -> MagicMock:
    """Mock de un tool_call OpenAI."""
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args_dict)
    return tc


def _resp_with_tools(*tcs) -> MagicMock:
    msg = MagicMock()
    msg.tool_calls = list(tcs)
    msg.content = None
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)
    return response


def _resp_text(text: str) -> MagicMock:
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
async def test_customllm_dedup_same_tool_same_args():
    """
    Caso real: list_listeners(search="Ciconia") llamado 2 veces.
    El segundo debe recibir _duplicate_call sin re-ejecutar la tool.
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
    llm._client.chat.completions.create = AsyncMock(side_effect=[
        # Round 1: list_listeners(search="Ciconia")
        _resp_with_tools(_tc("c1", "list_listeners", {"search": "Ciconia"})),
        # Round 2: MISMA call con los mismos args (debería caer en dedup)
        _resp_with_tools(_tc("c2", "list_listeners", {"search": "Ciconia"})),
        # Round 3: el modelo ya no llama tools, responde texto
        _resp_text("Reacción 😭 cuando alguien dice ciconia, etc."),
    ])
    llm._sampling_for = MagicMock(return_value=({"temperature": 0.7}, None))

    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"total": 1, "showing": 1, "rules": []})

    tools = MagicMock()
    tools.function_declarations = []
    OpenRouterLLM._convert_fairy_tool_to_openai = MagicMock(
        return_value=[{"function": {"name": "list_listeners"}}]
    )
    OpenRouterLLM._genai_to_openai = MagicMock(return_value=[])
    OpenRouterLLM._make_google_fc = MagicMock(return_value=MagicMock())

    result = await llm.generate_with_tools(
        system_prompt="test", contents=[],
        tools=tools, executor=executor, max_rounds=5,
    )

    # El executor solo debió ejecutarse UNA vez (la segunda fue dedup)
    assert executor.execute.await_count == 1, (
        f"Esperaba 1 ejecución, hubo {executor.execute.await_count}. "
        "El dedup no se disparó."
    )
    # Y el flujo terminó normalmente con el texto del round 3
    assert result == "Reacción 😭 cuando alguien dice ciconia, etc."


@pytest.mark.asyncio
async def test_customllm_dedup_different_args_not_blocked():
    """
    Caso legítimo: list_listeners con search distintos se ejecutan ambos.
    El dedup NO debe bloquear cuando los args difieren.
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
    llm._client.chat.completions.create = AsyncMock(side_effect=[
        _resp_with_tools(_tc("c1", "list_listeners", {"search": "aris"})),
        _resp_with_tools(_tc("c2", "list_listeners", {"search": "kuro"})),  # args distintos
        _resp_text("Encontré ambos."),
    ])
    llm._sampling_for = MagicMock(return_value=({"temperature": 0.7}, None))

    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"total": 0, "showing": 0, "rules": []})

    tools = MagicMock()
    tools.function_declarations = []
    OpenRouterLLM._convert_fairy_tool_to_openai = MagicMock(
        return_value=[{"function": {"name": "list_listeners"}}]
    )
    OpenRouterLLM._genai_to_openai = MagicMock(return_value=[])
    OpenRouterLLM._make_google_fc = MagicMock(return_value=MagicMock())

    result = await llm.generate_with_tools(
        system_prompt="test", contents=[],
        tools=tools, executor=executor, max_rounds=5,
    )

    # Las 2 calls eran distintas → ambas se ejecutaron
    assert executor.execute.await_count == 2
    assert result == "Encontré ambos."


@pytest.mark.asyncio
async def test_customllm_dedup_normalizes_arg_order():
    """
    Args con orden distinto pero valores iguales deben deduplicarse:
    {"a": 1, "b": 2} == {"b": 2, "a": 1}.
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
    # Primero {"a":1,"b":2}, después {"b":2,"a":1}: distinto JSON, mismos datos.
    tc1 = MagicMock(); tc1.id = "c1"; tc1.function = MagicMock()
    tc1.function.name = "list_listeners"; tc1.function.arguments = '{"a":1,"b":2}'
    tc2 = MagicMock(); tc2.id = "c2"; tc2.function = MagicMock()
    tc2.function.name = "list_listeners"; tc2.function.arguments = '{"b":2,"a":1}'

    msg1 = MagicMock(); msg1.tool_calls = [tc1]; msg1.content = None
    msg2 = MagicMock(); msg2.tool_calls = [tc2]; msg2.content = None
    msg3 = MagicMock(); msg3.tool_calls = None; msg3.content = "fin"

    def _r(m):
        c = MagicMock(); c.message = m; c.finish_reason = "tool_calls" if m.tool_calls else "stop"
        r = MagicMock(); r.choices = [c]; r.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        return r

    llm._client.chat.completions.create = AsyncMock(side_effect=[_r(msg1), _r(msg2), _r(msg3)])
    llm._sampling_for = MagicMock(return_value=({"temperature": 0.7}, None))

    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"ok": True})
    tools = MagicMock(); tools.function_declarations = []
    OpenRouterLLM._convert_fairy_tool_to_openai = MagicMock(return_value=[{"function": {"name": "list_listeners"}}])
    OpenRouterLLM._genai_to_openai = MagicMock(return_value=[])
    OpenRouterLLM._make_google_fc = MagicMock(return_value=MagicMock())

    await llm.generate_with_tools(
        system_prompt="test", contents=[],
        tools=tools, executor=executor, max_rounds=5,
    )

    # Solo 1 ejecución porque args normalizados son idénticos
    assert executor.execute.await_count == 1, (
        f"Dedup no normalizó orden: ejecuciones={executor.execute.await_count}"
    )

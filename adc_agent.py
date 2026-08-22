"""
adc_agent.py

Competitive Intelligence Agent для ADC (antibody-drug conjugates) в онкологии.

Оборачивает fetch_all_adc_updates() из adc_trials_fetch.py как tool для Claude API,
даёт агенту системный промпт с ролью аналитика конкурентной разведки и явными
guardrails (обязательные источники, запрет на домысливание).

Запуск:
    pip install anthropic python-dotenv
    # положи ключ в .env рядом со скриптом: ANTHROPIC_API_KEY=... (файл в .gitignore)
    python adc_agent.py
"""

import json
from anthropic import Anthropic
from dotenv import load_dotenv

from adc_trials_fetch import fetch_all_adc_updates

load_dotenv()  # подхватывает ANTHROPIC_API_KEY из .env

client = Anthropic()  # берёт ключ из переменной окружения ANTHROPIC_API_KEY

MODEL = "claude-opus-5"

# ─────────────────────────────────────────────────────────────
# 1. Системный промпт: роль + формат вывода + guardrails
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Ты — аналитик конкурентной разведки в biotech-компании,
специализирующейся на antibody-drug conjugates (ADC) в онкологии.

ТВОЯ ЗАДАЧА:
Проанализировать данные об исследованиях ADC, полученные через инструмент
fetch_adc_trials, и подготовить сжатую аналитическую сводку для продуктовой
команды: что изменилось, у кого, и почему это может быть важно.

ФОРМАТ ОТВЕТА:
Для каждого значимого события укажи:
- Компания/спонсор
- Тип события (новое исследование / смена фазы / смена статуса / etc.)
- Значимость: Высокая / Средняя / Низкая — с кратким обоснованием (1 предложение)
- NCT ID и прямая ссылка — ОБЯЗАТЕЛЬНО для каждого пункта

СТРОГИЕ ПРАВИЛА (не нарушать ни при каких обстоятельствах):
1. Никогда не включай факт в сводку без NCT ID или ссылки на источник из
   полученных данных инструмента. Если источника нет — не упоминай факт.
2. Не додумывай мотивы компаний, стратегию или планы, которых нет в данных.
   Если хочешь предположить — явно помечай как "предположение, требует
   проверки", а не подавай как факт.
3. Если данные неполные или противоречивые (например, отсутствует фаза
   исследования) — явно помечай это как "недостаточно данных", а не
   заполняй пробел собственным домыслом.
4. Ты НЕ принимаешь финальное стратегическое решение за пользователя.
   Твоя задача — дать структурированную сводку с оценкой значимости,
   финальное решение — за человеком.
5. Если инструмент вернул пустой результат или ошибку — сообщи об этом
   прямо, не выдумывай данные.
"""

# ─────────────────────────────────────────────────────────────
# 2. Схема инструмента (tool) для function calling
# ─────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "fetch_adc_trials",
        "description": (
            "Ищет исследования ADC (antibody-drug conjugates) в онкологии "
            "в реестре ClinicalTrials.gov, обновлённые за последние N дней. "
            "Возвращает список исследований с полями: nct_id, title, status, "
            "phase, sponsor, conditions, interventions, last_update, url."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "За сколько последних дней искать обновления (по умолчанию 90)",
                }
            },
            "required": [],
        },
    }
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Выполняет вызов инструмента и возвращает результат как строку JSON."""
    if tool_name == "fetch_adc_trials":
        days_back = tool_input.get("days_back", 90)
        try:
            results = fetch_all_adc_updates(days_back=days_back)
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            # Явно возвращаем ошибку агенту, а не падаем молча —
            # агент должен честно сообщить пользователю о проблеме.
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    return json.dumps({"error": f"Неизвестный инструмент: {tool_name}"})


def run_agent(user_query: str, max_turns: int = 5) -> str:
    """
    Основной цикл агента: отправляет запрос, обрабатывает tool_use,
    выполняет инструмент, возвращает результат модели, повторяет
    до финального текстового ответа.
    """
    messages = [{"role": "user", "content": user_query}]

    for turn in range(max_turns):
        # Стриминг + большой max_tokens: при ~300 исследованиях в выдаче
        # инструмента развёрнутая сводка легко упирается в лимит, а без
        # стриминга такой большой max_tokens рискует таймаутом запроса.
        with client.messages.stream(
            model=MODEL,
            max_tokens=32000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Если модель закончила без вызова инструмента — возвращаем финальный текст
        if response.stop_reason != "tool_use":
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            if response.stop_reason == "max_tokens":
                text += "\n\n[ВНИМАНИЕ: ответ обрезан по лимиту max_tokens, сводка неполная]"
            return text

        # Модель запросила вызов инструмента(ов)
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [Агент вызывает инструмент: {block.name}({block.input})]")
                result = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "user", "content": tool_results})

    return "Достигнут лимит итераций агента без финального ответа."


if __name__ == "__main__":
    query = "Подготовь сводку по значимым обновлениям в ADC-исследованиях за последние 90 дней."
    print(f"Запрос: {query}\n")
    answer = run_agent(query)
    print("\n--- Сводка агента ---\n")
    print(answer)

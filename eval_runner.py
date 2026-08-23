"""
eval_runner.py

Считает метрики качества агента на основе заполненного golden_set_template.csv.

Workflow:
1. Заполни golden_set_template.csv вручную (15-20 реальных событий по ADC).
2. Запусти adc_agent.py, получи сводку.
3. Вручную сверь: для каждой строки golden set — нашёл ли агент это событие
   (found_by_agent = yes/no) и как оценил значимость (agent_significance).
4. Запусти этот скрипт — посчитает метрики.

Отдельно: automated_hallucination_check() — полуавтоматическая проверка,
что каждый NCT ID, упомянутый агентом, реально существует в сырых данных
инструмента (а не придуман моделью).
"""

import csv
import re


def load_golden_set(path: str = "golden_set_template.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if row.get("event_id", "").strip().isdigit()]
    return rows


def compute_metrics(rows: list[dict]) -> dict:
    total = len(rows)
    filled = [r for r in rows if r.get("found_by_agent", "").strip()]

    if not filled:
        return {"error": "Нет заполненных строк — сначала сверь golden set с выводом агента."}

    found = sum(1 for r in filled if r["found_by_agent"].strip().lower() == "yes")
    recall = found / len(filled)

    # Точность классификации значимости считаем только для найденных агентом событий
    matched_significance = [
        r for r in filled
        if r["found_by_agent"].strip().lower() == "yes"
        and r.get("agent_significance", "").strip()
        and r.get("expected_significance", "").strip()
    ]
    correct_significance = sum(
        1 for r in matched_significance
        if r["agent_significance"].strip().lower() == r["expected_significance"].strip().lower()
    )
    significance_accuracy = (
        correct_significance / len(matched_significance) if matched_significance else None
    )

    return {
        "total_events_in_golden_set": total,
        "events_evaluated": len(filled),
        "recall": round(recall, 2),
        "found_count": found,
        "significance_accuracy": (
            round(significance_accuracy, 2) if significance_accuracy is not None else "н/д"
        ),
        "significance_evaluated_on": len(matched_significance),
    }


def check_hallucinated_nct_ids(agent_output_text: str, raw_tool_data: list[dict]) -> dict:
    """
    Полуавтоматическая проверка на галлюцинации: извлекает все NCT ID,
    упомянутые в тексте ответа агента, и сверяет с реальными NCT ID
    из сырых данных, которые вернул инструмент.

    Использование:
        raw_data = fetch_all_adc_updates(days_back=90)  # из adc_trials_fetch.py
        agent_text = "<скопируй сюда финальный вывод агента>"
        result = check_hallucinated_nct_ids(agent_text, raw_data)
    """
    real_nct_ids = {study["nct_id"] for study in raw_tool_data if study.get("nct_id")}
    mentioned_nct_ids = set(re.findall(r"NCT\d{8}", agent_output_text))

    hallucinated = mentioned_nct_ids - real_nct_ids

    return {
        "nct_ids_mentioned_by_agent": len(mentioned_nct_ids),
        "nct_ids_confirmed_real": len(mentioned_nct_ids & real_nct_ids),
        "hallucinated_nct_ids": list(hallucinated),
        "hallucination_rate": (
            round(len(hallucinated) / len(mentioned_nct_ids), 2)
            if mentioned_nct_ids else 0.0
        ),
    }


if __name__ == "__main__":
    rows = load_golden_set()
    metrics = compute_metrics(rows)
    print("=== Метрики качества агента ===\n")
    for key, value in metrics.items():
        print(f"{key}: {value}")

    print(
        "\nДля проверки на галлюцинации импортируй check_hallucinated_nct_ids() "
        "и передай сырые данные инструмента + текст ответа агента."
    )

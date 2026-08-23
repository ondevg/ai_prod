"""
check_hallucinations.py

Прогоняет check_hallucinated_nct_ids() из eval_runner.py на сохранённом
выводе adc_agent.py и свежих сырых данных fetch_all_adc_updates().

Запуск:
    python3 adc_agent.py > agent_output.txt   # сначала сохранить вывод агента
    python3 check_hallucinations.py           # затем проверить на галлюцинации
"""

import argparse
import sys

from adc_trials_fetch import fetch_all_adc_updates
from eval_runner import check_hallucinated_nct_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-output",
        default="agent_output.txt",
        help="Файл с выводом adc_agent.py (по умолчанию agent_output.txt)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help=(
            "days_back для fetch_all_adc_updates. Должен совпадать с тем, "
            "что фактически использовал агент при генерации сохранённого "
            "вывода — иначе сравнение будет с другим окном данных "
            "(по умолчанию 90, как в adc_agent.py)"
        ),
    )
    args = parser.parse_args()

    try:
        with open(args.agent_output, encoding="utf-8") as f:
            agent_text = f.read()
    except FileNotFoundError:
        print(
            f"Файл {args.agent_output} не найден — сначала сохрани вывод "
            f"adc_agent.py: python3 adc_agent.py > {args.agent_output}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Загружаю сырые данные инструмента (days_back={args.days_back})...")
    raw_data = fetch_all_adc_updates(days_back=args.days_back)
    print(f"Получено {len(raw_data)} исследований из реестра.\n")

    result = check_hallucinated_nct_ids(agent_text, raw_data)

    print("=== Проверка на галлюцинированные NCT ID ===\n")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

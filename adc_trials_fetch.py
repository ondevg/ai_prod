"""
adc_trials_fetch.py

Обёртка над ClinicalTrials.gov API v2 для поиска исследований по
antibody-drug conjugates (ADC) в онкологии.

Документация API: https://clinicaltrials.gov/data-api/api
Доступ без авторизации, бесплатно.

Запуск:
    pip install requests
    python adc_trials_fetch.py
"""

import time

import requests
from datetime import datetime, timedelta

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

# Ретраи на сетевые сбои/таймауты запросов к API.
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 1.0

# Ключевые слова для поиска ADC-испытаний.
# query.intr ищет по полю "intervention" (тип вмешательства/препарат).
# Можно расширять список по мере знакомства с данными
# (например, добавить конкретные payload-технологии: MMAE, DXd и т.д.)
ADC_SEARCH_TERMS = [
    "antibody-drug conjugate",
    "antibody drug conjugate",
    "ADC",
]

# Поля, которые запрашиваем — держим payload компактным.
FIELDS = [
    "NCTId",
    "BriefTitle",
    "OverallStatus",
    "Phase",
    "LeadSponsorName",
    "Condition",
    "InterventionName",
    "StartDate",
    "LastUpdatePostDate",
    "StudyFirstPostDate",
]


def _get_with_retry(url: str, params: dict, timeout: int = 30) -> requests.Response:
    """GET с экспоненциальным бэкоффом на таймауты и временные сетевые сбои."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == MAX_RETRIES:
                raise
            delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
            print(f"  [retry] {exc.__class__.__name__}, повтор через {delay:.0f}с "
                  f"(попытка {attempt + 1}/{MAX_RETRIES})")
            time.sleep(delay)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status >= 500 and attempt < MAX_RETRIES:
                delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
                print(f"  [retry] HTTP {status}, повтор через {delay:.0f}с "
                      f"(попытка {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                raise


def fetch_adc_trials(search_term: str, days_back: int = 90, page_size: int = 50, max_pages: int = 20) -> list[dict]:
    """
    Запрашивает исследования по ADC, обновлённые за последние `days_back` дней.

    Параметры API v2, которые тут используются:
    - query.intr: текстовый поиск по вмешательству (интервенции)
    - query.cond: сузили до онкологии (cancer)
    - filter.overallStatus: значения строго из enum (RECRUITING, COMPLETED и т.д.),
      регистрозависимые — см. документацию
    - sort: LastUpdatePostDate:desc — сначала самые свежие обновления
    - nextPageToken: результатов на термин обычно намного больше page_size
      (например, 800+ у "ADC"), поэтому листаем страницы, пока не упрёмся
      в cutoff_date или в отсутствие nextPageToken. Раз сортировка идёт по
      убыванию даты обновления, как только встречаем исследование старше
      cutoff_date, все последующие тоже будут старше — дальше не листаем.
    """
    cutoff_date = datetime.now() - timedelta(days=days_back)

    params = {
        "query.intr": search_term,
        "query.cond": "cancer",
        "fields": ",".join(FIELDS),
        "pageSize": page_size,
        "sort": "LastUpdatePostDate:desc",
        "format": "json",
        "countTotal": "true",
    }

    recent_studies = []
    for _ in range(max_pages):
        response = _get_with_retry(BASE_URL, params=params)
        data = response.json()

        studies = data.get("studies", [])
        reached_cutoff = False

        for study in studies:
            protocol = study.get("protocolSection", {})
            status_module = protocol.get("statusModule", {})
            last_update_str = status_module.get("lastUpdatePostDateStruct", {}).get("date")

            if last_update_str:
                try:
                    last_update = datetime.strptime(last_update_str, "%Y-%m-%d")
                except ValueError:
                    # Иногда даты приходят в формате "2024-01" без дня — пропускаем строгий фильтр
                    last_update = None
            else:
                last_update = None

            if last_update is not None and last_update < cutoff_date:
                reached_cutoff = True
                break

            recent_studies.append(_extract_summary(protocol))

        next_page_token = data.get("nextPageToken")
        if reached_cutoff or not next_page_token:
            break

        params["pageToken"] = next_page_token

    return recent_studies


def _extract_summary(protocol: dict) -> dict:
    """Достаёт компактную сводку из протокола испытания. Поля могут отсутствовать —
    везде используем .get() с дефолтом, как советует документация API."""
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {})
    interventions = protocol.get("armsInterventionsModule", {})

    return {
        "nct_id": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "status": status.get("overallStatus"),
        "phase": design.get("phases", []),
        "sponsor": sponsor.get("leadSponsor", {}).get("name"),
        "conditions": conditions.get("conditions", []),
        "interventions": [
            i.get("name") for i in interventions.get("interventions", [])
        ],
        "last_update": status.get("lastUpdatePostDateStruct", {}).get("date"),
        "first_posted": status.get("studyFirstPostDateStruct", {}).get("date"),
        "url": f"https://clinicaltrials.gov/study/{ident.get('nctId')}" if ident.get("nctId") else None,
    }


def fetch_all_adc_updates(days_back: int = 90) -> list[dict]:
    """Собирает и дедуплицирует результаты по всем поисковым терминам."""
    seen_nct_ids = set()
    all_results = []

    for term in ADC_SEARCH_TERMS:
        results = fetch_adc_trials(term, days_back=days_back)
        for r in results:
            nct_id = r.get("nct_id")
            if nct_id and nct_id not in seen_nct_ids:
                seen_nct_ids.add(nct_id)
                all_results.append(r)

    return all_results


if __name__ == "__main__":
    print("Ищу обновления по ADC-исследованиям в онкологии за последние 90 дней...\n")
    updates = fetch_all_adc_updates(days_back=90)

    print(f"Найдено {len(updates)} уникальных исследований:\n")
    for study in updates:
        print(f"[{study['nct_id']}] {study['title']}")
        print(f"  Статус: {study['status']} | Фаза: {study['phase']}")
        print(f"  Спонсор: {study['sponsor']}")
        print(f"  Обновлено: {study['last_update']}")
        print(f"  {study['url']}")
        print()

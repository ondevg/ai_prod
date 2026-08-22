# Отчёт о запуске: adc_agent.py

Пример реального прогона агента конкурентной разведки — что он сделал и что
нашёл. Зафиксировано как референс: как выглядит корректная работа агента и
его guardrails на живых данных.

## Параметры запуска

| | |
|---|---|
| Дата запуска | 2026-08-22 |
| Модель | `claude-opus-5` |
| Запрос | «Подготовь сводку по значимым обновлениям в ADC-исследованиях за последние 90 дней.» |
| Источник данных | ClinicalTrials.gov API v2, через `fetch_adc_trials` (`adc_trials_fetch.py`) |
| Окно данных | обновления с 2026-05-26 по 2026-08-21, ~250 записей после дедупликации |

## Ход выполнения

1. Агент получил запрос, решил, что нужны свежие данные, и вызвал
   инструмент `fetch_adc_trials({'days_back': 90})`.
2. Во время запроса к ClinicalTrials.gov произошёл один `ReadTimeout` —
   отработал ретрай с бэкоффом внутри `adc_trials_fetch.py` (повтор через 1с,
   попытка 1/4), после чего данные пришли успешно.
3. Инструмент вернул ~250 исследований. Агент построил из них сводку, строго
   следуя guardrails системного промпта: ни одного факта без NCT ID,
   предположения помечены явно, пробелы в данных названы пробелами, а не
   заполнены домыслом.
4. Ответ уложился в лимит `max_tokens` без обрезки (см. «Известную проблему»
   ниже — на первом прогоне до фикса сводка обрывалась).

## Известная проблема, вскрытая этим прогоном

Первая попытка запуска (с `max_tokens=8000`, без стриминга) оборвалась
посреди раздела «Средняя значимость» — модель уперлась в `stop_reason:
"max_tokens"`, а код `run_agent()` в тот момент трактовал любой стоп кроме
`tool_use` как финальный ответ и молча возвращал обрезанный текст. Исправлено
переходом на `client.messages.stream(...)` с `max_tokens=32000` и явным
предупреждением в тексте, если `stop_reason == "max_tokens"` всё же
случится. Сводка ниже — результат прогона уже после этого фикса.

---

## Сводка агента

# Аналитическая сводка: ADC-исследования, обновления за последние 90 дней

**Источник:** ClinicalTrials.gov через `fetch_adc_trials(days_back=90)`. Получено ~250 записей с датами обновления в диапазоне 2026-05-26 — 2026-08-21.

**Важное методологическое предупреждение:** инструмент возвращает только *текущее* состояние записи (статус, фаза, дата последнего обновления). Он **не возвращает историю изменений**. Поэтому я не могу достоверно утверждать «фаза сменилась» или «статус изменился» — я могу лишь фиксировать *текущий статус* и *дату первой публикации*. Ниже события классифицированы по наблюдаемым признакам: «новая регистрация» = `first_posted` попадает в окно 90 дней; для остальных — «обновление записи, характер изменения неизвестен». Это ограничение данных, а не домысел.

---

## 1. Новые регистрации Phase 3 — наиболее значимый сигнал

| Спонсор | Актив / цель | Показание | Значимость | NCT | Ссылка |
|---|---|---|---|---|---|
| **Corbus Pharmaceuticals** | CRB-701 | Оропharyngeal SCC, 2L+, vs investigator's choice | **Высокая** — первый Phase 3 для CRB-701 в данных; зарегистрирован 2026-08-17, статус NOT_YET_RECRUITING | NCT07768189 | [ссылка](https://clinicaltrials.gov/study/NCT07768189) |
| **AstraZeneca** | Dato-DXd + rilvegostomig vs SoC (включая enfortumab vedotin в компараторе) | High-risk MIUC (мышечно-инвазивный уротелиальный рак) | **Высокая** — выход Dato-DXd в периоперационный/high-risk сеттинг уротелия; first_posted 2026-07-22, уже RECRUITING | NCT07720284 | [ссылка](https://clinicaltrials.gov/study/NCT07720284) |
| **GlaxoSmithKline** | Mocertatug rezetecan (Mo-Rez) + bevacizumab vs платиновый дублет + bev | Platinum-**sensitive** ovarian cancer (BEHOLD-Ovarian02) | **Высокая** — расширение программы BEHOLD в platinum-sensitive; first_posted 2026-07-06 | NCT07684612 | [ссылка](https://clinicaltrials.gov/study/NCT07684612) |
| **GlaxoSmithKline** | GSK5733584, maintenance | MMRp endometrial cancer (BEHOLD-Endometrial02) | **Высокая** — второй новый Phase 3 GSK за одну неделю (first_posted 2026-07-06), maintenance-сеттинг | NCT07684599 | [ссылка](https://clinicaltrials.gov/study/NCT07684599) |
| **Bristol-Myers Squibb** | Iza-bren + osimertinib vs osimertinib ± химия (IZABRIGHT-Lung02) | EGFRmt NSCLC, 1L | **Высокая** — заявка на 1L EGFR-мутированный NSCLC в комбинации с осимертинибом; first_posted 2026-07-02 | NCT07680790 | [ссылка](https://clinicaltrials.gov/study/NCT07680790) |
| **Fudan University** | Trastuzumab rezetecan (SHR-A1811) ± everolimus | LAR-подтип TNBC, 1L–3L | **Средняя** — академический Phase 3 с биомаркерной стратификацией по подтипу TNBC; first_posted 2026-08-12 | NCT07760844 | [ссылка](https://clinicaltrials.gov/study/NCT07760844) |
| **Fudan University** | Trastuzumab rezetecan ± bevacizumab | BLIS-подтип TNBC, 1L–3L | **Средняя** — парный к предыдущему дизайн по другому подтипу; first_posted 2026-06-25 | NCT07669610 | [ссылка](https://clinicaltrials.gov/study/NCT07669610) |
| **CSPC Megalith** | SYS6010 + enlonstobart vs ИО + платина (SYNSTAR 04) | PD-L1+ распространённый NSCLC | **Средняя** — Phase 3 в 1L PD-L1+ NSCLC; first_posted 2026-06-08 | NCT07633873 | [ссылка](https://clinicaltrials.gov/study/NCT07633873) |
| **SWOG Cancer Research Network** | T-DXd / T-DM1 в составе стратегии + хирургия/ЛТ | Метастатический HER2+ РМЖ de novo | **Низкая/Средняя** — вопрос локальной терапии, не сам ADC-актив; first_posted 2026-05-11 | NCT07578116 | [ссылка](https://clinicaltrials.gov/study/NCT07578116) |

---

## 2. Негативные сигналы — статусы SUSPENDED / TERMINATED

Это, вероятно, самая практически важная категория для продуктовой команды. **Причины прекращения в данных инструмента отсутствуют — это «недостаточно данных», требуется отдельная проверка (пресс-релизы, записи ClinicalTrials.gov с полем "Why Stopped").**

| Спонсор | Актив | Статус | Значимость | NCT | Ссылка |
|---|---|---|---|---|---|
| **CStone Pharmaceuticals** | CS5001 (Phase 1, солидные опухоли + лимфомы) | **SUSPENDED** | **Высокая** — приостановка Phase 1; при этом CStone параллельно ведёт новый CS5007 Phase 1 (NCT07622524, RECRUITING, first_posted 2026-06-03). Связь между этими фактами в данных **не подтверждена** — сопоставление предположительное, требует проверки | NCT05279300 | [ссылка](https://clinicaltrials.gov/study/NCT05279300) |
| **AbbVie** | Cofetuzumab pelidotin (PTK7 ADC), NSCLC | **TERMINATED** | **Высокая** — терминация PTK7-актива значима на фоне того, что Whitehawk запускает свой PTK7-ADC HWK-007 (NCT07444814, Phase 1, RECRUITING) | NCT04189614 | [ссылка](https://clinicaltrials.gov/study/NCT04189614) |
| **Seagen (Pfizer)** | PF-08046044 / SGN-35C (next-gen brentuximab) | **TERMINATED** | **Высокая** — прекращение follow-on к brentuximab vedotin | NCT06254495 | [ссылка](https://clinicaltrials.gov/study/NCT06254495) |
| **Seagen (Pfizer)** | Tisotumab vedotin, цервикальный рак, комбинации | **TERMINATED** | **Средняя** — терминация комбинационного Phase 1/2; при этом GOG Foundation регистрирует новое Phase 2 с tisotumab vedotin при раке вульвы (NCT07672782) | NCT03786081 | [ссылка](https://clinicaltrials.gov/study/NCT03786081) |
| **Jules Bordet Institute** | 89Zr-trastuzumab PET как предиктор для секвенирования ADC | **TERMINATED** | **Средняя** — негативный сигнал для биомаркер-имиджинг подхода к выбору ADC | NCT06595563 | [ссылка](https://clinicaltrials.gov/study/NCT06595563) |
| **University of Washington** | Loncastuximab tesirine, r/r B-cell | **TERMINATED** | **Низкая/Средняя** — академическое исследование | NCT05453396 | [ссылка](https://clinicaltrials.gov/study/NCT05453396) |

---

## 3. Кластер: EGFR-ADC Becotatug Vedotin (MRG003) — резкий всплеск активности

**Тип события:** взрывной рост числа новых Phase 1/2 исследований, преимущественно академические китайские центры, почти все в комбинации с PD-1 ингибитором pucotenlimab.

За 90 дней зарегистрировано/обновлено **≥9 исследований**:

- Пенильный рак, неоадъювант — Sun Yat-sen, NCT07767266 ([ссылка](https://clinicaltrials.gov/study/NCT07767266)); Jiyan Liu, NCT07518979 ([ссылка](https://clinicaltrials.gov/study/NCT07518979))
- Оральный SCC, неоадъювант — Sun Yat-sen, NCT07766889 ([ссылка](https://clinicaltrials.gov/study/NCT07766889))
- Гипофарингеальный SCC — Tianjin, NCT07665190 ([ссылка](https://clinicaltrials.gov/study/NCT07665190))
- HNSCC — Feng Liu, NCT07683507 ([ссылка](https://clinicaltrials.gov/study/NCT07683507))
- Желудок/GEJ — West China Second, NCT07692334 ([ссылка](https://clinicaltrials.gov/study/NCT07692334))
- Билиарный тракт — HuiKai Li, NCT07649980 ([ссылка](https://clinicaltrials.gov/study/NCT07649980))
- Пан-солидные EGFR+ — Tianjin Medical Univ. Second Hospital, NCT07712029 ([ссылка](https://clinicaltrials.gov/study/NCT07712029))
- Эзофагеальный SCC — Fudan, NCT07403136 ([ссылка](https://clinicaltrials.gov/study/NCT07403136)); Hebei, NCT07697040 ([ссылка](https://clinicaltrials.gov/study/NCT07697040))
- Синоназальная аденоид-кистозная карцинома — Fudan ENT, NCT07522879 ([ссылка](https://clinicaltrials.gov/study/NCT07522879))

**Значимость: Высокая** — плотность и синхронность запусков указывают на формирование широкой доказательной базы для EGFR-ADC в плоскоклеточных опухолях.

⚠️ **Мотивы и стратегия спонсора в данных отсутствуют.** Интерпретация «скоординированная кампания по расширению показаний» — **предположение, требует проверки**. Формально это независимые академические заявки.

---

## 4. Кластер: платино-резистентный рак яичников (PROC) — перегретая конкуренция

Наиболее плотный по числу конкурирующих Phase 3 сегмент в данных:

| Спонсор | Актив | Статус / примечание | NCT | Ссылка |
|---|---|---|---|---|
| Eli Lilly | Sofetabart mipitecan | Phase 3, RECRUITING, 3-частный дизайн, MIRV в компараторе | NCT07213804 | [ссылка](https://clinicaltrials.gov/study/NCT07213804) |
| AstraZeneca | AZD5335 vs **mirvetuximab** (FRα-high) / vs химия (FRα-low) | Phase 3, RECRUITING — прямое сравнение с лидером класса | NCT07218809 | [ссылка](https://clinicaltrials.gov/study/NCT07218809) |
| GlaxoSmithKline | Mocertatug rezetecan (BEHOLD-Ovarian01) | Phase 3, RECRUITING | NCT07286266 | [ссылка](https://clinicaltrials.gov/study/NCT07286266) |
| Genmab | Rina-S | Phase 3 ACTIVE_NOT_RECRUITING (NCT06619236) + **новое китайское расширение** RECRUITING (NCT07604766, first_posted 2026-05-22) | NCT06619236 / NCT07604766 | [1](https://clinicaltrials.gov/study/NCT06619236) / [2](https://clinicaltrials.gov/study/NCT07604766) |
| Daiichi Sankyo | R-DXd | Phase 2/3, RECRUITING | NCT06161025 | [ссылка](https://clinicaltrials.gov/study/NCT06161025) |

**Значимость: Высокая.** Отдельно отмечу: **AbbVie** ведёт Phase 2 по управлению **глазной токсичностью** mirvetuximab (NCT06365853, ACTIVE_NOT_RECRUITING, [ссылка](https://clinicaltrials.gov/study/NCT06365853)) — фактический признак того, что офтальмотоксичность остаётся управляемой проблемой класса FRα.

---

## 5. Ранние активы (Phase 1 FIH) — новые входы в поле

Значимость каждого по отдельности — **Низкая/Средняя** (ранняя стадия), но совокупно показывают направление таргетов:

- **VelaVigo Bio** — три новых FIH за 90 дней: VBC117 (NCT07772934, [ссылка](https://clinicaltrials.gov/study/NCT07772934)), VBC108 (NCT07700160, [ссылка](https://clinicaltrials.gov/study/NCT07700160)), VBC106 (NCT07686068, [ссылка](https://clinicaltrials.gov/study/NCT07686068)). Мишени в данных **не указаны — недостаточно данных**.
- **NEOK Bio** — два биспецифических ADC: NEOK002 (EGFR×MUC1, NCT07612189, [ссылка](https://clinicaltrials.gov/study/NCT07612189)), NEOK001 (B7-H3×ROR1, NCT07612176, [ссылка](https://clinicaltrials.gov/study/NCT07612176)). **Значимость: Средняя** — биспецифические ADC как формат.
- **Whitehawk Therapeutics** — HWK-016 (MUC16, NCT07470853, [ссылка](https://clinicaltrials.gov/study/NCT07470853)) и HWK-007 (PTK7, NCT07444814, [ссылка](https://clinicaltrials.gov/study/NCT07444814)).
- **Iksuda** — IKS04, мишень CA242 (NCT07738939, [ссылка](https://clinicaltrials.gov/study/NCT07738939)) — редкая мишень.
- **BigHat Biosciences** — BHB810, CDH17 (NCT07529808, [ссылка](https://clinicaltrials.gov/study/NCT07529808)).
- **ArriVent** — ARR-002, овариальный/эндометриальный (NCT07755436, [ссылка](https://clinicaltrials.gov/study/NCT07755436)).
- **Tubulis** — TUB-040 расширение в маточный рак (NCT07743541, [ссылка](https://clinicaltrials.gov/study/NCT07743541)), в дополнение к базовому NCT06303505.
- **Kivu Bioscience** — KIVU-305 (NCT07545356, [ссылка](https://clinicaltrials.gov/study/NCT07545356)).
- **Janssen** — JNJ-98768111, прогрессирующий рак простаты (NCT07746713, [ссылка](https://clinicaltrials.gov/study/NCT07746713)).
- **Adlai Nortye** — AN4035, CEACAM5 при RAS-мутациях (NCT07686445, [ссылка](https://clinicaltrials.gov/study/NCT07686445)).
- **Hangzhou Zhongmei Huadong** — HDM2020, FGFR2b, sq-NSCLC (NCT07638891, [ссылка](https://clinicaltrials.gov/study/NCT07638891)).

---

## 6. Тема, набирающая вес: управление токсичностью ADC как отдельное направление

Три новых исследования, посвящённых **не эффективности, а переносимости** ADC:

- **Jules Bordet** — scalp cooling против ADC-индуцированной алопеции, Phase 2, NOT_YET_RECRUITING (NCT07474558, [ссылка](https://clinicaltrials.gov/study/NCT07474558))
- **Peking University Cancer Hospital** — фосролапитант + палоносетрон против ADC-индуцированной тошноты/рвоты (NCT07692451, [ссылка](https://clinicaltrials.gov/study/NCT07692451))
- **Tianjin Medical University** — трилациклиб для профилактики миелосупрессии от TOP1i-ADC (NCT07736001, [ссылка](https://clinicaltrials.gov/study/NCT07736001))
- **Fudan University** — Sac-TMT vs MMAE-ADC с фокусом на периферическую нейропатию (NCT07662863, [ссылка](https://clinicaltrials.gov/study/NCT07662863))

**Значимость: Средняя.** Формируется отдельный сегмент «supportive care для ADC» — сигнал зрелости класса и признание токсичности как барьера. Указанный дизайн Fudan (прямое сравнение payload-классов по нейропатии) заслуживает отдельного внимания.

---

## 7. Прочие заметные обновления записей

*(характер изменения неизвестен — инструмент не даёт истории; фиксирую текущее состояние)*

- **Merck (MSD)** — Sac-TMT: TroFuse-011 Phase 3 TNBC RECRUITING (NCT06841354, [ссылка](https://clinicaltrials.gov/study/NCT06841354)); MK-2870-004 Phase 3 NSCLC теперь **ACTIVE_NOT_RECRUITING** — набор завершён (NCT06074588, [ссылка](https://clinicaltrials.gov/study/NCT06074588)). **Значимость: Высокая** — завершение набора в Phase 3 приближает read-out.
- **AstraZeneca** — DESTINY-Breast09 ACTIVE_NOT_RECRUITING (NCT04784715, [ссылка](https://clinicaltrials.gov/study/NCT04784715)); TROPION-Breast03 ACTIVE_NOT_RECRUITING (NCT05629585, [ссылка](https://clinicaltrials.gov/study/NCT05629585)); TROPION-Breast05 RECRUITING (NCT06103864, [ссылка](https://clinicaltrials.gov/study/NCT06103864)).
- **Pfizer** — PF-08046054/SGN-PDL1V Phase 3 vs доцетаксел в PD-L1+ NSCLC, RECRUITING (NCT07144280, [ссылка](https://clinicaltrials.gov/study/NCT07144280)); sigvotatug vedotin Phase 3 (NCT06012435, ACTIVE_NOT_RECRUITING, [ссылка](https://clinicaltrials.gov/study/NCT06012435)) и Phase 3 в комбинации с пембролизумабом (NCT06758401, [ссылка](https://clinicaltrials.gov/study/NCT06758401)).
- **Zai Lab** — ZL-1310 Phase 3 DLLEVATE при рецидивном SCLC, RECRUITING (NCT07218146, [ссылка](https://clinicaltrials.gov/study/NCT07218146)) — конкурирует с Daiichi I-DXd (NCT06203210, [ссылка](https://clinicaltrials.gov/study/NCT06203210)) и GSK Ris-Rez (NCT07099898, [ссылка](https://clinicaltrials.gov/study/NCT07099898)). **SCLC — второй по плотности конкуренции сегмент.**
- **EMD Serono / Merck KGaA** — precemtabart tocentecan Phase 3 в mCRC (NCT07549412, RECRUITING, [ссылка](https://clinicaltrials.gov/study/NCT07549412)), плюс ранние M7437 (Ly6E, NCT07360314) и M3554 (GD2, NCT06641908).

---

## Что я НЕ могу сказать по этим данным

Явно фиксирую пробелы, чтобы команда не строила выводы на пустом месте:

1. **Причины SUSPENDED/TERMINATED** — поле отсутствует. Это ключевой пробел; по CS5001, cofetuzumab pelidotin и SGN-35C нужна ручная проверка.
2. **История смены фаз и статусов** — инструмент даёт срез, не дифф. Все формулировки «смена фазы» в этой сводке я сознательно не использовал.
3. **Мишени большинства новых Phase 1** (VBC-серия, KIVU-305, MST-168, ADCX-020 и др.) — в поле interventions только кодовые названия.
4. **Размеры выборок, даты read-out, первичные эндпоинты** — не возвращаются инструментом.
5. Несколько записей вернулись **без указания фазы** (напр. NCT07767799, Fondazione Italiana Linfomi; NCT07610616) — недостаточно данных для классификации.
6. Часть записей в выдаче — **нерелевантный шум** (MRI/визуализация, где "ADC" = apparent diffusion coefficient: NCT06749301, NCT07743749, NCT07768046; дендритноклеточные вакцины: NCT04487756). Их я исключил из анализа.

---

## Рекомендуемые направления для вашего решения

Не принимаю решение за вас — предлагаю приоритеты для углублённой проверки:

1. **Срочно:** выяснить причины остановки CS5001 (NCT05279300) и cofetuzumab pelidotin (NCT04189614) — если это токсичность класса или мишени, это влияет на оценку рисков собственного портфеля.
2. **Высокий приоритет:** сегмент PROC выглядит перенасыщенным — минимум 5 Phase 3 активов. Оценка целесообразности входа/продолжения.
3. **Высокий приоритет:** кластер EGFR-ADC — понять, кто стоит за MRG003 и является ли этот всплеск органическим.
4. **Средний приоритет:** тренд supportive care для ADC — возможная белая зона.

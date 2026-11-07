"""
Тестирование производительности pipeline.

Проверяет требование: время обработки одной вакансии <= 0.1 секунды.
Запускает pipeline на выборках разного размера и фиксирует метрики времени.

Запуск:
    python benchmark.py --input vacancies.json
    python benchmark.py --input vacancies.json --sizes 50 100 200

Формат vacancies.json — список вакансий как из HHCollector:
[{"id": "...", "title": "...", "description": "...", "company": "...", "area": "..."}, ...]
"""

import json
import time
import argparse
import statistics
from dataclasses import dataclass

from normalizer import SkillNormalizer
from extractor import SkillExtractor
from importance import SkillWeightAnalyzer
from matcher import SkillMatcher

THRESHOLD_SECONDS_PER_VACANCY = 0.1


# Структура результата одного прогона

@dataclass
class BenchmarkRun:
    sample_size: int          # сколько вакансий в прогоне
    total_seconds: float      # общее время
    per_vacancy_mean: float   # среднее время на вакансию
    per_vacancy_median: float
    per_vacancy_min: float
    per_vacancy_max: float
    per_vacancy_stdev: float
    times: list               # время каждой вакансии


# Загрузка pipeline

def load_pipeline(model_path: str):
    print("Загрузка pipeline...")
    t0 = time.perf_counter()

    normalizer = SkillNormalizer()
    extractor  = SkillExtractor(model_path, normalizer)
    nlp        = extractor.load_model()
    weighter   = SkillWeightAnalyzer(extractor, normalizer)
    matcher    = SkillMatcher()

    elapsed = time.perf_counter() - t0
    print(f"Pipeline загружен за {elapsed:.2f} сек\n")
    return nlp, weighter, matcher, extractor


# Один прогон на N вакансий

def run_benchmark(vacancies: list, nlp, weighter, matcher,
                  user_skills: set) -> BenchmarkRun:
    times = []

    for vacancy in vacancies:
        t0 = time.perf_counter()

        job_skills = weighter.extract_weighted_skills(vacancy["description"], nlp)
        if job_skills:
            matcher.match_skills(user_skills, job_skills)

        elapsed = time.perf_counter() - t0
        times.append(elapsed)

    total = sum(times)

    return BenchmarkRun(
        sample_size=len(vacancies),
        total_seconds=total,
        per_vacancy_mean=statistics.mean(times),
        per_vacancy_median=statistics.median(times),
        per_vacancy_min=min(times),
        per_vacancy_max=max(times),
        per_vacancy_stdev=statistics.stdev(times) if len(times) > 1 else 0.0,
        times=times,
    )


# Отчёт

def print_report(runs: list[BenchmarkRun]):
    print("\n" + "=" * 65)
    print(f"{'Стажировок':>9}  {'Всего, с':>9}  {'Среднее, с':>10}  "
          f"{'Медиана, с':>10}  {'Макс, с':>8}")
    print("-" * 65)

    threshold = THRESHOLD_SECONDS_PER_VACANCY

    for r in runs:
        print(
            f"{r.sample_size:>9}  "
            f"{r.total_seconds:>9.2f}  "
            f"{r.per_vacancy_mean:>10.3f}  "
            f"{r.per_vacancy_median:>10.3f}  "
            f"{r.per_vacancy_max:>8.3f}  "
        )

    print("=" * 65)
    print(f"\nПороговое значение: {threshold} сек/вакансию")

    # Итоговый вывод по требованию
    last = runs[-1]
    if last.per_vacancy_mean <= threshold:
        print(f"Требование выполнено: {last.per_vacancy_mean:.3f} сек/вакансию "
              f"при N={last.sample_size}")
    else:
        print(f"Требование НЕ выполнено: {last.per_vacancy_mean:.3f} сек/вакансию "
              f"при N={last.sample_size}")

    print("=" * 65)


# Сохранение отчёта

def save_report(runs: list[BenchmarkRun], output_path: str):
    report = [
        {
            "sample_size": r.sample_size,
            "total_seconds": round(r.total_seconds, 4),
            "per_vacancy_mean": round(r.per_vacancy_mean, 4),
            "per_vacancy_median": round(r.per_vacancy_median, 4),
            "per_vacancy_min": round(r.per_vacancy_min, 4),
            "per_vacancy_max": round(r.per_vacancy_max, 4),
            "per_vacancy_stdev": round(r.per_vacancy_stdev, 4),
            "threshold_seconds": THRESHOLD_SECONDS_PER_VACANCY,
            "passed": r.per_vacancy_mean <= THRESHOLD_SECONDS_PER_VACANCY,
        }
        for r in runs
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nДетальный отчёт сохранён: {output_path}")


# Точка входа

def main():
    parser = argparse.ArgumentParser(description="Бенчмарк pipeline")
    parser.add_argument("--input", required=True,
                        help="JSON с вакансиями (формат HHCollector)")
    parser.add_argument("--model", default="./custom_ner_lg",
                        help="Путь к модели spaCy")
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[50, 100, 200],
                        help="Размеры выборок для тестирования")
    parser.add_argument("--user_skills", default="Python,SQL,Git",
                        help="Навыки пользователя через запятую")
    parser.add_argument("--output", default="benchmark_report.json",
                        help="Путь для сохранения отчёта")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        all_vacancies = json.load(f)

    print(f"Загружено стажировок: {len(all_vacancies)}")

    nlp, weighter, matcher, extractor = load_pipeline(args.model)

    user_skills = extractor.get_user_skills(args.user_skills)

    runs = []
    for size in args.sizes:
        if size > len(all_vacancies):
            print(f"Пропуск N={size}: стажировок в файле меньше ({len(all_vacancies)})")
            continue

        sample = all_vacancies[:size]
        print(f"Прогон N={size}...", end=" ", flush=True)

        run = run_benchmark(sample, nlp, weighter, matcher, user_skills)
        runs.append(run)

        print(f"готово — среднее {run.per_vacancy_mean:.3f} сек/стажировка")

    print_report(runs)
    save_report(runs, args.output)


if __name__ == "__main__":
    main()
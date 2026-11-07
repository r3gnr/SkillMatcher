"""
Оценка точности всего pipeline извлечения навыков.

Структура эталонного файла (ground_truth.json):
[
    {
        "id": "vacancy_001",
        "description": "Текст вакансии...",
        "skills": ["python", "sql", "git"]   # нормализованные вручную
    },
    ...
]

Запуск:
    python evaluate_pipeline.py --ground_truth ground_truth.json
"""

import json
import argparse
from dataclasses import dataclass
from normalizer import SkillNormalizer
from extractor import SkillExtractor


# Структура результата по одной вакансии

@dataclass
class VacancyResult:
    vacancy_id: str
    predicted: set      # что выдал pipeline
    expected: set       # эталон
    tp: set             # верно найденные
    fp: set             # лишние (нет в эталоне)
    fn: set             # пропущенные (есть в эталоне, нет в предсказании)
    precision: float
    recall: float
    f1: float


# Метрики для одной вакансии

def compute_metrics(predicted: set, expected: set
                    ) -> tuple[float, float, float, set, set, set]:
    """
    Возвращает метрики.
    """
    tp = predicted & expected
    fp = predicted - expected
    fn = expected - predicted

    precision = len(tp) / len(predicted) if predicted else 0.0
    recall    = len(tp) / len(expected)  if expected  else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return precision, recall, f1, tp, fp, fn


# Загрузка pipeline

def load_pipeline(model_path: str = "./custom_ner_lg"):
    normalizer = SkillNormalizer()
    extractor  = SkillExtractor(model_path, normalizer)
    nlp        = extractor.load_model()
    return extractor, nlp


# Оценка одной вакансии

def evaluate_vacancy(extractor, nlp, item: dict) -> VacancyResult:
    description = item["description"]
    expected    = set(item["skills"])

    raw_predicted = extractor.extract_skills(nlp(description))
    predicted = set(raw_predicted)

    precision, recall, f1, tp, fp, fn = compute_metrics(predicted, expected)

    return VacancyResult(
        vacancy_id=item["id"],
        predicted=predicted,
        expected=expected,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
    )


# Агрегация по всей выборке

def macro_average(results: list[VacancyResult]) -> dict:
    """
    Macro-average: среднее метрик по вакансиям.
    """
    n = len(results)
    return {
        "macro_precision": sum(r.precision for r in results) / n,
        "macro_recall":    sum(r.recall    for r in results) / n,
        "macro_f1":        sum(r.f1        for r in results) / n,
    }


def micro_average(results: list[VacancyResult]) -> dict:
    """
    Micro-average: считаем TP/FP/FN по всем вакансиям суммарно.
    """
    total_tp = sum(len(r.tp) for r in results)
    total_fp = sum(len(r.fp) for r in results)
    total_fn = sum(len(r.fn) for r in results)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return {
        "micro_precision": precision,
        "micro_recall":    recall,
        "micro_f1":        f1,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
    }


# Отчёт

def print_report(results: list[VacancyResult]):
    print("\n" + "=" * 60)
    print(f"{'ID':<20} {'P':>6} {'R':>6} {'F1':>6}  TP  FP  FN")
    print("-" * 60)

    for r in results:
        print(
            f"{r.vacancy_id:<20} "
            f"{r.precision:>6.3f} {r.recall:>6.3f} {r.f1:>6.3f}  "
            f"{len(r.tp):>2}  {len(r.fp):>2}  {len(r.fn):>2}"
        )

    print("=" * 60)

    macro = macro_average(results)
    micro = micro_average(results)

    print(f"\nMacro-average  P={macro['macro_precision']:.3f}  "
          f"R={macro['macro_recall']:.3f}  F1={macro['macro_f1']:.3f}")
    print(f"Micro-average  P={micro['micro_precision']:.3f}  "
          f"R={micro['micro_recall']:.3f}  F1={micro['micro_f1']:.3f}")
    print(f"\nВсего: TP={micro['total_tp']}  FP={micro['total_fp']}  FN={micro['total_fn']}")

    threshold = 0.85
    result_f1 = micro["micro_f1"]
    status = "ПРОЙДЕНО" if result_f1 >= threshold else "НЕ ПРОЙДЕНО"
    print(f"\nТребование F1 ≥ {threshold}: {result_f1:.3f} — {status}")
    print("=" * 60)

    all_fp = [skill for r in results for skill in r.fp]
    all_fn = [skill for r in results for skill in r.fn]

    from collections import Counter
    top_fp = Counter(all_fp).most_common(10)
    top_fn = Counter(all_fn).most_common(10)

    print("\n10 лишних навыков:")
    for skill, count in top_fp:
        print(f"  {count:>3}×  {skill}")

    print("\n10 пропущенных навыков:")
    for skill, count in top_fn:
        print(f"  {count:>3}×  {skill}")


# Генерация шаблона ground_truth.json

def generate_template(output_path: str, n: int = 20):
    """
    Генерирует пустой шаблон для ручной разметки.
    """
    template = [
        {
            "id": f"vacancy_{i+1:03d}",
            "description": "<<вставьте текст вакансии>>",
            "skills": []
        }
        for i in range(n)
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    print(f"Шаблон сохранён: {output_path}")


# Точка входа

def main():
    parser = argparse.ArgumentParser(description="Оценка F-Score pipeline")
    parser.add_argument("--ground_truth", type=str,
                        help="Путь к файлу с эталонами (ground_truth.json)")
    parser.add_argument("--model", type=str,
                        default="./custom_ner_lg",
                        help="Путь к модели spaCy")
    parser.add_argument("--generate_template", type=str,
                        help="Сгенерировать пустой шаблон и сохранить по указанному пути")
    parser.add_argument("--template_size", type=int, default=20,
                        help="Количество вакансий в шаблоне (по умолчанию 20)")
    parser.add_argument("--output", default="evaluation_report.json",
                        help="Путь для сохранения отчёта")
    args = parser.parse_args()

    if args.generate_template:
        generate_template(args.generate_template, args.template_size)
        return

    if not args.ground_truth:
        parser.error("Укажите --ground_truth или --generate_template")

    with open(args.ground_truth, encoding="utf-8") as f:
        ground_truth = json.load(f)

    print(f"Загружено вакансий: {len(ground_truth)}")
    print("Загрузка pipeline...")

    extractor, nlp = load_pipeline(args.model)

    results = []
    for item in ground_truth:
        result = evaluate_vacancy(extractor, nlp, item)
        results.append(result)
        print(f"  [{item['id']}] F1={result.f1:.3f}")

    print_report(results)

    report_path = args.output
    report = {
        "macro": macro_average(results),
        "micro": micro_average(results),
        "per_vacancy": [
            {
                "id": r.vacancy_id,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "tp": sorted(r.tp),
                "fp": sorted(r.fp),
                "fn": sorted(r.fn),
            }
            for r in results
        ]
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nОтчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()
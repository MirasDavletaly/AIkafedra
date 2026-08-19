# ============================================================
# ai_engine.py — Собственный ИИ-движок кафедры (без внешних API)
# Обучается на данных кафедры, анализирует и рекомендует
# ============================================================
# Все величины нагрузки выражены в кредитах согласно
# П ЕНУ K.V.14-22 (Приложение 3): 1 кредит = 15 ак. часов
# для лекций, практических (семинарских) и лабораторных занятий.

import math
from datetime import datetime
from database import get_connection, init_db
from utils import workload_status

# Гарантируем актуальность схемы (миграция «часы → кредиты» по PDF)
# до того, как глобальный ai-ассистент попытается прочитать таблицу workload.
init_db()


# ════════════════════════════════════════════════════════════
# 1. СБОР И ПОДГОТОВКА ДАННЫХ (обучающая выборка)
# ════════════════════════════════════════════════════════════

def load_training_data():
    """Загружает и нормализует данные кафедры для обучения."""
    conn = get_connection()

    teachers = conn.execute("""
        SELECT t.id, t.full_name, t.position, t.max_workload,
               COALESCE(ROUND(SUM(w.lecture_credits + w.practice_credits + w.lab_credits), 2), 0) AS total_credits,
               COUNT(w.id) as subject_count
        FROM teachers t
        LEFT JOIN workload w ON w.teacher_id = t.id
        GROUP BY t.id
    """).fetchall()

    workload_rows = conn.execute("""
        SELECT w.teacher_id, w.subject_id, w.lecture_credits,
               w.practice_credits, w.lab_credits, w.semester, w.academic_year,
               t.position, t.max_workload, t.full_name,
               s.name AS subject_name,
               (w.lecture_credits + w.practice_credits + w.lab_credits) AS total
        FROM workload w
        JOIN teachers t ON t.id = w.teacher_id
        JOIN subjects s ON s.id = w.subject_id
    """).fetchall()

    subjects = conn.execute("SELECT * FROM subjects").fetchall()
    conn.close()

    return {
        "teachers":  [dict(t) for t in teachers],
        "workload":  [dict(w) for w in workload_rows],
        "subjects":  [dict(s) for s in subjects],
    }


# ════════════════════════════════════════════════════════════
# 2. МОДУЛЬ АНАЛИЗА — статистика и паттерны
# ════════════════════════════════════════════════════════════

class WorkloadAnalyzer:
    """Анализирует паттерны нагрузки и выявляет закономерности."""

    def __init__(self, data):
        self.teachers  = data["teachers"]
        self.workload  = data["workload"]
        self.subjects  = data["subjects"]
        self._build_patterns()

    def _build_patterns(self):
        """Строит паттерны: какая должность — сколько кредитов на тип занятий."""
        self.position_patterns = {}  # position -> avg credits per subject type

        by_position = {}
        for w in self.workload:
            pos = w["position"]
            if pos not in by_position:
                by_position[pos] = {"lecture": [], "practice": [], "lab": [], "total": []}
            by_position[pos]["lecture"].append(w["lecture_credits"])
            by_position[pos]["practice"].append(w["practice_credits"])
            by_position[pos]["lab"].append(w["lab_credits"])
            by_position[pos]["total"].append(w["total"])

        for pos, data in by_position.items():
            self.position_patterns[pos] = {
                "avg_lecture":  self._mean(data["lecture"]),
                "avg_practice": self._mean(data["practice"]),
                "avg_lab":      self._mean(data["lab"]),
                "avg_total":    self._mean(data["total"]),
                "std_total":    self._std(data["total"]),
                "count":        len(data["total"]),
            }

        # Паттерн по семестрам
        self.semester_patterns = {}
        for w in self.workload:
            sem = w["semester"]
            if sem not in self.semester_patterns:
                self.semester_patterns[sem] = {"totals": [], "teachers": set()}
            self.semester_patterns[sem]["totals"].append(w["total"])
            self.semester_patterns[sem]["teachers"].add(w["teacher_id"])

    def _mean(self, lst):
        return round(sum(lst) / len(lst), 2) if lst else 0

    def _std(self, lst):
        if len(lst) < 2:
            return 0
        m = self._mean(lst)
        variance = sum((x - m) ** 2 for x in lst) / len(lst)
        return round(math.sqrt(variance), 2)

    def get_anomalies(self):
        """Выявляет аномалии в нагрузке (перегруз, недогруз, дисбаланс)."""
        anomalies = []
        for t in self.teachers:
            st = workload_status(t["total_credits"], t["max_workload"])
            pct = st["percent"]

            if t["total_credits"] > t["max_workload"]:
                excess = round(t["total_credits"] - t["max_workload"], 2)
                anomalies.append({
                    "type": "overload",
                    "severity": "high",
                    "teacher": t["full_name"],
                    "message": f"Перегрузка на {excess} кр. ({pct}%)",
                    "value": excess,
                })
            elif pct < 40:
                lack = round(t["max_workload"] - t["total_credits"], 2)
                anomalies.append({
                    "type": "underload",
                    "severity": "medium",
                    "teacher": t["full_name"],
                    "message": f"Критически мало кредитов: {t['total_credits']}/{t['max_workload']} кр. ({pct}%)",
                    "value": lack,
                })
            elif pct < 60:
                anomalies.append({
                    "type": "low",
                    "severity": "low",
                    "teacher": t["full_name"],
                    "message": f"Низкая нагрузка: {pct}% от нормы",
                    "value": round(t["max_workload"] - t["total_credits"], 2),
                })

        return sorted(anomalies, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])

    def get_balance_score(self):
        """
        Оценка сбалансированности кафедры 0–100.
        Чем ближе к 100 — тем лучше распределена нагрузка.
        """
        if not self.teachers:
            return 0

        percents = []
        for t in self.teachers:
            st = workload_status(t["total_credits"], t["max_workload"])
            percents.append(st["percent"])

        avg = self._mean(percents)
        std = self._std(percents)

        # Идеал: все около 75-85%, минимальное отклонение
        deviation_from_ideal = abs(avg - 80)
        spread_penalty = std * 0.5

        score = max(0, 100 - deviation_from_ideal - spread_penalty)
        return round(score, 1)


# ════════════════════════════════════════════════════════════
# 3. МОДУЛЬ РЕКОМЕНДАЦИЙ — простой алгоритм ранжирования
# ════════════════════════════════════════════════════════════

class RecommendationEngine:
    """
    Алгоритм рекомендаций без внешних API.
    Использует взвешенное ранжирование на основе паттернов.
    """

    def __init__(self, data, analyzer):
        self.teachers  = data["teachers"]
        self.workload  = data["workload"]
        self.subjects  = data["subjects"]
        self.analyzer  = analyzer

    def recommend_distribution(self):
        """
        Рекомендует оптимальное распределение нагрузки.
        Алгоритм: жадное присвоение + балансировка.
        """
        recommendations = []

        current_load = {t["id"]: t["total_credits"]   for t in self.teachers}
        max_load     = {t["id"]: t["max_workload"] for t in self.teachers}

        for t in self.teachers:
            tid    = t["id"]
            used   = current_load[tid]
            maxc   = max_load[tid]
            free   = round(maxc - used, 2)
            st     = workload_status(used, maxc)

            if free <= 0:
                recommendations.append({
                    "teacher": t["full_name"],
                    "position": t["position"],
                    "action": "reduce",
                    "priority": "high",
                    "message": f"Снизить нагрузку на {abs(free)} кр. — уже превышен лимит",
                    "free_credits": free,
                    "percent": st["percent"],
                })
            elif st["percent"] < 60:
                pattern = self.analyzer.position_patterns.get(t["position"], {})
                avg_per_subj = pattern.get("avg_total", 3.6)
                can_add = max(1, round(free / max(avg_per_subj, 0.1)))

                recommendations.append({
                    "teacher": t["full_name"],
                    "position": t["position"],
                    "action": "add",
                    "priority": "medium" if st["percent"] >= 40 else "high",
                    "message": (
                        f"Добавить ~{can_add} дисциплин ({free} кр. свободно). "
                        f"Для {t['position']} средняя дисциплина ≈ {avg_per_subj} кр."
                    ),
                    "free_credits": free,
                    "percent": st["percent"],
                })
            else:
                recommendations.append({
                    "teacher": t["full_name"],
                    "position": t["position"],
                    "action": "ok",
                    "priority": "none",
                    "message": f"Нагрузка оптимальна: {st['percent']}% от нормы",
                    "free_credits": free,
                    "percent": st["percent"],
                })

        return sorted(recommendations,
                      key=lambda x: {"high": 0, "medium": 1, "none": 2}[x["priority"]])

    def suggest_teacher_for_subject(self, subject_credits):
        """
        Рекомендует лучшего преподавателя для новой дисциплины (объём в кредитах).
        Алгоритм: минимизация отклонения от целевой нагрузки (80%).
        """
        scored = []
        for t in self.teachers:
            used  = t["total_credits"]
            maxc  = t["max_workload"]
            free  = round(maxc - used, 2)

            if free < subject_credits:
                continue

            new_pct = ((used + subject_credits) / maxc) * 100 if maxc else 0
            score = 100 - abs(new_pct - 80)

            if t["position"] in ["Профессор", "Доцент"]:
                score += 5

            scored.append({
                "teacher":  t["full_name"],
                "position": t["position"],
                "score":    round(score, 1),
                "free":     free,
                "new_pct":  round(new_pct, 1),
            })

        return sorted(scored, key=lambda x: -x["score"])[:3]


# ════════════════════════════════════════════════════════════
# 4. МОДУЛЬ ОБУЧЕНИЯ — накапливает паттерны
# ════════════════════════════════════════════════════════════

class AdaptiveLearner:
    """
    Простое адаптивное обучение — накапливает паттерны
    из истории данных кафедры и корректирует рекомендации.
    """

    def __init__(self, data):
        self.workload  = data["workload"]
        self.teachers  = data["teachers"]
        self._learn()

    def _learn(self):
        """Вычисляет обученные веса из исторических данных."""
        self.type_ratios = {}

        by_pos = {}
        for w in self.workload:
            pos   = w["position"]
            total = w["total"]
            if total == 0:
                continue
            if pos not in by_pos:
                by_pos[pos] = {"lec": [], "prac": [], "lab": []}
            by_pos[pos]["lec"].append(w["lecture_credits"]  / total)
            by_pos[pos]["prac"].append(w["practice_credits"] / total)
            by_pos[pos]["lab"].append(w["lab_credits"]      / total)

        for pos, ratios in by_pos.items():
            def avg(lst): return round(sum(lst)/len(lst)*100, 1) if lst else 0
            self.type_ratios[pos] = {
                "lecture_pct":  avg(ratios["lec"]),
                "practice_pct": avg(ratios["prac"]),
                "lab_pct":      avg(ratios["lab"]),
            }

        # Обученная статистика по кафедре в целом
        all_totals = [w["total"] for w in self.workload if w["total"] > 0]
        self.avg_subject_credits = round(sum(all_totals) / len(all_totals), 2) if all_totals else 3.6
        self.total_records       = len(self.workload)
        self.trained_at          = datetime.now().strftime("%d.%m.%Y %H:%M")

    def predict_credits(self, position, total_credits):
        """
        Предсказывает разбивку кредитов (лекции/практика/лаб)
        для новой дисциплины на основе обученных паттернов.
        """
        ratios = self.type_ratios.get(position, {
            "lecture_pct": 40, "practice_pct": 35, "lab_pct": 25
        })
        return {
            "lecture":  round(total_credits * ratios["lecture_pct"]  / 100, 2),
            "practice": round(total_credits * ratios["practice_pct"] / 100, 2),
            "lab":      round(total_credits * ratios["lab_pct"]      / 100, 2),
        }

    def get_stats(self):
        return {
            "total_records":       self.total_records,
            "avg_subject_credits": self.avg_subject_credits,
            "trained_at":          self.trained_at,
            "positions_learned":   len(self.type_ratios),
            "type_ratios":         self.type_ratios,
        }


# ════════════════════════════════════════════════════════════
# 5. ГЛАВНЫЙ КЛАСС — объединяет всё
# ════════════════════════════════════════════════════════════

class AIAssistant:
    """Главный ИИ-ассистент кафедры."""

    def __init__(self):
        self.retrain()

    def retrain(self):
        """Переобучение на актуальных данных кафедры."""
        data            = load_training_data()
        self.analyzer   = WorkloadAnalyzer(data)
        self.recommender = RecommendationEngine(data, self.analyzer)
        self.learner    = AdaptiveLearner(data)
        self.data       = data
        return self

    def get_dashboard(self):
        """Полный дашборд для страницы ИИ."""
        anomalies     = self.analyzer.get_anomalies()
        recommendations = self.recommender.recommend_distribution()
        balance_score = self.analyzer.get_balance_score()
        learn_stats   = self.learner.get_stats()

        total_credits = round(sum(t["total_credits"] for t in self.data["teachers"]), 2)
        total_max     = round(sum(t["max_workload"]  for t in self.data["teachers"]), 2)

        return {
            "balance_score":   balance_score,
            "anomalies":       anomalies,
            "recommendations": recommendations,
            "learn_stats":     learn_stats,
            "summary": {
                "teachers":         len(self.data["teachers"]),
                "subjects":         len(self.data["subjects"]),
                "workload_records": len(self.data["workload"]),
                "total_credits":    total_credits,
                "total_max":        total_max,
                "dept_pct":         round(total_credits / total_max * 100, 1) if total_max else 0,
            },
            "teachers": self.data["teachers"],
        }

    def predict_for_position(self, position, total_credits):
        """Предсказать разбивку кредитов для должности."""
        return self.learner.predict_credits(position, total_credits)

    def find_best_teacher(self, subject_credits):
        """Найти лучшего преподавателя под новую дисциплину (в кредитах)."""
        return self.recommender.suggest_teacher_for_subject(subject_credits)


# Глобальный экземпляр — создаётся один раз при запуске
ai = AIAssistant()

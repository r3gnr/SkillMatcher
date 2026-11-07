from rapidfuzz import fuzz, process

class SkillMatcher:
    """
    Класс для сравнения набора навыков пользователя и вакансии.
    """
    FUZZY_THRESHOLD = 85


    def fuzzy_match(self, skill, skill_pool):
        """
        Применяет нечёткое сравнение строк.
        """
        match = process.extractOne(skill, skill_pool, scorer=fuzz.ratio)
        if match and match[1] >= self.FUZZY_THRESHOLD:
            return match[0]
        return None


    def match_skills(self, user_skills, job_skills):
        """
        Сравнивает навыки пользователи и вакансии, определяет оценку.
        """
        total_weight = 0
        matched_weight = 0
        matched = set()

        for skill, skill_importance in job_skills.items():
            weight = skill_importance.value
            total_weight += weight

            if skill in user_skills:
                matched_weight += weight
                matched.add(skill)

            else:
                fuzzy = self.fuzzy_match(skill, user_skills)
                if fuzzy:
                    matched_weight += weight
                    matched.add(skill)

        score = matched_weight / total_weight if total_weight else 0

        return {
            "match_score": round(score, 4),
            "matched": matched,
            "missing": set(job_skills) - matched
        }
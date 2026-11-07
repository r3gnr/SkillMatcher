import spacy
from spacy.symbols import ORTH
from spacy.util import compile_infix_regex
from normalizer import SkillNormalizer
from typing import List
import re

class SkillExtractor:
    """
    Класс для извлечения навыков
    """
    def __init__(self, model_path: str, normalizer: SkillNormalizer):
        self.normalizer = normalizer
        self.nlp = self.load_model(model_path)

    def load_model(self, model_path: str = "./custom_ner_lg"):
        """
        Загружает spaCy-модель.
        Добавляет кастомную токенизацию.
        Добавляет EntityRuler с каноническими навыками.
        """
        nlp = spacy.load(model_path)

        self._apply_custom_tokenizer(nlp)
        self._add_entity_ruler(nlp)

        if "sentencizer" in nlp.pipe_names:
            nlp.remove_pipe("sentencizer")

        nlp.add_pipe("sentencizer", config={"punct_chars": [".", "!", "?", "\n"]})

        return nlp


    def _add_entity_ruler(self, nlp):
        """
        Добавляет EntityRuler перед NER.
        Использует CANONICAL_MAP из normalizer.
        """
        if "entity_ruler" in nlp.pipe_names:
            nlp.remove_pipe("entity_ruler")

        ruler = nlp.add_pipe("entity_ruler", before="ner", config={"phrase_matcher_attr": "LOWER"})

        patterns = []
        for key, canonical in self.normalizer.CANONICAL_MAP.items():
            patterns.append({
                "label": "HARD_SKILL",
                "pattern": key,
                "id": canonical
            })

        ruler.add_patterns(patterns)


    def _apply_custom_tokenizer(self, nlp):
        """
        Применяет расширенную токенизацию к объекту.
        """
        special_cases = [
            "C++", "c++",
            "C#", "c#",
            "1С", "1C",
            "CI/CD",
            "UI/UX",
            ".NET", ".Net", ".net", "asp.net",
            "node.js", "react.js"
        ]

        for case in special_cases:
            nlp.tokenizer.add_special_case(case, [{ORTH: case}])

        infixes = list(nlp.Defaults.infixes)

        new_infixes = [
            r'/',
            r'\\',
            r'&',
            r':',
            r'\|',
            r'(?<=[A-Za-zА-Яа-я])\+(?=[A-Za-zА-Яа-я])'
        ]

        infix_re = compile_infix_regex(infixes + new_infixes)
        nlp.tokenizer.infix_finditer = infix_re.finditer

        return nlp

    def extract_skills(self, doc) -> list:
        """
        Вычленяет навыки из текста.
        """
        skills = []
        for ent in doc.ents:
            if ent.label_ != "HARD_SKILL":
                continue
            if ent.ent_id_:
                skills.append(ent.ent_id_)
            else:
                normalized = self.normalizer.normalize_skill(ent.text)
                if normalized:
                    skills.append(normalized)
        return skills

    def split_skills(self, text: str) -> List[str]:
        """
        Разбиваем навыки по запятым, "и", "&", "или"
        """
        parts = re.split(r',|\s+и\s+|&|\s+или\s+', text, flags=re.IGNORECASE)
        return [p.strip() for p in parts if p.strip()]

    def get_user_skills(self, user_input: str):
        """
        Извлекает навыки пользователя.
        Приводит всё к канонической форме.
        """

        doc = self.nlp(user_input)

        # NER
        ner_skills = self.extract_skills(doc)

        # Split fallback
        raw_split = self.split_skills(user_input)

        # Объединение
        combined_raw = set(ner_skills) | set(raw_split)

        # Нормализация
        normalized = {
            self.normalizer.normalize_skill(skill)
            for skill in combined_raw
            if skill
        }

        return normalized
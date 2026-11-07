from enum import Enum
from extractor import SkillExtractor
from normalizer import SkillNormalizer


class SkillImportance(Enum):
    REQUIRED = 1.0
    OPTIONAL = 0.5

class SkillWeightAnalyzer:
    """
    Класс для определения значимости и весов навыков.
    """
    REQUIRED_MARKERS = ["требуется", "обязательно", "необходимо", "must", "required", "требование", "требования"]
    OPTIONAL_MARKERS = ["плюсом", "желательно", "приветствуется", "nice to have", "преимущество", "бонусом"]

    def __init__(self, extractor: SkillExtractor, normalizer: SkillNormalizer):
        self.extractor = extractor
        self.normalizer = normalizer


    def get_skill_importance(self, ent, block_mode):
        sent = ent.sent
        skill_idx = ent.start

        # Определяются зоны скобок в тексте
        brackets = []
        stack = []
        for token in sent:
            if token.text == "(":
                stack.append(token.i)
            elif token.text == ")" and stack:
                opening_idx = stack.pop()
                brackets.append((opening_idx, token.i))

        def get_zone(idx):
            for b_start, b_end in brackets:
                if b_start < idx < b_end:
                    return (b_start, b_end)
            return "OUTSIDE"

        skill_zone = get_zone(skill_idx)

        # Ищутся маркеры в зоне навыков или перед скобками
        relevant_markers = []
        for token in sent:
            t_low = token.text.lower()
            m_status = None

            if any(m in t_low for m in self.OPTIONAL_MARKERS):
                m_status = SkillImportance.OPTIONAL
            elif any(m in t_low for m in self.REQUIRED_MARKERS):
                m_status = SkillImportance.REQUIRED

            if m_status:
                # Маркер релевантен, если он в той же зоне (оба снаружи или оба в одних скобках)
                if get_zone(token.i) == skill_zone:
                    relevant_markers.append((token.i, m_status))

        # Если в зоне навыка нет маркеров используется блочный режим
        if not relevant_markers:
            return block_mode

        # Если маркеры есть, выбираем ближайший
        best_status = block_mode
        min_dist = 999

        for m_pos, m_status in relevant_markers:
            dist = abs(m_pos - skill_idx)

            # Штраф за знаки препинания между маркером и навыком
            low, high = (m_pos, skill_idx) if m_pos < skill_idx else (skill_idx, m_pos)
            for i in range(low, high):
                if sent.doc[i].text in [",", ";"]:
                    dist += 5

            if dist < min_dist:
                min_dist = dist
                best_status = m_status

        return best_status

    def classify_sentence(self, sentence_text: str) -> str:
        s = sentence_text.lower().strip()
        # Если предложение короткое и содержит маркер
        if any(marker in s for marker in self.REQUIRED_MARKERS) and len(s.split()) < 4:
            return "REQUIRED_BLOCK"
        if any(marker in s for marker in self.OPTIONAL_MARKERS) and len(s.split()) < 4:
            return "OPTIONAL_BLOCK"
        return "DEFAULT"

    def extract_weighted_skills(self, text: str, nlp) -> dict:
        doc = nlp(text)
        skills = {}
        current_block_mode = SkillImportance.REQUIRED

        for sent in doc.sents:
            sent_type = self.classify_sentence(sent.text)
            if "OPTIONAL_BLOCK" in sent_type:
                current_block_mode = SkillImportance.OPTIONAL
                continue
            elif "REQUIRED_BLOCK" in sent_type:
                current_block_mode = SkillImportance.REQUIRED
                continue

            sent_skills = self.extractor.extract_skills(sent.as_doc())

            for skill_id, ent in zip(sent_skills,
                                     [e for e in sent.ents
                                      if e.label_ == "HARD_SKILL"]):
                category = self.get_skill_importance(ent, current_block_mode)
                if skill_id in skills and skills[skill_id] == SkillImportance.REQUIRED:
                    continue
                skills[skill_id] = category

        return skills
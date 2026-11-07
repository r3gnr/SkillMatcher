import re
import pymorphy3

class SkillNormalizer:
    """
    Класс для нормализации навыков.
    """
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()

    def is_cyrillic(self, skill: str) -> bool:
        return bool(re.search(r'[а-яА-ЯёЁ]', skill))

    def lemmatize_ru(self, skill: str) -> str:
        """
        Лемматизация русского текста.
        """
        words = skill.split()
        result = []
        for word in words:
            if self.is_cyrillic(word):
                parsed = self.morph.parse(word)
                result.append(parsed[0].normal_form)
            else:
                result.append(word)
        return " ".join(result)

    CANONICAL_MAP = {
        "python": "python",
        "питон": "python",
        "пайтон": "python",
        "py": "python",
        "python3": "python",
        "python 3": "python",

        "python-telegram-bot": "python-telegram-bot",

        "java": "java",
        "джава": "java",

        "джаваскрипт": "javascript",
        "джава скрипт": "javascript",
        "javascript": "javascript",
        "js": "javascript",

        "typescript": "typescript",
        "ts": "typescript",

        "c": "c",
        "си": "c",

        "c++": "cpp",
        "си++": "cpp",
        "cpp": "cpp",

        "stl": "stl",
        "стл": "stl",
        "boost": "boost",
        "буст": "boost",

        "c#": "csharp",
        "си шарп": "csharp",
        "csharp": "csharp",

        ".net": "dotnet",
        ".net core": "dotnet",
        "дотнет": "dotnet",
        "asp.net": "asp_net",
        "asp net": "asp_net",
        "asp.net core": "asp_net",
        "asp net core": "asp_net",
        "аспнет": "asp_net",

        "go": "go",
        "golang": "go",

        "rust": "rust",
        "раст": "rust",

        "php": "php",

        "ассемблер": "assembler",
        "assembly": "assembler",
        "асемблер": "assembler",
        "asm": "assembler",
        "асм": "assembler",

        "база данных": "database",
        "база данные": "database",
        "db": "database",
        "реляционный база данные": "database",

        "sql": "sql",
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "postgre": "postgresql",
        "pgsql": "postgresql",

        "mysql": "mysql",
        "mongodb": "mongodb",
        "mongo": "mongodb",

        "redis": "redis",

        "django": "django",
        "fastapi": "fastapi",
        "fast api": "fastapi",
        "фастапи": "fastapi",

        "flask": "flask",

        "react": "react",
        "reactjs": "react",
        "react.js": "react",

        "vue": "vue",
        "vuejs": "vue",
        "vue.js": "vue",

        "angular": "angular",

        "nodejs": "nodejs",
        "node": "nodejs",
        "node.js": "nodejs",

        "docker": "docker",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",

        "ci/cd": "ci_cd",
        "ci cd": "ci_cd",
        "cicd": "ci_cd",

        "git": "git",

        "machine learning": "machine_learning",
        "ml": "machine_learning",
        "машинное обучение": "machine_learning",

        "deep learning": "deep_learning",
        "глубокое обучение": "deep_learning",

        "data science": "data_science",
        "datascience": "data_science",

        "pandas": "pandas",
        "numpy": "numpy",
        "scikit-learn": "sklearn",
        "sklearn": "sklearn",

        "transformers": "transformers",
        "transformer": "transformers",
        "трансформеры": "transformers",
        "трансформер": "transformers",

        "tensorflow": "tensorflow",
        "pytorch": "pytorch",

        "1с": "1c",
        "1c": "1c",
        "битрикс": "bitrix",
        "1c-bitrix": "bitrix",

        "figma": "figma",
        "jira": "jira",
        "confluence": "confluence",
        "selenium": "selenium",
        "playwright": "playwright",
        "cypress": "cypress",
        "linux": "linux",
        "линукс": "linux",
        "jupyter": "jupyter",
        "xml": "xml",
        "swift": "swift",
        "свифт": "swift",
        "spring": "spring",
        "спринг": "spring",
        "composer": "composer",
        "tcp/ip": "tcp_ip",
        "xmlвёрстка": "xml",
        "rest api": "rest",
        "rest": "rest",
        "restapi": "rest",
        "ооп": "oop",
        "объектноориентированный программирование": "oop",
        "jupyter notebook": "jupyter",
        "express.js": "express",
        "express js": "express",
        "expressjs": "express",
        "azure": "azure",
        "бэкенд": "backend",
        "фронтенд": "frontend",
        "бэкэнд": "backend",
        "бекенд": "backend",
        "фронтэнд": "frontend",
        "3д": "3d"
    }

    VERSION_PATTERN = re.compile(r'\b\d+(\.\d+)*\b')

    PUNCT_PATTERN = re.compile(r'[^\w\s+#./]')


    def normalize_skill(self, skill: str) -> str:
        if not skill:
            return ""

        skill = skill.lower().strip()

        prefixes = [
            r"знание\s+", r"знаю\s+", r"опыт работы с\s+", r"опыт\s+",
            r"работаю с\s+", r"работа с\s+", r"умение\s+", r"владение\s+",
            r"профессионально\s+", r"уверенно\s+", r"глубоко\s+",
            r"отлично\s+", r"хорошо\s+", r"навыки\s+", r"навык\s+",
            r"умею\s+", r"профессиональное владение\s+", r"понимание\s+"
        ]

        for p in prefixes:
            skill = re.sub(p, "", skill, flags=re.IGNORECASE).strip()

        suffixes = [
            r"\s+разработчик$", r"\s+developer$", r"\s+программист$",
            r"\s+инженер$", r"\s+и т\.?д\.?$", r"\s+и др\.?$"
        ]

        for s in suffixes:
            skill = re.sub(s, "", skill, flags=re.IGNORECASE).strip()

        # Удаление версий
        skill = self.VERSION_PATTERN.sub('', skill)

        # Очистка пунктуации, но не без удаления + # . /
        skill = self.PUNCT_PATTERN.sub('', skill)
        skill = re.sub(r'\s+', ' ', skill).strip()

        # Проверка навыка в словаре
        if skill in self.CANONICAL_MAP:
            return self.CANONICAL_MAP[skill]

        # Лемматизация
        skill = self.lemmatize_ru(skill)
        skill = skill.lower()

        return self.CANONICAL_MAP.get(skill, skill)
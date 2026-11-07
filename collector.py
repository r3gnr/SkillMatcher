import requests
from typing import List, Dict, Any, Optional
import time
import os
import dotenv

dotenv.load_dotenv()

HH_API_URL = os.getenv("HH_API_URL", "https://api.hh.ru/vacancies")
USER_AGENT = os.getenv("HH_USER_AGENT", "SkillMatcher/1.0 (contact@example.com)")
ACCESS_TOKEN = os.getenv("HH_ACCESS_TOKEN")

if not ACCESS_TOKEN:
    raise ValueError("Не найден HH_ACCESS_TOKEN. Пожалуйста, создайте файл .env и укажите его там.")

class HHCollector:
    """
    Класс для сбора вакансий с API HeadHunter.
    """

    def __init__(
        self,
        access_token: str = ACCESS_TOKEN,
        per_page: int = 20,
        timeout: int = 10
    ):
        self.per_page = per_page
        self.timeout = timeout

        self.headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {access_token}"
        }

        self._it_role_ids = self._load_it_roles()

    def collect(
            self,
            query: str,
            limit: int = 50,
            area: Optional[int] = None,
            progress_callback=None
    ) -> List[Dict[str, Any]]:

        collected = []
        page = 0

        while len(collected) < limit:
            params = {
                "text": query,
                "per_page": self.per_page,
                "page": page,
                "experience": "noExperience",
                "professional_role": self._it_role_ids
            }

            if area:
                params["area"] = area

            response = requests.get(
                HH_API_URL,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            time.sleep(0.25)

            if response.status_code == 429:
                time.sleep(5)
                continue

            if response.status_code != 200:
                raise RuntimeError(
                    f"HH API error: {response.status_code} - {response.text}"
                )
            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                if len(collected) >= limit:
                    break

                vacancy_data = self._fetch_full_vacancy(item["id"])
                time.sleep(0.25)
                if vacancy_data:
                    collected.append(vacancy_data)

                    if progress_callback:
                        progress = int(len(collected) / limit * 100)
                        progress_callback(progress)

            page += 1

        return collected

    def _fetch_full_vacancy(self, vacancy_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение полной информации по вакансии.
        """
        url = f"{HH_API_URL}/{vacancy_id}"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout
        )

        if response.status_code != 200:
            return None

        data = response.json()

        return {
            "id": data.get("id"),
            "title": data.get("name"),
            "company": data.get("employer", {}).get("name"),
            "description": data.get("description") or "",
            "key_skills": [s["name"] for s in data.get("key_skills", [])],
            "area": data.get("area", {}).get("name"),
            "published_at": data.get("published_at"),
        }

    def get_areas(self):
        url = "https://api.hh.ru/areas"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            return []

        return resp.json()

    def _load_it_roles(self):
        resp = requests.get(
            'https://api.hh.ru/professional_roles',
            headers=self.headers,
            timeout=self.timeout
        )
        if resp.status_code != 200:
            return []

        categories = resp.json().get('categories', [])
        for cat in categories:
            if "Информационные технологии" in cat.get('name', ''):
                return [role['id'] for role in cat.get('roles', [])]
        return []
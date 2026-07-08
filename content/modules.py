# Метаданные курса — модули, уроки, порядок шагов.
# Тексты шагов хранятся в content/steps/{module_id}/{lesson_id}.md
# Практики хранятся в content/steps/{module_id}/{lesson_id}.practice.md
# Загрузка и конвертация через content/md_loader.py

MODULES = [
    # ══════════════════════════════════════════════════════════════════════════
    # ВВОДНЫЙ МОДУЛЬ
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "module_00",
        "title": "Вводный модуль",
        "intro": (
            "*Вводный модуль*\n\n"
            "Один урок о том, зачем дизайнеру понимать веб — и что будет в этом курсе."
        ),
        "lessons": [
            {
                "id": "lesson_01",
                "title": "О курсе",
                "steps": [{}, {}],
                "practice": [],
                "finish_image": "AgACAgIAAxkBAAIBPWoQLcMUF0vr6EhxiTwNARKaBJ5sAAL3G2sbGu2ASKF5stlm6B5KAQADAgADeAADOwQ"
            }
        ]
    },

    # ══════════════════════════════════════════════════════════════════════════
    # МОДУЛЬ 1. КАК УСТРОЕН ВЕБ
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "module_01",
        "title": "Модуль 1. Как устроен веб",
        "intro_image": "AgACAgIAAxkBAAP0ahAR4Kv4kGFUVYUv1qiNRiHgHUIAAiIbaxsa7YBIzN2eXOr_hmEBAAMCAAN5AAM7BA",
        "intro": (
            "*Модуль 1. Как устроен веб*\n\n"
            "Четыре урока о том, как устроен веб изнутри:\n"
            "— Как работает интернет: клиент-серверная архитектура, IP, DNS, хостинг\n"
            "— Как браузер строит страницу из файлов\n"
            "— Анатомия сайта и основы UX\n"
            "— Веб-аналитика и пользовательские исследования\n\n"
            "После первых двух уроков — небольшая практика."
        ),
        "lessons": [
            {
                "id": "lesson_01",
                "title": "Урок 1. Как устроен интернет",
                "steps": [{}, {}, {}],
                "practice": [],
                "practice_image": "AgACAgIAAxkBAAP8ahASKVGIvTOgESCzpSgqG-5KvZcAAiobaxsa7YBI6WApSn2XF5sBAAMCAAN4AAM7BA",
                "finish_image": "AgACAgIAAxkBAAP-ahASMbgWotWZCwa9-2IuuHU22d8AAi8baxsa7YBIvPcTaNasT-0BAAMCAAN4AAM7BA"
            },
            {
                "id": "lesson_02",
                "title": "Урок 2. Как браузер строит страницу",
                "steps": [{}, {}, {}, {}],
                "practice": [],
                "practice_image": "AgACAgIAAxkBAAIBCGoQEmNkgB4xgr1EPC19oe4xQpVkAAI2G2sbGu2ASBaX8716FP7mAQADAgADeAADOwQ",
                "finish_image": "AgACAgIAAxkBAAIBCmoQEmshYxXZ57-fYE5tLwABWIpLeAACNxtrGxrtgEhK5cb1bZgmBAEAAwIAA3gAAzsE"
            },
            {
                "id": "lesson_03",
                "title": "Урок 3. Анатомия сайта и основы UX",
                "steps": [{}, {}, {}, {}, {}],
                "practice": []
            },
            {
                "id": "lesson_04",
                "title": "Урок 4. Веб-аналитика и исследования",
                "steps": [{}, {}, {}, {}, {}],
                "practice": []
            }
        ]
    },

    # ══════════════════════════════════════════════════════════════════════════
    # МОДУЛЬ 2. HTML
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "module_02",
        "title": "Модуль 2. HTML",
        "intro": (
            "*Модуль 2. HTML*\n\n"
            "_Тестовый режим_ — модуль в разработке.\n\n"
            "В этом модуле ты разберёшься, как устроен HTML изнутри: "
            "структура документа, текст и ссылки, таблицы, списки и изображения. "
            "Четыре урока — от DOCTYPE до первой сверстанной страницы."
        ),
        "lessons": [
            {
                "id": "lesson_01",
                "title": "Урок 5. Структура HTML-документа",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_02",
                "title": "Урок 6. Текст, заголовки и ссылки",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_03",
                "title": "Урок 7. Таблицы и списки",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_04",
                "title": "Урок 8. Изображения и другие элементы",
                "steps": [{}],
                "practice": []
            }
        ]
    },

    # ══════════════════════════════════════════════════════════════════════════
    # МОДУЛЬ 3. CSS И ОСНОВЫ ФРОНТЕНДА
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "module_03",
        "title": "Модуль 3. CSS и основы фронтенда",
        "intro": (
            "*Модуль 3. CSS и основы фронтенда*\n\n"
            "_Тестовый режим_ — модуль в разработке.\n\n"
            "Этот модуль про то, как HTML обретает визуальный вид. "
            "Четыре урока: от подключения стилей до flexbox и обзора современного фронтенда."
        ),
        "lessons": [
            {
                "id": "lesson_01",
                "title": "Урок 9. Как работает CSS",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_02",
                "title": "Урок 10. Типографика и цвет в CSS",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_03",
                "title": "Урок 11. Блочная модель и позиционирование",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_04",
                "title": "Урок 12. Современный фронтенд",
                "steps": [{}],
                "practice": []
            }
        ]
    },

    # ══════════════════════════════════════════════════════════════════════════
    # МОДУЛЬ 4. UX/UI И ПРОЕКТИРОВАНИЕ
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "module_04",
        "title": "Модуль 4. UX/UI и проектирование",
        "intro": (
            "*Модуль 4. UX/UI и проектирование*\n\n"
            "_Тестовый режим_ — модуль в разработке.\n\n"
            "Финальный модуль курса — про дизайн как профессию. "
            "Десять уроков: от принципов UX до итоговой практической работы."
        ),
        "lessons": [
            {
                "id": "lesson_01",
                "title": "Урок 13. Принципы UX",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_02",
                "title": "Урок 14. Дизайн-процесс",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_03",
                "title": "Урок 15. Процесс проектирования",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_04",
                "title": "Урок 16. Конструкторы сайтов",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_05",
                "title": "Урок 17. Figma — продвинутая работа",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_06",
                "title": "Урок 18. UI-киты и дизайн-системы",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_07",
                "title": "Урок 19. Адаптивный дизайн",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_08",
                "title": "Урок 20. Композиция и иерархия",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_09",
                "title": "Урок 21. Анимация и прототипирование",
                "steps": [{}],
                "practice": []
            },
            {
                "id": "lesson_10",
                "title": "Урок 22. Итоговая практическая работа",
                "steps": [{}],
                "practice": []
            }
        ]
    }
]


def get_module(module_id: str) -> dict | None:
    """Возвращает модуль по его ID"""
    for module in MODULES:
        if module["id"] == module_id:
            return module
    return None


def get_lesson(module_id: str, lesson_id: str) -> dict | None:
    """Возвращает урок по ID модуля и ID урока"""
    module = get_module(module_id)
    if not module:
        return None
    for lesson in module["lessons"]:
        if lesson["id"] == lesson_id:
            return lesson
    return None


def get_next_lesson(module_id: str, lesson_id: str) -> tuple[str, str] | None:
    """
    Возвращает (module_id, lesson_id) следующего урока.
    Если уроки в модуле кончились — переходит к первому уроку следующего модуля.
    Если модули кончились — возвращает None (курс пройден).
    """
    module = get_module(module_id)
    if not module:
        return None

    lesson_ids = [l["id"] for l in module["lessons"]]

    if lesson_id in lesson_ids:
        idx = lesson_ids.index(lesson_id)
        if idx + 1 < len(lesson_ids):
            return (module_id, lesson_ids[idx + 1])

    module_ids = [m["id"] for m in MODULES]
    if module_id in module_ids:
        m_idx = module_ids.index(module_id)
        if m_idx + 1 < len(module_ids):
            next_module = MODULES[m_idx + 1]
            return (next_module["id"], next_module["lessons"][0]["id"])

    return None


def is_last_lesson_of_module(module_id: str, lesson_id: str) -> bool:
    """Проверяет, является ли урок последним в модуле"""
    module = get_module(module_id)
    if not module:
        return False
    return module["lessons"][-1]["id"] == lesson_id

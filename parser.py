import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ============================================================
# НАСТРОЙКИ
# ============================================================

# --- ОГЭ ---
# SOURCE_URL = "https://math100.ru/trenirovochnie-varianti-oge-new/"

# --- ЕГЭ профильный ---
# SOURCE_URL = "https://math100.ru/prof-var/"

# --- ЕГЭ СтатГрад профильный ---
# SOURCE_URL = "https://math100.ru/egeprofil-statgrad/"

# --- ЕГЭ СтатГрад базовый ---
# SOURCE_URL = "https://math100.ru/statgrad-baza/"

# --- Другие варианты ---

# Конкретный вариант
SOURCE_URL = "https://math100.ru/variant-ege-prof-335/"

OUTPUT_DIR = "pdf"

REQUEST_DELAY = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


def download_file(url, filepath):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        ""
    )

    if "pdf" not in content_type.lower():
        print(
            f"  ⚠️ Неожиданный Content-Type: "
            f"{content_type}"
        )

    with open(filepath, "wb") as file:
        file.write(response.content)


def get_exam_name(url):
    url = url.lower()

    # ЕГЭ
    if "prof-var" in url:
        return "ЕГЭ"

    if "variant-ege-prof-" in url:
        return "ЕГЭ"

    if "egeprofil-statgrad-" in url:
        return "ЕГЭ"

    if "baza-statgrad-" in url:
        return "ЕГЭ"

    # ОГЭ
    if "oge-var-" in url:
        return "ОГЭ"

    if "trenirovochnie-varianti-oge" in url:
        return "ОГЭ"

    return None


def get_filename(page_url):
    path = page_url.rstrip("/")

    slug = path.split("/")[-1]

    exam_name = get_exam_name(page_url)

    if exam_name:

        number_match = re.search(
            r"(\d+)",
            slug
        )

        if number_match:
            number = number_match.group(1)

            return (
                f"{exam_name}_{number}.pdf"
            )

    return f"{slug}.pdf"


def get_pdf_url(page_url):
    html = get_page(page_url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    iframe = soup.select_one(
        "iframe.m100-pdf__fallback-frame"
    )

    if not iframe:
        return None

    pdf_url = iframe.get("src")

    if not pdf_url:
        return None

    return urljoin(
        page_url,
        pdf_url
    )


def get_variant_links(section_url):
    html = get_page(section_url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = []

    for a in soup.find_all("a", href=True):

        full_url = urljoin(
            section_url,
            a["href"]
        )

        # ОГЭ
        if re.search(
                r"/oge-var-\d+/?$",
                full_url
        ):
            if full_url not in links:
                links.append(full_url)

            continue

        # ЕГЭ профиль
        if re.search(
                r"/variant-ege-prof-\d+/?$",
                full_url
        ):
            if full_url not in links:
                links.append(full_url)

            continue

        # ЕГЭ профиль СтатГрад
        if re.search(
                r"/egeprofil-statgrad-[^/]+/?$",
                full_url
        ):
            if full_url not in links:
                links.append(full_url)

            continue

        # ЕГЭ база СтатГрад
        if re.search(
                r"/baza-statgrad-[^/]+/?$",
                full_url
        ):
            if full_url not in links:
                links.append(full_url)

            continue

    return links


def download_variant(page_url):
    print()
    print(
        f"Открываем:\n"
        f"{page_url}"
    )

    try:
        pdf_url = get_pdf_url(
            page_url
        )

        if not pdf_url:
            print(
                "  ❌ PDF не найден"
            )

            return False

        filename = get_filename(
            page_url
        )

        os.makedirs(
            OUTPUT_DIR,
            exist_ok=True
        )

        filepath = os.path.join(
            OUTPUT_DIR,
            filename
        )

        if os.path.exists(filepath):
            print(
                f"  ⏭ Уже существует: "
                f"{filepath}"
            )

            return True

        print(
            f"  PDF:\n"
            f"  {pdf_url}"
        )

        download_file(
            pdf_url,
            filepath
        )

        print(
            f"  ✓ Сохранён:\n"
            f"  {filepath}"
        )

        return True

    except Exception as e:

        print(
            f"  ❌ Ошибка: {e}"
        )

        return False


def download_section(section_url):
    print()
    print("=" * 60)
    print("РАЗДЕЛ")
    print("=" * 60)

    print(
        f"URL:\n"
        f"{section_url}"
    )

    try:

        variant_links = get_variant_links(
            section_url
        )

    except Exception as e:

        print()
        print(
            f"❌ Не удалось получить список "
            f"вариантов:\n{e}"
        )

        return

    print()
    print(
        f"Найдено вариантов: "
        f"{len(variant_links)}"
    )

    if not variant_links:
        print(
            "⚠️ Варианты не найдены."
        )

        return

    for index, variant_url in enumerate(
            variant_links,
            start=1
    ):
        print()
        print(
            f"[{index}/{len(variant_links)}]"
        )

        download_variant(
            variant_url
        )

        time.sleep(
            REQUEST_DELAY
        )


def is_single_variant(url):
    path = url.rstrip("/").lower()

    patterns = [
        r"/oge-var-\d+$",
        r"/variant-ege-prof-\d+$",
        r"/egeprofil-statgrad-[^/]+$",
        r"/baza-statgrad-[^/]+$",
        r"/nov\d+$",
    ]

    return any(
        re.search(pattern, path)
        for pattern in patterns
    )


def main():
    print()
    print("=" * 60)
    print("MATH100 PDF DOWNLOADER")
    print("=" * 60)

    print(
        f"Источник:\n"
        f"{SOURCE_URL}"
    )

    if is_single_variant(
            SOURCE_URL
    ):

        print()
        print(
            "Режим: одиночный вариант"
        )

        download_variant(
            SOURCE_URL
        )

    else:

        print()
        print(
            "Режим: раздел"
        )

        download_section(
            SOURCE_URL
        )

    print()
    print("=" * 60)
    print("Готово")
    print("=" * 60)


# ============================================================

if __name__ == "__main__":
    main()

import re
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


REQUEST_TIMEOUT = 30

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
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.text


def get_exam_name(url):
    url = url.lower()

    if (
        "prof-var" in url
        or "variant-ege-prof-" in url
        or "variant-ege-baza-" in url
        or "egeprofil-statgrad-" in url
        or "baza-statgrad-" in url
    ):
        return "ЕГЭ"

    if (
        "oge-var-" in url
        or "trenirovochnie-varianti-oge" in url
    ):
        return "ОГЭ"

    return None


def is_single_variant(url):
    path = url.rstrip("/").lower()

    patterns = [
        r"/oge-var-\d+$",
        r"/variant-ege-prof-\d+$",
        r"/variant-ege-baza-\d+$",
        r"/egeprofil-statgrad-[^/]+$",
        r"/baza-statgrad-[^/]+$",
        r"/nov\d+$",
    ]

    return any(
        re.search(pattern, path)
        for pattern in patterns
    )


def get_variant_links(section_url):
    html = get_page(section_url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = []

    for a in soup.find_all(
        "a",
        href=True
    ):
        full_url = urljoin(
            section_url,
            a["href"]
        )

        patterns = [
            r"/oge-var-\d+/?$",
            r"/variant-ege-prof-\d+/?$",
            r"/variant-ege-baza-\d+/?$",
            r"/egeprofil-statgrad-[^/]+/?$",
            r"/baza-statgrad-[^/]+/?$",
        ]

        if any(
            re.search(pattern, full_url)
            for pattern in patterns
        ):
            if full_url not in links:
                links.append(full_url)

    return links


def get_pdf_url(page_url):
    html = get_page(page_url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    iframe = soup.find(
        "iframe",
        class_="m100-pdf__fallback-frame"
    )

    if not iframe:
        raise RuntimeError(
            "На странице не найден PDF iframe"
        )

    src = iframe.get("src")

    if not src:
        raise RuntimeError(
            "У PDF iframe отсутствует src"
        )

    return urljoin(
        page_url,
        src
    )


def get_filename(page_url):
    slug = page_url.rstrip("/").split("/")[-1]
    exam_name = get_exam_name(page_url)

    if exam_name:
        number_match = re.search(
            r"(\d+)",
            slug
        )

        if number_match:
            return (
                f"{exam_name}_"
                f"{number_match.group(1)}.pdf"
            )

    return f"{slug}.pdf"


def download_file(
    url,
    destination,
    stop_event=None,
    progress_callback=None
):
    destination = Path(destination)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_file = destination.with_suffix(
        destination.suffix + ".part"
    )

    try:
        with requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            stream=True
        ) as response:

            response.raise_for_status()

            total_size = int(
                response.headers.get(
                    "content-length",
                    0
                )
            )

            downloaded = 0

            with open(
                temp_file,
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=64 * 1024
                ):
                    if (
                        stop_event
                        and stop_event.is_set()
                    ):
                        return False

                    if not chunk:
                        continue

                    file.write(chunk)
                    downloaded += len(chunk)

                    if (
                        progress_callback
                        and total_size > 0
                    ):
                        progress_callback(
                            downloaded / total_size * 100
                        )

        if (
            stop_event
            and stop_event.is_set()
        ):
            return False

        temp_file.replace(destination)

        return True

    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass

        raise

    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


class Math100Downloader:

    def __init__(self, root):
        self.root = root

        self.root.title(
            "Math100 PDF Downloader"
        )

        self.root.geometry(
            "800x650"
        )

        self.root.minsize(
            700,
            550
        )

        self.stop_event = threading.Event()
        self.download_thread = None
        self.help_window = None

        self.create_widgets()

    def create_widgets(self):
        main = ttk.Frame(
            self.root,
            padding=15
        )

        main.pack(
            fill="both",
            expand=True
        )

        url_label_frame = ttk.Frame(main)

        url_label_frame.pack(
            fill="x"
        )

        ttk.Label(
            url_label_frame,
            text="Ссылка на раздел или конкретный вариант:"
        ).pack(
            side="left"
        )

        ttk.Button(
            url_label_frame,
            text="?",
            width=3,
            command=self.show_help
        ).pack(
            side="left",
            padx=(7, 0)
        )

        self.url_entry = ttk.Entry(
            main
        )

        self.url_entry.pack(
            fill="x",
            pady=(5, 15)
        )

        ttk.Label(
            main,
            text="Папка для сохранения:"
        ).pack(
            anchor="w"
        )

        folder_frame = ttk.Frame(main)

        folder_frame.pack(
            fill="x",
            pady=(5, 15)
        )

        self.folder_var = tk.StringVar(
            value=str(
                Path.cwd() / "pdf"
            )
        )

        self.folder_entry = ttk.Entry(
            folder_frame,
            textvariable=self.folder_var
        )

        self.folder_entry.pack(
            side="left",
            fill="x",
            expand=True
        )

        ttk.Button(
            folder_frame,
            text="Выбрать...",
            command=self.choose_folder
        ).pack(
            side="left",
            padx=(10, 0)
        )

        buttons_frame = ttk.Frame(main)

        buttons_frame.pack(
            fill="x",
            pady=(0, 15)
        )

        self.download_button = ttk.Button(
            buttons_frame,
            text="СКАЧАТЬ",
            command=self.start_download
        )

        self.download_button.pack(
            side="left"
        )

        self.stop_button = ttk.Button(
            buttons_frame,
            text="ОСТАНОВИТЬ",
            command=self.stop_download,
            state="disabled"
        )

        self.stop_button.pack(
            side="left",
            padx=(10, 0)
        )

        self.progress = ttk.Progressbar(
            main,
            orient="horizontal",
            mode="determinate",
            maximum=100
        )

        self.progress.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            main,
            text="Лог:"
        ).pack(
            anchor="w"
        )

        self.log = ScrolledText(
            main,
            height=20,
            wrap="word"
        )

        self.log.pack(
            fill="both",
            expand=True,
            pady=(5, 0)
        )

        self.url_entry.bind(
            "<KeyPress>",
            self.handle_keypress
        )

        self.folder_entry.bind(
            "<KeyPress>",
            self.handle_keypress
        )

    def show_help(self):
        if (
            self.help_window
            and self.help_window.winfo_exists()
        ):
            self.help_window.lift()
            self.help_window.focus_force()
            return

        self.help_window = tk.Toplevel(
            self.root
        )

        self.help_window.title(
            "Поддерживаемые разделы"
        )

        self.help_window.geometry(
            "650x350"
        )

        self.help_window.resizable(
            False,
            False
        )

        self.help_window.transient(
            self.root
        )

        frame = ttk.Frame(
            self.help_window,
            padding=15
        )

        frame.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            frame,
            text="Поддерживаемые разделы",
            font=("TkDefaultFont", 11, "bold")
        ).pack(
            anchor="w",
            pady=(0, 15)
        )

        sections = [
            (
                "ОГЭ ФИПИ",
                "Тренировочные варианты",
                "https://math100.ru/trenirovochnie-varianti-oge-new/"
            ),
            (
                "ЕГЭ",
                "Профиль - Тренировочные варианты",
                "https://math100.ru/prof-var/"
            ),
            (
                "ЕГЭ ФИПИ",
                "База",
                "https://math100.ru/baza-var/"
            ),
            (
                "ЕГЭ СтатГрад",
                "Профиль",
                "https://math100.ru/egeprofil-statgrad/"
            ),
            (
                "ЕГЭ СтатГрад",
                "База",
                "https://math100.ru/statgrad-baza/"
            ),
        ]

        for exam_name, description, url in sections:
            ttk.Label(
                frame,
                text=f"{exam_name} — {description}",
                font=("TkDefaultFont", 9, "bold")
            ).pack(
                anchor="w",
                pady=(5, 2)
            )

            link = tk.Label(
                frame,
                text=url,
                foreground="blue",
                cursor="hand2",
                anchor="w"
            )

            link.pack(
                anchor="w"
            )

            link.bind(
                "<Button-1>",
                lambda event, link_url=url: webbrowser.open(
                    link_url
                )
            )

            link.bind(
                "<Enter>",
                lambda event, widget=link: widget.config(
                    font=("TkDefaultFont", 9, "underline")
                )
            )

            link.bind(
                "<Leave>",
                lambda event, widget=link: widget.config(
                    font=("TkDefaultFont", 9)
                )
            )

        ttk.Button(
            frame,
            text="Закрыть",
            command=self.help_window.destroy
        ).pack(
            anchor="e",
            pady=(20, 0)
        )

    def handle_keypress(self, event):
        widget = event.widget

        if widget not in (
            self.url_entry,
            self.folder_entry
        ):
            return

        ctrl_pressed = bool(
            event.state & 0x4
        )

        is_paste = (
            event.keysym.lower() == "v"
            or event.char == "\x16"
        )

        is_copy = (
            event.keysym.lower() == "c"
            or event.char == "\x03"
        )

        is_cut = (
            event.keysym.lower() == "x"
            or event.char == "\x18"
        )

        is_select_all = (
            event.keysym.lower() == "a"
            or event.char == "\x01"
        )

        if ctrl_pressed and is_paste:
            try:
                clipboard_text = (
                    self.root.clipboard_get()
                )
            except tk.TclError:
                return "break"

            try:
                widget.delete(
                    "sel.first",
                    "sel.last"
                )
            except tk.TclError:
                pass

            widget.insert(
                "insert",
                clipboard_text
            )

            return "break"

        if ctrl_pressed and is_copy:
            try:
                selected_text = (
                    widget.selection_get()
                )
            except tk.TclError:
                return "break"

            self.root.clipboard_clear()
            self.root.clipboard_append(
                selected_text
            )

            return "break"

        if ctrl_pressed and is_cut:
            try:
                selected_text = (
                    widget.selection_get()
                )
            except tk.TclError:
                return "break"

            self.root.clipboard_clear()
            self.root.clipboard_append(
                selected_text
            )

            try:
                widget.delete(
                    "sel.first",
                    "sel.last"
                )
            except tk.TclError:
                pass

            return "break"

        if ctrl_pressed and is_select_all:
            widget.select_range(
                0,
                "end"
            )

            widget.icursor(
                "end"
            )

            return "break"

    def log_message(self, message):
        self.root.after(
            0,
            self._log_message,
            message
        )

    def _log_message(self, message):
        self.log.insert(
            "end",
            message + "\n"
        )

        self.log.see("end")

    def choose_folder(self):
        folder = filedialog.askdirectory()

        if folder:
            self.folder_var.set(folder)

    def update_progress(self, value):
        self.root.after(
            0,
            lambda: self.progress.configure(
                value=value
            )
        )

    def start_download(self):
        source_url = (
            self.url_entry.get().strip()
        )

        if not source_url:
            messagebox.showwarning(
                "Ошибка",
                "Вставьте ссылку."
            )
            return

        if not source_url.startswith(
            (
                "http://",
                "https://"
            )
        ):
            messagebox.showwarning(
                "Ошибка",
                "Ссылка должна начинаться с http:// или https://"
            )
            return

        output_folder = Path(
            self.folder_var.get().strip()
        )

        self.stop_event.clear()
        self.progress["value"] = 0

        self.log.delete(
            "1.0",
            "end"
        )

        self.download_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.download_thread = threading.Thread(
            target=self.download_worker,
            args=(
                source_url,
                output_folder
            ),
            daemon=True
        )

        self.download_thread.start()

    def stop_download(self):
        self.stop_event.set()

        self.log_message(
            "Остановка..."
        )

        self.stop_button.configure(
            state="disabled"
        )

    def download_worker(
        self,
        source_url,
        output_folder
    ):
        try:
            output_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            if is_single_variant(
                source_url
            ):
                self.log_message(
                    "Одиночный вариант."
                )

                self.log_message(
                    f"Страница: {source_url}"
                )

                if self.stop_event.is_set():
                    return

                pdf_url = get_pdf_url(
                    source_url
                )

                self.log_message(
                    f"PDF: {pdf_url}"
                )

                filename = get_filename(
                    source_url
                )

                destination = (
                    output_folder / filename
                )

                self.log_message(
                    f"Сохранение: {destination}"
                )

                success = download_file(
                    pdf_url,
                    destination,
                    self.stop_event,
                    self.update_progress
                )

                if success:
                    self.log_message(
                        f"Готово: {filename}"
                    )
                else:
                    self.log_message(
                        "Скачивание остановлено."
                    )

                return

            self.log_message(
                "Получение списка вариантов..."
            )

            variant_links = get_variant_links(
                source_url
            )

            if not variant_links:
                raise RuntimeError(
                    "Варианты на странице не найдены."
                )

            self.log_message(
                f"Найдено вариантов: "
                f"{len(variant_links)}"
            )

            total = len(
                variant_links
            )

            for index, variant_url in enumerate(
                variant_links,
                start=1
            ):
                if self.stop_event.is_set():
                    self.log_message(
                        "Остановка."
                    )
                    break

                self.log_message("")

                self.log_message(
                    f"[{index}/{total}] "
                    f"{variant_url}"
                )

                try:
                    pdf_url = get_pdf_url(
                        variant_url
                    )

                    filename = get_filename(
                        variant_url
                    )

                    destination = (
                        output_folder / filename
                    )

                    self.log_message(
                        f"PDF: {filename}"
                    )

                    success = download_file(
                        pdf_url,
                        destination,
                        self.stop_event,
                        self.update_progress
                    )

                    if success:
                        self.log_message(
                            "✓ Скачано"
                        )
                    else:
                        self.log_message(
                            "Остановлено."
                        )
                        break

                except Exception as error:
                    self.log_message(
                        f"✗ Ошибка: {error}"
                    )

                self.update_progress(0)

            if not self.stop_event.is_set():
                self.log_message("")
                self.log_message("Готово.")

        except Exception as error:
            self.log_message("")
            self.log_message(
                f"ОШИБКА: {error}"
            )

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Ошибка",
                    str(error)
                )
            )

        finally:
            self.root.after(
                0,
                self.download_finished
            )

    def download_finished(self):
        self.download_button.configure(
            state="normal"
        )

        self.stop_button.configure(
            state="disabled"
        )


def main():
    root = tk.Tk()

    Math100Downloader(root)

    root.mainloop()


if __name__ == "__main__":
    main()
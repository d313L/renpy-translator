import os
import threading
from tkinter import filedialog, Tk, messagebox, Toplevel, Label, Text, Button, END, StringVar, OptionMenu
from datetime import datetime
# Импортируем новые функции из extractor.py
from utils.extractor import extract_renpy_translatable_data, strip_tags, restore_tags 
from utils.replacer import replace_lines_in_rpy
from utils.deepl_translator import translate_single # Импортируем translate_single напрямую

# Добавление поддерживаемых DeepL языков
DEEPL_TARGET_LANGS = {
    "Русский": "RU", "English": "EN", "Болгарский": "BG", "Чешский": "CS",
    "Датский": "DA", "Немецкий": "DE", "Греческий": "EL", "Испанский": "ES",
    "Эстонский": "ET", "Финский": "FI", "Французский": "FR", "Венгерский": "HU",
    "Индонезийский": "ID", "Итальянский": "IT", "Японский": "JA", "Корейский": "KO",
    "Литовский": "LT", "Латышский": "LV", "Норвежский (Букмол)": "NB",
    "Нидерландский": "NL", "Польский": "PL", "Португальский": "PT",
    "Румынский": "RO", "Словацкий": "SK", "Словенский": "SL",
    "Шведский": "SV", "Турецкий": "TR", "Украинский": "UK", "Китайский (упр.)": "ZH"
}


def show_progress_window(root, text_var):
    win = Toplevel(root)
    win.title("Прогресс перевода")
    Label(win, textvariable=text_var, padx=20, pady=20).pack()
    win.geometry("450x120") # Увеличим размер для более длинного текста
    win.resizable(False, False)
    win.attributes('-topmost', True)
    win.protocol("WM_DELETE_WINDOW", lambda: None) # Делаем окно не закрываемым кнопкой X
    return win

def get_api_key_and_lang(root):
    result = {"key": "", "lang": "RU"} # Значение по умолчанию
    win = Toplevel(root)
    win.title("Настройки DeepL")
    win.geometry("500x250")
    win.resizable(False, False)
    win.attributes('-topmost', True)

    Label(win, text="Вставьте ваш DeepL API ключ:", pady=10).pack()
    textbox = Text(win, height=2, width=50)
    textbox.pack()
    textbox.focus_set()

    Label(win, text="Выберите целевой язык:", pady=10).pack()
    
    lang_var = StringVar(win)
    lang_var.set("Русский") # Значение по умолчанию
    lang_options = list(DEEPL_TARGET_LANGS.keys())
    option_menu = OptionMenu(win, lang_var, *lang_options)
    option_menu.pack()

    def confirm():
        result["key"] = textbox.get("1.0", END).strip()
        result["lang"] = DEEPL_TARGET_LANGS[lang_var.get()]
        win.destroy()

    Button(win, text="OK", command=confirm).pack(pady=10)
    root.wait_window(win)
    return result["key"], result["lang"]

def main():
    root = Tk()
    root.withdraw() # Скрываем основное окно Tkinter

    messagebox.showinfo("Переводчик Ren'Py", "Выберите папку с распакованной Ren'Py-игрой (.rpy файлы).")
    game_dir = filedialog.askdirectory(title="Выбор папки игры")
    if not game_dir:
        messagebox.showwarning("Отмена", "Папка не выбрана. Выход.")
        return

    api_key, target_lang = get_api_key_and_lang(root)
    if not api_key:
        messagebox.showwarning("Отмена", "Ключ не введён. Выход.")
        return

    status_text = StringVar()
    status_text.set("Инициализация...")
    progress_win = show_progress_window(root, status_text)
    root.update()

    def work():
        try:
            # 1. Создание папки для бэкапа
            backup_root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            current_backup_dir = os.path.join(backup_root_dir, f"backup_{timestamp}")
            os.makedirs(current_backup_dir, exist_ok=True)
            root.after(0, status_text.set, f"Создание резервной копии в: {os.path.basename(current_backup_dir)}...")
            
            # 2. Извлечение строк из всех .rpy файлов
            root.after(0, status_text.set, "Извлечение строк для перевода...")
            
            all_extracted_data = [] # Список всех извлеченных элементов со всех файлов
            extracted_data_per_file = {} # Словарь {путь_к_файлу: список_извлеченных_данных_из_этого_файла}

            rpy_files_found = []
            for root_dir, _, files in os.walk(game_dir):
                for file in files:
                    if file.endswith(".rpy"):
                        rpy_files_found.append(os.path.join(root_dir, file))
            
            if not rpy_files_found:
                root.after(0, lambda: [progress_win.destroy(),
                    messagebox.showinfo("Нет файлов", "В выбранной папке не найдено .rpy файлов.")])
                return

            total_lines_to_translate = 0
            for rpy_file_path in rpy_files_found:
                root.after(0, status_text.set, f"Обработка файла: {os.path.basename(rpy_file_path)}...")
                try:
                    with open(rpy_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                    
                    extracted_for_file = extract_renpy_translatable_data(file_content)
                    if extracted_for_file:
                        # Добавляем путь к файлу в каждый элемент для replacer
                        for item in extracted_for_file:
                            item['file_path'] = rpy_file_path
                        all_extracted_data.extend(extracted_for_file)
                        extracted_data_per_file[rpy_file_path] = extracted_for_file
                        total_lines_to_translate += len(extracted_for_file)
                except Exception as e:
                    print(f"Ошибка при извлечении из файла {rpy_file_path}: {e}")
                    # Продолжаем, но можно добавить в лог ошибок

            if not all_extracted_data:
                root.after(0, lambda: [progress_win.destroy(),
                    messagebox.showinfo("Нет строк", "В .rpy файлах не найдено строк для перевода.")])
                return

            # 3. Перевод строк
            translations_map = {} # Словарь {очищенный_оригинальный_текст: переведенный_текст_с_тегами}
            error_log_entries = [] # Для более детального лога ошибок перевода
            
            for i, item in enumerate(all_extracted_data, 1):
                text_to_translate_cleaned = item['text_to_translate']
                tag_mapping = item['tag_mapping']
                original_line_preview = item['original_line'].strip()[:70] + "..." if len(item['original_line'].strip()) > 70 else item['original_line'].strip()

                root.after(0, status_text.set, f"Перевод {i}/{total_lines_to_translate}:\n'{original_line_preview}'")
                root.update_idletasks() # Обновляем GUI немедленно
                
                translated_text_with_tags = translate_single(text_to_translate_cleaned, api_key, tag_mapping, target_lang=target_lang)
                
                translations_map[text_to_translate_cleaned] = translated_text_with_tags
                if translated_text_with_tags == "[ОШИБКА ПЕРЕВОДА]":
                    error_log_entries.append(f"Ошибка перевода строки (файл: {os.path.basename(item['file_path'])}, строка: {item['line_number']}):\nОригинал: {item['original_line'].strip()}\nТекст для перевода: {text_to_translate_cleaned}\nПеревод: {translated_text_with_tags}\n")

            # 4. Замена строк
            root.after(0, status_text.set, "Замена строк в файлах Ren'Py и создание бэкапов...")
            replace_lines_in_rpy(game_dir, extracted_data_per_file, translations_map, backup_dir=current_backup_dir)

            # 5. Сохранение лога
            logname = f"лог_перевода_{timestamp}.txt"
            fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), logname)
            with open(fullpath, "w", encoding="utf-8") as f:
                f.write(f"--- Лог перевода Ren'Py игры ---\n")
                f.write(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Папка игры: {game_dir}\n")
                f.write(f"Целевой язык: {target_lang}\n")
                f.write(f"Всего строк для перевода: {total_lines_to_translate}\n")
                f.write(f"Местоположение резервной копии: {current_backup_dir}\n\n")
                
                f.write("--- Детали перевода ---\n\n")
                for item in all_extracted_data:
                    original_text_cleaned = item['text_to_translate']
                    translated_text = translations_map.get(original_text_cleaned, "[ПЕРЕВОД НЕ НАЙДЕН]")
                    f.write(f"Файл: {os.path.basename(item['file_path'])}, Строка: {item['line_number']}\n")
                    f.write(f"Оригинал (полная строка): {item['original_line'].strip()}\n")
                    f.write(f"Оригинал (для перевода): {original_text_cleaned}\n")
                    f.write(f"Перевод (с тегами): {translated_text}\n\n")
                
                if error_log_entries:
                    f.write("\n--- Ошибки перевода ---\n\n")
                    for entry in error_log_entries:
                        f.write(entry + "\n")

            root.after(0, lambda: [progress_win.destroy(),
                messagebox.showinfo("Готово", f"Перевод завершён. Лог: {logname}\nРезервная копия: {os.path.basename(current_backup_dir)}")])
        except Exception as e:
            root.after(0, lambda: [progress_win.destroy(),
                messagebox.showerror("Ошибка", f"Произошла непредвиденная ошибка: {e}")])
            import traceback
            traceback.print_exc() # Вывод полного traceback в консоль для отладки

    threading.Thread(target=work).start()
    root.mainloop()

if __name__ == "__main__":
    main()
import os
import threading
from tkinter import filedialog, Tk, messagebox, Toplevel, Label, Text, Button, END, StringVar, OptionMenu
from datetime import datetime
import tempfile
import shutil
# Импортируем новые функции из extractor.py
from utils.extractor import extract_renpy_translatable_data, strip_tags, restore_tags 
from utils.replacer import replace_lines_in_rpy
from utils.deepl_translator import translate_single # Импортируем translate_single напрямую
from utils.extract_rpa import extract_rpa
from utils.game_detector import detect_game_structure, should_translate_file

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

def extract_rpa_archives(game_dir, temp_dir, status_callback):
    """Извлечение всех .rpa архивов в временную папку"""
    extracted_count = 0
    
    for file in os.listdir(game_dir):
        if file.endswith('.rpa'):
            rpa_path = os.path.join(game_dir, file)
            status_callback(f"Распаковка архива: {file}...")
            
            try:
                files_extracted = extract_rpa(rpa_path, temp_dir)
                extracted_count += files_extracted
                print(f"Извлечено {files_extracted} файлов из {file}")
            except Exception as e:
                print(f"Ошибка при извлечении {file}: {e}")
                status_callback(f"Ошибка при распаковке {file}: {e}")
    
    return extracted_count

def main():
    root = Tk()
    root.withdraw() # Скрываем основное окно Tkinter

    messagebox.showinfo("Переводчик Ren'Py", "Выберите папку с Ren'Py-игрой (с .rpy файлами или .rpa архивами).")
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
        temp_dir = None
        try:
            # 1. Определяем структуру игры
            root.after(0, status_text.set, "Анализ структуры игры...")
            game_structure = detect_game_structure(game_dir)
            
            working_dir = game_dir
            is_temp_dir = False
            
            # 2. Если найдены .rpa архивы, распаковываем их
            if game_structure['has_rpa']:
                root.after(0, status_text.set, "Обнаружены .rpa архивы. Распаковка...")
                temp_dir = tempfile.mkdtemp(prefix="renpy_translator_")
                is_temp_dir = True
                
                def status_callback(msg):
                    root.after(0, status_text.set, msg)
                
                extracted_count = extract_rpa_archives(game_dir, temp_dir, status_callback)
                
                if extracted_count == 0:
                    root.after(0, lambda: [progress_win.destroy(),
                        messagebox.showwarning("Ошибка", "Не удалось извлечь файлы из .rpa архивов.")])
                    return
                
                working_dir = temp_dir
                root.after(0, status_text.set, f"Распаковано {extracted_count} файлов.")
            
            # 3. Создание папки для бэкапа
            backup_root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            current_backup_dir = os.path.join(backup_root_dir, f"backup_{timestamp}")
            os.makedirs(current_backup_dir, exist_ok=True)
            root.after(0, status_text.set, f"Создание резервной копии в: {os.path.basename(current_backup_dir)}...")
            
            # 4. Поиск и фильтрация .rpy файлов
            root.after(0, status_text.set, "Поиск .rpy файлов для перевода...")
            
            all_rpy_files = []
            for root_dir, _, files in os.walk(working_dir):
                for file in files:
                    if file.endswith(".rpy"):
                        all_rpy_files.append(os.path.join(root_dir, file))
            
            if not all_rpy_files:
                root.after(0, lambda: [progress_win.destroy(),
                    messagebox.showinfo("Нет файлов", "В выбранной папке не найдено .rpy файлов.")])
                return
            
            # Фильтрация файлов - оставляем только те, что содержат переводимый текст
            translatable_files = []
            skipped_files = []
            
            for rpy_file_path in all_rpy_files:
                file_name = os.path.basename(rpy_file_path)
                root.after(0, status_text.set, f"Анализ файла: {file_name}...")
                
                if should_translate_file(rpy_file_path):
                    translatable_files.append(rpy_file_path)
                else:
                    skipped_files.append(rpy_file_path)
            
            root.after(0, status_text.set, f"Найдено файлов для перевода: {len(translatable_files)}, пропущено: {len(skipped_files)}")
            
            if not translatable_files:
                root.after(0, lambda: [progress_win.destroy(),
                    messagebox.showinfo("Нет файлов", "Не найдено .rpy файлов с переводимым текстом.")])
                return
            
            # 5. Извлечение строк из отфильтрованных .rpy файлов
            root.after(0, status_text.set, "Извлечение строк для перевода...")
            
            all_extracted_data = [] # Список всех извлеченных элементов со всех файлов
            extracted_data_per_file = {} # Словарь {путь_к_файлу: список_извлеченных_данных_из_этого_файла}

            total_lines_to_translate = 0
            for rpy_file_path in translatable_files:
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

            # 6. Перевод строк
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

            # 7. Определяем целевую папку для сохранения переведённых файлов
            if is_temp_dir:
                # Если работали с .rpa, создаём папку для переведённых файлов
                translated_dir = os.path.join(game_dir, f"translated_{timestamp}")
                os.makedirs(translated_dir, exist_ok=True)
                
                # Копируем структуру папок и переведённые файлы
                root.after(0, status_text.set, "Копирование переведённых файлов...")
                
                for rpy_file_path in extracted_data_per_file.keys():
                    relative_path = os.path.relpath(rpy_file_path, working_dir)
                    target_path = os.path.join(translated_dir, relative_path)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # Заменяем строки в временных файлах
                replace_lines_in_rpy(working_dir, extracted_data_per_file, translations_map, backup_dir=None)
                
                # Копируем переведённые файлы в целевую папку
                for rpy_file_path in extracted_data_per_file.keys():
                    relative_path = os.path.relpath(rpy_file_path, working_dir)
                    target_path = os.path.join(translated_dir, relative_path)
                    shutil.copy2(rpy_file_path, target_path)
                
                final_message = f"Перевод завершён.\nПереведённые файлы сохранены в: {os.path.basename(translated_dir)}"
            else:
                # Если работали с уже распакованной игрой
                root.after(0, status_text.set, "Замена строк в файлах Ren'Py и создание бэкапов...")
                replace_lines_in_rpy(working_dir, extracted_data_per_file, translations_map, backup_dir=current_backup_dir)
                final_message = f"Перевод завершён.\nРезервная копия: {os.path.basename(current_backup_dir)}"

            # 8. Сохранение лога
            logname = f"лог_перевода_{timestamp}.txt"
            fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), logname)
            with open(fullpath, "w", encoding="utf-8") as f:
                f.write(f"--- Лог перевода Ren'Py игры ---\n")
                f.write(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Исходная папка игры: {game_dir}\n")
                f.write(f"Структура игры: {'RPA архивы' if game_structure['has_rpa'] else 'Распакованные файлы'}\n")
                f.write(f"Целевой язык: {target_lang}\n")
                f.write(f"Всего .rpy файлов найдено: {len(all_rpy_files)}\n")
                f.write(f"Файлов для перевода: {len(translatable_files)}\n")
                f.write(f"Пропущено файлов: {len(skipped_files)}\n")
                f.write(f"Всего строк для перевода: {total_lines_to_translate}\n")
                if not is_temp_dir:
                    f.write(f"Местоположение резервной копии: {current_backup_dir}\n")
                f.write("\n")
                
                if skipped_files:
                    f.write("--- Пропущенные файлы (системные/без переводимого текста) ---\n")
                    for skipped_file in skipped_files:
                        f.write(f"{os.path.relpath(skipped_file, working_dir)}\n")
                    f.write("\n")
                
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
                messagebox.showinfo("Готово", f"{final_message}\nЛог: {logname}")])
                
        except Exception as e:
            root.after(0, lambda: [progress_win.destroy(),
                messagebox.showerror("Ошибка", f"Произошла непредвиденная ошибка: {e}")])
            import traceback
            traceback.print_exc() # Вывод полного traceback в консоль для отладки
        finally:
            # Очистка временных файлов
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print(f"Временная папка {temp_dir} удалена.")
                except Exception as e:
                    print(f"Не удалось удалить временную папку {temp_dir}: {e}")

    threading.Thread(target=work).start()
    root.mainloop()

if __name__ == "__main__":
    main()
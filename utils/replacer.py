import os
import shutil
import re
from utils.extractor import restore_tags

def replace_lines_in_rpy(directory, extracted_data_per_file, translations_map, backup_dir=None):
    if backup_dir:
        print(f"Создание резервных копий в: {backup_dir}")
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".rpy"):
                    src_path = os.path.join(root, file)
                    relative_path = os.path.relpath(src_path, directory)
                    dest_path = os.path.join(backup_dir, relative_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    try:
                        shutil.copy2(src_path, dest_path)
                    except Exception as e:
                        print(f"Ошибка при создании бэкапа файла {src_path}: {e}")
        print("Резервные копии созданы.")

    for rpy_file_path, extracted_items in extracted_data_per_file.items():
        try:
            with open(rpy_file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            updated_lines = list(lines)
            extracted_by_line_number = {item['line_number']: item for item in extracted_items}

            for line_num, original_line_content in enumerate(lines):
                if line_num in extracted_by_line_number:
                    item = extracted_by_line_number[line_num]
                    
                    original_cleaned_text = item['text_to_translate']
                    translated_text_with_tags = translations_map.get(
                        original_cleaned_text, 
                        f"[ОШИБКА ПЕРЕВОДА] {original_cleaned_text}"
                    )

                    # --- НОВАЯ УПРОЩЕННАЯ ЛОГИКА ЗАМЕНЫ ---

                    # 1. Получаем оригинальный текст (до удаления тегов) и тип кавычек из экстрактора.
                    original_text_from_extractor = item['original_text_with_tags']
                    quote_char = item['quote_char']

                    # 2. Экранируем кавычки в переведенном тексте, чтобы избежать синтаксических ошибок в Ren'Py.
                    # Например, если перевод "Он сказал "Привет!"", он станет "Он сказал \"Привет!\"".
                    escaped_translated_text = translated_text_with_tags.replace(quote_char, f'\\{quote_char}')

                    # 3. Собираем полную "старую" и "новую" часть строки для замены.
                    # Это включает в себя кавычки, обрамляющие текст.
                    old_part = f"{quote_char}{original_text_from_extractor}{quote_char}"
                    new_part = f"{quote_char}{escaped_translated_text}{quote_char}"
                    
                    # 4. Выполняем замену. Мы заменяем точную подстроку (оригинальный текст в кавычках)
                    # на новую подстроку (переведенный текст в кавычках).
                    # Это намного надежнее, чем предыдущая логика с re.search.
                    if old_part in original_line_content:
                        updated_lines[line_num] = original_line_content.replace(old_part, new_part, 1)
                    else:
                        # Fallback для _("...") функции
                        old_part_underscore = f'_({old_part})'
                        new_part_underscore = f'_({new_part})'
                        if old_part_underscore in original_line_content:
                             updated_lines[line_num] = original_line_content.replace(old_part_underscore, new_part_underscore, 1)
                        else:
                            print(f"Warning: Could not find exact string to replace in line {line_num}: '{original_line_content.strip()}'")
                            print(f"   Expected to find: {old_part} or {old_part_underscore}")


            with open(rpy_file_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

        except Exception as e:
            print(f"Ошибка при обработке файла {rpy_file_path}: {e}")
            import traceback
            traceback.print_exc()
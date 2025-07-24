"""
Утилита для анализа и тестирования переводчика Ren'Py
"""
import os
import sys
from game_detector import detect_game_structure, should_translate_file, analyze_rpy_files
from extractor import analyze_file_content, extract_renpy_translatable_data

def analyze_game_directory(game_dir):
    """
    Анализирует папку с игрой и выводит подробную статистику.
    
    Args:
        game_dir (str): Путь к папке с игрой
    """
    print(f"Анализ игры в папке: {game_dir}")
    print("=" * 50)
    
    # Определяем структуру игры
    structure = detect_game_structure(game_dir)
    
    print(f"Структура игры:")
    print(f"  - RPA архивы: {'Да' if structure['has_rpa'] else 'Нет'} ({len(structure['rpa_files'])} файлов)")
    print(f"  - RPY файлы: {'Да' if structure['has_rpy'] else 'Нет'} ({len(structure['rpy_files'])} файлов)")
    
    if structure['rpa_files']:
        print(f"\nНайденные RPA архивы:")
        for rpa_file in structure['rpa_files']:
            size_mb = os.path.getsize(rpa_file) / (1024 * 1024)
            print(f"  - {os.path.basename(rpa_file)} ({size_mb:.1f} MB)")
    
    if not structure['rpy_files']:
        print("\nНет RPY файлов для анализа.")
        return
    
    # Анализируем RPY файлы
    print(f"\nАнализ RPY файлов...")
    analysis = analyze_rpy_files(structure['rpy_files'])
    
    print(f"\nКлассификация файлов:")
    print(f"  - Для перевода: {len(analysis['translatable'])}")
    print(f"  - Системные: {len(analysis['system'])}")  
    print(f"  - Пустые/без текста: {len(analysis['empty'])}")
    
    # Подробная статистика по переводимым файлам
    if analysis['translatable']:
        print(f"\nПереводимые файлы:")
        total_strings = 0
        
        for file_path in analysis['translatable'][:10]:  # Показываем первые 10
            stats = analyze_file_content(file_path)
            if stats:
                filename = os.path.relpath(file_path, game_dir)
                print(f"  - {filename}: {stats['translatable_strings']} строк")
                total_strings += stats['translatable_strings']
        
        if len(analysis['translatable']) > 10:
            print(f"  ... и ещё {len(analysis['translatable']) - 10} файлов")
            
            # Подсчитываем общее количество строк
            for file_path in analysis['translatable'][10:]:
                stats = analyze_file_content(file_path)
                if stats:
                    total_strings += stats['translatable_strings']
        
        print(f"\nВсего строк для перевода: {total_strings}")
    
    # Системные файлы
    if analysis['system']:
        print(f"\nСистемные файлы (пропущены):")
        for file_path in analysis['system'][:5]:  # Показываем первые 5
            filename = os.path.relpath(file_path, game_dir)
            print(f"  - {filename}")
        if len(analysis['system']) > 5:
            print(f"  ... и ещё {len(analysis['system']) - 5} файлов")

def test_file_extraction(file_path):
    """
    Тестирует извлечение строк из конкретного файла.
    
    Args:
        file_path (str): Путь к .rpy файлу
    """
    print(f"Тест извлечения из файла: {os.path.basename(file_path)}")
    print("=" * 50)
    
    if not os.path.exists(file_path):
        print("Файл не найден!")
        return
    
    # Анализируем файл
    stats = analyze_file_content(file_path)
    if stats:
        print(f"Статистика файла:")
        print(f"  - Всего строк: {stats['total_lines']}")
        print(f"  - Строки кода: {stats['code_lines']}")
        print(f"  - Диалоги: {stats['dialogue_lines']}")
        print(f"  - Переводимые строки: {stats['translatable_strings']}")
        print(f"  - В основном код: {'Да' if stats['is_mostly_code'] else 'Нет'}")
    
    # Извлекаем строки
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        extracted = extract_renpy_translatable_data(content)
        
        print(f"\nИзвлечённые строки ({len(extracted)}):")
        for i, item in enumerate(extracted[:10], 1):  # Показываем первые 10
            original = item['original_text_with_tags'][:50]
            if len(item['original_text_with_tags']) > 50:
                original += "..."
            cleaned = item['text_to_translate'][:50]
            if len(item['text_to_translate']) > 50:
                cleaned += "..."
            
            print(f"  {i}. Строка {item['line_number']}:")
            print(f"     Оригинал: {original}")
            print(f"     Для перевода: {cleaned}")
            
            if item['tag_mapping']:
                print(f"     Теги: {list(item['tag_mapping'].keys())}")
            print()
        
        if len(extracted) > 10:
            print(f"  ... и ещё {len(extracted) - 10} строк")
            
    except Exception as e:
        print(f"Ошибка при извлечении: {e}")

def main():
    """Главная функция для запуска тестов"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python test_analyzer.py <путь_к_игре>")
        print("  python test_analyzer.py <путь_к_файлу.rpy> --file")
        return
    
    path = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == "--file":
        # Тест конкретного файла
        test_file_extraction(path)
    else:
        # Анализ игры
        if os.path.isdir(path):
            analyze_game_directory(path)
        else:
            print("Указанный путь не является папкой!")

if __name__ == "__main__":
    main()
import os
import re
from utils.extractor import extract_renpy_translatable_data

def detect_game_structure(game_dir):
    """
    Анализирует структуру игры и определяет, что содержится в папке.
    
    Returns:
        dict: {
            'has_rpa': bool,  # Есть ли .rpa архивы
            'has_rpy': bool,  # Есть ли .rpy файлы
            'rpa_files': list,  # Список найденных .rpa файлов
            'rpy_files': list   # Список найденных .rpy файлов
        }
    """
    structure = {
        'has_rpa': False,
        'has_rpy': False,
        'rpa_files': [],
        'rpy_files': []
    }
    
    # Проверяем содержимое основной папки
    for item in os.listdir(game_dir):
        item_path = os.path.join(game_dir, item)
        
        if item.endswith('.rpa') and os.path.isfile(item_path):
            structure['has_rpa'] = True
            structure['rpa_files'].append(item_path)
        elif item.endswith('.rpy') and os.path.isfile(item_path):
            structure['has_rpy'] = True
            structure['rpy_files'].append(item_path)
    
    # Также проверяем подпапки на наличие .rpy файлов
    for root, dirs, files in os.walk(game_dir):
        for file in files:
            if file.endswith('.rpy'):
                file_path = os.path.join(root, file)
                if file_path not in structure['rpy_files']:
                    structure['has_rpy'] = True
                    structure['rpy_files'].append(file_path)
    
    return structure

def is_system_file(file_path):
    """
    Определяет, является ли файл системным файлом Ren'Py, который не следует переводить.
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        bool: True если файл системный
    """
    filename = os.path.basename(file_path).lower()
    
    # Системные файлы Ren'Py обычно начинаются с числовых префиксов
    system_patterns = [
        r'^00.*\.rpy$',  # 00console.rpy, 00keymap.rpy и т.д.
        r'^01.*\.rpy$',  # 01init.rpy и т.д.
        r'^02.*\.rpy$',  # Системные файлы с префиксом 02
        r'^screens\.rpy$',  # screens.rpy - файл интерфейса
        r'^gui\.rpy$',  # gui.rpy - файл интерфейса
        r'^options\.rpy$',  # options.rpy - настройки игры
        r'^.*_ren\.py$',  # Файлы, созданные автоматически Ren'Py
    ]
    
    for pattern in system_patterns:
        if re.match(pattern, filename):
            return True
    
    return False

def contains_translatable_content(file_path, min_strings=1):
    """
    Проверяет, содержит ли файл переводимый контент.
    
    Args:
        file_path (str): Путь к файлу
        min_strings (int): Минимальное количество переводимых строк
        
    Returns:
        bool: True если файл содержит достаточно переводимого контента
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Используем существующую функцию извлечения
        extracted_data = extract_renpy_translatable_data(content)
        
        if not extracted_data:
            return False
        
        # Фильтруем очевидно технические строки
        meaningful_strings = []
        for item in extracted_data:
            text = item['text_to_translate'].strip()
            
            # Пропускаем очень короткие строки (возможно, технические)
            if len(text) < 2:
                continue
                
            # Пропускаем строки, состоящие только из символов/цифр
            if re.match(r'^[^\w\s]*$', text) or re.match(r'^\d+$', text):
                continue
                
            # Пропускаем очевидно технические строки
            technical_patterns = [
                r'^[a-zA-Z_][a-zA-Z0-9_]*$',  # Имена переменных
                r'^#.*',  # Комментарии
                r'^\$.*',  # Python код
                r'^[{}\[\]()]+$',  # Только скобки
                r'^[.,:;!?-]+$',  # Только знаки препинания
            ]
            
            is_technical = False
            for pattern in technical_patterns:
                if re.match(pattern, text):
                    is_technical = True
                    break
            
            if not is_technical:
                meaningful_strings.append(item)
        
        return len(meaningful_strings) >= min_strings
        
    except Exception as e:
        print(f"Ошибка при анализе файла {file_path}: {e}")
        return False

def should_translate_file(file_path):
    """
    Определяет, следует ли переводить данный файл.
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        bool: True если файл следует переводить
    """
    # Сначала проверяем, не является ли файл системным
    if is_system_file(file_path):
        return False
    
    # Затем проверяем, содержит ли файл переводимый контент
    if not contains_translatable_content(file_path):
        return False
    
    # Дополнительная проверка: анализируем содержимое файла
    try:
        from utils.extractor import analyze_file_content
        stats = analyze_file_content(file_path)
        
        if stats is None:
            return False
        
        # Если файл в основном состоит из кода и мало переводимых строк, пропускаем
        if stats['is_mostly_code'] and stats['translatable_strings'] < 3:
            return False
            
        # Если в файле есть хотя бы несколько переводимых строк, переводим
        return stats['translatable_strings'] >= 1
        
    except ImportError:
        # Если новый модуль недоступен, используем старую логику
        return contains_translatable_content(file_path)

def analyze_rpy_files(file_paths, progress_callback=None):
    """
    Анализирует список .rpy файлов и разделяет их на переводимые и системные.
    
    Args:
        file_paths (list): Список путей к .rpy файлам
        progress_callback (callable): Функция для отображения прогресса
        
    Returns:
        dict: {
            'translatable': list,  # Файлы для перевода
            'system': list,       # Системные файлы
            'empty': list         # Файлы без переводимого контента
        }
    """
    result = {
        'translatable': [],
        'system': [],
        'empty': []
    }
    
    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(f"Анализ файла {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
        
        if is_system_file(file_path):
            result['system'].append(file_path)
        elif contains_translatable_content(file_path):
            result['translatable'].append(file_path)
        else:
            result['empty'].append(file_path)
    
    return result
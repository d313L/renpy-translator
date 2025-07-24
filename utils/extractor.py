import os
import re

# --- Вспомогательные функции для обработки Ren'Py тегов ---

# Улучшенное регулярное выражение для обработки 's после переменных
RENPY_TAG_PATTERN = re.compile(r"\{[^{}]*\}|\[[^\[\]]*\](?:'s)?|\*.*?\*")

def strip_tags(text_with_tags):
    """
    Заменяет теги, переменные и действия на уникальные самозакрывающиеся XML-теги (<x0/>, <x1/>),
    чтобы улучшить их обработку API DeepL.
    """
    tag_mapping = {}
    
    def replace_tag_with_placeholder(match):
        original_tag = match.group(0)
        placeholder = f'<x{len(tag_mapping)}/>'
        tag_mapping[placeholder] = original_tag
        return placeholder

    clean_text = RENPY_TAG_PATTERN.sub(replace_tag_with_placeholder, text_with_tags)
    return clean_text, tag_mapping

def restore_tags(translated_text, tag_mapping):
    """
    Восстанавливает оригинальные теги из XML-плейсхолдеров.
    """
    restored_text = translated_text
    # Сортируем ключи по длине в обратном порядке, чтобы избежать замены <x1/> внутри <x10/>
    for placeholder in sorted(tag_mapping.keys(), key=len, reverse=True):
        original_tag = tag_mapping[placeholder]
        restored_text = restored_text.replace(placeholder, original_tag)
        
    return restored_text

# --- Функции для фильтрации технических строк ---

def is_technical_string(text):
    """
    Определяет, является ли строка технической (не требующей перевода).
    
    Args:
        text (str): Текст для проверки
        
    Returns:
        bool: True если строка техническая
    """
    text = text.strip()
    
    # Пустые строки
    if not text:
        return True
        
    # Очень короткие строки (часто технические)
    if len(text) < 2:
        return True
    
    # Строки, состоящие только из символов/цифр
    if re.match(r'^[^\w\s]*$', text) or re.match(r'^\d+$', text):
        return True
    
    # Технические паттерны
    technical_patterns = [
        r'^[a-zA-Z_][a-zA-Z0-9_]*$',  # Имена переменных
        r'^#.*',  # Комментарии  
        r'^\$.*',  # Python код
        r'^[{}\[\]()]+$',  # Только скобки
        r'^[.,:;!?-]+$',  # Только знаки препинания
        r'^https?://.*',  # URL
        r'^[a-zA-Z]:\\.*',  # Пути Windows
        r'^/.*',  # Пути Unix
        r'^\w+\.\w+$',  # Расширения файлов
        r'^rgb\([0-9, ]+\)$',  # RGB цвета
        r'^#[0-9a-fA-F]{6}$',  # HEX цвета
        r'^\d+(\.\d+)?%?$',  # Числа с процентами
    ]
    
    for pattern in technical_patterns:
        if re.match(pattern, text):
            return True
    
    # Проверяем на системные команды Ren'Py
    renpy_commands = [
        'nvl_clear', 'pause', 'return', 'jump', 'call', 'scene', 'show', 'hide',
        'with', 'window', 'menu', 'label', 'define', 'default', 'transform',
        'style', 'init', 'python', 'if', 'elif', 'else', 'while', 'for'
    ]
    
    if text.lower() in renpy_commands:
        return True
    
    return False

def is_meaningful_dialogue(text):
    """
    Определяет, является ли текст осмысленным диалогом для перевода.
    
    Args:
        text (str): Текст для проверки
        
    Returns:
        bool: True если текст нужно переводить
    """
    text = text.strip()
    
    # Базовые проверки
    if is_technical_string(text):
        return False
    
    # Минимальная длина для диалога
    if len(text) < 3:
        return False
    
    # Должен содержать хотя бы одну букву
    if not re.search(r'[a-zA-Zа-яА-ЯёЁ]', text):
        return False
    
    # Не должен быть только заглавными буквами (часто системные константы)
    if text.isupper() and len(text) > 5:
        return False
    
    # Не должен содержать только специальные символы Ren'Py
    renpy_only_pattern = r'^[\{\}\[\]_\*\(\)]+$'
    if re.match(renpy_only_pattern, text):
        return False
    
    return True

# --- Основная функция экстрактора ---

def extract_renpy_translatable_data(rpy_file_content):
    """
    Извлекает переводимый текст из содержимого Ren'Py файла.
    Теперь с улучшенной фильтрацией технических строк.
    """
    translatable_data = []
    lines = rpy_file_content.splitlines()
    in_python_block = False
    python_block_indent = -1
    in_init_block = False
    init_block_indent = -1
    
    for i, line in enumerate(lines):
        original_line = line
        stripped_line = line.strip()
        
        # Пропускаем пустые строки и комментарии
        if not stripped_line or stripped_line.startswith('#'):
            continue

        current_indent = len(line) - len(line.lstrip())
        
        # Обработка Python блоков
        if stripped_line.startswith(('init python:', 'python:')):
            in_python_block = True
            python_block_indent = current_indent
            continue
        elif stripped_line.startswith('$'):
            continue
        elif in_python_block:
            if current_indent <= python_block_indent:
                in_python_block = False
                python_block_indent = -1
            else:
                continue
        
        # Обработка init блоков (часто содержат техническую информацию)
        if stripped_line.startswith('init'):
            in_init_block = True
            init_block_indent = current_indent
            continue
        elif in_init_block:
            if current_indent <= init_block_indent:
                in_init_block = False
                init_block_indent = -1
            else:
                # В init блоках переводим только очевидные строки диалогов
                pass

        text_to_translate = None
        quote_char = None
        
        # 1. Поиск текста в _() функциях (функции перевода)
        match_underscore = re.search(r'_\("((?:\\.|[^"\\])*)"\)|_\(' + r"'((?:\\.|[^'\\])*)'\)", stripped_line)
        if match_underscore:
            if match_underscore.group(1) is not None:
                text_to_translate = match_underscore.group(1)
                quote_char = '"'
            else:
                text_to_translate = match_underscore.group(2)
                quote_char = "'"
        else:
            # 2. Поиск текста в диалогах, меню и т.д.
            # Улучшенное регулярное выражение для поиска строк
            match_quoted_string = re.match(
                r'^\s*(?:[a-zA-Z_]\w*\s*)?' + 
                r'(?:' + 
                    r'"((?:\\.|[^"\\])*)"' + # Двойные кавычки
                    r'|' + 
                    r"'((?:\\.|[^'\\])*)'" + # Одинарные кавычки
                r')' + 
                r'(?:\s*#.*)?$', 
                stripped_line
            )
            if match_quoted_string:
                if match_quoted_string.group(1) is not None:
                    text_to_translate = match_quoted_string.group(1)
                    quote_char = '"'
                else:
                    text_to_translate = match_quoted_string.group(2)
                    quote_char = "'"

        # 3. Дополнительные проверки для специальных конструкций
        if text_to_translate is None:
            # Проверяем menu опции
            menu_match = re.search(r'"([^"]+)"\s*:', stripped_line)
            if menu_match:
                text_to_translate = menu_match.group(1)
                quote_char = '"'

        if text_to_translate is not None:
            # Проверяем, стоит ли переводить эту строку
            if is_meaningful_dialogue(text_to_translate):
                cleaned_text, tag_mapping = strip_tags(text_to_translate)
                
                # Дополнительная проверка очищенного текста
                if cleaned_text.strip() and is_meaningful_dialogue(cleaned_text):
                    translatable_data.append({
                        'original_line': original_line,
                        'text_to_translate': cleaned_text,
                        'line_number': i,
                        'tag_mapping': tag_mapping,
                        'original_text_with_tags': text_to_translate,
                        'quote_char': quote_char,
                    })
            
    return translatable_data

def analyze_file_content(file_path):
    """
    Анализирует содержимое .rpy файла и возвращает статистику.
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        dict: Статистика файла
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        lines = content.splitlines()
        stats = {
            'total_lines': len(lines),
            'code_lines': 0,
            'comment_lines': 0,
            'dialogue_lines': 0,
            'empty_lines': 0,
            'translatable_strings': 0,
            'is_mostly_code': False
        }
        
        extracted_data = extract_renpy_translatable_data(content)
        stats['translatable_strings'] = len(extracted_data)
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                stats['empty_lines'] += 1
            elif stripped.startswith('#'):
                stats['comment_lines'] += 1
            elif any(stripped.startswith(cmd) for cmd in ['label', 'jump', 'call', 'if', 'while', 'for', 'def', 'class', 'import']):
                stats['code_lines'] += 1
            elif '"' in stripped or "'" in stripped:
                stats['dialogue_lines'] += 1
            else:
                stats['code_lines'] += 1
        
        # Определяем, является ли файл в основном кодом
        total_meaningful = stats['total_lines'] - stats['empty_lines'] - stats['comment_lines']
        if total_meaningful > 0:
            code_ratio = stats['code_lines'] / total_meaningful
            stats['is_mostly_code'] = code_ratio > 0.7  # Если больше 70% строк - код
        
        return stats
        
    except Exception as e:
        print(f"Ошибка при анализе файла {file_path}: {e}")
        return None
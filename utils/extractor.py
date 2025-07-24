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

# --- Основная функция экстрактора ---

def extract_renpy_translatable_data(rpy_file_content):
    """
    Извлекает переводимый текст из содержимого Ren'Py файла.
    Эта функция теперь снова на месте и будет работать корректно.
    """
    translatable_data = []
    lines = rpy_file_content.splitlines()
    in_python_block = False
    python_block_indent = -1
    
    for i, line in enumerate(lines):
        original_line = line
        stripped_line = line.strip()
        
        if not stripped_line or stripped_line.startswith('#'):
            continue

        current_indent = len(line) - len(line.lstrip())
        if stripped_line.startswith(('init python:', 'python:')):
            in_python_block = True
            python_block_indent = current_indent
            continue
        if stripped_line.startswith('$'):
            continue
        if in_python_block:
            if current_indent <= python_block_indent:
                in_python_block = False
                python_block_indent = -1
            else:
                continue

        text_to_translate = None
        quote_char = None
        
        # 1. Поиск текста в _()
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

        if text_to_translate is not None:
            cleaned_text, tag_mapping = strip_tags(text_to_translate)
            
            if cleaned_text.strip():
                translatable_data.append({
                    'original_line': original_line,
                    'text_to_translate': cleaned_text,
                    'line_number': i,
                    'tag_mapping': tag_mapping,
                    'original_text_with_tags': text_to_translate,
                    'quote_char': quote_char,
                })
            
    return translatable_data
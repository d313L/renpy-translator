import os
import struct
import zlib
import pickle

def extract_rpa(archive_path, output_dir):
    """
    Извлекает файлы из RPA архива Ren'Py.
    Поддерживает различные версии RPA формата.
    
    Args:
        archive_path (str): Путь к .rpa файлу
        output_dir (str): Папка для извлечения
        
    Returns:
        int: Количество извлечённых файлов
    """
    extracted_count = 0
    
    try:
        with open(archive_path, "rb") as f:
            # Читаем заголовок
            header = f.read(16)
            
            # Определяем версию RPA
            if header.startswith(b"RPA-3.0"):
                extracted_count = _extract_rpa3(f, output_dir)
            elif header.startswith(b"RPA-2.0"):
                extracted_count = _extract_rpa2(f, output_dir)
            elif header.startswith(b"RPA-1.0"):
                extracted_count = _extract_rpa1(f, output_dir)
            else:  
                # Пытаемся как RPA-3.0 по умолчанию
                f.seek(0)
                if f.read(7) == b"RPA-3.0":
                    extracted_count = _extract_rpa3(f, output_dir)
                else:
                    raise ValueError(f"Неподдерживаемый формат RPA файла: {archive_path}")
    
    except Exception as e:
        print(f"Ошибка при извлечении {archive_path}: {e}")
        raise e
    
    return extracted_count

def _extract_rpa3(f, output_dir):
    """Извлечение RPA-3.0 архива"""
    f.seek(7)  # Пропускаем "RPA-3.0"
    
    # Читаем смещение индекса
    index_offset = struct.unpack("<Q", f.read(8))[0]
    
    # Читаем ключ (если есть)
    key = struct.unpack("<I", f.read(4))[0]
    
    # Переходим к индексу
    f.seek(index_offset)
    
    # Читаем индекс
    try:
        index_data = f.read()
        
        # Декодируем индекс с учётом ключа
        if key != 0:
            # Простое XOR декодирование
            decoded_data = bytearray()
            for i, byte in enumerate(index_data):
                decoded_data.append(byte ^ ((key >> (8 * (i % 4))) & 0xFF))
            index_data = bytes(decoded_data)
        
        # Парсим индекс как Python объект
        index = eval(index_data.decode("utf-8"), {"__builtins__": {}})
        
    except Exception as e:
        # Если не удалось декодировать с ключом, пробуем без него
        f.seek(index_offset)
        index_data = f.read()
        try:
            index = eval(index_data.decode("utf-8"), {"__builtins__": {}})
        except:
            # Последняя попытка - через pickle
            f.seek(index_offset)
            index = pickle.load(f)
    
    return _extract_files_from_index(f, index, output_dir)

def _extract_rpa2(f, output_dir):
    """Извлечение RPA-2.0 архива"""
    f.seek(7)  # Пропускаем "RPA-2.0"
    
    # Читаем смещение индекса
    index_offset = struct.unpack("<I", f.read(4))[0]
    
    # Переходим к индексу
    f.seek(index_offset)
    
    # Читаем и парсим индекс
    index_data = f.read()
    index = eval(index_data.decode("utf-8"), {"__builtins__": {}})
    
    return _extract_files_from_index(f, index, output_dir)

def _extract_rpa1(f, output_dir):
    """Извлечение RPA-1.0 архива"""
    f.seek(7)  # Пропускаем "RPA-1.0"
    
    # RPA-1.0 использует другую структуру
    # Читаем индекс напрямую
    try:
        index = pickle.load(f)
    except:
        # Альтернативный способ для некоторых RPA-1.0
        f.seek(7)
        index_data = f.read()
        index = eval(index_data.decode("utf-8"), {"__builtins__": {}})
    
    return _extract_files_from_index(f, index, output_dir)

def _extract_files_from_index(f, index, output_dir):
    """Извлекает файлы используя индекс"""
    extracted_count = 0
    
    for path, info in index.items():
        try:
            # Создаём папки если нужно
            full_path = os.path.join(output_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Определяем параметры файла
            if isinstance(info, tuple) and len(info) >= 2:
                offset = info[0]
                length = info[1]
                compression = info[2] if len(info) > 2 else None
            elif isinstance(info, list) and len(info) >= 2:
                offset = info[0]
                length = info[1] 
                compression = info[2] if len(info) > 2 else None
            else:
                print(f"Неизвестный формат информации о файле: {path}")
                continue
            
            # Читаем данные файла
            f.seek(offset)
            data = f.read(length)
            
            # Распаковываем если нужно
            if compression == "z":
                data = zlib.decompress(data)
            elif compression == "m":
                # LZMA сжатие (редко используется)
                try:
                    import lzma
                    data = lzma.decompress(data)
                except ImportError:
                    print(f"LZMA сжатие не поддерживается для файла {path}")
                    continue
            
            # Записываем файл
            with open(full_path, "wb") as out_file:
                out_file.write(data)
            
            extracted_count += 1
            
        except Exception as e:
            print(f"Ошибка при извлечении файла {path}: {e}")
            continue
    
    return extracted_count

def is_rpa_archive(file_path):
    """
    Проверяет, является ли файл RPA архивом
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        bool: True если файл является RPA архивом
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            return (header.startswith(b"RPA-1.0") or 
                   header.startswith(b"RPA-2.0") or 
                   header.startswith(b"RPA-3.0"))
    except:
        return False

def get_rpa_version(file_path):
    """
    Определяет версию RPA архива
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        str: Версия RPA или None если не RPA файл
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(7).decode('ascii')
            if header in ["RPA-1.0", "RPA-2.0", "RPA-3.0"]:
                return header
    except:
        pass
    return None
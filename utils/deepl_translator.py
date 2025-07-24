import requests
import time
from utils.extractor import restore_tags

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

def sanitize(text):
    # ... (код функции без изменений) ...
    text = text.replace("“", "\"").replace("”", "\"")
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("~", "-")
    text = text.replace("—", "--").replace("–", "-")
    return text

def translate_single(text_to_translate_cleaned, api_key, tag_mapping, target_lang="RU", retries=3):
    raw_text = text_to_translate_cleaned
    
    if not raw_text.strip():
        return restore_tags("", tag_mapping)

    for attempt in range(retries):
        try:
            # ИЗМЕНЕНО: Добавлены параметры для улучшения качества перевода.
            # split_sentences=0: Не дробить строку на предложения. Важно для фраз с тегами.
            # preserve_formatting=1: Попытаться сохранить форматирование.
            # tag_handling='xml': Ключевой параметр для работы с нашими новыми тегами <x.../>.
            data = {
                "auth_key": api_key,
                "text": raw_text,
                "target_lang": target_lang,
                "tag_handling": "xml",
                "split_sentences": "0",
                "preserve_formatting": "1",
            }

            response = requests.post(DEEPL_API_URL, data=data, timeout=20)
            response.raise_for_status()

            translated_raw = response.json()["translations"][0]["text"]
            time.sleep(0.6)

            final_text_with_tags = restore_tags(translated_raw, tag_mapping)
            return sanitize(final_text_with_tags)

        except requests.exceptions.RequestException as e:
            print(f"DeepL API connection error: {e} (attempt {attempt + 1}/{retries}). Retrying...")
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            print(f"An unexpected error occurred: {e} (attempt {attempt + 1}/{retries}).")
            time.sleep(2 * (attempt + 1))
            
    return f"[ОШИБКА ПЕРЕВОДА] {raw_text}"
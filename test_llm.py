#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест OpenAI. Запуск: python3 test_llm.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def main():
    from config import LLM_API_KEY, LLM_CONSOLE_URL, PROXY_URL
    print("Конфигурация:")
    print("  LLM_API_KEY:", "задан" if LLM_API_KEY else "НЕТ")
    print("  LLM_CONSOLE_URL:", LLM_CONSOLE_URL or "(пусто, используется OpenAI)")
    print("  PROXY_URL:", "задан" if PROXY_URL else "(пусто)")
    print()

    if not LLM_API_KEY and not LLM_CONSOLE_URL:
        print("Задайте LLM_API_KEY в .env для OpenAI")
        return 1

    from modules.llm import get_greeting, chat
    print("Тест get_greeting()...")
    r = get_greeting()
    print("  Ответ:", r or "(пусто)")
    if not r:
        print("  Ошибка: проверьте ключ и прокси")
        return 1

    print()
    print("Тест chat('Привет!')...")
    r = chat("Привет! Скажи что-нибудь короткое.")
    print("  Ответ:", r or "(пусто)")
    print()
    print("OpenAI работает.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

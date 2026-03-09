# -*- coding: utf-8 -*-
"""Общение через OpenAI API. Поддержка прокси SOCKS5."""

import json
import os

from config import (
    LLM_CONSOLE_URL,
    LLM_API_URL,
    LLM_API_KEY,
    LLM_MODEL,
    PROXY_URL,
    HTTP_TIMEOUT,
    HTTP_RETRIES,
    ASSISTANT_CHARACTER,
)

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def _log(msg: str):
    try:
        from modules.watchlog import log
        log("llm", msg)
    except Exception:
        print(f"[LLM] {msg}")


CHARACTERS = {
    "robot_cat": {
        "name": "робот-кот",
        "system": "Ты робот-кот. Ты дружелюбный, немного игривый, теплый в общении. Иногда уместно добавляй легкие кошачьи интонации, но без перебора. Отвечай коротко и естественно на русском.",
        "startup": "Привет! Я робот-кот и уже готов к работе.",
    },
    "assistant": {
        "name": "ассистент",
        "system": "Ты дружелюбный голосовой ассистент робота. Говори спокойно, вежливо и коротко на русском.",
        "startup": "Привет! Я робот и уже готов к работе.",
    },
    "guard": {
        "name": "охранник",
        "system": "Ты вежливый робот-охранник. Говори уверенно, коротко и доброжелательно на русском.",
        "startup": "Здравствуйте. Робот-охранник на посту и готов к работе.",
    },
    "professor": {
        "name": "профессор",
        "system": "Ты робот-профессор. Говори умно, спокойно, но просто и доброжелательно. Отвечай коротко на русском.",
        "startup": "Здравствуйте. Робот-профессор готов к работе.",
    },
    "pirate": {
        "name": "пират",
        "system": "Ты робот-пират. Говори весело, харизматично и коротко на русском. Добавляй легкий пиратский стиль, но не превращай ответ в пародию.",
        "startup": "Йо-хо-хо! Робот-пират готов к работе.",
    },
}


def get_character_settings():
    key = (ASSISTANT_CHARACTER or "robot_cat").strip().lower()
    settings = CHARACTERS.get(key, CHARACTERS["robot_cat"]).copy()
    settings["id"] = key if key in CHARACTERS else "robot_cat"
    return settings


def _persona_prompt(task: str) -> str:
    persona = get_character_settings()
    return f"{persona['system']} {task}"


def _http_session():
    """Сессия с прокси и retry."""
    session = requests.Session()
    if PROXY_URL:
        session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    retry = Retry(total=HTTP_RETRIES, backoff_factor=0.6)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def _openai_client():
    """Клиент OpenAI с прокси SOCKS5."""
    if not HAS_OPENAI or not LLM_API_KEY:
        return None
    kwargs = {"api_key": LLM_API_KEY}
    if PROXY_URL:
        try:
            import httpx
            kwargs["http_client"] = httpx.Client(proxy=PROXY_URL, timeout=float(HTTP_TIMEOUT))
        except Exception:
            os.environ["HTTP_PROXY"] = PROXY_URL
            os.environ["HTTPS_PROXY"] = PROXY_URL
    return OpenAI(**kwargs)


def _call_console(prompt: str) -> str:
    """Вызов mediarise-robot-console (ESP32)."""
    if not LLM_CONSOLE_URL:
        return ""
    url = LLM_CONSOLE_URL.rstrip("/") + "/chat" if "/chat" not in LLM_CONSOLE_URL else LLM_CONSOLE_URL
    payload = {"text": prompt, "messages": [{"role": "user", "content": prompt}]}
    try:
        if HAS_REQUESTS:
            r = _http_session().post(url, json=payload, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            out = r.json()
        else:
            import urllib.request
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                out = json.loads(resp.read().decode())
        return out.get("reply", out.get("text", out.get("content", ""))).strip()
    except Exception as e:
        _log(f"Console ошибка: {e}")
        return ""


def _call_openai(messages: list, max_tokens: int = 150) -> str:
    """Вызов OpenAI API (официальный клиент или REST)."""
    if not LLM_API_KEY:
        _log("LLM_API_KEY не задан в .env")
        return ""

    # 1) Официальный клиент OpenAI
    if HAS_OPENAI:
        try:
            client = _openai_client()
            if client:
                r = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                content = r.choices[0].message.content if r.choices else ""
                return (content or "").strip()
        except Exception as e:
            _log(f"OpenAI ошибка: {e}")

    # 2) REST API через requests
    if HAS_REQUESTS:
        try:
            payload = {"model": LLM_MODEL, "messages": messages, "max_tokens": max_tokens}
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
            r = _http_session().post(LLM_API_URL, json=payload, headers=headers, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            out = r.json()
            return out.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            err = str(e)
            _log(f"OpenAI REST ошибка: {err}")
            if "SOCKS" in err or "socks" in err.lower():
                _log("Установите: pip install pysocks requests[socks]")

    return ""


def get_joke() -> str:
    """Получить короткую добрую шутку через OpenAI."""
    if LLM_CONSOLE_URL:
        return _call_console(_persona_prompt("Расскажи одну короткую добрую шутку на русском."))
    return _call_openai([
        {"role": "system", "content": _persona_prompt("Отвечай только одной короткой доброй шуткой на русском, без лишнего текста.")},
        {"role": "user", "content": "Расскажи добрую шутку."},
    ], max_tokens=100)


def get_greeting() -> str:
    """Приветствие при обнаружении человека через OpenAI."""
    if LLM_CONSOLE_URL:
        return _call_console(_persona_prompt("Поздоровайся с человеком одним коротким приветствием."))
    return _call_openai([
        {"role": "system", "content": _persona_prompt("Ответь одним коротким приветствием на русском.")},
        {"role": "user", "content": "Поздоровайся с человеком."},
    ], max_tokens=50)


def get_how_are_you_response() -> str:
    """Ответ на вопрос 'как дела' через OpenAI."""
    if LLM_CONSOLE_URL:
        return _call_console(_persona_prompt("Ответь коротко и дружелюбно на вопрос 'как дела?'"))
    return _call_openai([
        {"role": "system", "content": _persona_prompt("Ответь коротко и дружелюбно на вопрос как дела, на русском.")},
        {"role": "user", "content": "Как дела?"},
    ], max_tokens=80)


def chat(user_message: str, history: list = None) -> str:
    """Диалог с ассистентом через OpenAI."""
    if LLM_CONSOLE_URL:
        return _call_console(_persona_prompt(f"Ответь на сообщение пользователя: {user_message}"))
    history = history or []
    messages = [{"role": "system", "content": _persona_prompt("Ты голосовой ассистент робота. Отвечай кратко и по делу на русском.")}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_message})
    return _call_openai(messages, max_tokens=200)

#!/usr/bin/env python3
"""Проверка заданий курса «Чат-боты на Python».

  python3 kurs_check.py ЗАДАНИЕ ФАЙЛ          проверить решение (ЗАДАНИЕ — папка задания или task.json)
  python3 kurs_check.py ЗАДАНИЕ ФАЙЛ --json   то же, ответ в JSON (для панели VS Code)
  python3 kurs_check.py --run ФАЙЛ             запустить программу, ошибку объяснить по-русски

Нужна только стандартная библиотека Python 3.8+. Файл самодостаточный:
его копируют на ученические ПК вместе с панелью VS Code.
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import tokenize
import traceback

TIMEOUT = 5          # секунд на один запуск
MAX_OUT = 3000       # сколько символов вывода показывать

# ---------------------------------------------------------------------------
# Раскладка: ученик забыл переключиться на английскую
# ---------------------------------------------------------------------------
RU2EN = dict(zip("йцукенгшщзфывапролдячсмитьЙЦУКЕНГШЩЗФЫВАПРОЛДЯЧСМИТЬ",
                 "qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM"))
KNOWN_WORDS = {
    "if", "elif", "else", "and", "or", "not", "in", "is", "for", "while", "def", "return",
    "import", "from", "as", "try", "except", "break", "continue", "pass", "true", "false", "none",
    "print", "input", "int", "str", "float", "len", "range", "lower", "upper", "strip", "split",
    "exit", "quit", "list", "dict", "append", "json", "open", "with", "random", "time",
}
CYR = re.compile(r"[а-яёА-ЯЁ]")


def layout_fix(word: str) -> str | None:
    """«шf» → «if», «зкште» → «print». None, если слово не похоже на набранное в русской раскладке."""
    if not CYR.search(word):
        return None
    latin = "".join(RU2EN.get(ch, ch) for ch in word)
    if CYR.search(latin):
        return None
    return latin if latin.lower() in KNOWN_WORDS else None


def layout_hint_for_line(line: str) -> str | None:
    """Ищет в строке кода (вне кавычек и комментариев) слово, набранное не в той раскладке."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(line + "\n").readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        toks = []
        for m in re.finditer(r"[A-Za-zА-Яа-яЁё_]+", re.sub(r"(\".*?\"|'.*?'|#.*$)", "", line)):
            toks.append(tokenize.TokenInfo(tokenize.NAME, m.group(), (1, 0), (1, 0), line))
    for t in toks:
        if t.type == tokenize.NAME or t.type == tokenize.ERRORTOKEN:
            fixed = layout_fix(t.string)
            if fixed:
                return (f"Слово «{t.string}» набрано в русской раскладке. Наверное, ты хотел написать «{fixed}». "
                        "Переключи раскладку на английскую и набери слово заново.")
    return None


# ---------------------------------------------------------------------------
# Объяснение ошибок по-русски
# ---------------------------------------------------------------------------
def _line(code: str, n: int | None) -> str:
    if not n:
        return ""
    lines = code.splitlines()
    return lines[n - 1] if 0 < n <= len(lines) else ""


def explain_syntax(msg: str, lineno: int | None, code: str, kind: str = "SyntaxError") -> dict:
    """Понятное объяснение SyntaxError / IndentationError."""
    line = _line(code, lineno)
    stripped = line.strip()
    m = msg.lower()
    where = f"в строке {lineno}" if lineno else ""
    text = None
    title = "Python не понимает строку"

    layout = layout_hint_for_line(line)
    if layout:
        title, text = "Не та раскладка", layout
    elif "invalid character" in m and any(q in m for q in "«»“”„"):
        title = "Не те кавычки"
        text = "Кавычки-ёлочки « » и “ ” Python не понимает. Нужны прямые кавычки: \" \". Набери их на английской раскладке."
    elif "invalid character" in m:
        title = "Лишний символ"
        text = "В коде есть символ, которого Python не знает. Часто это русская буква или кавычка-ёлочка вне текста в кавычках."
    elif "missing parentheses" in m and "print" in m:
        title = "print без скобок"
        text = "После print нужны скобки: print(\"текст\")."
    elif ("unterminated string" in m or "eol while scanning" in m
          or "unterminated triple" in m or "eof while scanning" in m):
        title = "Кавычка не закрыта"
        text = "Текст начинается с кавычки, а закрывающей кавычки нет. Поставь вторую кавычку в конце текста."
    elif kind == "IndentationError" or "indent" in m:
        if "unexpected indent" in m:
            title = "Лишний отступ"
            text = "У этой строки отступ, а он здесь не нужен. Убери пробелы в начале строки (Shift+Tab)."
        elif "expected an indented block" in m:
            title = "Нет отступа"
            text = ("После строки с двоеточием следующая строка должна начинаться с отступа: 4 пробела (клавиша Tab). "
                    "Так Python понимает, что строка относится к условию.")
        elif "unindent does not match" in m or "inconsistent" in m:
            title = "Отступы разные"
            text = "Отступы не совпадают: у строк одного блока должно быть одинаковое число пробелов (обычно 4)."
        else:
            title = "Ошибка в отступах"
            text = "Проверь отступы: внутри if, elif и else строки сдвинуты на 4 пробела."
    elif re.match(r"^(if|elif|while)\b", stripped) and re.search(r"(?<![=!<>])=(?!=)", stripped.split("#")[0]):
        title = "В условии один знак ="
        text = "В условии сравнивают двумя знаками: ==. Один знак = кладёт значение в переменную."
    elif "expected ':'" in m or (re.match(r"^(if|elif|else|while|for|def|try|except)\b", stripped)
                                and not stripped.split("#")[0].rstrip().endswith(":")):
        title = "Нет двоеточия"
        text = "В конце строки с if, elif, else (и for, while, def) нужно двоеточие «:»."
    elif "was never closed" in m or "unexpected eof" in m:
        title = "Скобка не закрыта"
        text = "Открылась скобка ( или [, а закрывающей нет. Посчитай скобки: открывающих и закрывающих должно быть поровну."
    elif "unmatched" in m:
        title = "Лишняя скобка"
        text = "Здесь закрывающая скобка, для которой нет открывающей. Убери лишнюю."
    elif re.match(r"^else\b", stripped) or re.match(r"^elif\b", stripped):
        title = "else без if"
        text = "elif и else пишутся сразу после блока if, на том же отступе, что и сам if."
    elif "cannot assign" in m or "maybe you meant '=='" in m:
        title = "В условии один знак ="
        text = "Чтобы сравнить, нужно ==. Один знак = кладёт значение в переменную."
    if text is None:
        text = "Python не может прочитать эту строку. Проверь кавычки, скобки, двоеточие и что слова набраны на английской раскладке."
    return {"title": title, "text": f"{text}", "line": lineno, "code_line": line, "where": where, "raw": f"{kind}: {msg}"}


def explain_runtime(etype: str, msg: str, lineno: int | None, code: str, name: str | None = None) -> dict:
    """Понятное объяснение ошибки, случившейся во время работы программы."""
    line = _line(code, lineno)
    title, text = f"Ошибка {etype}", None
    m = msg.lower()
    if etype == "NameError":
        nm = name
        if not nm:
            mm = re.search(r"name '([^']+)'", msg)
            nm = mm.group(1) if mm else "?"
        fixed = layout_fix(nm)
        title = "Python не знает такого слова"
        if fixed:
            text = f"Слово «{nm}» набрано в русской раскладке. Наверное, ты хотел написать «{fixed}». Переключи раскладку."
        elif nm[:1].isupper() and nm.lower() in KNOWN_WORDS:
            text = f"Python различает большие и маленькие буквы. Пиши «{nm.lower()}», а не «{nm}»."
        elif CYR.search(nm):
            text = (f"Слово «{nm}» Python считает именем переменной, а такой переменной нет. "
                    f"Если это текст, возьми его в кавычки: \"{nm}\".")
        else:
            text = (f"Переменной «{nm}» ещё нет. Проверь, что имя написано так же, как там, где ты её создал, "
                    "и что она создаётся выше этой строки.")
    elif etype == "ValueError" and "invalid literal for int()" in m:
        mm = re.search(r": '(.*)'$", msg)
        val = mm.group(1) if mm else ""
        title = "Это не число"
        text = (f"int() превращает в число только цифры, а получил «{val}». "
                "Проверь, что вводишь число, и что int() стоит там, где ждут число.")
    elif etype == "ValueError" and "could not convert string to float" in m:
        title = "Это не число"
        text = "float() превращает в число только цифры (дробь — через точку: 2.5). Проверь, что вводишь число."
    elif etype == "UnboundLocalError":
        title = "Переменная внутри функции"
        text = ("Внутри функции эта переменная ещё не создана. Передай её в функцию параметром "
                "или верни новое значение через return.")
    elif etype == "TypeError" and ("required positional argument" in m or "positional argument" in m and "takes" in m):
        title = "Не столько значений в скобках"
        text = "Функцию вызвали не с тем числом значений в скобках. Сравни вызов с тем, что написано после def."
    elif etype == "TypeError" and "'nonetype'" in m:
        title = "Функция ничего не вернула"
        text = "Здесь используется результат функции, а она вернула None. Проверь, что в функции есть return."
    elif etype == "TypeError" and "not supported between instances of 'str' and 'int'" in m \
            or etype == "TypeError" and "not supported between instances of 'int' and 'str'" in m:
        title = "Текст сравнивается с числом"
        text = "input() всегда возвращает текст. Чтобы сравнивать с числом, оберни его: int(input(...))."
    elif etype == "TypeError" and "can only concatenate str" in m:
        title = "Текст склеивается с числом"
        text = "Нельзя сложить текст и число через +. Используй запятую в print или str(число)."
    elif etype == "TypeError" and "unsupported operand" in m and "str" in m:
        title = "Действие с текстом и числом"
        text = "Одна из переменных — текст. Если это должно быть число, оберни input в int()."
    elif etype == "AttributeError":
        mm = re.search(r"'(\w+)' object has no attribute '(\w+)'", msg)
        title = "Нет такой команды"
        if mm and mm.group(1) == "int" and mm.group(2) in ("lower", "strip", "upper"):
            text = f"{mm.group(2)}() работает только с текстом, а здесь число."
        elif mm:
            text = f"У значения нет команды «{mm.group(2)}». Проверь, нет ли опечатки, и не забыты ли скобки ()."
        else:
            text = "Проверь написание команды после точки."
    elif etype == "EOFError":
        title = "Программа ждёт лишний ответ"
        text = "Программа задаёт больше вопросов (input), чем нужно в задании."
    elif etype == "ZeroDivisionError":
        title = "Деление на ноль"
        text = "На ноль делить нельзя. Проверь число, на которое делишь."
    elif etype == "IndexError":
        title = "Нет элемента с таким номером"
        text = "Обращение к элементу списка по номеру, которого нет. Нумерация начинается с 0."
    elif etype == "KeyError":
        title = "Нет такого ключа"
        text = f"В словаре нет ключа {msg}. Проверь написание или используй .get()."
    elif etype == "FileNotFoundError":
        title = "Файла нет"
        text = ("Программа открывает файл, которого ещё нет. Перед чтением проверь: "
                "if os.path.exists(имя_файла): ... — а если файла нет, начни с пустой памяти.")
    elif etype == "JSONDecodeError":
        title = "Файл JSON испорчен"
        text = "В файле не JSON или он пустой. Удали файл (программа создаст новый) или проверь, что записываешь через json.dump."
    elif etype == "ModuleNotFoundError":
        title = "Не найден модуль"
        text = "Python не нашёл подключаемый модуль. Проверь имя после import и что нужный файл лежит рядом."
    elif etype == "RecursionError":
        title = "Функция вызывает сама себя без конца"
        text = "Проверь, что у функции есть условие остановки."
    if text is None:
        text = "Во время работы программы случилась ошибка. Посмотри на строку, которую показывает Python."
    return {"title": title, "text": text, "line": lineno, "code_line": line,
            "where": f"в строке {lineno}" if lineno else "", "raw": f"{etype}: {msg}"}


def explain_exception(exc: BaseException, code: str, filename: str) -> dict:
    if isinstance(exc, SyntaxError):
        return explain_syntax(exc.msg or "", exc.lineno, code, type(exc).__name__)
    lineno = None
    for fr in traceback.extract_tb(exc.__traceback__):
        if os.path.abspath(fr.filename) == os.path.abspath(filename):
            lineno = fr.lineno
    return explain_runtime(type(exc).__name__, str(exc), lineno, code, getattr(exc, "name", None))


# ---------------------------------------------------------------------------
# Разбор кода: структура
# ---------------------------------------------------------------------------
def _is_elif(node: ast.If, lines: list[str]) -> bool:
    ln = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
    return ln.lstrip().startswith("elif")


def _features(tree: ast.AST, code: str) -> set[str]:
    lines = code.splitlines()
    f: set[str] = set()
    bool_names: set[str] = set()
    cond_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            f.add("if")
            if node.orelse:
                if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) and _is_elif(node.orelse[0], lines):
                    f.add("elif")
                else:
                    f.add("else")
            # вложенный if: внутри тела (или настоящего else) есть ещё один if
            inner = list(node.body)
            if node.orelse and not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
                                    and _is_elif(node.orelse[0], lines)):
                inner += node.orelse
            for st in inner:
                for sub in ast.walk(st):
                    if isinstance(sub, ast.If):
                        f.add("nested_if")
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Name):
                    cond_names.add(sub.id)
        elif isinstance(node, ast.BoolOp):
            f.add("and" if isinstance(node.op, ast.And) else "or")
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    cond_names.add(sub.id)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            f.add("not")
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                f.add({ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.Gt: ">", ast.LtE: "<=",
                       ast.GtE: ">=", ast.In: "in", ast.NotIn: "not in"}.get(type(op), "cmp"))
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                f.add(f"call:{fn.id}")
            elif isinstance(fn, ast.Attribute):
                f.add(f"method:{fn.attr}")
            for kw in node.keywords:
                if kw.arg:
                    f.add(f"kw:{kw.arg}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else (node.names[0].name if node.names else "")
            f.add(f"import:{mod}")
        elif isinstance(node, ast.JoinedStr):
            f.add("fstring")
        elif isinstance(node, ast.While):
            f.add("while")
        elif isinstance(node, ast.Break):
            f.add("break")
        elif isinstance(node, ast.Continue):
            f.add("continue")
        elif isinstance(node, ast.Try):
            f.add("try")
            for h in node.handlers:
                if isinstance(h.type, ast.Name):
                    f.add(f"except:{h.type.id}")
                elif h.type is None:
                    f.add("except:*")
        elif isinstance(node, ast.List) and node.elts:
            f.add("list")
        elif isinstance(node, ast.Dict):
            f.add("dict")
        elif isinstance(node, ast.AugAssign):
            f.add("augassign")
        elif isinstance(node, ast.Return) and node.value is not None:
            f.add("return")
        elif isinstance(node, ast.With):
            f.add("with")
        elif isinstance(node, ast.For):
            f.add("for")
        elif isinstance(node, ast.FunctionDef):
            f.add("def")
            f.add(f"def:{node.name}")
            if node.args.args:
                f.add("params")
        elif isinstance(node, ast.Assign):
            # счётчик вида count = count + 1 — то же, что count += 1
            if isinstance(node.value, ast.BinOp) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and any(isinstance(x, ast.Name) and x.id == node.targets[0].id for x in (node.value.left, node.value.right)):
                f.add("augassign")
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        bool_names.add(t.id)
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            counts[node.func.id] = counts.get(node.func.id, 0) + 1
    for name, n in counts.items():
        for k in range(2, n + 1):
            f.add(f"call:{name}x{k}")
    if bool_names & cond_names:
        f.add("flag")
    if f & {"==", "!=", "<", ">", "<=", ">="}:
        f.add("compare")
    if f & {"<", "<=", ">", ">="}:
        f.add("order")
    if f & {"call:exit", "call:quit", "method:exit"}:
        f.add("exit")
    return f


FEATURE_TITLES = {
    "if": "есть if", "else": "есть else", "elif": "есть elif", "and": "есть and", "or": "есть or",
    "not": "есть not", "in": "есть in", "nested_if": "есть условие внутри условия", "flag": "есть флажок True/False",
    "call:int": "есть int()", "method:lower": "есть lower()", "method:strip": "есть strip()",
    "exit": "есть exit()", "order": "есть сравнение < или >", "compare": "есть сравнение",
    "import:ai": "есть from ai import ...", "fstring": "есть f-строка", "kw:system": "есть роль system=",
    "kw:temperature": "есть temperature=", "call:ask": "есть ask()",
    "while": "есть цикл while", "break": "есть break", "continue": "есть continue", "try": "есть try / except",
    "except:ValueError": "ловится ValueError", "list": "есть список [...]", "dict": "есть словарь {...}",
    "augassign": "есть счётчик +=", "def": "есть своя функция def", "return": "функция возвращает return",
    "params": "у функции есть параметр", "for": "есть цикл for", "with": "файл открыт через with",
    "method:append": "есть append()", "call:len": "есть len()", "method:choice": "есть random.choice()",
    "method:randint": "есть random.randint()", "import:random": "есть import random",
    "import:json": "есть import json", "method:dump": "есть json.dump()", "method:load": "есть json.load()",
    "call:chat": "есть chat()", "call:chat_text": "есть chat_text()", "kw:tools": "передаются tools=",
    "call:make_tool": "есть make_tool()", "call:agent_answer": "есть agent_answer()",
}


# ---------------------------------------------------------------------------
# Запуск программы ученика
# ---------------------------------------------------------------------------
RUNNER = r'''
import builtins, json, os, runpy, sys, traceback
FILE = sys.argv[1]
ERR = sys.argv[2]
def _input(prompt=""):
    sys.stdout.write("\x01" + str(prompt) + "\x02")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError("EOF when reading a line")
    line = line.rstrip("\r\n")
    sys.stdout.write("\x03" + line + "\x04\n")
    sys.stdout.flush()
    return line
builtins.input = _input
sys.argv = [FILE]
# случайность под контролем проверки: одинаковый результат при каждом запуске,
# а нужные тесту числа и выборы подставляются по очереди (последнее повторяется)
import random as _random
_random.seed(int(os.environ.get("KURS_SEED") or 7))
_plan = json.loads(os.environ.get("KURS_RANDOM") or "{}")
_randint0, _choice0 = _random.randint, _random.choice
def _next(name):
    q = _plan.get(name) or []
    if not q:
        return None
    return q[0] if len(q) == 1 else q.pop(0)
def _randint(a, b):
    v = _next("randint")
    return _randint0(a, b) if v is None else max(a, min(b, v))
def _choice(seq):
    v = _next("choice")
    return _choice0(seq) if v is None else seq[v % len(seq)]
_random.randint, _random.choice = _randint, _choice
try:
    runpy.run_path(FILE, run_name="__main__")
except SystemExit as e:
    code = e.code
    sys.stdout.flush()
    os._exit(code if isinstance(code, int) else 0)
except BaseException as e:
    lineno = None
    for fr in traceback.extract_tb(e.__traceback__):
        if os.path.abspath(fr.filename) == os.path.abspath(FILE):
            lineno = fr.lineno
    if isinstance(e, SyntaxError):
        lineno = e.lineno
    with open(ERR, "w", encoding="utf-8") as fh:
        json.dump({"type": type(e).__name__, "msg": getattr(e, "msg", None) if isinstance(e, SyntaxError) else str(e),
                   "line": lineno, "name": getattr(e, "name", None)}, fh, ensure_ascii=False)
    sys.stdout.flush()
    traceback.print_exc()
    os._exit(1)
'''


AI_STUB = r'''# Заглушка ai.py для проверки: отвечает мгновенно, без сети, и записывает, как её вызвали.
import json, os
from types import SimpleNamespace
_LOG = os.environ.get("KURS_AI_LOG")
_ANSWERS = json.loads(os.environ.get("KURS_AI_ANSWERS") or "[]")


def _answer(text):
    for rule in _ANSWERS:
        if "answer" in rule and rule.get("if", "").lower() in text.lower():
            return rule["answer"]
    return "(ответ нейросети)"


def _sample_args(tool):
    """Значения для обязательных параметров инструмента — как их подставила бы нейросеть."""
    params = (tool.get("function") or tool).get("parameters") or {}
    props = params.get("properties") or {}
    sample = {"string": "кот", "integer": 3, "number": 3, "boolean": True}
    return {k: sample.get((props.get(k) or {}).get("type"), "кот") for k in params.get("required") or []}


def _get(m, key):
    return m.get(key) if isinstance(m, dict) else getattr(m, key, None)


def _write(rec):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def chat(messages, tools=None, temperature=0.7, max_tokens=1500):
    msgs = [{"role": str(_get(m, "role")), "content": str(_get(m, "content") or "")} for m in messages]
    system = " ".join(m["content"] for m in msgs if m["role"] == "system")
    user = [m["content"] for m in msgs if m["role"] == "user"]
    names = [((t.get("function") or {}).get("name") or t.get("name")) for t in tools or [] if isinstance(t, dict)]
    after_tool = bool(msgs) and msgs[-1]["role"] == "tool"
    _write({"system": system, "prompt": user[-1] if user else "", "temperature": temperature,
            "messages": len(msgs), "all": msgs, "tools": names, "after_tool": after_tool})
    if after_tool:
        # инструмент отработал — «нейросеть» пересказывает его результат
        results = []
        for m in reversed(msgs):
            if m["role"] != "tool":
                break
            results.insert(0, m["content"])
        return SimpleNamespace(role="assistant", content="(ответ нейросети: " + "; ".join(results) + ")", tool_calls=None)
    for rule in _ANSWERS:
        if rule.get("if", "").lower() not in (user[-1] if user else "").lower():
            continue
        name = rule.get("tool")
        if "tool_index" in rule and rule["tool_index"] < len(names):
            name = names[rule["tool_index"]]          # инструмент ученика: имя заранее неизвестно
        if name and name in names:
            args = rule.get("arguments")
            if args is None:
                args = _sample_args(tools[names.index(name)])
            call = SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(
                name=name, arguments=json.dumps(args, ensure_ascii=False)))
            return SimpleNamespace(role="assistant", content="", tool_calls=[call])
    return SimpleNamespace(role="assistant", content=_answer((user[-1] if user else "") + " " + system), tool_calls=None)


def chat_text(messages, temperature=0.7, max_tokens=1500, **options):
    return chat(messages, temperature=temperature, max_tokens=max_tokens, **options).content


def ask(question, system=None, temperature=0.7, max_tokens=1500, **options):
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": str(question)})
    return chat_text(messages, temperature=temperature, max_tokens=max_tokens, **options)
'''


def _clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    return env


RERUN = "\n— программа запущена ещё раз —\n"
SERVICE = {"_kurs_runner.py", "_kurs_error.json", "_kurs_ai.jsonl", "ai.py", "__pycache__"}


def run_program(code: str, filename: str, inputs: list, stubs: list[str] | None = None,
                python: str | None = None, ai: list | None = None, files: dict | None = None,
                random_plan: dict | None = None) -> dict:
    """Запускает программу ученика во временной папке с заданным вводом.

    inputs — ответы на input(); список списков — несколько запусков подряд в одной папке
    (так проверяется память в файле). files — файлы, которые лежат в папке до запуска.
    """
    tmp = tempfile.mkdtemp(prefix="kurs_")
    try:
        prog = os.path.join(tmp, os.path.basename(filename) or "main.py")
        with open(prog, "w", encoding="utf-8") as fh:
            fh.write(code)
        for s in stubs or []:
            if os.path.isfile(s):
                shutil.copy(s, tmp)
        for name, content in (files or {}).items():
            with open(os.path.join(tmp, os.path.basename(name)), "w", encoding="utf-8") as fh:
                fh.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
        env = _clean_env()
        if random_plan:
            env["KURS_RANDOM"] = json.dumps(random_plan)
        if ai is not None:
            # нейросеть подменяем заглушкой: проверка быстрая, без интернета и всегда одинаковая
            with open(os.path.join(tmp, "ai.py"), "w", encoding="utf-8") as fh:
                fh.write(AI_STUB)
            env["KURS_AI_LOG"] = os.path.join(tmp, "_kurs_ai.jsonl")
            env["KURS_AI_ANSWERS"] = json.dumps(ai, ensure_ascii=False)
        runner = os.path.join(tmp, "_kurs_runner.py")
        with open(runner, "w", encoding="utf-8") as fh:
            fh.write(RUNNER)
        errf = os.path.join(tmp, "_kurs_error.json")
        runs = inputs if inputs and all(isinstance(x, list) for x in inputs) else [inputs]
        out, rc, timeout, err = "", 0, False, None
        for i, run_inputs in enumerate(runs):
            if i:
                out += RERUN
            stdin = "".join(str(x) + "\n" for x in run_inputs)
            try:
                r = subprocess.run([python or sys.executable, runner, prog, errf], input=stdin, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT, cwd=tmp,
                                   env=env)
                out, rc = out + r.stdout, r.returncode
            except subprocess.TimeoutExpired as e:
                part = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
                out, rc, timeout = out + part, None, True
            if os.path.exists(errf):
                with open(errf, encoding="utf-8") as fh:
                    err = json.load(fh)
            if timeout or err:
                break
        calls = []
        logf = env.get("KURS_AI_LOG")
        if logf and os.path.exists(logf):
            with open(logf, encoding="utf-8") as fh:
                calls = [json.loads(x) for x in fh if x.strip()]
        made = {}
        for name in os.listdir(tmp):
            full = os.path.join(tmp, name)
            if name in SERVICE or full == prog or not os.path.isfile(full) or os.path.getsize(full) > 100_000:
                continue
            with open(full, encoding="utf-8", errors="replace") as fh:
                made[name] = fh.read()
        return {"raw": out, "rc": rc, "timeout": timeout, "error": err, "ai_calls": calls, "files": made}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def split_output(raw: str) -> tuple[str, str]:
    """(что напечатала программа без подсказок input, расшифровка диалога для показа ученику)."""
    plain = re.sub(r"\x01.*?\x02", "", raw, flags=re.S)
    plain = re.sub(r"\x03.*?\x04\n?", "", plain, flags=re.S)
    shown = re.sub(r"[\x01-\x04]", "", raw)
    return plain, shown


def dialog_of(raw: str) -> list[list[str]]:
    """Разговор с программой по репликам: [["bot", текст], ["you", ответ], ...] — для показа в виде чата."""
    out: list[list[str]] = []

    def add(who: str, text: str):
        text = text.strip("\n")
        if who == "bot" and not text.strip():
            return
        if out and out[-1][0] == who == "bot":
            out[-1][1] = (out[-1][1] + "\n" + text).strip("\n")
        else:
            out.append([who, text])

    for m in re.finditer(r"\x01(.*?)\x02|\x03(.*?)\x04\n?|([^\x01\x03]+)", raw, flags=re.S):
        if m.group(1) is not None:
            add("bot", m.group(1).rstrip())
        elif m.group(2) is not None:
            add("you", m.group(2))
        else:
            add("bot", m.group(3))
    return out[-40:]


def norm(s: str) -> str:
    s = s.lower().replace("ё", "е")
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# Проверка задания
# ---------------------------------------------------------------------------
def load_task(path: str) -> tuple[dict, str]:
    if os.path.isdir(path):
        path = os.path.join(path, "task.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh), os.path.dirname(os.path.abspath(path))


def _meaningful(code: str) -> bool:
    for ln in code.splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            return True
    return False


def find_helpers(task: dict, task_dir: str | None, src_dir: str | None) -> list[str]:
    """Общие модули занятия (например agent.py): берём из папки ученика, иначе из папки задания."""
    out = []
    for name in task.get("helpers", []):
        for folder in (src_dir, task_dir):
            if folder and os.path.isfile(os.path.join(folder, name)):
                out.append(os.path.join(folder, name))
                break
    return out


def check(task: dict, code: str, filename: str = "main.py", task_dir: str | None = None,
          python: str | None = None, src_dir: str | None = None) -> dict:
    items: list[dict] = []
    res = {"task": task.get("id"), "ok": False, "items": items, "error": None, "summary": ""}

    def done(summary: str) -> dict:
        res["summary"] = summary
        return res

    # 1. Пустой файл и пропуски
    if not _meaningful(code):
        res["error"] = {"title": "Файл пустой", "text": "Напиши программу в этом файле и сохрани его (Ctrl+S).",
                        "line": None, "code_line": "", "where": ""}
        return done("Сначала напиши программу")
    blanks = [i + 1 for i, ln in enumerate(code.splitlines()) if "___" in ln and not ln.lstrip().startswith("#")]
    if blanks:
        nums = ", ".join(map(str, blanks))
        res["error"] = {"title": "Остались пропуски ___",
                        "text": f"Впиши нужное вместо ___ (строк{'а' if len(blanks) == 1 else 'и'} {nums}).",
                        "line": blanks[0], "code_line": _line(code, blanks[0]), "where": f"в строке {blanks[0]}"}
        return done("Заполни пропуски")

    # 2. Синтаксис
    try:
        tree = ast.parse(code, filename)
    except SyntaxError as e:
        res["error"] = explain_syntax(e.msg or "", e.lineno, code, type(e).__name__)
        return done("Python не может прочитать программу")

    # 3. Тесты с вводом
    stubs = [os.path.join(task_dir, s) for s in task.get("stubs", [])] if task_dir else []
    stubs += find_helpers(task, task_dir, src_dir)
    runtime_error = None
    for t in task.get("tests", []):
        inputs = t.get("runs") or t.get("input", [])
        if isinstance(inputs, str):
            inputs = [inputs]
        random_plan = {k: list(t[k]) for k in ("randint", "choice") if k in t}
        answers = t.get("ai_answers", task.get("ai_answers", [])) if task.get("uses_ai") else None
        r = run_program(code, filename, inputs, stubs, python, answers, t.get("files"), random_plan)
        plain, shown = split_output(r["raw"])
        n = norm(plain)
        if t.get("runs"):
            label = " · ".join(f"{i}-й запуск: " + (" → ".join(f"«{x}»" for x in run) or "без ввода")
                               for i, run in enumerate(inputs, 1))
            inputs = [x for run in inputs for x in run]
        else:
            label = "Ввод: " + " → ".join(f"«{x}»" for x in inputs) if inputs else "Запуск"
        item = {"kind": "test", "title": label, "ok": True, "message": "", "output": shown[-MAX_OUT:],
                "input": inputs, "expect": t.get("expect", []), "dialog": dialog_of(r["raw"][-MAX_OUT:])}
        if r["timeout"]:
            item["ok"] = False
            item["message"] = "Программа работает слишком долго. Возможно, бесконечный цикл."
        elif r["error"]:
            e = r["error"]
            item["ok"] = False
            if e["type"] == "EOFError":
                item["message"] = t.get("on_eof") or ("Программа задаёт больше вопросов, чем нужно. "
                                                      + (t.get("fail") or ""))
            else:
                exp = explain_runtime(e["type"], e.get("msg") or "", e.get("line"), code, e.get("name"))
                if runtime_error is None:
                    # подробное объяснение показывается один раз, в блоке ошибки над тестами
                    item["message"] = f"Программа остановилась: {exp['title'].lower()} {exp['where']}."
                    runtime_error = exp
                elif runtime_error["raw"] == exp["raw"]:
                    item["message"] = "Та же ошибка."
                else:
                    item["message"] = f"{exp['title']} {exp['where']}: {exp['text']}"
                if t.get("fail") and t["fail"] not in item["message"]:
                    item["message"] += " " + t["fail"]
        else:
            missing = [x for x in t.get("expect", []) if norm(x) not in n]
            extra = [x for x in t.get("reject", []) if norm(x) in n]
            ai_problem = check_ai(t.get("ai"), r["ai_calls"]) if t.get("ai") else None
            file_problem = check_files(t, r["files"])
            if file_problem and not ai_problem:
                item["ok"] = False
                item["message"] = file_problem
            elif ai_problem:
                # неправильная работа с нейросетью — главная причина, объясняем её первой
                item["ok"] = False
                item["message"] = ai_problem
                item["ai_problem"] = True
            elif missing or extra:
                item["ok"] = False
                item["mismatch"] = True          # панель покажет переписку и пояснение
                item["why"] = t.get("fail", "")
                parts = []
                if t.get("fail"):
                    parts.append(t["fail"])
                if missing:
                    parts.append("Ждали в ответе: " + ", ".join(f"«{x}»" for x in missing) + ".")
                if extra:
                    parts.append("Лишнее в ответе: " + ", ".join(f"«{x}»" for x in extra) + ".")
                item["message"] = " ".join(parts)
        items.append(item)

    # 4. Конструкции
    feats = _features(tree, code)
    for s in task.get("structure", []):
        if "forbid" in s:
            # конструкция, которой быть НЕ должно (например, eval)
            ok = s["forbid"] not in feats
            items.append({"kind": "structure", "title": s.get("title") or f"нет {s['forbid'].split(':')[-1]}()",
                          "ok": ok, "message": "" if ok else s.get("msg", ""), "output": ""})
            continue
        need = s["need"]
        alts = need if isinstance(need, list) else [need]
        ok = any(a in feats for a in alts)
        items.append({"kind": "structure", "title": s.get("title") or FEATURE_TITLES.get(alts[0], alts[0]),
                      "ok": ok, "message": "" if ok else s.get("msg", ""), "output": ""})

    res["error"] = runtime_error
    passed = sum(1 for i in items if i["ok"])
    res["ok"] = passed == len(items) and len(items) > 0
    return done("Все проверки пройдены!" if res["ok"] else f"Пройдено {passed} из {len(items)}")


# ---------------------------------------------------------------------------
# Вывод для человека
# ---------------------------------------------------------------------------
def check_files(test: dict, files: dict) -> str | None:
    """Проверяет файлы, которые программа оставила после себя (например, memory.json)."""
    for name, words in (test.get("file_has") or {}).items():
        if name not in files:
            return test.get("fail_file") or f"Программа не сохранила файл {name}. Нужна запись: json.dump(...)."
        for w in words:
            if norm(w) not in norm(files[name]):
                return test.get("fail_file") or f"В файле {name} нет «{w}». Проверь, что сохраняешь данные после изменения."
    return None


def check_ai(rule: dict, calls: list) -> str | None:
    """Проверяет, как программа обращалась к нейросети. Возвращает понятное сообщение или None."""
    if rule.get("called") is False and calls:
        return rule.get("msg_not_called") or "Здесь бот отвечает сам — нейросеть тут не нужна (так экономим очередь)."
    if rule.get("called") is True and not calls:
        return rule.get("msg_called") or "Бот должен был спросить нейросеть, но не спросил. Нужен вызов ask(...)."
    if rule.get("min_calls") and len(calls) < rule["min_calls"]:
        return rule.get("msg_min_calls") or f"Нейросеть должна получить {rule['min_calls']} вопроса, а получила {len(calls)}."
    for word in rule.get("prompt_has", []):
        if not any(norm(word) in norm(c.get("prompt", "")) for c in calls):
            return rule.get("msg_prompt") or f"В вопросе к нейросети нет «{word}». Подставь то, что ввёл человек (например, через f-строку)."
    for word in rule.get("system_has", []):
        if not any(norm(word) in norm(c.get("system", "")) for c in calls):
            return rule.get("msg_system") or f"У бота нет роли со словом «{word}». Передай её так: ask(вопрос, system=\"...\")."
    for word in rule.get("text_has", []):
        if not any(norm(word) in norm(c.get("prompt", "") + " " + c.get("system", "")) for c in calls):
            return rule.get("msg_text") or f"Нейросеть не получила слово «{word}» ни в вопросе, ни в роли."
    for word in rule.get("history_has", []):
        # слово должно прийти в одном запросе вместе с более поздними репликами — то есть из истории
        if not any(norm(word) in norm(m["content"]) for c in calls for m in (c.get("all") or [])[:-1]):
            return rule.get("msg_history") or (f"Нейросеть не видит прошлых реплик: в переписке нет «{word}». "
                                               "Добавляй реплики в историю (history.append) и отправляй всю историю.")
    if rule.get("system_always") and not all(c.get("system") for c in calls):
        return rule.get("msg_system_always") or ("В одном из запросов пропала роль бота (system). "
                                                 "Первую реплику истории — system — никогда не удаляй.")
    for word in rule.get("last_lacks", []):
        if calls and any(norm(word) in norm(m["content"]) for m in calls[-1].get("all") or []):
            return rule.get("msg_last_lacks") or f"Бот всё ещё помнит «{word}», а должен был забыть."
    if rule.get("has_assistant") and not any(m["role"] == "assistant" for c in calls for m in c.get("all") or []):
        return rule.get("msg_assistant") or ("В истории нет ответов бота. Сохраняй и их: "
                                             "history.append({\"role\": \"assistant\", \"content\": answer}).")
    if "max_messages" in rule and any(c.get("messages", 0) > rule["max_messages"] for c in calls):
        return rule.get("msg_max") or (f"История растёт без конца: в запросе больше {rule['max_messages']} сообщений. "
                                       "Оставляй system и последние реплики.")
    for name in rule.get("tools_has", []):
        if not any(name in (c.get("tools") or []) for c in calls):
            return rule.get("msg_tools") or (f"Нейросеть не знает об инструменте «{name}». "
                                             "Опиши его через make_tool(...) в списке TOOLS и передай tools=TOOLS.")
    results = [m["content"] for c in calls for m in c.get("all") or [] if m["role"] == "tool"]
    if rule.get("tool_result_has") or rule.get("tool_ok"):
        for r in results:
            if r.startswith("Нет инструмента"):
                name = r.split()[-1]
                return (f"Нейросеть попросила инструмент «{name}», а в словаре функций нет такого имени. "
                        "Имя в make_tool(...) и ключ в словаре функций должны совпадать.")
            if r.startswith("Ошибка инструмента"):
                return (f"Инструмент сломался: {r}. Проверь функцию и то, как она берёт значения из args "
                        "(например, args[\"text\"] или args.get(\"sides\", 6)).")
    if rule.get("tool_ok"):
        if not results:
            return rule.get("msg_tool_ok") or "Нейросеть не смогла вызвать твой инструмент: проверь, что он описан в TOOLS через make_tool(...)."
        bad = [r for r in results if r.startswith(("Нет инструмента", "Ошибка инструмента"))]
        if bad:
            return (f"Инструмент не сработал: {bad[0]}. Имя в make_tool и в FUNCTIONS должно совпадать, "
                    "а значения функция берёт из args.")
    for word in rule.get("tool_result_has", []):
        if not any(c.get("after_tool") and any(m["role"] == "tool" and norm(word) in norm(m["content"]) for m in c["all"])
                   for c in calls):
            return rule.get("msg_tool_result") or (f"Нейросеть не получила результат инструмента (ждали «{word}»). "
                                                   "Запусти функцию и верни её ответ сообщением с ролью tool.")
    temps = [c.get("temperature") for c in calls if isinstance(c.get("temperature"), (int, float))]
    if "low_temp" in rule and not any(x <= rule["low_temp"] for x in temps):
        return f"Нужен вопрос со строгим режимом: temperature={rule['low_temp'] if rule['low_temp'] else 0}."
    if "high_temp" in rule and not any(x >= rule["high_temp"] for x in temps):
        return f"Нужен вопрос с творческим режимом: temperature={rule['high_temp']} или больше."
    return None


def print_report(task: dict, res: dict) -> None:
    print(f"\nЗадание {task.get('num', '')}. {task.get('title', '')}")
    print("=" * 50)
    if res["error"] and not res["items"]:
        e = res["error"]
        print(f"✗ {e['title']} {e.get('where', '')}")
        if e.get("code_line"):
            print(f"    {e['code_line'].strip()}")
        print(f"  {e['text']}")
        return
    if res["error"]:
        e = res["error"]
        print(f"✗ {e['title']} {e.get('where', '')}")
        if e.get("code_line"):
            print(f"    {e['code_line'].strip()}")
        print(f"  {e['text']}\n")
    for it in res["items"]:
        print(f"{'✓' if it['ok'] else '✗'} {it['title']}")
        if not it["ok"]:
            if it["message"]:
                print(f"    {it['message']}")
            if it["output"]:
                print("    Программа вывела:")
                for ln in it["output"].rstrip().splitlines()[-8:]:
                    print(f"      | {ln}")
    print("-" * 50)
    print(("🎉 " if res["ok"] else "") + res["summary"])


def run_interactive(path: str) -> int:
    """Режим «Запустить»: обычный запуск, но ошибка объясняется по-русски."""
    path = os.path.abspath(path)
    with open(path, encoding="utf-8") as fh:
        code = fh.read()
    sys.argv = [path]
    sys.path.insert(0, os.path.dirname(path))
    os.chdir(os.path.dirname(path))
    try:
        compile(code, path, "exec")
        runpy.run_path(path, run_name="__main__")
    except KeyboardInterrupt:
        print("\n⏹ Программа остановлена (Ctrl+C).")
        return 130
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except BaseException as e:  # noqa: BLE001 — показываем ученику любую ошибку
        sys.stdout.flush()
        # в трассировке оставляем только файлы ученика: без строк runpy и этой проверки
        folder = os.path.dirname(path)
        frames = [f for f in traceback.extract_tb(e.__traceback__)
                  if os.path.isfile(f.filename) and os.path.abspath(f.filename).startswith(folder) and os.path.abspath(f.filename) != os.path.abspath(__file__)]
        print("\nTraceback (most recent call last):", file=sys.stderr)
        print("".join(traceback.format_list(frames)) + "".join(traceback.format_exception_only(type(e), e)),
              end="", file=sys.stderr)
        exp = explain_exception(e, code, path)
        if os.environ.get("KURS_ERROR_FILE"):
            # панель VS Code подчеркнёт строку с ошибкой в редакторе
            try:
                with open(os.environ["KURS_ERROR_FILE"], "w", encoding="utf-8") as fh:
                    json.dump(exp, fh, ensure_ascii=False)
            except OSError:
                pass
        print("\n" + "─" * 50, file=sys.stderr)
        print(f"💡 {exp['title']} {exp['where']}".rstrip(), file=sys.stderr)
        if exp.get("code_line"):
            print(f"   {exp['code_line'].strip()}", file=sys.stderr)
        print(f"   {exp['text']}", file=sys.stderr)
        print("─" * 50, file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    if len(argv) >= 2 and argv[0] == "--run":
        return run_interactive(argv[1])
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    task, task_dir = load_task(args[0])
    with open(args[1], encoding="utf-8") as fh:
        code = fh.read()
    python = None
    for a in argv:
        if a.startswith("--python="):
            python = a.split("=", 1)[1]
    res = check(task, code, os.path.basename(args[1]), task_dir, python, os.path.dirname(os.path.abspath(args[1])))
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print_report(task, res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

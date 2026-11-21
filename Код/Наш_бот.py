# Наш_бот.py — бот вашей команды. Этот файл кладёт панель курса, менять его не нужно.
#
# Он сам собирает инструменты всех участников команды:
#   Мои_инструменты.py  — твои инструменты (их пишешь только ты);
#   Команда/*.py        — инструменты товарищей (панель приносит их сама, только для чтения).
# Имя бота, характер и тему команда задаёт в панели курса, вкладка «👥 Команда» (файл команда.json).
#
# Если в чьём-то файле ошибка — его инструменты временно выключаются, а бот работает с остальными.
# Команды в разговоре: /tools — какие инструменты есть и кто их сделал, /reset — забыть разговор, /exit — выйти.

import ast
import glob
import importlib.util
import io
import json
import os
import re
import tokenize

from agent import agent_answer, card_answer, make_tool, run_tool

HERE = os.path.dirname(os.path.abspath(__file__))
CARD_FILE = os.path.join(HERE, "команда.json")
MY_FILE = os.path.join(HERE, "Мои_инструменты.py")
TEAM_DIR = os.path.join(HERE, "Команда")
MEMORY_FILE = os.path.join(HERE, "память_бота.json")
MAX_HISTORY = 20

# Инструменты товарищей запускаются на твоём компьютере, поэтому сначала проверяем их файлы:
# только безопасные модули и никакого eval/exec (как на занятии про безопасные инструменты).
SAFE_MODULES = {"random", "datetime", "math", "time", "string", "json", "re", "agent"}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__", "input",
    "open", "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
}

_IGNORED_BLANK_TOKENS = {tokenize.STRING, tokenize.COMMENT}
for _tok_name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    if hasattr(tokenize, _tok_name):
        _IGNORED_BLANK_TOKENS.add(getattr(tokenize, _tok_name))


def has_blanks(code):
    """Есть ли в коде незаполненный пропуск ___ вне строк и комментариев."""
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in _IGNORED_BLANK_TOKENS:
                continue
            if "___" in tok.string:
                return True
        return False
    except (tokenize.TokenError, IndentationError):
        for line in code.splitlines():
            if line.lstrip().startswith("#"):
                continue
            no_str = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', "", line)
            if "___" in no_str.split("#", 1)[0]:
                return True
        return False


def load_card():
    try:
        with open(CARD_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _is_main_if(node):
    if not isinstance(node, ast.If):
        return False
    if hasattr(ast, "unparse"):
        return ast.unparse(node.test).replace("'", '"') == '__name__ == "__main__"'
    return (isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
            and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "__main__")


def _in_main_block(tree, target):
    """Лежит ли узел внутри блока «if __name__ == "__main__":»."""
    for node in tree.body:
        if _is_main_if(node) and any(sub is target for sub in ast.walk(node)):
            return True
    return False


def problem_in(code):
    """Почему файл с инструментами нельзя подключить (или None, если можно)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return f"Python не может прочитать файл (строка {error.lineno})"
    for node in tree.body:
        if isinstance(node, ast.If):
            if not _is_main_if(node):
                return f"строка {node.lineno}: код вне функций — перенеси его в функцию"
        elif isinstance(node, ast.Expr):
            # допускаем только строковый docstring на верхнем уровне
            if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                return f"строка {node.lineno}: вызов или выражение вне функций — перенеси в функцию или в if __name__ == \"__main__\""
        elif not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign,
                                   ast.AnnAssign, ast.AugAssign)):
            return f"строка {node.lineno}: цикл или другой код вне функций — перенеси его в функцию"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            for name in names:
                if name.split(".")[0] not in SAFE_MODULES:
                    return f"строка {node.lineno}: модуль {name} инструментам не нужен (можно: {', '.join(sorted(SAFE_MODULES))})"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"строка {node.lineno}: обращение к служебному атрибуту {node.attr} в инструментах запрещено"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            # input() внутри «if __name__ == "__main__":» не страшен — этот кусок здесь не запускается
            if node.func.id == "input" and _in_main_block(tree, node):
                continue
            return f"строка {node.lineno}: {node.func.id}() в инструментах нельзя"
    return None


def tool_files():
    """[(автор, путь)]: сначала свой файл, потом файлы товарищей."""
    out = []
    if os.path.isfile(MY_FILE):
        out.append(("ты", MY_FILE))
    for path in sorted(glob.glob(os.path.join(TEAM_DIR, "*.py"))):
        out.append((os.path.splitext(os.path.basename(path))[0].replace("_", " "), path))
    return out


def load_tools(cards=None):
    tools, functions, owners = [], {}, {}
    for n, (author, path) in enumerate(tool_files()):
        with open(path, encoding="utf-8") as f:
            code = f.read()
        if has_blanks(code):
            print(f"  ⏳ {author}: в файле ещё есть пропуски ___ — инструменты пока выключены")
            continue
        problem = problem_in(code)
        if problem:
            print(f"  ⚠ {author}: {problem} — инструменты пока выключены")
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"team_tools_{n}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as error:
            print(f"  ⚠ {author}: ошибка в файле ({type(error).__name__}: {error}) — инструменты пока выключены")
            continue
        if hasattr(module, "CARD_TITLE"):
            title = module.CARD_TITLE
            get_card = getattr(module, "get_card", None)
            if not isinstance(title, str) or not title.strip() or not callable(get_card):
                print(f"  ⏳ {author}: заполни название и текст карточки в своём файле")
                continue
            name = f"course_card_{n + 1}"
            while name in owners:
                name += "_"
            title = title.strip()
            tools.append(make_tool(name, f'Выдать карточку команды «{title}» по просьбе пользователя.'))
            functions[name] = lambda args, fn=get_card: card_answer(fn)
            owners[name] = author
            if cards is not None:
                cards[name] = title
            continue
        their_tools = getattr(module, "TOOLS", [])
        their_functions = getattr(module, "FUNCTIONS", {})
        for tool in their_tools:
            name = tool.get("function", {}).get("name", "?")
            if name in owners:
                who = "тебя" if owners[name] == "ты" else f"«{owners[name]}»"
                print(f"  ⚠ {author}: инструмент {name} уже есть у {who} — договоритесь и переименуйте")
            elif name not in their_functions:
                print(f"  ⚠ {author}: {name} есть в TOOLS, но нет в FUNCTIONS")
            else:
                tools.append(tool)
                functions[name] = their_functions[name]
                owners[name] = author
    return tools, functions, owners


def load_history():
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_history(history):
    clean = [m for m in history if m["role"] in ("user", "assistant") and m.get("content")]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)


def show_tools(owners, cards):
    if not owners:
        print("  Инструментов пока нет: напишите их в Мои_инструменты.py и сохраните (Ctrl+S).")
        return
    by_author = {}
    for name, author in owners.items():
        by_author.setdefault(author, []).append(cards.get(name, name))
    for author, names in by_author.items():
        print(f"  🔧 {author}: {', '.join(names)}")


def main():
    card = load_card()
    bot_name = card.get("bot_name") or "Бот команды"
    team = card.get("team") or "без названия"
    persona = (f"Ты {bot_name}. {card.get('persona') or 'Дружелюбный помощник.'} "
               f"{('Тема: ' + card['topic'] + '. ') if card.get('topic') else ''}"
               "Говоришь по-русски, коротко. Если подходит инструмент — используй его, а не выдумывай.")
    print(f"🤖 {bot_name} — бот команды «{team}»")
    cards = {}
    tools, functions, owners = load_tools(cards)
    show_tools(owners, cards)
    history = load_history()
    print(f"{bot_name} на связи! /demo — показать карточки, /tools — список, /exit — выйти.")
    if history:
        print(f"(помню наш прошлый разговор: {len(history)} реплик)")
    while True:
        try:
            text = input("Ты: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо встречи!")
            break
        if text.lower() == "/exit":
            break
        if text.lower() == "/tools":
            show_tools(owners, cards)
            continue
        if text.lower() == "/demo":
            if not cards:
                print("Сначала сохрани хотя бы одну карточку в Мои_инструменты.py и перезапусти бота.")
            for name, title in cards.items():
                print(f"{title} ({owners[name]}): {run_tool(functions, name, {})}")
            continue
        if text.lower() == "/reset":
            history = []
            save_history(history)
            print(f"{bot_name}: всё забыл!")
            continue
        if not text:
            continue
        messages = [{"role": "system", "content": persona}] + history
        messages.append({"role": "user", "content": text})
        answer = agent_answer(messages, tools, functions)
        print(f"{bot_name}:", answer)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": answer})
        history = history[-MAX_HISTORY:]
        save_history(history)


if __name__ == "__main__":
    main()

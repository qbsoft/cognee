import io
import sys
import traceback


def wrap_in_async_handler(user_code: str) -> str:
    return (
        "import asyncio\n"
        + "asyncio.set_event_loop(running_loop)\n\n"
        + "from cognee.infrastructure.utils.run_sync import run_sync\n\n"
        + "async def __user_main__():\n"
        + "\n".join("    " + line for line in user_code.strip().split("\n"))
        + "\n"
        + "    globals().update(locals())\n\n"
        + "run_sync(__user_main__(), running_loop)\n"
    )


def normalize_chinese_punctuation(code: str) -> str:
    """
    Convert full-width (Chinese) punctuation to half-width (ASCII) punctuation
    to avoid syntax errors in Python code.
    """
    punctuation_map = {
        '，': ',',   # Chinese comma to ASCII comma
        '。': '.',   # Chinese period to ASCII period
        '！': '!',   # Chinese exclamation to ASCII
        '？': '?',   # Chinese question mark to ASCII
        '；': ';',   # Chinese semicolon to ASCII
        '：': ':',   # Chinese colon to ASCII
        '（': '(',   # Chinese left paren to ASCII
        '）': ')',   # Chinese right paren to ASCII
        '【': '[',   # Chinese left bracket to ASCII
        '】': ']',   # Chinese right bracket to ASCII
        '｛': '{',   # Full-width left brace to ASCII
        '｝': '}',   # Full-width right brace to ASCII
    }
    
    for chinese_punct, ascii_punct in punctuation_map.items():
        code = code.replace(chinese_punct, ascii_punct)
    
    return code


def run_in_local_sandbox(code, environment=None, loop=None):
    environment = environment or {}
    
    # Normalize Chinese punctuation before processing
    code = normalize_chinese_punctuation(code)
    code = wrap_in_async_handler(code.replace("\xa0", "\n"))

    buffer = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = buffer
    sys.stderr = buffer

    error = None

    printOutput = []

    def customPrintFunction(output):
        printOutput.append(output)

    environment["print"] = customPrintFunction
    environment["running_loop"] = loop

    try:
        exec(code, environment)
    except SyntaxError as e:
        # Provide more helpful error message for common syntax errors
        error_msg = str(e)
        
        # Check if the error is due to bare Chinese/English text (not in a string)
        if 'invalid syntax' in error_msg.lower():
            # Try to detect if this is bare text without quotes
            original_code_lines = code.split('\n')
            error_line_no = e.lineno if hasattr(e, 'lineno') else None
            
            if error_line_no and error_line_no <= len(original_code_lines):
                error_line = original_code_lines[error_line_no - 1].strip()
                
                # Check if line doesn't start with Python keywords/symbols
                if error_line and not any(error_line.startswith(kw) for kw in 
                    ['import', 'from', 'def', 'class', 'if', 'for', 'while', 'try', 
                     'print', 'return', '#', '@', 'await', 'async']):
                    
                    # Check if line contains Chinese characters or looks like plain text
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in error_line)
                    has_no_assignment = '=' not in error_line and '(' not in error_line
                    
                    if has_chinese or (has_no_assignment and len(error_line) > 10):
                        error = (
                            f"SyntaxError: 这看起来是纯文本，而不是 Python 代码。\n\n"
                            f"错误的代码：\n  {error_line}\n\n"
                            f"建议的修复方法：\n"
                            f"1. 如果这是要输出的文本，请使用：\n"
                            f"   text = \"{error_line}\"\n"
                            f"   print(text)\n\n"
                            f"2. 如果这是注释，请使用：\n"
                            f"   # {error_line}\n\n"
                            f"原始错误: {error_msg}"
                        )
                        return printOutput, error
        
        # Default syntax error handling
        error = traceback.format_exc()
    except Exception:
        error = traceback.format_exc()
    finally:
        sys.stdout = sys_stdout
        sys.stderr = sys_stdout

    return printOutput, error


if __name__ == "__main__":
    run_in_local_sandbox("""
import cognee

await cognee.add("Test file with some random content 3.")

a = "asd"

b = {"c": "dfgh"}
""")

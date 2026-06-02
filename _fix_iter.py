"""
Comprehensive fix for writing_mode.py - handles all problematic quote patterns.
Uses iterative approach: fix one error, re-compile, repeat.
"""
import sys, os, py_compile, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(r"c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent")

from src.utils.text_sanitizer import safe_dict_value, safe_writing_for_python

MAX_ITER = 30

for iteration in range(MAX_ITER):
    # Check current state
    try:
        py_compile.compile('src/core/writing_mode.py', doraise=True)
        print(f"\n=== SUCCESS after {iteration} iterations ===")
        break
    except py_compile.PyCompileError as e:
        err_str = str(e)
        m = re.search(r'line (\d+)', err_str)
        if not m:
            print(f"Cannot parse error at iteration {iteration}")
            print(err_str[:500])
            break
        
        err_line = int(m.group(1))
        
        # Read file
        with open('src/core/writing_mode.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        line = lines[err_line - 1]
        
        # Strategy: for lines with problematic inner quotes,
        # convert the value part to single-quoted format if possible,
        # or replace inner double quotes with angle brackets
        
        # First check: does the line contain a Python string with inner " issues?
        # Patterns that fail:
        # ""text""text"..."  ->  ""text"" is parsed as empty string + identifier
        # We need to find what the intended single string value is
        
        # For lines like:    "value with "inner" text",
        # or:                 "value with ""inner"" text",
        
        # Approach: find the indentation level, then extract the full line content
        indent = len(line) - len(line.lstrip())
        
        # Determine if this is inside a list [] or not
        # Look at surrounding context
        context_start = max(0, err_line - 3)
        context_end = min(len(lines), err_line + 1)
        context = ''.join(lines[context_start:context_end])
        
        # The problematic line usually looks like:
        #   "text1"  --> valid
        #   ""text""  --> ERROR: "" is empty string, then text"" is invalid
        #   ""text1""text2""  --> multiple issues
        
        stripped = line.strip()
        
        # Try to reconstruct what was intended
        # If the line has patterns like ""X""Y"" where X and Y are Chinese text,
        # the intended value is probably: "X"Y"  (with inner Chinese quotes)
        
        # We'll use safe_dict_value to sanitize the whole thing
        # But first we need to figure out the actual string content
        
        # Strip the leading whitespace and trailing comma
        if stripped.endswith(','):
            stripped = stripped[:-1].strip()
        
        # Remove outer quotes if present
        if stripped.startswith('"') and stripped.endswith('"'):
            inner = stripped[1:-1]
            # Sanitize
            safe_inner = safe_dict_value(inner)
            new_stripped = '"' + safe_inner + '"'
        elif stripped.startswith('"'):
            # Starts with quote but doesn't end with one (multi-part)
            inner = stripped[1:]
            safe_inner = safe_dict_value(inner)
            new_stripped = '"' + safe_inner + '"'
        else:
            # Try to reconstruct
            safe_inner = safe_dict_value(stripped)
            new_stripped = '"' + safe_inner + '"'
        
        # Re-add trailing comma if original had it
        if lines[err_line - 1].rstrip().endswith(','):
            new_stripped += ','
        
        new_line = ' ' * indent + new_stripped + '\n'
        
        if new_line.strip() != lines[err_line - 1].strip():
            print(f"Iter {iteration+1}: Fixed line {err_line}")
            print(f"  OLD: {lines[err_line-1].rstrip()[:120]}")
            print(f"  NEW: {new_line.rstrip()[:120]}")
        else:
            print(f"Iter {iteration+1}: Line {err_line} unchanged, may need different fix")
            # Show context
            print(f"  LINE: {lines[err_line-1].rstrip()[:200]}")
            # The issue might be a multi-line structure problem
            # or the error is actually on a different line
            break
        
        lines[err_line - 1] = new_line
        
        with open('src/core/writing_mode.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
else:
    print(f"\n=== Did not converge after {MAX_ITER} iterations ===")
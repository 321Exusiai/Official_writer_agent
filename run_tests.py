import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open('tests/test_all.py', encoding='utf-8').read())
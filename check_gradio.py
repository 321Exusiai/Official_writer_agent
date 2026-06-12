"""检查 gradio_app.py 中的返回值匹配问题"""
import ast
import re

def count_return_values(code):
    """统计函数中所有 return 语句的返回值数量"""
    tree = ast.parse(code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'GradioApp':
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    func_name = item.name
                    returns = []
                    
                    for n in ast.walk(item):
                        if isinstance(n, ast.Return):
                            if isinstance(n.value, ast.Tuple):
                                returns.append(len(n.value.elts))
                            elif n.value is None:
                                returns.append(0)
                            else:
                                returns.append(1)
                    
                    if returns:
                        unique = set(returns)
                        if len(unique) > 1:
                            print(f"❌ {func_name}: 返回值数量不一致 {unique}")
                        else:
                            print(f"✓ {func_name}: 返回 {returns[0]} 个值")

# 读取文件
with open('gradio_app.py', 'r', encoding='utf-8') as f:
    code = f.read()

print("=== 检查 GradioApp 类中的返回值 ===\n")
count_return_values(code)

print("\n=== 检查事件绑定的 outputs 数量 ===\n")

# 提取事件绑定
pattern = r'(\w+)\.click\(\s*fn=.*?outputs=\[(.*?)\]'
matches = re.findall(pattern, code, re.DOTALL)

for button, outputs in matches:
    outputs_list = [o.strip() for o in outputs.split(',') if o.strip()]
    print(f"{button}: {len(outputs_list)} 个 outputs")

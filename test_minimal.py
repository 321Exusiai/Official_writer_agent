"""测试 Gradio 5.x 输入处理 - 带日志版本"""
import gradio as gr

def process(name: str, session: dict):
    print(f"\n=== 函数被调用 ===")
    print(f"name = '{name}'")
    print(f"name type = {type(name)}")
    print(f"name is None = {name is None}")
    print(f"name repr = {repr(name)}")
    
    if name is None:
        return "输入为 None", session
    if not name:
        return "输入为空字符串", session
    if not name.strip():
        return f"输入只有空白: {repr(name)}", session
    
    session["name"] = name.strip()
    return f"成功！你输入了: {name}", session

with gr.Blocks() as demo:
    session = gr.State({})
    name_input = gr.Textbox(label="用户名", placeholder="输入中文名字")
    btn = gr.Button("确认")
    output = gr.Markdown()
    
    btn.click(
        fn=process,
        inputs=[name_input, session],
        outputs=[output, session]
    )

demo.launch(server_name="127.0.0.1", server_port=7862, share=False)

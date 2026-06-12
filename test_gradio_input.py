"""测试 Gradio 输入处理"""
import gradio as gr

def test_input(text: str):
    print(f"Received input: '{text}'")
    print(f"Type: {type(text)}")
    print(f"Length: {len(text) if text else 0}")
    return f"你输入了: {text}"

with gr.Blocks() as demo:
    t = gr.Textbox(label="测试输入")
    b = gr.Button("测试")
    o = gr.Textbox(label="输出")
    b.click(fn=test_input, inputs=[t], outputs=[o])

demo.launch(server_name="127.0.0.1", server_port=7861)

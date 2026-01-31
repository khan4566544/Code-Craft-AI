
import gradio as gr
import os
import json
from pathlib import Path

class MockAgent:
    def chat(self, message, history):
        responses = {
            "hello": "Hello! I'm your AI coding assistant. How can I help with coding today?",
            "help": "I can help with:\n• Writing code\n• Code reviews\n• Debugging\n• Explaining concepts\n• File operations",
            "write python function": "def example():\n    return 'Hello from AI assistant'",
        }
        
        # Simple response matching
        msg_lower = message.lower()
        for key in responses:
            if key in msg_lower:
                return responses[key]
        
        return f"I received: {message}. This is a mock response. In production, this would call Cohere API."

# Initialize agent
agent = MockAgent()

# File system for workspace
WORKSPACE_DIR = "workspace"
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def chat_with_agent(message, history):
    """Chat interface for the agent"""
    response = agent.chat(message, history)
    history.append((message, response))
    return history, history, ""  # Return updated history and clear input

def list_files():
    """List files in workspace"""
    files = []
    for root, dirs, filenames in os.walk(WORKSPACE_DIR):
        for filename in filenames:
            if not filename.startswith('.'):
                rel_path = os.path.relpath(os.path.join(root, filename), WORKSPACE_DIR)
                files.append(rel_path)
    return "\n".join(files[:20]) or "No files in workspace"

def read_file(filepath):
    """Read a file"""
    full_path = os.path.join(WORKSPACE_DIR, filepath)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, 'r') as f:
                return f.read()
        except:
            return "Error reading file"
    return "File not found"

def write_file(filepath, content):
    """Write to a file"""
    try:
        full_path = os.path.join(WORKSPACE_DIR, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return f"✅ File saved: {filepath}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def create_example_files():
    """Create example files"""
    examples = {
        "example.py": """def hello_world():
    print("Hello, World!")

def add_numbers(a, b):
    return a + b

if __name__ == "__main__":
    hello_world()
    print(f"2 + 3 = {add_numbers(2, 3)}")""",
        "README.md": """# AI Coding Agent Workspace

Welcome to the AI Coding Agent!

This is a demo workspace for the Hugging Face Space."""
    }
    
    results = []
    for filename, content in examples.items():
        result = write_file(filename, content)
        results.append(f"{filename}: {result}")
    
    return "\n".join(results)

# Gradio interface
with gr.Blocks(title="AI Coding Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 AI Coding Agent")
    gr.Markdown("An intelligent coding assistant that can help write, review, and explain code.")
    
    with gr.Tabs():
        with gr.TabItem("💬 Chat"):
            chatbot = gr.Chatbot(label="Conversation", height=400)
            msg = gr.Textbox(label="Your message", placeholder="Ask me about coding...")
            clear = gr.Button("Clear")
            
            def respond(message, chat_history):
                bot_message = agent.chat(message, chat_history)
                chat_history.append((message, bot_message))
                return "", chat_history
            
            msg.submit(respond, [msg, chatbot], [msg, chatbot])
            clear.click(lambda: None, None, chatbot, queue=False)
        
        with gr.TabItem("📁 Files"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### File Operations")
                    file_list = gr.Textbox(label="Workspace Files", interactive=False, lines=10)
                    refresh_btn = gr.Button("🔄 Refresh Files")
                    
                    file_name = gr.Textbox(label="Filename", placeholder="example.py")
                    file_content = gr.Textbox(label="Content", lines=10, placeholder="Your code here...")
                    save_btn = gr.Button("💾 Save File")
                    
                    create_examples_btn = gr.Button("📝 Create Example Files")
                    
                    def update_file_list():
                        return list_files()
                    
                    refresh_btn.click(update_file_list, outputs=file_list)
                    create_examples_btn.click(create_example_files, outputs=file_list)
                    
                    def save_file(fname, content):
                        result = write_file(fname, content)
                        return result, update_file_list()
                    
                    save_btn.click(save_file, [file_name, file_content], 
                                  [gr.Textbox(label="Result"), file_list])
                
                with gr.Column(scale=1):
                    gr.Markdown("### Read File")
                    read_filename = gr.Textbox(label="Filename to read", placeholder="example.py")
                    read_btn = gr.Button("📖 Read File")
                    file_display = gr.Textbox(label="File Content", interactive=False, lines=20)
                    
                    def display_file(filename):
                        return read_file(filename)
                    
                    read_btn.click(display_file, inputs=read_filename, outputs=file_display)
        
        with gr.TabItem("⚙️ Settings"):
            gr.Markdown("### Agent Settings")
            
            persona = gr.Radio(
                choices=["Coder", "Reviewer", "Architect"],
                value="Coder",
                label="Agent Persona"
            )
            
            temperature = gr.Slider(
                minimum=0.0,
                maximum=1.0,
                value=0.2,
                step=0.1,
                label="Creativity (Temperature)"
            )
            
            api_key = gr.Textbox(
                label="Cohere API Key (optional)",
                type="password",
                placeholder="Enter your API key for full functionality"
            )
            
            save_settings = gr.Button("Save Settings")
            settings_status = gr.Textbox(label="Status", interactive=False)
            
            def save_settings_func(persona_val, temp_val, api_val):
                # In production, save to config
                return f"Settings saved: {persona_val} mode, Temperature: {temp_val}"
            
            save_settings.click(
                save_settings_func,
                [persona, temperature, api_key],
                outputs=settings_status
            )
    
    gr.Markdown("---")
    gr.Markdown("### Quick Examples")
    
    with gr.Row():
        examples = [
            ("Write a Python function to check prime numbers", "💬 Chat"),
            ("Explain recursion with an example", "💬 Chat"),
            ("Review this code: def add(a,b): return a+b", "💬 Chat"),
            ("Create a REST API structure", "💬 Chat"),
        ]
        
        for example_text, tab in examples:
            btn = gr.Button(example_text)
            # This would need JavaScript to switch tabs - simplified for demo

if __name__ == "__main__":
    demo.launch()
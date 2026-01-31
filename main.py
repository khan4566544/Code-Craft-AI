# Entry point for CLI version
import cohere
from dotenv import load_dotenv
import os
import json
from pathlib import Path
import ast
import re
from Prompts.system_prompts import (
    COHERE_CODING_AGENT,
    COHERE_CODE_REVIEWER, 
    COHERE_ARCHITECT
)

load_dotenv()

cohere_api_key = os.getenv("COHERE_API_KEY")
print(cohere_api_key[0:5] + "*" * len(cohere_api_key) if cohere_api_key else "No API key found")

co = cohere.ClientV2(cohere_api_key)


class FileSystemManager:
    """Manages file reading, writing, and analysis"""
    
    def __init__(self, workspace_dir="workspace"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.create_workspace()
        
        # Unsafe patterns for security
        self.unsafe_patterns = [
            r"os\.system\(",
            r"subprocess\.[^Popen]",  # Allow Popen with validation
            r"eval\(",
            r"exec\(",
            r"__import__\(",
            r"rm -rf",
            r"shutil\.rmtree",
        ]
    
    def create_workspace(self):
        """Create workspace directory if it doesn't exist"""
        os.makedirs(self.workspace_dir, exist_ok=True)
        print(f"📁 Workspace: {self.workspace_dir}")
    
    def read_file(self, file_path):
        """Read a file with safety checks"""
        try:
            # Convert to absolute path within workspace
            abs_path = self._resolve_path(file_path)
            
            # Security check
            if not self._is_safe_path(abs_path):
                return {"error": f"Access restricted: {file_path}"}
            
            if not os.path.exists(abs_path):
                return {"error": f"File not found: {file_path}"}
            
            if not os.path.isfile(abs_path):
                return {"error": f"Not a file: {file_path}"}
            
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {
                "success": True,
                "path": abs_path,
                "content": content,
                "size": len(content),
                "lines": len(content.split('\n'))
            }
            
        except PermissionError:
            return {"error": f"Permission denied: {file_path}"}
        except Exception as e:
            return {"error": f"Error reading {file_path}: {str(e)}"}
    
    def write_file(self, file_path, content):
        """Write content to a file"""
        try:
            abs_path = self._resolve_path(file_path)
            
            # Security check
            if not self._is_safe_path(abs_path):
                return {"error": f"Write restricted: {file_path}"}
            
            # Create directory if needed
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "path": abs_path,
                "message": f"File written: {abs_path}",
                "size": len(content)
            }
            
        except Exception as e:
            return {"error": f"Error writing {file_path}: {str(e)}"}
    
    def create_file(self, file_path, content=""):
        """Create a new file with optional content"""
        return self.write_file(file_path, content)
    
    def list_files(self, directory=".", pattern="*"):
        """List files in a directory"""
        try:
            dir_path = self._resolve_path(directory)
            
            if not os.path.exists(dir_path):
                return {"error": f"Directory not found: {directory}"}
            
            if not os.path.isdir(dir_path):
                return {"error": f"Not a directory: {directory}"}
            
            files = []
            for root, dirs, filenames in os.walk(dir_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if not filename.startswith('.'):  # Skip hidden files
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, self.workspace_dir)
                        
                        try:
                            stat = os.stat(full_path)
                            files.append({
                                "name": filename,
                                "path": rel_path,
                                "size": stat.st_size,
                                "modified": stat.st_mtime
                            })
                        except:
                            continue
            
            return {
                "success": True,
                "directory": dir_path,
                "files": sorted(files, key=lambda x: x["path"]),
                "count": len(files)
            }
            
        except Exception as e:
            return {"error": f"Error listing files: {str(e)}"}
    
    def analyze_file(self, file_path):
        """Analyze a Python file using AST"""
        read_result = self.read_file(file_path)
        if "error" in read_result:
            return read_result
        
        content = read_result["content"]
        
        try:
            tree = ast.parse(content)
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
            
            return {
                "success": True,
                "path": read_result["path"],
                "valid_python": True,
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "analysis": f"Found {len(functions)} functions, {len(classes)} classes, {len(imports)} imports"
            }
            
        except SyntaxError as e:
            return {
                "success": False,
                "path": read_result["path"],
                "valid_python": False,
                "error": f"Syntax error at line {e.lineno}: {e.msg}"
            }
        except Exception as e:
            return {
                "success": False,
                "path": read_result["path"],
                "error": f"Analysis error: {str(e)}"
            }
    
    def _resolve_path(self, path):
        """Resolve path relative to workspace"""
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace_dir, path)
    
    def _is_safe_path(self, path):
        """Check if path is safe to access"""
        abs_path = os.path.abspath(path)
        
        # Must be within workspace
        if not abs_path.startswith(self.workspace_dir):
            return False
        
        # Block sensitive files
        sensitive = ['.env', 'secret', 'password', 'key', 'token', '.git', '__pycache__']
        for pattern in sensitive:
            if pattern in abs_path.lower():
                return False
        
        return True

# Initialize file system manager
fs = FileSystemManager()

# ===== Enhanced Agent Functions =====
def coding_agent(task, context="", persona="coder", file_context=None):
    """Enhanced coding agent with file context support"""
    
    persona_prompts = {
        'coder': COHERE_CODING_AGENT,
        'reviewer': COHERE_CODE_REVIEWER,
        'architect': COHERE_ARCHITECT
    }
    
    system_prompt = persona_prompts.get(persona, COHERE_CODING_AGENT)
    full_prompt = f"{system_prompt}\n\nTask: {task}"
    
    if context:
        full_prompt += f"\n\nCode Context:\n```python\n{context}\n```"
    
    if file_context:
        full_prompt += f"\n\nFile Context:\n{file_context}"
    
    response = co.chat(
        model="command-a-03-2025",
        messages=[
            {
                "role": "user",
                "content": full_prompt,
            }
        ],
    )
    
    return response.message.content[0].text

def simple_agent():
    """Test the function"""
    response = co.chat(
        model='command-a-03-2025',
        messages=[
            {
                'role': 'user',
                'content': "I'm joining a new startup called Co1t today. Could you help me write a one-sentence introduction message to my teammates"
            }
        ],
    )
    print(response.message.content[0].text)

def interactive_agent():
    """CLI for the agent with file operations"""
    print("🤖 AI Coding Agent (with File System)")
    print("Type 'quit' to exit, 'help' for commands\n")
    
    while True:
        user_input = input("\n> ").strip()
        
        if user_input.lower() == 'quit':
            print("Goodbye!")
            break
        
        elif user_input.lower() == 'help':
            print("\n📚 COMMANDS:")
            print("  help                    - Show this help")
            print("  quit                    - Exit")
            print("  test                    - Test agent")
            print("  read <file>             - Read a file")
            print("  write <file> <content>  - Write to file")
            print("  create <file> [content] - Create new file")
            print("  list [dir]              - List files")
            print("  analyze <file>          - Analyze Python file")
            print("  review <file/code>      - Review code")
            print("  architect <task>        - Use architect")
            print("  edit <file>             - Edit file with AI")
            print("  Or ask any coding question!")
            continue
        
        elif user_input.lower() == 'test':
            print("\n🧪 Testing agent...")
            result = coding_agent(
                "Write Python function to check prime numbers",
                persona="coder"
            )
            print(f"\n{result}")
        
        # ===== FILE OPERATIONS =====
        elif user_input.lower().startswith('read '):
            file_path = user_input[5:].strip()
            if not file_path:
                print("❌ Please provide file path")
                continue
            
            print(f"\n📖 Reading {file_path}...")
            result = fs.read_file(file_path)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ File: {result['path']}")
                print(f"Size: {result['size']} chars, Lines: {result['lines']}")
                print("-" * 60)
                # Show first 500 chars
                preview = result['content']
                if len(preview) > 500:
                    preview = preview[:500] + "...\n[Truncated]"
                print(preview)
                print("-" * 60)
        
        elif user_input.lower().startswith('write '):
            parts = user_input[6:].strip().split(' ', 1)
            if len(parts) < 2:
                print("❌ Usage: write <file> <content>")
                continue
            
            file_path, content = parts
            print(f"\n✏️ Writing to {file_path}...")
            result = fs.write_file(file_path, content)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ {result['message']}")
        
        elif user_input.lower().startswith('create '):
            parts = user_input[7:].strip().split(' ', 1)
            file_path = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            
            print(f"\n📝 Creating {file_path}...")
            result = fs.create_file(file_path, content)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ File created: {result['path']}")
                if content:
                    print(f"   With {len(content)} characters of content")
        
        elif user_input.lower().startswith('list'):
            dir_path = user_input[5:].strip() or "."
            print(f"\n📁 Listing files in {dir_path}...")
            result = fs.list_files(dir_path)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ Directory: {result['directory']}")
                print(f"Found {result['count']} files:")
                print("-" * 60)
                for file_info in result['files'][:20]:  # Show first 20
                    size_kb = file_info['size'] / 1024
                    print(f"{file_info['path']:40} ({size_kb:.1f} KB)")
                
                if result['count'] > 20:
                    print(f"... and {result['count'] - 20} more files")
                print("-" * 60)
        
        elif user_input.lower().startswith('analyze '):
            file_path = user_input[8:].strip()
            if not file_path:
                print("❌ Please provide file path")
                continue
            
            print(f"\n🔍 Analyzing {file_path}...")
            result = fs.analyze_file(file_path)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            elif not result.get("valid_python", True):
                print(f"⚠️  {result['error']}")
            else:
                print(f"✅ Valid Python file: {result['path']}")
                print(f"📊 Analysis: {result['analysis']}")
                
                if result['functions']:
                    print("\n📋 Functions:")
                    for func in result['functions'][:5]:  # Show first 5
                        args = ', '.join(func['args'])
                        print(f"  • {func['name']}({args}) (line {func['line']})")
                
                if result['classes']:
                    print("\n🏗️ Classes:")
                    for cls in result['classes'][:5]:
                        print(f"  • {cls['name']} (line {cls['line']})")
                
                if result['imports']:
                    print("\n📦 Imports:")
                    for imp in result['imports'][:10]:  # Show first 10
                        print(f"  • {imp}")
        
        elif user_input.lower().startswith('review'):
            # Check if it's a file or inline code
            target = user_input[7:].strip()
            
            if os.path.exists(target) or '/' in target or '.' in target:
                # It's probably a file path
                print(f"\n🔍 Reviewing file: {target}")
                read_result = fs.read_file(target)
                
                if "error" in read_result:
                    print(f"❌ Error reading file: {read_result['error']}")
                    continue
                
                context = read_result['content']
                print(f"📄 Read {len(context)} characters from file")
            else:
                # It's inline code
                context = target
                if not context:
                    print("❌ Please provide code or file path to review")
                    continue
                print(f"\n🔍 Reviewing code ({len(context)} chars)...")
            
            print("🤖 Analyzing with AI reviewer...")
            result = coding_agent(
                "Review this code for security issues, bugs, and improvements",
                context=context,
                persona="reviewer"
            )
            print(f"\n{result}")
        
        elif user_input.lower().startswith('edit '):
            # AI-powered file editing
            parts = user_input[5:].strip().split(' ', 1)
            if len(parts) < 2:
                print("❌ Usage: edit <file> <instructions>")
                continue
            
            file_path, instructions = parts
            print(f"\n✏️ Editing {file_path} with AI...")
            
            # Read current file
            read_result = fs.read_file(file_path)
            if "error" in read_result:
                print(f"❌ Error reading file: {read_result['error']}")
                continue
            
            current_content = read_result['content']
            print(f"📄 Current file: {len(current_content)} characters")
            
            # Ask AI to edit
            edit_prompt = f"""Edit this file according to these instructions:
            
            File: {file_path}
            Instructions: {instructions}
            
            Current content:
            ```python
            {current_content[:1000]}  # First 1000 chars
            ```
            
            Return the COMPLETE new file content. Only output the code, no explanations."""
            
            print("🤖 AI is editing the file...")
            try:
                new_content = coding_agent(edit_prompt, context=current_content, persona="coder")
                
                # Write edited content
                write_result = fs.write_file(file_path, new_content)
                if "error" in write_result:
                    print(f"❌ Error saving: {write_result['error']}")
                else:
                    print(f"✅ File updated: {write_result['path']}")
                    print(f"   New size: {len(new_content)} characters")
                    
                    # Show diff summary
                    old_lines = current_content.split('\n')
                    new_lines = new_content.split('\n')
                    print(f"   Lines changed: {abs(len(new_lines) - len(old_lines))}")
            
            except Exception as e:
                print(f"❌ AI editing failed: {str(e)}")
        
        elif user_input.lower().startswith('architect'):
            task = user_input[10:].strip()
            if not task:
                print("❌ Please provide a task for the architect")
                continue
            
            print("\n🏗️ Architect thinking...")
            result = coding_agent(task, persona="architect")
            print(f"\n{result}")
        
        else:
            # Check if query mentions a file
            file_mentioned = None
            for word in user_input.split():
                if '.' in word and not word.startswith('.'):
                    # Might be a file reference
                    possible_file = word.strip('.,!?;:"\'')
                    if os.path.exists(possible_file) or '/' in possible_file:
                        file_mentioned = possible_file
                        break
            
            if file_mentioned:
                # Try to read the file for context
                print(f"\n📄 Detected file reference: {file_mentioned}")
                read_result = fs.read_file(file_mentioned)
                
                if "error" not in read_result:
                    print(f"✅ Adding file context ({len(read_result['content'])} chars)")
                    file_context = f"File '{file_mentioned}' content:\n{read_result['content'][:2000]}"
                    result = coding_agent(user_input, file_context=file_context, persona="coder")
                else:
                    print(f"⚠️  Could not read file, proceeding without context")
                    result = coding_agent(user_input, persona="coder")
            else:
                # General coding question
                result = coding_agent(user_input, persona="coder")
            
            print(f"\n🤖 Assistant:\n{result}")

# ===== Example Files Creation =====
def setup_example_files():
    """Create example files in workspace"""
    examples = {
        "math_operations.py": """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

# Test the functions
if __name__ == "__main__":
    print("Testing math operations:")
    print(f"2 + 3 = {add(2, 3)}")
    print(f"5 - 2 = {subtract(5, 2)}")
    print(f"4 * 6 = {multiply(4, 6)}")
    print(f"10 / 2 = {divide(10, 2)}")""",
        
        "data_processor.py": """import json
from typing import List, Dict, Any

class DataProcessor:
    def __init__(self):
        self.data = []
    
    def load_from_file(self, filepath: str):
        with open(filepath, 'r') as f:
            self.data = json.load(f)
        return self
    
    def filter_by_key(self, key: str, value: Any) -> List[Dict]:
        return [item for item in self.data if item.get(key) == value]
    
    def calculate_average(self, key: str) -> float:
        values = [item[key] for item in self.data if key in item]
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def save_results(self, filepath: str, results: List[Dict]):
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)""",
        
        "README.md": """# AI Coding Agent Workspace

This workspace contains example files for the AI coding agent.

## Files:
- `math_operations.py`: Basic math functions
- `data_processor.py`: Data processing class
- `config.json`: Configuration file

## Usage:
Use the agent commands to read, write, and analyze these files."""
    }
    
    print("\n📁 Setting up example workspace...")
    for filename, content in examples.items():
        result = fs.create_file(filename, content)
        if "error" in result:
            print(f"❌ Failed to create {filename}: {result['error']}")
        else:
            print(f"✅ Created {filename}")
    
    # Create empty config file
    fs.create_file("config.json", '{"debug": true, "version": "1.0.0"}')
    
    print("\n🎉 Workspace ready! Try these commands:")
    print("  • list")
    print("  • read math_operations.py")
    print("  • analyze data_processor.py")
    print("  • review math_operations.py")
    print("  • edit math_operations.py 'add docstrings to all functions'")

if __name__ == '__main__':
    # Setup workspace
    setup_example_files()
    
    # Test basic functionality
    print("\n" + "="*60)
    simple_agent()
    
    # Start interactive mode
    print("\n" + "="*60)
    interactive_agent()
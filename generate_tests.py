#!/usr/bin/env python3
"""
AI Test Generator - Interactive Chat Interface
Generate unit and integration tests for Spring Boot applications using AI
"""
import os
import sys
import argparse
import threading
import time
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.ai_client import AIClient
from lib.java_parser import JavaParser
from lib.context_gatherer import ContextGatherer
from lib.prompt_builder import PromptBuilder
from lib.test_writer import TestWriter
from lib.dependency_graph import DependencyGraphBuilder
from lib.test_validator import TestValidator

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class TestGeneratorChat:
    """Interactive chat interface for generating tests"""
    
    def __init__(self, project_root: str):
        # If running from tools/test-generator, go up to project root
        self.project_root = Path(project_root).resolve()
        if self.project_root.name == "test-generator":
            self.project_root = self.project_root.parent.parent
        
        self.console = Console() if RICH_AVAILABLE else None
        
        # Initialize components
        self.parser = JavaParser(str(self.project_root / "src/main/java"))
        self.context = ContextGatherer(str(self.project_root))
        self.prompt_builder = PromptBuilder(self.context)
        self.writer = TestWriter(str(self.project_root))
        self.dep_graph = DependencyGraphBuilder(str(self.project_root))
        self.validator = None  # Initialized after AI client
        self.ai_client = None
        
        # State
        self.current_java_class = None
        self.current_test_code = None
        self.current_test_type = None
        self.related_content = {}
        self.required_mocks = {}
    
    def print(self, message: str, style: str = None):
        """Print message with optional styling"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def print_code(self, code: str, language: str = "java"):
        """Print code with syntax highlighting"""
        if self.console:
            syntax = Syntax(code, language, theme="monokai", line_numbers=True)
            self.console.print(syntax)
        else:
            print(code)
    
    def print_markdown(self, md: str):
        """Print markdown content"""
        if self.console:
            self.console.print(Markdown(md))
        else:
            print(md)
    
    def call_with_spinner(self, func, message: str = "Generating..."):
        """Execute a function while showing a loading spinner"""
        import sys
        result = [None]
        error = [None]
        
        def run():
            try:
                result[0] = func()
            except Exception as e:
                error[0] = e
        
        thread = threading.Thread(target=run)
        thread.start()
        
        spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        print()  # New line before spinner
        while thread.is_alive():
            sys.stdout.write(f"\r{spinner_chars[idx % len(spinner_chars)]} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1
        sys.stdout.write("\r" + " " * (len(message) + 5) + "\r")
        sys.stdout.flush()
        print()  # New line after spinner
        
        thread.join()
        
        if error[0]:
            raise error[0]
        
        return result[0]
    
    def initialize_ai(self):
        """Initialize AI client and validator"""
        try:
            self.print("\n🔄 Initializing AI...", style="cyan")
            self.ai_client = AIClient(verbose=False)  # Disable verbose during init
            self.validator = TestValidator(str(self.project_root), self.ai_client)
            
            # Send system prompt with loading messages
            system_prompt = self.prompt_builder.build_system_prompt()
            
            def send_system_prompt():
                return self.ai_client.send_message(system_prompt)
            
            # Show loading message while building context
            self.call_with_spinner(
                send_system_prompt,
                "📦 Building project context & understanding your code..."
            )
            
            # Re-enable verbose mode for subsequent calls
            self.ai_client.verbose = True
            
            return True
        except Exception as e:
            self.print(f"❌ Error initializing AI: {e}", style="red")
            return False
    
    def find_class(self, class_name: str) -> Path:
        """Find a Java class by name (fuzzy search)"""
        # Remove .java extension if provided
        class_name = class_name.replace('.java', '').strip()
        
        src_path = self.project_root / "src" / "main" / "java"
        pattern = f"**/*{class_name}*.java"
        
        matches = list(src_path.glob(pattern))
        
        if not matches:
            self.print(f"❌ No class found matching: {class_name}", style="red")
            return None
        
        if len(matches) == 1:
            self.print(f"📁 Found: {matches[0].name}", style="cyan")
            return matches[0]
        
        # Multiple matches - let user choose
        self.print(f"\n🔍 Found {len(matches)} matches for '{class_name}':", style="cyan")
        for i, match in enumerate(matches[:20], 1):
            rel_path = match.relative_to(self.project_root)
            self.print(f"   {i}. {match.name} ({rel_path.parent})")
        
        if len(matches) > 20:
            self.print(f"   ... and {len(matches) - 20} more")
        
        try:
            choice = input("\n🧑 Enter number to load (or 'q' to cancel): ").strip()
            if choice.lower() == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                return matches[idx]
        except (ValueError, KeyboardInterrupt):
            pass
        
        return None
    
    def get_recommended_test_type(self) -> str:
        """Determine recommended test type based on class type"""
        if not self.current_java_class:
            return "unit"
        
        class_name = self.current_java_class.name
        
        # ServiceImpl and Controller benefit from integration tests
        if "ServiceImpl" in class_name or "Controller" in class_name:
            return "integration"
        
        # Mappers and Validators are good for unit tests
        if "Mapper" in class_name or "Validator" in class_name:
            return "unit"
        
        # Default to unit for simple classes
        return "unit"
    
    def load_source_file(self, file_path: str) -> bool:
        """Load and parse a Java source file. Supports class name or full path."""
        try:
            # Resolve path relative to project root
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project_root / file_path
            
            # If path doesn't exist, try to find by class name
            if not path.exists():
                found_path = self.find_class(file_path)
                if found_path:
                    path = found_path
                else:
                    return False
            
            self.current_java_class = self.parser.parse_file(str(path))
            related_files = self.parser.find_related_files(self.current_java_class)
            self.related_content = self.context.get_related_files_content(related_files)
            
            # Extract method calls for better mock understanding
            self.method_calls = self.parser.extract_method_calls(self.current_java_class)
            
            # Determine recommended test type
            recommended = self.get_recommended_test_type()
            
            self.print(f"\n✅ Loaded: {self.current_java_class.name}", style="green")
            self.print(f"   Package: {self.current_java_class.package}")
            self.print(f"   Methods: {len(self.current_java_class.methods)}")
            self.print(f"   Dependencies: {len(self.current_java_class.fields)}")
            self.print(f"   Related files: {list(self.related_content.keys())}")
            
            # Show internal calls that need mocking
            total_calls = sum(len(v) for v in self.method_calls.values())
            if total_calls > 0:
                self.print(f"\n📋 Internal Calls Detected (need mocking):", style="cyan")
                for call_type, calls in self.method_calls.items():
                    if calls:
                        self.print(f"   {call_type}: {', '.join(calls[:5])}")
            
            # Show recommendation
            if recommended == "integration":
                self.print(f"\n💡 Recommendation: Use 'integration' (ServiceImpl/Controller with many dependencies)", style="yellow")
                self.print(f"   Type 'integration' to generate E2E test with real DB via Testcontainers", style="yellow")
            else:
                self.print(f"\n💡 Recommendation: Use 'unit' (simple class with testable logic)", style="yellow")
            
            return True
        except Exception as e:
            self.print(f"❌ Error loading file: {e}", style="red")
            return False
    
    def generate_unit_test(self) -> str:
        """Generate unit test for loaded class"""
        if not self.current_java_class:
            return "No source file loaded. Use 'load <filepath>' first."
        
        # Pass method_calls if available
        method_calls = getattr(self, 'method_calls', None)
        
        prompt = self.prompt_builder.build_unit_test_prompt(
            self.current_java_class, 
            self.related_content,
            method_calls
        )
        
        # Use spinner for loading indication
        response = self.call_with_spinner(
            lambda: self.ai_client.send_message(prompt),
            f"🔄 Generating unit test for {self.current_java_class.name}..."
        )
        self.current_test_code = response
        self.current_test_type = "unit"
        return response
    
    def generate_integration_test(self) -> str:
        """Generate integration test for loaded class"""
        if not self.current_java_class:
            return "No source file loaded. Use 'load <filepath>' first."
        
        prompt = self.prompt_builder.build_integration_test_prompt(
            self.current_java_class,
            self.related_content
        )
        
        response = self.call_with_spinner(
            lambda: self.ai_client.send_message(prompt),
            f"🔄 Generating integration test for {self.current_java_class.name}..."
        )
        self.current_test_code = response
        self.current_test_type = "integration"
        return response
    
    def refine_test(self, feedback: str) -> str:
        """Refine current test based on user feedback"""
        if not self.current_test_code:
            return "No test generated yet. Generate a test first."
        
        prompt = self.prompt_builder.build_refinement_prompt(
            self.current_test_code,
            feedback
        )
        
        response = self.call_with_spinner(
            lambda: self.ai_client.send_message(prompt),
            "🔄 Refining test based on feedback..."
        )
        self.current_test_code = response
        return response
    
    def save_test(self) -> str:
        """Save current test to file"""
        if not self.current_java_class:
            return "❌ No source file loaded. Use 'load <classname>' first."
        
        if not self.current_test_code:
            return "❌ No test generated yet. Use 'unit' or 'integration' first."
        
        # Debug: Check code length
        code_length = len(self.current_test_code) if self.current_test_code else 0
        if code_length < 100:
            return f"❌ Test code seems too short ({code_length} chars). Generate a test first."
        
        try:
            is_integration = self.current_test_type == "integration"
            file_path = self.writer.write_test(
                self.current_java_class.package,
                self.current_java_class.name,
                self.current_test_code,
                is_integration
            )
            return f"✅ Test saved to:\n{file_path}"
        except Exception as e:
            return f"❌ Error saving test: {e}"
    
    def show_help(self):
        """Show available commands"""
        help_text = """
## 🤖 AI Test Generator v2.0 Commands

| Command | Description |
|---------|-------------|
| `load <name>` | Load class by name (e.g., `load ApiKeyServiceImpl`) |
| `unit` | Generate unit test for loaded class |
| `integration` | Generate E2E integration test |
| `validate` | Compile, run & auto-fix current test |
| `save` | Save current test to file |
| `show` | Show current generated test |
| `deps` | Show dependency analysis for loaded class |
| `reset` | Reset chat and start fresh |
| `clear` | Clear the console screen |
| `help` | Show this help |
| `quit` | Exit the chat |

## 🔍 Load Examples:
- `load OrderService` - finds and loads OrderServiceImpl
- `load ApiKeyMapper` - loads the exact file
- `load Project` - shows all matching classes to choose from

## 💬 Chat Mode
After generating a test, just type your feedback to refine it:
- "Add more edge cases"
- "Use different test data"
- "Add test for error handling"
"""
        self.print_markdown(help_text)
    
    def run(self):
        """Main chat loop"""
        self.print("\n" + "=" * 60)
        self.print("🤖 AI Test Generator for Spring Boot")
        self.print("=" * 60)
        
        # Initialize AI
        if not self.initialize_ai():
            return
        
        self.print("\n✅ AI initialized. Type 'help' for commands.\n", style="green")
        
        while True:
            try:
                user_input = input("\n🧑 You: ").strip()
                
                if not user_input:
                    continue
                
                # Auto-detect: If input looks like a class name or .java file, auto-load it
                first_word = user_input.split()[0]
                if first_word.endswith('.java') or (first_word[0].isupper() and 'Impl' in first_word or 'Mapper' in first_word or 'Service' in first_word or 'Validator' in first_word or 'Controller' in first_word):
                    # Treat as load command
                    class_name = first_word.replace('.java', '')
                    self.print(f"📁 Auto-loading: {class_name}", style="cyan")
                    if self.load_source_file(class_name):
                        self.print("\n💡 Now use 'unit' to generate a test, or 'help' for more commands.", style="yellow")
                    continue
                
                # Handle commands
                cmd = user_input.lower().split()[0]
                
                if cmd == "quit" or cmd == "exit":
                    self.print("\n👋 Goodbye!", style="blue")
                    break
                
                elif cmd == "help":
                    self.show_help()
                
                elif cmd == "load":
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        self.print("Usage: load <filepath>", style="red")
                    else:
                        self.load_source_file(parts[1])
                
                elif cmd == "unit":
                    response = self.generate_unit_test()
                    self.print("\n🤖 AI:", style="blue")
                    self.print_code(response)
                
                elif cmd == "integration":
                    response = self.generate_integration_test()
                    self.print("\n🤖 AI:", style="blue")
                    self.print_code(response)
                
                elif cmd == "save":
                    result = self.save_test()
                    self.print(result, style="green")
                
                elif cmd == "show":
                    if self.current_test_code:
                        self.print("\n📄 Current Test:", style="blue")
                        self.print_code(self.current_test_code)
                    else:
                        self.print("No test generated yet.", style="yellow")
                
                elif cmd == "reset":
                    self.ai_client.reset_chat()
                    self.ai_client.send_message(self.prompt_builder.build_system_prompt())
                    self.current_test_code = None
                    self.current_java_class = None
                    self.print("✅ Chat reset.", style="green")
                
                elif cmd == "clear":
                    # Clear the console screen
                    os.system('cls' if os.name == 'nt' else 'clear')
                    self.print("🧹 Console cleared.", style="green")
                
                elif cmd == "validate":
                    if not self.current_test_code or not self.current_java_class:
                        self.print("❌ No test to validate. Generate a test first.", style="red")
                    else:
                        self.print("\n🔬 Validating test (compile → run → auto-fix)...", style="yellow")
                        fixed_code, success = self.validator.validate_and_fix(
                            self.current_test_code,
                            self.current_java_class.name,
                            self.current_java_class.package
                        )
                        self.current_test_code = fixed_code
                        if success:
                            self.print("\n✅ Test validated successfully!", style="green")
                        else:
                            self.print("\n⚠️ Validation completed with issues. Test code updated.", style="yellow")
                        self.print("\nType 'save' to save the test or 'show' to see it.")
                
                elif cmd == "deps":
                    if not self.current_java_class:
                        self.print("❌ No class loaded. Use 'load <filepath>' first.", style="red")
                    else:
                        self.print("\n📊 Dependency Analysis:", style="cyan")
                        graph = self.dep_graph.build_graph_for_class(self.current_java_class.file_path)
                        mocks = self.dep_graph.get_all_required_mocks(graph, self.current_java_class.name)
                        for dep, methods in mocks.items():
                            self.print(f"   @Mock {dep}: {', '.join(methods) if methods else 'inject only'}")
                
                else:
                    # Treat as feedback for refinement
                    if self.current_test_code:
                        response = self.refine_test(user_input)
                        self.print("\n🤖 AI:", style="blue")
                        self.print_code(response)
                    else:
                        # General question
                        response = self.ai_client.send_message(user_input)
                        self.print("\n🤖 AI:", style="blue")
                        self.print_markdown(response)
            
            except KeyboardInterrupt:
                self.print("\n\n👋 Goodbye!", style="blue")
                break
            except Exception as e:
                self.print(f"\n❌ Error: {e}", style="red")


def main():
    parser = argparse.ArgumentParser(description='AI Test Generator for Spring Boot')
    parser.add_argument('--project', '-p', default='.', 
                        help='Project root directory (default: current directory)')
    parser.add_argument('--file', '-f', 
                        help='Java file to generate tests for (optional)')
    parser.add_argument('--type', '-t', choices=['unit', 'integration'],
                        help='Test type to generate (optional)')
    
    args = parser.parse_args()
    
    chat = TestGeneratorChat(args.project)
    
    # If file provided, load it
    if args.file:
        chat.load_source_file(args.file)
    
    chat.run()


if __name__ == "__main__":
    main()

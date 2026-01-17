"""
Test Validator - Compile, run, and auto-fix generated tests
Implements the validation loop: generate -> compile -> run -> fix -> repeat
"""
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class TestResult:
    """Result of a test compilation or execution"""
    success: bool
    output: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_line: Optional[int] = None
    suggested_fix: Optional[str] = None


class TestValidator:
    """Validate generated tests by compiling and running them"""
    
    def __init__(self, project_root: str, ai_client=None):
        self.project_root = Path(project_root)
        self.ai_client = ai_client
        self.max_fix_attempts = 3
    
    def validate_and_fix(self, test_code: str, test_class_name: str, test_package: str) -> Tuple[str, bool]:
        """
        Validate a generated test and attempt to fix any issues
        Returns: (fixed_test_code, success)
        """
        current_code = test_code
        
        for attempt in range(self.max_fix_attempts):
            print(f"🔄 Validation attempt {attempt + 1}/{self.max_fix_attempts}")
            
            # Step 1: Write test file
            test_path = self._write_test_file(current_code, test_class_name, test_package)
            if not test_path:
                print("❌ Failed to write test file")
                return current_code, False
            
            # Step 2: Compile
            compile_result = self._compile_test(test_class_name)
            if not compile_result.success:
                print(f"❌ Compilation failed: {compile_result.error_message}")
                if self.ai_client and attempt < self.max_fix_attempts - 1:
                    current_code = self._fix_with_ai(current_code, compile_result, "compile")
                    continue
                return current_code, False
            
            print("✅ Compilation successful")
            
            # Step 3: Run test
            run_result = self._run_test(test_class_name)
            if not run_result.success:
                print(f"❌ Test failed: {run_result.error_message}")
                if self.ai_client and attempt < self.max_fix_attempts - 1:
                    current_code = self._fix_with_ai(current_code, run_result, "runtime")
                    continue
                return current_code, False
            
            print("✅ Test passed!")
            return current_code, True
        
        return current_code, False
    
    def _write_test_file(self, test_code: str, class_name: str, package: str) -> Optional[Path]:
        """Write test code to appropriate location"""
        # Clean up markdown if present
        test_code = self._clean_test_code(test_code)
        
        # Build path
        package_path = package.replace('.', '/')
        test_dir = self.project_root / "src" / "test" / "java" / package_path
        test_dir.mkdir(parents=True, exist_ok=True)
        
        test_file = test_dir / f"{class_name}Test.java"
        test_file.write_text(test_code, encoding='utf-8')
        
        return test_file
    
    def _clean_test_code(self, code: str) -> str:
        """Remove markdown code blocks if present"""
        # Remove ```java and ``` markers
        code = re.sub(r'^```java\s*\n?', '', code.strip())
        code = re.sub(r'^```\s*\n?', '', code.strip())
        code = re.sub(r'\n?```\s*$', '', code.strip())
        return code.strip()
    
    def _compile_test(self, test_class_name: str) -> TestResult:
        """Compile the test using Maven"""
        try:
            result = subprocess.run(
                ["mvn", "test-compile", "-q", f"-Dtest={test_class_name}Test"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return TestResult(success=True, output=result.stdout)
            
            # Parse compilation error
            error_info = self._parse_compile_error(result.stderr + result.stdout)
            return TestResult(
                success=False,
                output=result.stdout + result.stderr,
                error_type="compilation",
                error_message=error_info.get('message', 'Unknown compilation error'),
                error_line=error_info.get('line')
            )
        except subprocess.TimeoutExpired:
            return TestResult(success=False, output="", error_type="timeout", error_message="Compilation timed out")
        except Exception as e:
            return TestResult(success=False, output="", error_type="exception", error_message=str(e))
    
    def _run_test(self, test_class_name: str) -> TestResult:
        """Run the test using Maven"""
        try:
            result = subprocess.run(
                ["mvn", "test", "-q", f"-Dtest={test_class_name}Test"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return TestResult(success=True, output=result.stdout)
            
            # Parse test failure
            error_info = self._parse_test_error(result.stderr + result.stdout)
            return TestResult(
                success=False,
                output=result.stdout + result.stderr,
                error_type=error_info.get('type', 'test_failure'),
                error_message=error_info.get('message', 'Test failed'),
                error_line=error_info.get('line')
            )
        except subprocess.TimeoutExpired:
            return TestResult(success=False, output="", error_type="timeout", error_message="Test execution timed out")
        except Exception as e:
            return TestResult(success=False, output="", error_type="exception", error_message=str(e))
    
    def _parse_compile_error(self, output: str) -> dict:
        """Parse Maven compilation error output"""
        info = {}
        
        # Look for error line pattern: [ERROR] /path/to/File.java:[line,col] error: message
        error_pattern = r'\[ERROR\].*\.java:\[(\d+),\d+\]\s*(.*)'
        match = re.search(error_pattern, output)
        if match:
            info['line'] = int(match.group(1))
            info['message'] = match.group(2)
        else:
            # Try simpler pattern
            lines = output.split('\n')
            for line in lines:
                if '[ERROR]' in line:
                    info['message'] = line.replace('[ERROR]', '').strip()
                    break
        
        return info
    
    def _parse_test_error(self, output: str) -> dict:
        """Parse Maven test failure output"""
        info = {'type': 'test_failure'}
        
        # Look for common error patterns (ordered by specificity)
        error_patterns = [
            # Mockito errors
            (r'MockitoException.*Only void methods can doNothing', 'doNothing_on_non_void'),
            (r'NotAMockException', 'NotAMockException'),
            (r'PotentialStubbingProblem', 'PotentialStubbingProblem'),
            (r'UnnecessaryStubbingException', 'UnnecessaryStubbingException'),
            (r'InvalidUseOfMatchersException', 'InvalidMatchers'),
            (r'WrongTypeOfReturnValue', 'WrongReturnType'),
            (r'UnfinishedStubbingException', 'UnfinishedStubbing'),
            
            # Common runtime errors
            (r'NullPointerException', 'NullPointerException'),
            (r'NoSuchMethodError', 'NoSuchMethodError'),
            (r'NoSuchFieldError', 'NoSuchFieldError'),
            (r'ClassCastException', 'ClassCastException'),
            (r'IllegalArgumentException', 'IllegalArgumentException'),
            (r'IllegalStateException', 'IllegalStateException'),
            
            # Instancio errors
            (r'InstancioApiException', 'InstancioError'),
            (r'No candidates found for method call', 'InstancioMethodError'),
            
            # MapStruct errors
            (r'Cannot instantiate.*interface', 'interface_instantiation'),
            (r'Mappers\.getMapper.*returned null', 'MapperNotGenerated'),
            
            # Assertion errors
            (r'AssertionFailedError.*expected.*but was', 'AssertionMismatch'),
            (r'AssertionError', 'AssertionError'),
            
            # Compilation in test (shouldn't reach here but just in case)
            (r'cannot find symbol', 'SymbolNotFound'),
            (r'incompatible types', 'IncompatibleTypes'),
        ]
        
        for pattern, error_type in error_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                info['type'] = error_type
                # Extract context around the error
                match = re.search(f'({pattern}[^\\n]*)', output, re.IGNORECASE)
                if match:
                    info['message'] = match.group(1)[:500]  # Limit message length
                break
        
        # If no pattern matched, try to get any error message
        if 'message' not in info:
            # Look for failure summary
            failure_match = re.search(r'Failures:\s*\n\s*\d+\)\s*(.*?)(?:\n\n|\Z)', output, re.DOTALL)
            if failure_match:
                info['message'] = failure_match.group(1)[:500].strip()
            else:
                info['message'] = 'Test failed - check output for details'
        
        # Extract stack trace line number
        line_pattern = r'at.*Test\.(java|kt):(\d+)'
        line_match = re.search(line_pattern, output)
        if line_match:
            info['line'] = int(line_match.group(2))
        
        return info
    
    def _fix_with_ai(self, test_code: str, error: TestResult, error_phase: str) -> str:
        """Use AI to fix the test based on the error"""
        if not self.ai_client:
            return test_code
        
        fix_prompt = f"""The following test has a {error_phase} error. Please fix it.

## ERROR TYPE: {error.error_type}
## ERROR MESSAGE: {error.error_message}
## ERROR LINE: {error.error_line if error.error_line else 'Unknown'}

## FULL ERROR OUTPUT (last 2000 chars):
{error.output[-2000:]}

## CURRENT TEST CODE:
```java
{test_code}
```

## FIX INSTRUCTIONS:
1. Identify the root cause of the error
2. Apply the minimal fix needed
3. Return ONLY the complete fixed Java test code
4. Do NOT include any markdown formatting or explanations
5. The response should start with 'package' and end with closing brace

Common fixes:
- NullPointerException: Add proper mocking with when().thenReturn()
- NotAMockException: Use @Mock annotation, not Mappers.getMapper() when stubbing
- doNothing on non-void: Use when().thenReturn() instead
- PotentialStubbingProblem: Use any() matchers or lenient()

Return the fixed test code:
"""
        
        try:
            response = self.ai_client.send_message(fix_prompt)
            fixed_code = self._clean_test_code(response)
            return fixed_code
        except Exception as e:
            print(f"AI fix failed: {e}")
            return test_code
    
    def quick_compile_check(self, test_code: str, test_class_name: str, test_package: str) -> TestResult:
        """Quick check if test compiles without running it"""
        test_path = self._write_test_file(test_code, test_class_name, test_package)
        if not test_path:
            return TestResult(success=False, output="", error_message="Failed to write file")
        
        return self._compile_test(test_class_name)


if __name__ == "__main__":
    # Test the validator
    validator = TestValidator(".")
    print("Test validator initialized. Use with AI client for auto-fixing.")

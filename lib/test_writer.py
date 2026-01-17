"""
Test Writer - Save generated tests to files
"""
import os
from pathlib import Path
from typing import Optional


class TestWriter:
    """Write generated test files to the test directory"""
    
    def __init__(self, project_root: str, test_dir: str = "src/test/java"):
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / test_dir
    
    def write_test(self, package: str, class_name: str, content: str, 
                   is_integration: bool = False) -> str:
        """Write test content to file"""
        # Determine test class name
        if is_integration:
            test_class_name = class_name.replace("Impl", "") + "IntegrationTest"
        else:
            test_class_name = class_name + "Test"
        
        # Create directory path from package
        package_path = package.replace(".", os.sep)
        dir_path = self.test_dir / package_path
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Write file
        file_path = dir_path / f"{test_class_name}.java"
        
        # Clean the content (remove markdown code blocks if present)
        clean_content = self._clean_code(content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(clean_content)
        
        return str(file_path)
    
    def _clean_code(self, content: str) -> str:
        """Remove markdown code blocks and clean up the content"""
        # Remove ```java and ``` markers
        lines = content.split('\n')
        clean_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```java'):
                in_code_block = True
                continue
            elif line.strip() == '```':
                in_code_block = False
                continue
            clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    def get_test_path(self, package: str, class_name: str, 
                      is_integration: bool = False) -> str:
        """Get the path where the test would be written"""
        if is_integration:
            test_class_name = class_name.replace("Impl", "") + "IntegrationTest"
        else:
            test_class_name = class_name + "Test"
        
        package_path = package.replace(".", os.sep)
        return str(self.test_dir / package_path / f"{test_class_name}.java")
    
    def test_exists(self, package: str, class_name: str, 
                    is_integration: bool = False) -> bool:
        """Check if a test file already exists"""
        path = self.get_test_path(package, class_name, is_integration)
        return Path(path).exists()


if __name__ == "__main__":
    # Test the writer
    writer = TestWriter(".")
    print("Test path:", writer.get_test_path("de.cathago.earth.domain.order.core", "OrderServiceImpl"))

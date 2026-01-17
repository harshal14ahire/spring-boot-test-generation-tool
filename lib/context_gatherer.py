"""
Context Gatherer - Collect repository context for AI prompts
Includes metadata.txt, architecture.md, and comprehensive project scan
"""
import os
import re
from pathlib import Path
from typing import Optional, Dict, List


class ContextGatherer:
    """Gather project context for AI prompts"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.metadata_cache = None
        self.architecture_cache = None
        self.project_context_cache = None
        
        # Build comprehensive context at initialization
        self._build_project_context()
    
    def _build_project_context(self):
        """Scan entire project and build comprehensive context"""
        print("📚 Building project context...")
        
        self.project_context_cache = {
            'entities': {},
            'services': {},
            'mappers': {},
            'validators': {},
            'enums': {},
            'existing_tests': {},
            'common_patterns': {}
        }
        
        src_path = self.project_root / "src" / "main" / "java"
        test_path = self.project_root / "src" / "test" / "java"
        
        if src_path.exists():
            self._scan_directory(src_path, 'main')
        
        if test_path.exists():
            self._scan_directory(test_path, 'test')
        
        # Extract patterns from existing tests
        self._extract_test_patterns()
        
        print(f"   ✅ Found {len(self.project_context_cache['entities'])} entities")
        print(f"   ✅ Found {len(self.project_context_cache['services'])} services")
        print(f"   ✅ Found {len(self.project_context_cache['mappers'])} mappers")
        print(f"   ✅ Found {len(self.project_context_cache['validators'])} validators")
        print(f"   ✅ Found {len(self.project_context_cache['enums'])} enums")
        print(f"   ✅ Found {len(self.project_context_cache['existing_tests'])} existing tests")
    
    def _scan_directory(self, path: Path, source_type: str):
        """Recursively scan directory for Java files"""
        for java_file in path.rglob("*.java"):
            file_name = java_file.stem
            relative_path = str(java_file.relative_to(self.project_root))
            
            # Categorize files
            if source_type == 'main':
                # First check if it's an enum by reading file content
                if self._is_enum_file(java_file):
                    enum_values = self._extract_enum_values(java_file)
                    self.project_context_cache['enums'][file_name] = {
                        'path': relative_path,
                        'values': enum_values
                    }
                elif file_name.endswith('Entity'):
                    self.project_context_cache['entities'][file_name] = {
                        'path': relative_path,
                        'methods': self._extract_methods(java_file)
                    }
                elif file_name.endswith('ServiceImpl'):
                    self.project_context_cache['services'][file_name] = {
                        'path': relative_path,
                        'methods': self._extract_methods(java_file),
                        'dependencies': self._extract_dependencies(java_file)
                    }
                elif file_name.endswith('Mapper'):
                    self.project_context_cache['mappers'][file_name] = {
                        'path': relative_path,
                        'methods': self._extract_methods(java_file)
                    }
                elif file_name.endswith('Validator'):
                    self.project_context_cache['validators'][file_name] = {
                        'path': relative_path,
                        'methods': self._extract_methods(java_file)
                    }
            elif source_type == 'test':
                if file_name.endswith('Test'):
                    self.project_context_cache['existing_tests'][file_name] = {
                        'path': relative_path,
                        'content_preview': self._get_file_preview(java_file, 100)
                    }
    
    def _is_enum_file(self, file_path: Path) -> bool:
        """Check if a Java file is an enum by looking for 'public enum' keyword"""
        try:
            content = file_path.read_text(encoding='utf-8')
            return 'public enum ' in content
        except:
            return False
    
    def _extract_enum_values(self, file_path: Path) -> List[str]:
        """Extract enum values from an enum file"""
        values = []
        try:
            content = file_path.read_text(encoding='utf-8')
            # Match enum values (uppercase identifiers after '{' and before first method or '}')
            match = re.search(r'enum\s+\w+\s*\{([^}]+)', content)
            if match:
                enum_body = match.group(1)
                # Extract just the enum constants (before any semicolon or method)
                if ';' in enum_body:
                    enum_body = enum_body.split(';')[0]
                # Match uppercase identifiers (enum values)
                values = re.findall(r'\b([A-Z][A-Z0-9_]+)\b', enum_body)
                values = list(dict.fromkeys(values))[:20]  # Remove duplicates, limit to 20
        except:
            pass
        return values
    
    def _extract_methods(self, file_path: Path) -> List[str]:
        """Extract method signatures from a Java file"""
        methods = []
        try:
            content = file_path.read_text(encoding='utf-8')
            # Match public/protected methods
            pattern = r'(?:public|protected)\s+(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)'
            matches = re.findall(pattern, content)
            methods = list(set(matches))[:20]  # Limit to 20 methods
        except:
            pass
        return methods
    
    def _extract_dependencies(self, file_path: Path) -> List[str]:
        """Extract injected dependencies from a service file"""
        dependencies = []
        try:
            content = file_path.read_text(encoding='utf-8')
            # Match field injections
            pattern = r'private\s+(?:final\s+)?(\w+(?:Service|Validator|Dao|Mapper|Repository))\s+\w+'
            matches = re.findall(pattern, content)
            dependencies = list(set(matches))
        except:
            pass
        return dependencies
    
    def _get_file_preview(self, file_path: Path, lines: int = 50) -> str:
        """Get first N lines of a file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            return '\n'.join(content.split('\n')[:lines])
        except:
            return ""
    
    def _extract_test_patterns(self):
        """Extract common patterns from existing tests"""
        patterns = {
            'uses_instancio': False,
            'uses_mockito': False,
            'uses_nested': False,
            'uses_assertj': False,
            'common_setup': []
        }
        
        for test_name, test_info in self.project_context_cache['existing_tests'].items():
            content = test_info.get('content_preview', '')
            if 'Instancio' in content:
                patterns['uses_instancio'] = True
            if '@Mock' in content:
                patterns['uses_mockito'] = True
            if '@Nested' in content:
                patterns['uses_nested'] = True
            if 'assertThat' in content:
                patterns['uses_assertj'] = True
        
        self.project_context_cache['common_patterns'] = patterns
    
    def get_project_summary(self) -> str:
        """Get a summary of the entire project for AI context"""
        if not self.project_context_cache:
            return ""
        
        summary = []
        summary.append("## PROJECT STRUCTURE SUMMARY\n")
        
        # Entities
        if self.project_context_cache['entities']:
            summary.append("### Entities:")
            for name, info in list(self.project_context_cache['entities'].items())[:30]:
                summary.append(f"- {name}: {', '.join(info['methods'][:5])}")
        
        # Validators (important for understanding what mocks are needed)
        if self.project_context_cache['validators']:
            summary.append("\n### Validators (need to be mocked in tests):")
            for name, info in list(self.project_context_cache['validators'].items())[:20]:
                summary.append(f"- {name}: {', '.join(info['methods'][:5])}")
        
        # Enums with valid values (critical for correct test data)
        if self.project_context_cache['enums']:
            summary.append("\n### Enums (use ONLY these valid values):")
            for name, info in list(self.project_context_cache['enums'].items())[:50]:
                values = info.get('values', [])
                if values:
                    summary.append(f"- {name}: {', '.join(values)}")
        
        # Common patterns
        patterns = self.project_context_cache.get('common_patterns', {})
        summary.append("\n### Testing Patterns Used in This Project:")
        summary.append(f"- Uses Instancio: {patterns.get('uses_instancio', False)}")
        summary.append(f"- Uses Mockito: {patterns.get('uses_mockito', False)}")
        summary.append(f"- Uses AssertJ: {patterns.get('uses_assertj', False)}")
        
        return '\n'.join(summary)
    
    def get_service_dependencies(self, service_name: str) -> List[str]:
        """Get dependencies for a specific service"""
        if service_name in self.project_context_cache.get('services', {}):
            return self.project_context_cache['services'][service_name].get('dependencies', [])
        return []
    
    def get_metadata(self) -> str:
        """Load metadata.txt with entity relationships and sample data"""
        if self.metadata_cache:
            return self.metadata_cache
        
        metadata_path = self.project_root / "metadata.txt"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.metadata_cache = f.read()
            return self.metadata_cache
        return ""
    
    def get_metadata_summary(self) -> str:
        """Get a condensed version of metadata for prompts (to save tokens)"""
        full_metadata = self.get_metadata()
        if not full_metadata:
            return "No metadata available."
        
        # Extract key sections: ER diagram and sample records
        lines = full_metadata.split('\n')
        summary_lines = []
        include_section = False
        section_count = 0
        
        for line in lines:
            # Include ER diagram section
            if 'ER DIAGRAM' in line or 'ENTITY LIST' in line:
                include_section = True
                section_count = 0
            elif 'SAMPLE RECORDS' in line:
                include_section = True
                section_count = 0
            elif line.startswith('===') and include_section:
                section_count += 1
                if section_count > 1:
                    include_section = False
            
            if include_section:
                summary_lines.append(line)
            
            # Limit size
            if len(summary_lines) > 200:
                break
        
        return '\n'.join(summary_lines) if summary_lines else full_metadata[:3000]
    
    def get_architecture(self) -> str:
        """Load architecture.md with coding conventions"""
        if self.architecture_cache:
            return self.architecture_cache
        
        arch_path = self.project_root / "docs" / "architecture.md"
        if arch_path.exists():
            with open(arch_path, 'r', encoding='utf-8') as f:
                self.architecture_cache = f.read()
            return self.architecture_cache
        return ""
    
    def get_architecture_summary(self) -> str:
        """Get coding conventions section from architecture.md"""
        full_arch = self.get_architecture()
        if not full_arch:
            return "No architecture documentation available."
        
        # Extract coding conventions section
        if "## Coding Conventions" in full_arch:
            start = full_arch.find("## Coding Conventions")
            return full_arch[start:start + 4000]  # First 4000 chars of conventions
        
        return full_arch[:2000]  # Fallback: first 2000 chars
    
    def get_file_content(self, file_path: str) -> str:
        """Read content of a source file"""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / file_path
        
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def get_related_files_content(self, related_files: dict) -> dict:
        """Get content of related files (Entity, DTO, etc.)"""
        contents = {}
        for key, file_path in related_files.items():
            content = self.get_file_content(file_path)
            if content:
                contents[key] = {
                    'path': file_path,
                    'content': content
                }
        return contents
    
    def get_sample_test_data(self, entity_type: str) -> str:
        """Get sample data for a specific entity type from metadata"""
        metadata = self.get_metadata()
        if not metadata:
            return ""
        
        # Find the section for this entity type
        entity_patterns = {
            'order': 'ORDERS (20 Records)',
            'orderitem': 'ORDER ITEMS (20 Records)',
            'project': 'PROJECTS (20 Records)',
            'companyaccount': 'COMPANY ACCOUNTS (20 Records)',
            'supplieraccount': 'SUPPLIER ACCOUNTS (20 Records)',
            'user': 'USERS (20 Records)',
            'catalog': 'CATALOGS (20 Records)',
        }
        
        pattern = entity_patterns.get(entity_type.lower(), '')
        if pattern and pattern in metadata:
            start = metadata.find(pattern)
            end = metadata.find('---', start + 100)
            if end == -1:
                end = start + 1500
            return metadata[start:end]
        
        return ""


if __name__ == "__main__":
    # Test the context gatherer
    gatherer = ContextGatherer(".")
    print("\nProject summary:")
    print(gatherer.get_project_summary())

"""
Dependency Graph Builder - Analyze class dependencies for smart context selection
Builds a DAG of class dependencies to determine exactly what mocks are needed
"""
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class ClassDependency:
    """Represents a class and its dependencies"""
    name: str
    file_path: str
    dependencies: List[str] = field(default_factory=list)  # Injected dependencies
    method_calls: Dict[str, List[str]] = field(default_factory=dict)  # method -> [calls]
    is_interface: bool = False
    is_mapper: bool = False
    is_validator: bool = False
    is_service: bool = False
    

class DependencyGraphBuilder:
    """Build dependency graph for Java classes"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.src_path = self.project_root / "src" / "main" / "java"
        self.class_cache: Dict[str, ClassDependency] = {}
    
    def build_graph_for_class(self, file_path: str) -> Dict[str, ClassDependency]:
        """
        Build complete dependency graph for a class
        Returns dict of class_name -> ClassDependency for all relevant classes
        """
        graph = {}
        to_process = [file_path]
        processed = set()
        
        while to_process:
            current_path = to_process.pop(0)
            if current_path in processed:
                continue
            processed.add(current_path)
            
            try:
                class_dep = self._analyze_class(current_path)
                if class_dep:
                    graph[class_dep.name] = class_dep
                    
                    # Add direct dependencies to process queue
                    for dep_name in class_dep.dependencies:
                        dep_path = self._find_class_file(dep_name)
                        if dep_path and dep_path not in processed:
                            to_process.append(dep_path)
            except Exception as e:
                print(f"Warning: Could not analyze {current_path}: {e}")
        
        return graph
    
    def _analyze_class(self, file_path: str) -> Optional[ClassDependency]:
        """Analyze a single Java class file"""
        path = Path(file_path)
        if not path.exists():
            return None
        
        content = path.read_text(encoding='utf-8')
        class_name = path.stem
        
        # Detect class type
        is_interface = bool(re.search(r'public\s+interface\s+\w+', content))
        is_mapper = 'Mapper' in class_name or '@Mapper' in content
        is_validator = 'Validator' in class_name
        is_service = 'Service' in class_name
        
        # Extract injected dependencies (fields)
        dependencies = self._extract_dependencies(content)
        
        # Extract method-to-call mapping
        method_calls = self._extract_method_calls(content)
        
        return ClassDependency(
            name=class_name,
            file_path=str(path),
            dependencies=dependencies,
            method_calls=method_calls,
            is_interface=is_interface,
            is_mapper=is_mapper,
            is_validator=is_validator,
            is_service=is_service
        )
    
    def _extract_dependencies(self, content: str) -> List[str]:
        """Extract injected field dependencies"""
        dependencies = []
        
        # Match field declarations like: SomeService someService;
        # With @RequiredArgsConstructor, all final fields are dependencies
        pattern = r'(?:private|protected)\s+(?:final\s+)?(\w+(?:Service|Validator|Dao|Mapper|Repository|Helper))\s+\w+\s*;'
        matches = re.findall(pattern, content)
        dependencies.extend(matches)
        
        # Also check for SearchMapper<T> pattern
        generic_pattern = r'(?:private|protected)\s+(?:final\s+)?(\w+Mapper)<[^>]+>\s+\w+\s*;'
        generic_matches = re.findall(generic_pattern, content)
        dependencies.extend(generic_matches)
        
        return list(set(dependencies))
    
    def _extract_method_calls(self, content: str) -> Dict[str, List[str]]:
        """Extract method-to-call mapping for each public method"""
        method_calls = {}
        
        # Find all methods
        method_pattern = r'(?:@Override\s+)?(?:public|protected)\s+(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*\{'
        
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            # Find the method body
            start = match.end()
            body = self._extract_method_body(content, start)
            
            # Extract all service/validator/dao calls from body
            calls = set()
            
            # Pattern: variableName.methodName(
            call_pattern = r'(\w+(?:Service|Validator|Dao|Mapper|Helper))\.(\w+)\s*\('
            for call_match in re.finditer(call_pattern, body):
                calls.add(f"{call_match.group(1)}.{call_match.group(2)}()")
            
            # Also extract private method calls (same class)
            private_pattern = r'\b([a-z]\w+)\s*\([^)]*\)'
            for private_match in re.finditer(private_pattern, body):
                potential_private = private_match.group(1)
                # Check if it's a private method in this class
                if re.search(rf'private\s+\w+\s+{potential_private}\s*\(', content):
                    calls.add(f"this.{potential_private}()")
            
            if calls:
                method_calls[method_name] = list(calls)
        
        return method_calls
    
    def _extract_method_body(self, content: str, start: int) -> str:
        """Extract method body starting from given position"""
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            if content[pos] == '{':
                depth += 1
            elif content[pos] == '}':
                depth -= 1
            pos += 1
        return content[start:pos-1]
    
    def _find_class_file(self, class_name: str) -> Optional[str]:
        """Find Java file for a given class name"""
        # Remove generic part if present
        class_name = re.sub(r'<.*>', '', class_name)
        
        # Search in src/main/java
        pattern = f"**/{class_name}.java"
        matches = list(self.src_path.rglob(pattern))
        
        if matches:
            return str(matches[0])
        return None
    
    def get_all_required_mocks(self, graph: Dict[str, ClassDependency], target_class: str) -> Dict[str, Set[str]]:
        """
        Given a dependency graph and target class, determine all mocks needed
        Returns: {dependency_class: {method1(), method2(), ...}}
        """
        required_mocks = {}
        
        if target_class not in graph:
            return required_mocks
        
        target = graph[target_class]
        
        # Direct dependencies need to be mocked
        for dep in target.dependencies:
            required_mocks[dep] = set()
        
        # Analyze method calls to know which methods to mock
        for method_name, calls in target.method_calls.items():
            for call in calls:
                if '.' in call:
                    parts = call.split('.')
                    dep_name = parts[0]
                    method = parts[1].rstrip('()')
                    
                    # Skip 'this' calls (private methods)
                    if dep_name == 'this':
                        # Trace into private method
                        private_method = method.replace('()', '')
                        if private_method in target.method_calls:
                            for nested_call in target.method_calls.get(private_method, []):
                                if '.' in nested_call:
                                    nested_parts = nested_call.split('.')
                                    nested_dep = nested_parts[0]
                                    nested_method = nested_parts[1]
                                    if nested_dep in required_mocks:
                                        required_mocks[nested_dep].add(nested_method)
                    elif dep_name in required_mocks:
                        required_mocks[dep_name].add(f"{method}()")
        
        return required_mocks
    
    def get_smart_context(self, file_path: str, max_files: int = 5) -> Dict[str, str]:
        """
        Get smart context for a class - only the most relevant files
        Returns dict of {context_type: file_content}
        """
        graph = self.build_graph_for_class(file_path)
        target_name = Path(file_path).stem
        
        if target_name not in graph:
            return {}
        
        target = graph[target_name]
        context = {}
        files_added = 0
        
        # Priority 1: The class itself
        context['target'] = Path(file_path).read_text(encoding='utf-8')
        
        # Priority 2: Entity class (for understanding data model)
        base_name = target_name.replace('ServiceImpl', '').replace('Service', '').replace('Validator', '').replace('Controller', '')
        entity_path = self._find_class_file(f"{base_name}Entity")
        if entity_path and files_added < max_files:
            context['entity'] = Path(entity_path).read_text(encoding='utf-8')
            files_added += 1
        
        # Priority 3: DTO class
        dto_path = self._find_class_file(base_name)
        if dto_path and files_added < max_files:
            content = Path(dto_path).read_text(encoding='utf-8')
            # Only include if it has InDto/OutDto
            if 'InDto' in content or 'OutDto' in content:
                context['dto'] = content
                files_added += 1
        
        # Priority 4: Validator (need to know what exceptions it throws)
        validator_path = self._find_class_file(f"{base_name}Validator")
        if validator_path and validator_path != file_path and files_added < max_files:
            context['validator'] = Path(validator_path).read_text(encoding='utf-8')
            files_added += 1
        
        # Priority 5: Mapper (need to know mapping methods)
        mapper_path = self._find_class_file(f"{base_name}Mapper")
        if mapper_path and files_added < max_files:
            context['mapper'] = Path(mapper_path).read_text(encoding='utf-8')
            files_added += 1
        
        return context


if __name__ == "__main__":
    # Test the dependency graph builder
    import sys
    builder = DependencyGraphBuilder(".")
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Building dependency graph for: {file_path}")
        graph = builder.build_graph_for_class(file_path)
        
        for name, dep in graph.items():
            print(f"\n{name}:")
            print(f"  Dependencies: {dep.dependencies}")
            print(f"  Methods with calls: {list(dep.method_calls.keys())}")
        
        target = Path(file_path).stem
        required_mocks = builder.get_all_required_mocks(graph, target)
        print(f"\nRequired mocks for {target}:")
        for dep, methods in required_mocks.items():
            print(f"  {dep}: {methods}")

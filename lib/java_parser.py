"""
Java Parser - Extract class information from Java source files
"""
import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JavaMethod:
    name: str
    return_type: str
    parameters: List[str]
    annotations: List[str]
    is_public: bool
    body_preview: str = ""


@dataclass
class JavaClass:
    name: str
    package: str
    file_path: str
    imports: List[str]
    annotations: List[str]
    extends: Optional[str]
    implements: List[str]
    fields: List[str]
    methods: List[JavaMethod]
    source_code: str
    class_type: str = "class"  # class, interface, abstract


class JavaParser:
    """Parse Java source files to extract class information"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
    
    def parse_file(self, file_path: str) -> JavaClass:
        """Parse a Java file and extract class information"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        return self._parse_source(source_code, str(path))
    
    def _parse_source(self, source: str, file_path: str) -> JavaClass:
        """Parse Java source code"""
        # Extract package
        package_match = re.search(r'package\s+([\w.]+);', source)
        package = package_match.group(1) if package_match else ""
        
        # Extract imports
        imports = re.findall(r'import\s+([\w.*]+);', source)
        
        # Extract class declaration
        class_pattern = r'(?:(@\w+(?:\([^)]*\))?)\s*)*(?:public\s+)?(?:(abstract)\s+)?(class|interface)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?'
        class_match = re.search(class_pattern, source)
        
        class_name = class_match.group(4) if class_match else Path(file_path).stem
        extends = class_match.group(5) if class_match and class_match.group(5) else None
        implements_str = class_match.group(6) if class_match and class_match.group(6) else ""
        implements = [i.strip() for i in implements_str.split(',')] if implements_str else []
        class_type = class_match.group(3) if class_match else "class"
        if class_match and class_match.group(2):
            class_type = "abstract"
        
        # Extract class-level annotations
        annotations = re.findall(r'@(\w+(?:\([^)]*\))?)', source[:source.find('class ')] if 'class ' in source else source)
        
        # Extract fields (injected dependencies)
        fields = self._extract_fields(source)
        
        # Extract methods
        methods = self._extract_methods(source)
        
        return JavaClass(
            name=class_name,
            package=package,
            file_path=file_path,
            imports=imports,
            annotations=annotations,
            extends=extends,
            implements=implements,
            fields=fields,
            methods=methods,
            source_code=source,
            class_type=class_type
        )
    
    def _extract_fields(self, source: str) -> List[str]:
        """Extract field declarations"""
        # Match fields like: OrderDao orderDao; or @Autowired OrderDao orderDao;
        field_pattern = r'(?:@\w+\s+)*(?:private|protected|public)?\s*(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*;'
        matches = re.findall(field_pattern, source)
        return [f"{type_} {name}" for type_, name in matches]
    
    def _extract_methods(self, source: str) -> List[JavaMethod]:
        """Extract method declarations with body analysis"""
        methods = []
        
        # Pattern for method declarations (access modifier is optional for interface methods)
        method_pattern = r'((?:@\w+(?:\([^)]*\))?\s*)+)?(?:(?:public|private|protected)\s+)?(?:(?:static|final|abstract|default)\s+)*(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(method_pattern, source):
            annotations_str = match.group(1) or ""
            annotations = re.findall(r'@(\w+)', annotations_str)
            return_type = match.group(2)
            method_name = match.group(3)
            params_str = match.group(4)
            
            # Parse parameters
            params = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param:
                        params.append(param)
            
            is_public = 'public' in source[max(0, match.start()-20):match.start()]
            
            # Extract method body for analysis
            body_preview = self._extract_method_body(source, match.end())
            
            methods.append(JavaMethod(
                name=method_name,
                return_type=return_type,
                parameters=params,
                annotations=annotations,
                is_public=is_public,
                body_preview=body_preview
            ))
        
        return methods
    
    def _extract_method_body(self, source: str, start_pos: int) -> str:
        """Extract method body for analysis (up to 500 chars)"""
        # Find the opening brace
        brace_pos = source.find('{', start_pos)
        if brace_pos == -1:
            return ""
        
        # Find matching closing brace
        depth = 1
        pos = brace_pos + 1
        while pos < len(source) and depth > 0:
            if source[pos] == '{':
                depth += 1
            elif source[pos] == '}':
                depth -= 1
            pos += 1
        
        body = source[brace_pos + 1:pos - 1]
        return body[:800]  # Limit to 800 chars
    
    def extract_method_calls(self, java_class: JavaClass) -> dict:
        """Extract all service/validator/dao method calls from class methods"""
        calls = {
            'validator_calls': set(),
            'service_calls': set(),
            'dao_calls': set(),
            'mapper_calls': set()
        }
        
        for method in java_class.methods:
            body = method.body_preview
            if not body:
                continue
            
            # Extract validator calls: validatorName.methodName(...)
            validator_pattern = r'(\w+Validator)\.(\w+)\s*\('
            for match in re.finditer(validator_pattern, body):
                calls['validator_calls'].add(f"{match.group(1)}.{match.group(2)}()")
            
            # Extract service calls
            service_pattern = r'(\w+Service)\.(\w+)\s*\('
            for match in re.finditer(service_pattern, body):
                calls['service_calls'].add(f"{match.group(1)}.{match.group(2)}()")
            
            # Extract dao calls
            dao_pattern = r'(\w+Dao)\.(\w+)\s*\('
            for match in re.finditer(dao_pattern, body):
                calls['dao_calls'].add(f"{match.group(1)}.{match.group(2)}()")
            
            # Extract mapper calls
            mapper_pattern = r'(\w+Mapper)\.(\w+)\s*\('
            for match in re.finditer(mapper_pattern, body):
                calls['mapper_calls'].add(f"{match.group(1)}.{match.group(2)}()")
        
        return {k: list(v) for k, v in calls.items()}
    
    def extract_mapper_types(self, java_class: JavaClass) -> set:
        """Extract DTO and Entity types from Mapper method signatures.
        
        For MapStruct Mappers, we need to extract all referenced types from:
        - Method return types (e.g., BillingAddressEntity, List<BillingAddressOutDto>)
        - Method parameters (e.g., BillingAddressInDto, @MappingTarget BillingAddressEntity)
        
        Returns a set of type names to find.
        """
        types = set()
        
        for method in java_class.methods:
            # Extract return type
            return_type = method.return_type
            if return_type and return_type not in ('void', 'boolean', 'int', 'long', 'String'):
                # Handle generics: List<TypeName> -> TypeName
                if '<' in return_type:
                    inner_type = re.search(r'<(\w+)>', return_type)
                    if inner_type:
                        types.add(inner_type.group(1))
                else:
                    types.add(return_type)
            
            # Extract parameter types
            for param in method.parameters:
                # Remove annotations like @MappingTarget
                param_clean = re.sub(r'@\w+\s*', '', param).strip()
                # Extract type name (first word, handling generics)
                type_match = re.match(r'([\w<>]+)', param_clean)
                if type_match:
                    param_type = type_match.group(1)
                    if param_type not in ('void', 'boolean', 'int', 'long', 'String'):
                        if '<' in param_type:
                            inner_type = re.search(r'<(\w+)>', param_type)
                            if inner_type:
                                types.add(inner_type.group(1))
                        else:
                            types.add(param_type)
        
        # Filter to only DTO/Entity patterns (ends with InDto, OutDto, Entity, or starts with uppercase)
        filtered_types = set()
        for t in types:
            if t.endswith('InDto') or t.endswith('OutDto') or t.endswith('Entity') or t.endswith('Dto'):
                filtered_types.add(t)
        
        return filtered_types
    
    def extract_uses_mappers(self, java_class: JavaClass) -> list:
        """Extract dependent mappers from @Mapper(uses = {...}) annotation.
        
        For MapStruct Mappers like:
        @Mapper(componentModel = "spring", uses = {CatalogHasTenantMapper.class, SupplierAccountMapper.class})
        
        Returns a list of mapper class names.
        """
        mappers = []
        
        # Search in source code for @Mapper annotation with uses
        uses_pattern = r'@Mapper\s*\([^)]*uses\s*=\s*\{([^}]+)\}'
        match = re.search(uses_pattern, java_class.source_code)
        
        if match:
            uses_content = match.group(1)
            # Extract individual mapper classes: XxxMapper.class -> XxxMapper
            mapper_pattern = r'(\w+Mapper)\.class'
            for mapper_match in re.finditer(mapper_pattern, uses_content):
                mappers.append(mapper_match.group(1))
        
        return mappers
    
    def find_related_files(self, java_class: JavaClass) -> dict:
        """Find related files (Entity, DTO, Mapper, etc.)"""
        related = {}
        base_name = java_class.name.replace("ServiceImpl", "").replace("Service", "").replace("Controller", "").replace("Mapper", "")
        
        # Check if this is a Mapper class
        is_mapper = java_class.name.endswith('Mapper') or any('Mapper' in ann for ann in java_class.annotations)
        
        # Common related file patterns
        patterns = {
            'entity': f"{base_name}Entity.java",
            'dto': f"{base_name}.java",  # DTO container
            'mapper': f"{base_name}Mapper.java",
            'validator': f"{base_name}Validator.java",
            'dao': f"{base_name}Dao.java",
            'service': f"{base_name}Service.java",
            'service_impl': f"{base_name}ServiceImpl.java",
        }
        
        for key, pattern in patterns.items():
            found = list(self.base_dir.rglob(pattern))
            if found:
                related[key] = str(found[0])
        
        # For Mapper classes, also find all types referenced in method signatures
        if is_mapper:
            mapper_types = self.extract_mapper_types(java_class)
            for type_name in mapper_types:
                # Skip if already found
                if type_name in related:
                    continue
                
                # InDto/OutDto are often nested classes in a container file
                # e.g., BillingAddressInDto is in BillingAddress.java
                container_name = None
                if type_name.endswith('InDto') or type_name.endswith('OutDto'):
                    # Extract base: BillingAddressInDto -> BillingAddress
                    container_name = re.sub(r'(In|Out)Dto$', '', type_name)
                
                # Try to find the file
                if type_name.endswith('Entity'):
                    found = list(self.base_dir.rglob(f"{type_name}.java"))
                    if found:
                        related[f'mapper_entity_{type_name}'] = str(found[0])
                elif container_name:
                    # Look for container file (e.g., BillingAddress.java for BillingAddressInDto)
                    found = list(self.base_dir.rglob(f"{container_name}.java"))
                    if found:
                        related[f'mapper_dto_{container_name}'] = str(found[0])
                else:
                    # Direct search for the type
                    found = list(self.base_dir.rglob(f"{type_name}.java"))
                    if found:
                        related[f'mapper_type_{type_name}'] = str(found[0])
            
            # Also include dependent mappers from @Mapper(uses = {...})
            uses_mappers = self.extract_uses_mappers(java_class)
            for mapper_name in uses_mappers:
                found = list(self.base_dir.rglob(f"{mapper_name}.java"))
                if found:
                    related[f'uses_mapper_{mapper_name}'] = str(found[0])
        
        return related


if __name__ == "__main__":
    # Test the parser
    parser = JavaParser("src/main/java")
    java_class = parser.parse_file("src/main/java/de/cathago/earth/domain/order/core/OrderServiceImpl.java")
    print(f"Class: {java_class.name}")
    print(f"Package: {java_class.package}")
    print(f"Fields: {java_class.fields}")
    print(f"Methods: {[m.name for m in java_class.methods]}")

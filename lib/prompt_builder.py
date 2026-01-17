"""
Prompt Builder - Create context-aware prompts for test generation
"""
from typing import Optional
from .java_parser import JavaClass
from .context_gatherer import ContextGatherer


class PromptBuilder:
    """Build prompts for AI test generation"""
    
    def __init__(self, context_gatherer: ContextGatherer):
        self.context = context_gatherer
    
    def build_system_prompt(self) -> str:
        """Build the system prompt with project context"""
        return f"""You are an expert Java developer specializing in Spring Boot testing.
You write high-quality, maintainable test code following modern best practices.

## PROJECT CONTEXT

This is a B2B procurement platform called "Cathago Earth". Here are the key conventions:

### Project Structure (scanned at startup):
{self.context.get_project_summary()[:3000]}

### Coding Conventions (from architecture.md):
{self.context.get_architecture_summary()[:2000]}

### Entity Relationships & Sample Data (from metadata.txt):
{self.context.get_metadata_summary()[:2000]}

## TESTING STANDARDS

Always follow these practices:
1. **JUnit 5** - Use @Test, @DisplayName, @Nested, @BeforeEach
2. **Mockito** - Use @Mock, @InjectMocks, @ExtendWith(MockitoExtension.class)
3. **AssertJ** - Use assertThat() for fluent assertions
4. **BDD Style** - Structure tests with // Given, // When, // Then comments
5. **Instancio** - Use Instancio.create() for test data generation
6. **Descriptive Names** - Methods should start with "should" and describe expected behavior

## CRITICAL MOCKITO BEST PRACTICES (to avoid test failures)

1. **ALWAYS use any() matchers for dynamic IDs:**
   - WRONG: `when(dao.findById("project-123")).thenReturn(entity);`
   - CORRECT: `when(dao.findById(any(String.class))).thenReturn(entity);`
   
2. **For generic types with Instancio, use TypeToken:**
   - WRONG: `SearchOutDto<ProjectOutDto> dto = Instancio.create(SearchOutDto.class);`
   - CORRECT: `SearchOutDto<ProjectOutDto> dto = Instancio.create(new TypeToken<SearchOutDto<ProjectOutDto>>() {{}});`
   
3. **Set non-null nested entities when testing methods with internal logic:**
   ```java
   ProjectEntity projectEntity = Instancio.of(ProjectEntity.class)
       .set(field(ProjectEntity::getProjectImageDocument), Instancio.create(DocumentEntity.class))
       .create();
   ```

4. **Use lenient() when stubs may not be called:**
   - `lenient().when(service.method(any())).thenReturn(result);`

5. **For methods that call private methods accessing entity fields, ensure ALL nested objects are non-null**

6. **Always mock validators that throw exceptions:**
   ```java
   when(validator.findById(any())).thenReturn(Instancio.create(Entity.class));
   ```

7. **NEVER use doNothing() on non-void methods:**
   - WRONG: `doNothing().when(service).updateAll(anyString(), any());` // if updateAll returns something
   - CORRECT: `when(service.updateAll(anyString(), any())).thenReturn(Collections.emptyList());`
   - `doNothing()` is ONLY for void methods!

8. **Check method return types carefully before choosing stub syntax:**
   - Void method: `doNothing().when(mock).voidMethod();`
   - Non-void method: `when(mock.method()).thenReturn(value);`

9. **For patchUpdate methods that might be void OR return value, use:**
   - `lenient().when(service.patchUpdate(any(), any())).thenReturn(Instancio.create(OutDto.class));`

## OUTPUT FORMAT

When generating tests:
1. Output ONLY valid Java code - no markdown, no explanations
2. Triple-check all class names for typos before outputting
3. Cover happy paths and edge cases
4. For Integration tests: Use @SpringBootTest, MockMvc, and Testcontainers

## REQUIRED IMPORTS (use EXACTLY these spellings):
```java
// Testing framework
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.extension.ExtendWith;

// Mockito (CORRECT spellings)
import org.mockito.Mock;
import org.mockito.InjectMocks;
import org.mockito.ArgumentCaptor;  // NOT ArgumentCaptCaptor!
import org.mockito.junit.jupiter.MockitoExtension;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

// AssertJ
import static org.assertj.core.api.Assertions.*;

// Instancio
import org.instancio.Instancio;
import org.instancio.TypeToken;
import org.instancio.settings.Keys;
import org.instancio.settings.Settings;
import static org.instancio.Select.field;
```
"""

    def build_unit_test_prompt(self, java_class: JavaClass, related_content: dict, method_calls: dict = None) -> str:
        """Build prompt for unit test generation"""
        related_code = self._format_related_content(related_content)
        
        # Format method calls that need mocking
        mock_requirements = ""
        if method_calls:
            mock_requirements = "\n## METHODS THAT MUST BE MOCKED (extracted from method bodies):\n"
            if method_calls.get('validator_calls'):
                mock_requirements += f"\n### Validator calls:\n"
                for call in method_calls['validator_calls'][:10]:
                    mock_requirements += f"- {call}\n"
            if method_calls.get('service_calls'):
                mock_requirements += f"\n### Service calls:\n"
                for call in method_calls['service_calls'][:10]:
                    mock_requirements += f"- {call}\n"
            if method_calls.get('dao_calls'):
                mock_requirements += f"\n### DAO calls:\n"
                for call in method_calls['dao_calls'][:10]:
                    mock_requirements += f"- {call}\n"
            if method_calls.get('mapper_calls'):
                mock_requirements += f"\n### Mapper calls:\n"
                for call in method_calls['mapper_calls'][:10]:
                    mock_requirements += f"- {call}\n"
        
        # Extract enums used in this specific class
        enum_context = self._extract_class_specific_enums(java_class.source_code)
        if enum_context:
            mock_requirements += f"\n## ENUMS USED IN THIS CLASS (use ONLY these values):\n{enum_context}\n"
        
        return f"""Generate a comprehensive unit test for the following Spring Boot service class.

## TARGET CLASS TO TEST:
```java
{java_class.source_code}
```

## RELATED CLASSES (for context):
{related_code}
{mock_requirements}

## CRITICAL REQUIREMENTS (follow exactly to avoid test failures):

### 0. CRITICAL: NEVER RECREATE EXISTING PROJECT CLASSES
DO NOT create inner classes or local copies of project classes in the test file!
- All entities (BaseEntity, XxxEntity) EXIST in the project - IMPORT them
- All DTOs (XxxInDto, XxxOutDto) EXIST in the project - IMPORT them  
- All enums (XxxType, XxxStatus) EXIST in the project - IMPORT them
- All exceptions (XxxException) EXIST in the project - IMPORT them
- All utility classes (XxxUtil) EXIST in the project - IMPORT them

The test file should ONLY contain:
1. Package declaration
2. Import statements (for ALL needed classes)
3. The @ExtendWith annotation
4. The test class with test methods

WRONG - DO NOT DO THIS:
```java
// DON'T recreate classes that exist in the project
class BaseEntity {{ ... }}  // WRONG!
enum ApiKeyType {{ ... }}    // WRONG!
class ApiKeyEntity {{ ... }} // WRONG!
```

CORRECT - Always import:
```java
import de.cathago.earth.domain.configuration.subDomain.apiKey.core.ApiKeyEntity;
import de.cathago.earth.domain.configuration.subDomain.apiKey.core.ApiKeyType;
import de.cathago.earth.domain.core.common.entity.BaseEntity;
```

### 1. Test Class Structure
- Create a test class named `{java_class.name}Test`
- Use `@ExtendWith(MockitoExtension.class)` on the class
- DO NOT use @Nested inner classes - put ALL test methods directly in the test class
- Include `@DisplayName` with clear descriptions (format: "methodName - should do X when Y")

### 1a. IMPORTANT: When Testing a Mapper (class name ends with "Mapper")
If you are testing a MapStruct Mapper directly, use Mappers.getMapper():
```java
// When testing the mapper itself
private SomeMapper mapper = Mappers.getMapper(SomeMapper.class);
// Do NOT use when() on this - it's a real object, not a mock!
```

### 1b. IMPORTANT: When Testing a ServiceImpl that USES a Mapper
If the class under test (ServiceImpl) has a mapper as a dependency, use @Mock:
```java
@Mock
private SomeMapper someMapper;  // <- This is a mock, when() works on this

@InjectMocks
private SomeServiceImpl service;

// In tests:
when(someMapper.entityToOutDto(any())).thenReturn(expectedOutDto);  // <- CORRECT
```

### 1c. NEVER DO THIS (causes NotAMockException):
```java
private SomeMapper mapper = Mappers.getMapper(SomeMapper.class);  // Real object
when(mapper.method()).thenReturn(x);  // WRONG! Can't use when() on real objects!
```

### 1d. Mappers with @Mapper(uses = {{...}}) - Dependent Mappers
When a Mapper has `uses = {{OtherMapper.class, ...}}`, MapStruct generates an implementation that automatically includes all dependent mappers. You do NOT need to mock or manually wire these.

```java
// CatalogMapper uses CatalogHasTenantMapper, SupplierAccountMapper, CompanyAccountMapper
@Mapper(componentModel = "spring", uses = {{CatalogHasTenantMapper.class, SupplierAccountMapper.class}})
public interface CatalogMapper {{ ... }}

// In test: Just use getMapper - dependent mappers are auto-included
private CatalogMapper catalogMapper = Mappers.getMapper(CatalogMapper.class);
// All uses-mappers are automatically resolved by MapStruct's generated impl

// Do NOT do this - no need to manually wire dependent mappers:
// WRONG: mapper = new CatalogMapperImpl(tenantMapper, supplierMapper); 
```

### 2. IMPORTANT: Instancio Configuration for Non-Null Nested Objects
Many methods call private helper methods that access nested entity fields. Configure Instancio to create non-null nested objects:

```java
@BeforeEach
void setUp() {{
    // Create entities with ALL nested objects populated (no nulls)
    entity = Instancio.of(EntityClass.class)
        .withSettings(Settings.create()
            .set(Keys.SET_BACK_REFERENCES, false)
            .set(Keys.MAX_DEPTH, 4))
        .create();
}}
```

### 2b. CRITICAL: Instancio.withSettings() is NOT a standalone method!
```java
// WRONG - will cause compilation error "No candidates found for method call"
Instancio.withSettings(Settings.create()...)  // THIS IS WRONG!

// CORRECT - withSettings() is ONLY valid on Instancio.of()
entity = Instancio.of(EntityClass.class)
    .withSettings(Settings.create().set(Keys.MAX_DEPTH, 4))
    .create();

// Or simply don't use withSettings at all for simple entities:
entity = Instancio.create(EntityClass.class);
```

### 3. IMPORTANT: Use any() Matchers Everywhere
NEVER use hardcoded IDs in mock setups. Instancio generates random IDs:
```java
// WRONG - will cause stubbing mismatch
when(validator.findById("hardcoded-id")).thenReturn(entity);

// CORRECT - matches any ID
when(validator.findById(any(String.class))).thenReturn(entity);
when(dao.save(any(EntityClass.class))).thenReturn(entity);
```

### 4. CRITICAL: Check Return Types Before Using doNothing()
`doNothing()` ONLY works on VOID methods! Using it on non-void methods causes:
`MockitoException: Only void methods can doNothing()`

```java
// WRONG - updateStatus returns DocumentOutDto, NOT void!
doNothing().when(documentService).updateStatus(anyString(), any(DocumentStatus.class)); // ERROR!

// CORRECT - use when().thenReturn() for methods that return something:
when(documentService.updateStatus(anyString(), any(DocumentStatus.class))).thenReturn(Instancio.create(DocumentOutDto.class));

// For VOID methods like delete(), use doNothing():
doNothing().when(documentService).delete(anyString()); // OK - delete() is void

// RULE: Check the service interface to see if method is void or returns something!
// void delete(String id);  -> use doNothing()
// DocumentOutDto updateStatus(String id, Status s); -> use when().thenReturn()
```
// If unsure, use lenient():
lenient().when(service.method(any())).thenReturn(result);
```

### 5. CRITICAL: DO NOT USE MockedStatic
MockedStatic requires mockito-inline which is NOT available:
```java
// WRONG - will fail with "SubclassByteBuddyMockMaker does not support static mocks"
try (MockedStatic<SomeUtil> mockedStatic = mockStatic(SomeUtil.class)) {{
    mockedStatic.when(SomeUtil::createToken).thenReturn("token");
}}

// CORRECT - just use the real static method or bypass it:
// Option 1: Don't mock static methods at all, let them run
// Option 2: Use any() matcher and don't verify the static call
when(mapper.inDtoToEntity(any(), anyString(), any())).thenReturn(entity);
```

### 6. CRITICAL: verify() ONLY Works on @Mock Fields, NOT Entities
```java
// WRONG - apiKeyEntity is NOT a mock, it's an entity created with Instancio
verify(apiKeyEntity).setEnabled(false);  // ERROR: NotAMockException!

// CORRECT - only verify @Mock annotated fields:
verify(apiKeyDao).save(any(ApiKeyEntity.class));
verify(apiKeyMapper).entityToOutDto(any(ApiKeyEntity.class));
verify(apiKeyValidator).findById(any(String.class));

// If you need to check entity state, use assertions instead:
assertThat(apiKeyEntity.getEnabled()).isFalse();
```

### 7. Mock ALL Validators and Services Called by Private Methods
Look at what the public method calls internally. Mock return values for ALL validators:
```java
when(documentValidator.findById(any())).thenReturn(Instancio.create(DocumentEntity.class));
when(addressValidator.findById(any())).thenReturn(Instancio.create(AddressEntity.class));
```

### 8. Use lenient() for Stubs That May Not Always Be Called
```java
lenient().when(optionalService.method(any())).thenReturn(result);
```

### 7. Standard Test Structure (BDD Style)
```java
@Test
@DisplayName("should do X when Y")
void shouldDoXWhenY() {{
    // Given
    when(dependency.method(any())).thenReturn(expectedValue);
    
    // When  
    Result result = serviceUnderTest.methodToTest(input);
    
    // Then
    assertThat(result).isEqualTo(expectedValue);
    verify(dependency).method(any());
}}
```

### 8. Required Imports
```java
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import org.instancio.Instancio;
import org.instancio.settings.Keys;
import org.instancio.settings.Settings;
```

Generate the complete test class with all imports."""

    def build_integration_test_prompt(self, java_class: JavaClass, related_content: dict) -> str:
        """Build prompt for E2E integration test generation"""
        related_code = self._format_related_content(related_content)
        sample_data = self.context.get_sample_test_data(
            java_class.name.replace("Controller", "").replace("ServiceImpl", "")
        )
        
        # Extract domain name from package
        domain_name = java_class.package.split('.')[-2] if java_class.package else "domain"
        
        return f"""Generate a complete end-to-end integration test for the following Spring Boot controller.

## TARGET CLASS TO TEST:
```java
{java_class.source_code}
```

## RELATED CLASSES (for context):
{related_code}

## SAMPLE DATA FOR TESTS (use realistic values):
{sample_data}

## CRITICAL: Follow the EXACT project patterns below

### 1. Test Class Structure
```java
@Slf4j
class {java_class.name.replace('Controller', 'IntegrationTest').replace('Procurement', '').replace('Supplier', '')} extends BaseEarthApplicationIntegrationTest {{

    private static final String API_ENDPOINT = "/api/gateways/procurement/{domain_name.lower()}s";
    private static final String COMPANY_ACCOUNT_ID = "test_a_ca_1";

    @Value("classpath:dtos/{domain_name.lower()}/GET_{domain_name}OutDto.json")
    Resource GET_{domain_name}OutDtoJson;

    @Value("classpath:dtos/{domain_name.lower()}/POST_{domain_name}InDto.json")  
    Resource POST_{domain_name}InDtoJson;

    @Autowired
    private ProcurementUserContext procurementUserContext;

    @Test
    @Order(1)
    void findAll() throws Exception {{
        ResultActions resultActions = mockMvc.perform(MockMvcRequestBuilders.get(API_ENDPOINT)
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", procurementUserContext.getToken())
                .param("companyAccountId", COMPANY_ACCOUNT_ID))
            .andExpect(status().isOk())
            .andDo(result -> printIfFailed(result, HttpStatus.OK));
        assertResponse(resultActions, GET_{domain_name}OutDtosJson);
    }}

    @Test
    @Order(2)  
    void find() throws Exception {{
        ResultActions resultActions = mockMvc.perform(MockMvcRequestBuilders.get(API_ENDPOINT + "/" + ENTITY_ID)
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", procurementUserContext.getToken())
                .param("companyAccountId", COMPANY_ACCOUNT_ID))
            .andExpect(status().isOk());
        assertResponse(resultActions, GET_{domain_name}OutDtoJson);
    }}

    @Test
    @Order(3)
    void create() throws Exception {{
        ResultActions resultActions = mockMvc.perform(MockMvcRequestBuilders.post(API_ENDPOINT)
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", procurementUserContext.getToken())
                .param("companyAccountId", COMPANY_ACCOUNT_ID)
                .content(basicJsonTester.from(POST_{domain_name}InDtoJson).getJson()))
            .andExpect(status().isCreated());
        assertResponse(resultActions, POST_{domain_name}OutDtoJson);
    }}

    @Test
    @Order(4)
    void delete() throws Exception {{
        mockMvc.perform(MockMvcRequestBuilders.delete(API_ENDPOINT + "/" + ENTITY_ID)
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", procurementUserContext.getToken())
                .param("companyAccountId", COMPANY_ACCOUNT_ID))
            .andExpect(status().isNoContent());
    }}
}}
```

### 2. REQUIREMENTS:
1. Extend `BaseEarthApplicationIntegrationTest` (NOT AbstractIntegrationTest)
2. Use `@Order` annotation for test execution sequence (find → create → update → delete)
3. Use `@Value("classpath:dtos/{{domain}}/{{file}}.json")` for expected JSON responses
4. Use `procurementUserContext.getToken()` for Authorization header
5. Always pass `companyAccountId` as request parameter
6. Use `assertResponse(resultActions, resourceJson)` for JSON comparison
7. Use `basicJsonTester.from(resource).getJson()` for request bodies
8. Use `printIfFailed(result, HttpStatus.OK)` for debugging
9. DO NOT use @Nested classes - keep all tests in main class
10. Use realistic entity IDs that match test data (e.g., "project1", "12uu21")

### 3. Required Imports:
```java
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import de.cathago.earth.BaseEarthApplicationIntegrationTest;
import de.cathago.earth.ProcurementUserContext;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
```

### 4. IMPORTANT:
- The test data already exists in SQL migration scripts (e.g., M003__create_project.sql)
- Use existing entity IDs from those scripts (project1, project2, 12uu21, etc.)
- Expected JSON files should be created in src/test/resources/dtos/{{domain}}/

Generate the complete test class with all imports."""

    def build_refinement_prompt(self, current_code: str, user_feedback: str) -> str:
        """Build prompt for refining/modifying generated tests"""
        return f"""The user wants to modify the following test code.

## CURRENT TEST CODE:
```java
{current_code}
```

## USER'S REQUESTED CHANGES:
{user_feedback}

## INSTRUCTIONS:
1. Apply the requested changes
2. Keep all existing good patterns
3. Maintain BDD style and naming conventions
4. Output the complete modified test class

Generate the updated test class."""

    def _format_related_content(self, related_content: dict) -> str:
        """Format related files content for prompt"""
        if not related_content:
            return "No related files found."
        
        parts = []
        for key, data in related_content.items():
            # Limit each file to prevent token overflow
            content = data['content'][:3000] if len(data['content']) > 3000 else data['content']
            parts.append(f"### {key.upper()} ({data['path']}):\n```java\n{content}\n```")
        
        return '\n\n'.join(parts)
    
    def _extract_class_specific_enums(self, source_code: str) -> str:
        """Extract enums used in this class and get their valid values from project context"""
        import re
        
        # Find enum types used in the source code (patterns like XxxType, XxxStatus)
        enum_patterns = [
            r'\b(\w+Type)\b',          # e.g., ApiKeyType
            r'\b(\w+Status)\b',        # e.g., OrderStatus
            r'\b(\w+State)\b',         # e.g., ProcessState
            r'\b(\w+Mode)\b',          # e.g., DeliveryMode
            r'\b(\w+Category)\b',      # e.g., ProductCategory
            r'\b(\w+Enum)\b',          # e.g., SomeEnum
        ]
        
        found_enums = set()
        for pattern in enum_patterns:
            matches = re.findall(pattern, source_code)
            found_enums.update(matches)
        
        if not found_enums:
            return ""
        
        # Lookup actual values from project context
        enum_info = []
        project_enums = self.context.project_context_cache.get('enums', {})
        
        for enum_name in found_enums:
            # Try exact match first
            if enum_name in project_enums:
                values = project_enums[enum_name].get('values', [])
                if values:
                    enum_info.append(f"- {enum_name}: {', '.join(values)}")
            else:
                # Try partial match (enum might be stored without suffix)
                for stored_name, info in project_enums.items():
                    if enum_name in stored_name or stored_name in enum_name:
                        values = info.get('values', [])
                        if values:
                            enum_info.append(f"- {enum_name}: {', '.join(values)}")
                            break
        
        return '\n'.join(enum_info) if enum_info else ""


if __name__ == "__main__":
    # Test the prompt builder
    from .context_gatherer import ContextGatherer
    context = ContextGatherer(".")
    builder = PromptBuilder(context)
    print("System prompt length:", len(builder.build_system_prompt()))

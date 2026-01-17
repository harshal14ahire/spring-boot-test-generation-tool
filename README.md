# 🤖 AI Test Generator for Spring Boot

An interactive, chat-based tool that automatically generates unit and integration tests for Spring Boot applications using Google Gemini AI.

## Features

- **Interactive Chat Interface** - Have a conversation to refine tests
- **Context-Aware** - Uses `metadata.txt` and `architecture.md` for realistic test data
- **Modern Practices** - JUnit 5, Mockito, AssertJ, Instancio, BDD style
- **Full E2E Integration Tests** - Controller → Service → DAO → Database with Testcontainers
- **Iterative Refinement** - Request changes and the AI will update the tests

## Quick Start

### 1. Install Dependencies

```bash
cd tools/test-generator
pip install -r requirements.txt
```

### 2. Set API Key

Get a free API key from [Google AI Studio](https://aistudio.google.com):

```bash
export GEMINI_API_KEY='your-api-key-here'
```

### 3. Run the Tool

```bash
python generate_tests.py
```

## Usage

### Interactive Commands

| Command | Description |
|---------|-------------|
| `load <filepath>` | Load a Java source file |
| `unit` | Generate unit test for loaded class |
| `integration` | Generate E2E integration test |
| `save` | Save current test to file |
| `show` | Show current generated test |
| `reset` | Reset chat and start fresh |
| `help` | Show available commands |
| `quit` | Exit the tool |

### Example Session

```
🤖 AI Test Generator for Spring Boot
=====================================

✅ AI initialized. Type 'help' for commands.

🧑 You: load src/main/java/de/cathago/earth/domain/order/core/OrderServiceImpl.java

✅ Loaded: OrderServiceImpl
   Package: de.cathago.earth.domain.order.core
   Methods: 12
   Dependencies: 8
   Related files: ['entity', 'mapper', 'validator', 'dao']

🧑 You: unit

🔄 Generating unit test...

🤖 AI:
[Generated unit test code appears here]

🧑 You: Add more edge cases for the create method

🔄 Refining test...

🤖 AI:
[Updated test with additional edge cases]

🧑 You: save

✅ Test saved to: src/test/java/de/cathago/earth/domain/order/core/OrderServiceImplTest.java
```

### Integration Test Example

```
🧑 You: load src/main/java/de/cathago/earth/domain/order/gateway/procurement/ProcurementOrderController.java

🧑 You: integration

🔄 Generating integration test...

🤖 AI:
[Generated E2E test with MockMvc and Testcontainers]

🧑 You: Use sample data from metadata.txt

🔄 Refining test...

🤖 AI:
[Updated test with realistic data like "Mumbai-Pune Expressway" project]
```

## Test Dependencies (Add to pom.xml)

```xml
<!-- Instancio for test data generation -->
<dependency>
    <groupId>org.instancio</groupId>
    <artifactId>instancio-junit</artifactId>
    <version>4.0.0</version>
    <scope>test</scope>
</dependency>

<!-- Testcontainers -->
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>

<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>postgresql</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>

<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>mongodb</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>

<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>kafka</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>

<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>
```

## AbstractIntegrationTest

Copy the template from `lib/templates/AbstractIntegrationTest.java` to your test sources:

```bash
cp lib/templates/AbstractIntegrationTest.java \
   ../../src/test/java/de/cathago/earth/AbstractIntegrationTest.java
```

## Configuration

Edit `config.yaml` to customize:

- AI provider and model
- Test naming conventions
- Testcontainers settings
- Project paths

## Troubleshooting

### "GEMINI_API_KEY not found"
```bash
export GEMINI_API_KEY='your-key-here'
```

### "google-generativeai not installed"
```bash
pip install google-generativeai
```

### Rate Limiting
Gemini free tier: 15 requests/minute. Wait a moment if you hit limits.

---

Made with ❤️ for Spring Boot developers

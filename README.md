# Spring MCP Bridge

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)
![Spring](https://img.shields.io/badge/spring-boot%203.x-green.svg)

**Spring MCP Bridge** is a tool that automatically converts REST endpoints from Spring Boot applications into an MCP (Message Conversation Protocol) server, allowing AI assistants like Claude, Cursor, and other MCP-compatible tools to directly interact with your APIs.

*It does not currently include authentication. If your Spring Boot API requires authentication, you will need to modify the handler code to include the appropriate headers or tokens.

## 📖 Overview

Integrating existing APIs with AI assistants typically requires manual coding or complex configuration. Spring MCP Bridge eliminates this complexity by automatically scanning your Spring Boot project and generating a ready-to-use MCP server.

### ✨ Features

- **Automatic Scanning**: Discovers all REST endpoints (@RestController, @GetMapping, etc.)
- **Zero Configuration**: No modifications needed to existing Spring Boot code
- **Model Preservation**: Maintains request and response models as MCP tools
- **Javadoc Extraction**: Uses existing documentation to enhance MCP tool descriptions
- **Complete Documentation**: Generates README and clear instructions for use

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/brunosantos/spring-mcp-bridge.git

# Enter the directory
cd spring-mcp-bridge
```

## 🛠️ Usage

1. **Scan your Spring Boot project**:

```bash
python spring_boot_mcp_converter.py --project /path/to/spring-project --output ./mcp_server --name MyAPI
```

2. **Run the generated MCP server**:

```bash
cd mcp_server
pip install -r requirements.txt
python main.py
```

3. **Connect via MCP client**:
   - Configure your MCP client (Claude, Cursor, etc.) to use `http://localhost:8000`
   - The MCP schema will be available at `http://localhost:8000/.well-known/mcp-schema.json`

## 📋 Arguments

| Argument    | Description                      | Default      |
|-------------|----------------------------------|--------------|
| `--project` | Path to Spring Boot project      | (required)   |
| `--output`  | Output directory                 | ./mcp_server |
| `--name`    | Application name                 | SpringAPI    |
| `--debug`   | Enable debug logging             | False        |

## 💻 Example

```bash
python spring_mcp_bridge.py --project ~/projects/my-spring-api --output ./mcp_server --name MyAPI
```

The tool will:
1. Scan the Spring Boot project for REST controllers
2. Identify model types, parameters, and return types
3. Generate a fully functional MCP server in Python/FastAPI
4. Create a compatible MCP schema that describes all endpoints

## 🔄 How It Works

1. **Scanning**: Analyzes Java source code to extract metadata from REST endpoints
2. **Conversion**: Converts Java types to JSON Schema types for MCP compatibility
3. **Generation**: Creates a FastAPI application that maps MCP calls to Spring REST calls
4. **Forwarding**: Routes requests from MCP client to the Spring Boot application

## 🔍 Spring Boot Features Supported

- REST Controllers (`@RestController`, `@Controller`)
- HTTP Methods (`@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping`)
- Request Parameters (`@RequestParam`)
- Path Variables (`@PathVariable`)
- Request Bodies (`@RequestBody`)
- Java Models and DTOs

## ⚙️ Configuration

The generated MCP server can be configured by editing the `main.py` file:

```python
# The Spring Boot base URL - modify this to match your target API
SPRING_BASE_URL = "http://localhost:8080"
```

## 🧪 Testing

To test the MCP server:

1. Ensure your Spring Boot application is running
2. Start the MCP server
3. Visit `http://localhost:8000/docs` to see the FastAPI documentation
4. Check the MCP schema at `http://localhost:8000/.well-known/mcp-schema.json`
5. Connect with an MCP client like Claude

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 Author

**Bruno Santos**

## 🙏 Acknowledgments

- Inspired by FastAPI-MCP and the growing ecosystem of MCP-compatible tools
- Thanks to the Spring Boot and FastAPI communities
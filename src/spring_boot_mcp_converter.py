#!/usr/bin/env python3
"""
Spring Boot to MCP Converter

Author: Bruno Santos
Version: 1.0.0
Date: April 15, 2025
License: MIT

This tool scans a local Spring Boot application and automatically converts
its REST endpoints into an MCP (Message Conversation Protocol) server.
This allows Spring Boot APIs to be used with AI assistants and other
MCP clients like Claude, Cursor, etc.

Usage:
    python spring_boot_mcp_converter.py --project /path/to/spring-project --output ./mcp_server --name MyAPI

For more information about MCP: https://messageconversationprotocol.org
"""

import os
import re
import json
import logging
import argparse
from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, List, Optional

app = FastAPI()

# Global variable that will be filled with the MCP schema
MCP_SCHEMA = {}

class JavaTypeConverter:
    """Helper class to convert Java types to JSON schema types."""
    
    @staticmethod
    def to_json_schema_type(java_type: str) -> str:
        """Convert Java type to JSON schema type."""
        if java_type in ["int", "Integer", "long", "Long", "short", "Short", "byte", "Byte"]:
            return "integer"
        elif java_type in ["double", "Double", "float", "Float", "BigDecimal"]:
            return "number"
        elif java_type in ["boolean", "Boolean"]:
            return "boolean"
        elif java_type in ["List", "ArrayList", "Set", "HashSet", "Collection"] or "<" in java_type:
            return "array"
        elif java_type in ["Map", "HashMap", "TreeMap"] or java_type.startswith("Map<"):
            return "object"
        else:
            return "string"


class SpringEndpointScanner:
    """Scanner for Spring Boot endpoints and models."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.endpoints = []
        self.models = {}
        self.base_package = self._detect_base_package()
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the scanner."""
        logger = logging.getLogger("spring_mcp_scanner")
        logger.setLevel(logging.INFO)
        
        # Create console handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        
        return logger
    
    def _detect_base_package(self) -> str:
        """Detect the base package of the Spring Boot application."""
        main_class_pattern = re.compile(r'@SpringBootApplication')
        
        for java_file in Path(self.project_path).glob('**/src/main/java/**/*.java'):
            try:
                with open(java_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if main_class_pattern.search(content):
                        # Extract package from the file
                        package_match = re.search(r'package\s+([\w.]+);', content)
                        if package_match:
                            package = package_match.group(1)
                            # Remove the last part if it's the filename's package
                            parts = package.split('.')
                            if len(parts) > 2:
                                return '.'.join(parts[:-1])
                            return package
            except UnicodeDecodeError:
                # Skip files that can't be decoded as UTF-8
                continue
            except FileNotFoundError:
                self.logger.error(f"File not found: {java_file}")
                continue
            except PermissionError:
                self.logger.error(f"Permission denied: {java_file}")
                continue
        
        return ""  # Default if not found
    
    def _extract_request_mapping(self, content: str, class_mapping: str = "") -> List[Dict]:
        """Extract request mappings from a controller class."""
        mappings = []
        
        # Extract class-level mapping
        class_mapping_pattern = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)')
        class_match = class_mapping_pattern.search(content)
        if class_match:
            class_mapping = class_match.group(1)
            if not class_mapping.startswith('/'):
                class_mapping = '/' + class_mapping
        
        # Extract method mappings
        method_mapping_patterns = [
            (r'@GetMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)', 'GET'),
            (r'@PostMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)', 'POST'),
            (r'@PutMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)', 'PUT'),
            (r'@DeleteMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)', 'DELETE'),
            (r'@PatchMapping\s*\(\s*(?:value\s*=)?\s*"([^"]+)"\s*\)', 'PATCH')
        ]
        
        # Extract method descriptions from javadoc comments
        javadoc_pattern = re.compile(r'/\*\*([\s\S]*?)\*/')
        javadoc_descriptions = {}
        
        for javadoc_match in javadoc_pattern.finditer(content):
            javadoc = javadoc_match.group(1)
            description = ""
            
            # Extract the main description from the javadoc
            for line in javadoc.split('\n'):
                line = line.strip().lstrip('*').strip()
                if line and not line.startswith('@'):
                    description += line + " "
            
            # Find the method name that follows this javadoc
            method_pos = javadoc_match.end()
            method_search = content[method_pos:method_pos+200]  # Look at next 200 chars
            method_name_match = re.search(r'(?:public|private|protected)?\s+\w+\s+(\w+)\s*\(', method_search)
            
            if method_name_match and description:
                javadoc_descriptions[method_name_match.group(1)] = description.strip()
        
        for pattern, method in method_mapping_patterns:
            for match in re.finditer(pattern, content):
                path = match.group(1)
                if not path.startswith('/'):
                    path = '/' + path
                
                # Find method name and details
                try:
                    method_content = content[match.end():].split('}')[0]
                    method_name_match = re.search(r'(?:public|private|protected)?\s+\w+\s+(\w+)\s*\(', method_content)
                
                    if method_name_match:
                        method_name = method_name_match.group(1)
                        
                        # Extract method parameters
                        param_section = re.search(r'\(\s*(.*?)\s*\)', method_content)
                        parameters = []
                        response_type = "Object"
                        
                        if param_section:
                            # Extract return type
                            return_match = re.search(r'(?:public|private|protected)?\s+(\w+(?:<.*?>)?)\s+\w+\s*\(', method_content)
                            if return_match:
                                response_type = return_match.group(1)
                            
                            # Extract parameters
                            param_text = param_section.group(1)
                            if param_text.strip():
                                param_list = param_text.split(',')
                                for param in param_list:
                                    param = param.strip()
                                    if param:
                                        param_parts = param.split()
                                        if len(param_parts) >= 2:
                                            param_type = param_parts[-2]
                                            param_name = param_parts[-1]
                                            
                                            # Check for request body
                                            is_body = '@RequestBody' in param
                                            
                                            # Check for path variable
                                            path_var_match = re.search(r'@PathVariable\s*(?:\(\s*(?:name|value)\s*=\s*"([^"]+)"\s*\))?', param)
                                            path_var = path_var_match.group(1) if path_var_match else None
                                            
                                            # Check for request param
                                            req_param_match = re.search(r'@RequestParam\s*(?:\(\s*(?:name|value)\s*=\s*"([^"]+)"\s*(?:,\s*required\s*=\s*(true|false))?\))?', param)
                                            req_param = req_param_match.group(1) if req_param_match else None
                                            req_param_required = True
                                            if req_param_match and req_param_match.group(2) == "false":
                                                req_param_required = False
                                            
                                            parameter = {
                                                "name": param_name.replace(";", ""),
                                                "type": param_type,
                                                "isBody": is_body,
                                            }
                                            
                                            if path_var:
                                                parameter["pathVariable"] = path_var
                                            elif req_param:
                                                parameter["requestParam"] = req_param
                                                parameter["required"] = req_param_required
                                            
                                            parameters.append(parameter)
                        
                        full_path = class_mapping + path if class_mapping else path
                        
                        # Get description from javadoc if available
                        description = javadoc_descriptions.get(method_name, f"{method} endpoint for {full_path}")
                        
                        endpoint = {
                            "path": full_path,
                            "method": method,
                            "methodName": method_name,
                            "parameters": parameters,
                            "responseType": response_type,
                            "description": description
                        }
                        
                        mappings.append(endpoint)
                except Exception as e:
                    # Log the error and continue with the next match
                    logging.error(f"Error processing mapping: {str(e)}")
                    continue
        
        return mappings
    
    def _extract_models(self, java_file: Path) -> Dict:
        """Extract model classes from Java files."""
        try:
            with open(java_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it's a model class (typically has @Entity or @Data annotation)
            model_pattern = re.compile(r'@(\w+)\s*\(')
            models = {}
            for match in model_pattern.finditer(content):
                annotation = match.group(1)
                if annotation in ['Entity', 'Data', 'Serializable']:
                    # Extract class name
                    class_name_match = re.search(r'class\s+(\w+)', content)
                    if class_name_match:
                        class_name = class_name_match.group(1)
                        fields = []
                        
                        # Extract fields
                        field_pattern = re.compile(r'private\s+(\w+\s+\w+)\s*;')
                        for field_match in field_pattern.finditer(content):
                            field = field_match.group(1).strip()
                            field_parts = field.split()
                            if len(field_parts) == 2:
                                field_type, field_name = field_parts
                                fields.append({
                                    'name': field_name,
                                    'type': JavaTypeConverter.to_json_schema_type(field_type)
                                })
                        models[class_name] = fields
            return models
        except Exception as e:
            self.logger.error(f"Error extracting models from {java_file}: {str(e)}")
            return {}
    
    def scan_project(self):
        """Scan the project directory and extract endpoints and models."""
        if not self.project_path.exists():
            raise FileNotFoundError(f"Project path '{self.project_path}' does not exist.")
        
        # First find all Java files
        java_files = list(self.project_path.glob('**/src/main/java/**/*.java'))
        
        if not java_files:
            self.logger.warning("No Java files found in the project path. Check if the path is correct.")
            return
        
        for java_file in java_files:
            self.logger.info(f"Scanning file: {java_file}")
            
            try:
                # Extract models from this file
                models = self._extract_models(java_file)
                self.models.update(models)
                
                with open(java_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract endpoints only if contains controller annotations
                if re.search(r'@(RestController|Controller)', content):
                    endpoints = self._extract_request_mapping(content)
                    self.endpoints.extend(endpoints)
            except Exception as e:
                self.logger.error(f"Error processing file {java_file}: {str(e)}")
                continue
        
        self.logger.info(f"Found {len(self.endpoints)} endpoints.")
        self.logger.info(f"Found {len(self.models)} models.")


class MCPServer:
    """Generate MCP server from extracted endpoints and models."""
    
    def __init__(self, name: str, endpoints: List[Dict], models: Dict):
        self.name = name
        self.endpoints = endpoints
        self.models = models
    
    def generate_schema(self) -> Dict:
        """Generate MCP schema."""
        schema = {
            "name": self.name,
            "endpoints": self.endpoints,
            "models": self.models
        }
        return schema
    
    def generate_server(self, output_dir: Path):
        """Generate the MCP server code."""
        # Create the output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create the schema file
        schema = self.generate_schema()
        schema_path = output_dir / "mcp_schema.json"
        
        with open(schema_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2)
        
        # Create main.py with FastAPI server
        main_py_content = """#!/usr/bin/env python3
'''
MCP Server for {name}
Generated by Spring Boot to MCP Converter
'''

import json
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

app = FastAPI(title="{name} MCP Server")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the MCP schema
with open("mcp_schema.json", "r") as f:
    MCP_SCHEMA = json.load(f)

# Define the base URL for the Spring Boot application
# You should set this to the actual URL of your Spring Boot app
SPRING_BOOT_BASE_URL = os.getenv("SPRING_BOOT_URL", "http://localhost:8080")

@app.get("/.well-known/mcp-schema.json")
async def get_mcp_schema():
    ""Return the MCP schema for this server.""
    return MCP_SCHEMA

# Generate dynamic endpoints based on the schema
for endpoint in MCP_SCHEMA["endpoints"]:
    path = endpoint["path"]
    method = endpoint["method"].lower()
    method_name = endpoint["methodName"]
    
    # Create a function to handle the request
    async def create_handler(endpoint_info):
        async def handler(request: Request):
            # Extract path params, query params, and request body
            path_params = {{}}
            query_params = {{}}
            
            for param in endpoint_info["parameters"]:
                if "pathVariable" in param:
                    # Extract path variable from request path
                    path_var = param["pathVariable"]
                    path_params[path_var] = request.path_params.get(path_var)
                elif "requestParam" in param:
                    # Extract query parameters
                    req_param = param["requestParam"]
                    query_params[req_param] = request.query_params.get(req_param)
            
            # Prepare the URL for the Spring Boot application
            target_url = f"{{SPRING_BOOT_BASE_URL}}{{endpoint_info['path']}}"
            
            # Forward the request to the Spring Boot application
            async with httpx.AsyncClient() as client:
                if method == "get":
                    response = await client.get(target_url, params=query_params)
                elif method == "post":
                    body = await request.json() if request.headers.get("content-type") == "application/json" else None
                    response = await client.post(target_url, params=query_params, json=body)
                elif method == "put":
                    body = await request.json() if request.headers.get("content-type") == "application/json" else None
                    response = await client.put(target_url, params=query_params, json=body)
                elif method == "delete":
                    response = await client.delete(target_url, params=query_params)
                elif method == "patch":
                    body = await request.json() if request.headers.get("content-type") == "application/json" else None
                    response = await client.patch(target_url, params=query_params, json=body)
                else:
                    return {{"error": f"Unsupported method: {{method}}"}}
            
            # Return the response from the Spring Boot application
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
        
        return handler
    
    # Register the endpoint with FastAPI
    handler = create_handler(endpoint)
    
    # Register the endpoint with FastAPI using the appropriate HTTP method
    if method == "get":
        app.get(path)(handler)
    elif method == "post":
        app.post(path)(handler)
    elif method == "put":
        app.put(path)(handler)
    elif method == "delete":
        app.delete(path)(handler)
    elif method == "patch":
        app.patch(path)(handler)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
        main_py = output_dir / "main.py"
        with open(main_py, 'w', encoding='utf-8') as f:
            f.write(main_py_content.format(name=self.name))
        
        # Create requirements.txt
        requirements_txt = output_dir / "requirements.txt"
        with open(requirements_txt, 'w', encoding='utf-8') as f:
            f.write("""fastapi>=0.95.0
uvicorn>=0.21.1
httpx>=0.24.0
pydantic>=1.10.7
""")
        
        # Create README.md
        readme_content = """# {name} MCP Server

This is an automatically generated MCP (Message Conversation Protocol) server for the Spring Boot application.

## Getting Started

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set the environment variable to your Spring Boot application URL:
   ```
   export SPRING_BOOT_URL="http://localhost:8080"
   ```

3. Start the MCP server:
   ```
   python main.py
   ```

4. The server will be available at http://localhost:8000

5. The MCP schema is available at http://localhost:8000/.well-known/mcp-schema.json

## Endpoints

Total endpoints: {endpoint_count}

"""
        
        readme_md = output_dir / "README.md"
        with open(readme_md, 'w', encoding='utf-8') as f:
            f.write(readme_content.format(name=self.name, endpoint_count=len(self.endpoints)))
            
            # Add endpoint details to README
            for endpoint in self.endpoints:
                f.write(f"- **{endpoint['method']}** `{endpoint['path']}`: {endpoint['description']}\n")


@app.get("/.well-known/mcp-schema.json")
async def get_mcp_schema():
    """Return the MCP schema for this server."""
    return MCP_SCHEMA


# Main function
def main():
    parser = argparse.ArgumentParser(description="Spring Boot to MCP Converter")
    parser.add_argument('--project', required=True, help="Path to the Spring Boot project")
    parser.add_argument('--output', required=True, help="Output directory for MCP server")
    parser.add_argument('--name', default="MyAPI", help="Name of the generated MCP server")
    args = parser.parse_args()
    
    print(f"Starting Spring Boot to MCP conversion...")
    print(f"Project path: {args.project}")
    print(f"Output directory: {args.output}")
    print(f"API name: {args.name}")
    
    try:
        # Scan the Spring Boot project for endpoints and models
        scanner = SpringEndpointScanner(args.project)
        scanner.scan_project()
        
        # Create MCP server schema
        mcp_server = MCPServer(args.name, scanner.endpoints, scanner.models)
        
        # Generate the MCP server
        output_path = Path(args.output)
        mcp_server.generate_server(output_path)
        
        print(f"MCP server generated successfully at: {output_path}")
        print(f"To start the server:")
        print(f"  1. cd {args.output}")
        print(f"  2. pip install -r requirements.txt")
        print(f"  3. python main.py")
        print(f"The server will be available at http://localhost:8000")
        print(f"The MCP schema will be available at http://localhost:8000/.well-known/mcp-schema.json")
        
        # Update the global MCP_SCHEMA
        global MCP_SCHEMA
        MCP_SCHEMA = mcp_server.generate_schema()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
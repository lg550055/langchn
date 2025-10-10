import asyncio
import json
import sqlite3
from aiohttp import web, ClientSession

# Initialize SQLite database with sample data
def init_db():
    conn = sqlite3.connect("example.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    # Insert sample data
    cursor.executemany(
        "INSERT OR IGNORE INTO users (id, name, email) VALUES (?, ?, ?)",
        [(1, "Alice", "alice@example.com"), (2, "Bob", "bob@example.com")]
    )
    conn.commit()
    conn.close()

# MCP Server: Exposes database query capability
async def mcp_server(request):
    try:
        # Parse JSON-RPC 2.0 request
        data = await request.json()
        if data.get("jsonrpc") != "2.0" or not data.get("method"):
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": data.get("id")
            })

        method = data["method"]
        params = data.get("params", {})

        # Handle MCP capability: read_file
        if method == "read_file":
            file_path = params.get("file_path")
            if not file_path:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Missing file_path parameter"},
                    "id": data["id"]
                })

            try:
                with open(file_path, "r") as f:
                    content = f.read()
                return web.json_response({
                    "jsonrpc": "2.0",
                    "result": {"content": content},
                    "id": data["id"]
                })
            except FileNotFoundError:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": f"File {file_path} not found"},
                    "id": data["id"]
                })

        # Handle MCP capability: query_db
        if method == "query_db":
            query = params.get("query")
            query_params = params.get("query_params", [])
            if not query:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Missing query parameter"},
                    "id": data["id"]
                })

            try:
                conn = sqlite3.connect("example.db")
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, query_params)
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
                conn.close()
                return web.json_response({
                    "jsonrpc": "2.0",
                    "result": {"rows": results},
                    "id": data["id"]
                })
            except sqlite3.Error as e:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": f"Database error: {str(e)}"},
                    "id": data["id"]
                })

        return web.json_response({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method {method} not found"},
            "id": data["id"]
        })

    except json.JSONDecodeError:
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        })

# MCP Client: Sends requests
async def mcp_client(method, params):
    async with ClientSession() as session:
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        async with session.post("http://localhost:8080/mcp", json=request) as resp:
            response = await resp.json()
            return response

async def start_server():
    app = web.Application()
    app.router.add_post("/mcp", mcp_server)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()
    print("MCP Server running on http://localhost:8080/mcp")

async def main():
    # Start server in the background
    server_task = asyncio.create_task(start_server())
    await asyncio.sleep(1)  # Allow server to start

    # Simulate AI request: Query users by name
    method = "query_db"
    query = "SELECT id, name, email FROM users WHERE name = ?"
    query_params = ["Alice"]
    params = {"query": query, "query_params": query_params}
    response = await mcp_client(method, params)
    print("Client received:", json.dumps(response, indent=2))

    # Simulate another AI request: Get all users
    query = "SELECT id, name, email FROM users"
    params = {"query": query, "query_params": []}
    response = await mcp_client(method, params)
    print("Client received:", json.dumps(response, indent=2))

    # Simulate AI request to read a file
    method = "read_file"
    params = {"file_path": "example.txt"}
    response = await mcp_client(method, params)
    print("Client received:", json.dumps(response, indent=2))

    # Cleanup (in practice, server runs indefinitely)
    server_task.cancel()

if __name__ == "__main__":
    # init_db()  # run once (or if the DB is deleted or need to seed changes)
    asyncio.run(main())

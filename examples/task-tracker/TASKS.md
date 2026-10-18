# Build tasks

1. Create basic server with health check
   Implement create_server(host, port) returning ThreadingHTTPServer. Add GET /health returning JSON {"status":"ok"}. Include main block parsing --host and --port arguments.
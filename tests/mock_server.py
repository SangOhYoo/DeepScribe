import json
import re
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

class MockLlamaServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress server access log to keep clean console
        return

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            messages = payload.get("messages", [])
            system_content = ""
            user_content = ""
            
            for msg in messages:
                role = msg.get("role")
                if role == "system":
                    system_content = msg.get("content", "")
                elif role == "user":
                    user_content = msg.get("content", "")

            # Check if this is Step 1 (vision/manga translation) or Step 2 (diffusion tag extraction)
            is_step1 = True
            if "diffusion" in system_content.lower():
                is_step1 = False

            # Determine cut number
            cut_number = 1
            if isinstance(user_content, list):
                # OpenAI format message
                text_part = next((item.get("text", "") for item in user_content if item.get("type") == "text"), "")
                match = re.search(r"Cut Number:\s*(\d+)", text_part)
                if match:
                    cut_number = int(match.group(1))
            elif isinstance(user_content, str):
                match = re.search(r"Cut Number:\s*(\d+)", user_content)
                if match:
                    cut_number = int(match.group(1))

            if is_step1:
                # Mock Step 1 response wrapped in markdown block
                response_text = f"""```json
{{
  "scene_description": "A close-up shot of a determined character looking forward, Cut {cut_number}.",
  "camera_angle": "close-up",
  "manga_effects": "speed lines",
  "novel_paragraph": "주인공은 비장한 각오를 다지며 정면을 응시했다. (컷 {cut_number} 소설 텍스트)"
}}
```"""
            else:
                # Mock Step 2 response with messy lead/trail text and markdown
                response_text = f"""Here is the extracted positive and negative prompts:
```json
{{
  "positive_prompt": "masterpiece, warrior, determined eyes, speed lines, close-up, 8k resolution, manga style, cut {cut_number}",
  "negative_prompt": "low quality, blurry, worst quality, text, logo"
}}
```
Let me know if you need anything else!"""

            response_payload = {
                "choices": [
                    {
                        "message": {
                            "content": response_text
                        }
                    }
                ]
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

def run(port=8081):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, MockLlamaServer)
    print(f"Starting mock llama.cpp server on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock server...")
        sys.exit(0)

if __name__ == '__main__':
    port = 8081
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run(port)

import subprocess
import time
from pyngrok import ngrok

# Authenticate ngrok with the token (this should be done once on the server)
ngrok.set_auth_token("2zj0rfWuBnz61jWWBxpWhrJATs5_75UCKcjC8ztBLMYJp5tGX")

# Define the command to run vLLM with specified parameters
cmd = [
    "vllm", "serve", "Qwen/Qwen2.5-VL-32B-Instruct",
    "--dtype", "float16",
    "--max-num-seqs", "16",
    "--gpu-memory-utilization", "0.9",
    "--disable-log-requests"
]

# Start the vLLM server process on the remote machine
process = subprocess.Popen(cmd)

# Give the server some time to start
time.sleep(10)

# Now start ngrok to expose the server (exposing port 5000)
public_url = ngrok.connect(5000)

# Print the public URL to access the server
print(f"LLM server is running and exposed via ngrok at: {public_url}")

# Optional: Wait for the process to keep running
try:
    process.wait()
except KeyboardInterrupt:
    print("Server stopped by user.")
    process.terminate()
    ngrok.disconnect(public_url)
    print("ngrok disconnected and server terminated.")

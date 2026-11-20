# hrc-platform
Hospital Resource Coordination platform, CS7CS3 Group 8 project

## Python agents and AI services (thin slice skeleton)

Hello-world skeletons with no real logic yet. Each service gets `hello` and replies `hit <service>`,
which shows the services can reach each other. Plain Python (no libraries), one `app.py` and
`Dockerfile` per service.

| Service | Port | What it does now |
|---|---|---|
| allocation-coordinator | 8101 | Calls `rag-service` and `explanation-service`, returns their replies |
| patient-transfer-agent | 8102 | Calls `allocation-coordinator` |
| emergency-coordination-agent | 8103 | Replies only |
| ambulance-coordination-agent | 8104 | Calls `allocation-coordinator` |
| rag-service | 8105 | Returns a placeholder policy passage |
| explanation-service | 8106 | Sends one prompt to vLLM (the LLM) and returns the answer |

Each agent follows a perceive -> decide -> act structure; real rules go in `decide()` later.

### Run it

Needs only Docker. Ports 8101-8106 must be free.

```bash
docker compose -f docker-compose.agents.yml up -d --build
./send-hello.sh        # sends "hello" to every service and prints the replies
docker compose -f docker-compose.agents.yml down
```

`send-hello.sh` is a bash script. On Windows use Git Bash or WSL, or send a request directly:
`curl -X POST -d hello http://localhost:8101`

### The LLM (optional)

`explanation-service` talks to vLLM running on the host machine, outside Docker, on port 8010.
Without it everything still runs and the reply says `LLM not reachable`.

- **Apple Silicon Mac:** install vllm-metal, then start a small model:
  ```bash
  brew tap vllm-project/vllm-metal https://github.com/vllm-project/vllm-metal
  brew install vllm-project/vllm-metal/vllm-metal
  vllm serve mlx-community/Qwen2.5-0.5B-Instruct-4bit --host 0.0.0.0 --port 8010 --api-key local
  ```
- **Linux or Windows with an NVIDIA GPU:** run standard vLLM with any small model on port 8010.
- To use a different server or model, set `VLLM_URL` and `VLLM_MODEL` on `explanation-service`.

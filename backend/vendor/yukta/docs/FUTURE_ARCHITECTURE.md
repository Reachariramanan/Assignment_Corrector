# Future Architecture: Centralized Production Deployment

This document outlines the roadmap and architectural blueprint for migrating the `yukta-ecosystem` from local execution scripts into a robust, enterprise-grade, centralized production system. 

The core philosophy of this upgrade is to shift to a **Client-Server Architecture** where the heavy `yukta` engine is centralized, and clients (CLI, IDEs) act purely as interfaces.

---

## 1. The Centralized API Architecture (Backend)

We will wrap the existing static `wrapper` within a **FastAPI REST & WebSocket Server**.

### Dockerization Strategy
The backend will be packaged as a single, immutable Docker container.
*   **The Engine**: The Docker image contains the `yukta-package`, the `wrapper`, and the FastAPI application.
*   **The Data (Volume Mounts)**: The ecosystem is injected into the container at runtime via volume mounts. This ensures the "engine" never changes, but the skills, tools, and agents can be updated dynamically without rebuilding the image.
    *   `VOLUME /app/global-ecosystem`: The core, company-wide ecosystem.

---

## 2. User-Based Segregation (Multi-Tenant Ecosystems)

To support multiple developers hitting the same central API, the system implements a **Layered Ecosystem Strategy**. 

### Storage & Runtime Merging
1.  **Global Storage**: The mounted `/app/global-ecosystem` contains standard tools (git, terminal) and standard agents (Architect, Reviewer).
2.  **User Storage**: A separate volume or database (e.g., `/app/users/{user_id}/ecosystem`) holds personal overrides, custom personal tools, and private agents.
3.  **Runtime Merge**: When `user_A` authenticates and requests an agent run, the API dynamically merges the Global Ecosystem with `user_A`'s Local Ecosystem in memory. The `yukta` engine executes using this customized, merged state.

### Security & Accountability
*   **Authentication**: All requests require a JWT token tied to a specific `user_id`.
*   **Logging**: All agent actions, tool usages, and LLM token costs are tagged with the `user_id` for accountability.
*   **Sandboxing**: Personal tools uploaded by users will be executed in a restricted sandbox (e.g., an isolated sub-container or gVisor) to prevent malicious Python code from accessing the host or other users' local ecosystems.

---

## 3. The Thin Client CLI

We will build a Command Line Interface that does **not** rely on a complex local Python environment or PyPI publication (`pip install`).

*   **The Design**: The CLI is a "Thin Client" (written in Python but compiled using `PyInstaller`, or written in Go/Rust). It contains no LLM logic.
*   **The Execution**: It takes user input, packages it into a JSON payload, and sends an HTTP/WebSocket request to the FastAPI backend.
*   **Distribution**: It is distributed as a single standalone executable (e.g., `yukta-cli.exe` or `yukta-cli-linux`). Users simply download the binary and run `yukta login` followed by `yukta run "task"`.

---

## 4. Planned API Endpoints Blueprint

To fully support the CLI, IDE extensions, and automated CI/CD pipelines, the backend will expose the following comprehensive API.

### A. Authentication
*   `POST /v1/auth/login`: Authenticates the user and returns a short-lived JWT.
*   `POST /v1/auth/refresh`: Refreshes the JWT session.

### B. Execution & Tasks (The Core)
*   `POST /v1/tasks/run`: Submits a task to a specific agent or team. Returns a `task_id`.
*   `GET /v1/tasks/{task_id}/status`: Polls for task status (Queued, Running, Completed, Failed).
*   `WS /v1/tasks/{task_id}/stream`: A WebSocket endpoint. Connects to a running task and streams the agent's internal thoughts, tool execution logs, and final outputs back to the client in real-time.

### C. Ecosystem Management (CRUD)
Endpoints to manage both Global (if admin) and Personal ecosystems.

**Agents**
*   `GET /v1/ecosystem/agents`: List available agents (query params: `scope=global|personal`).
*   `POST /v1/ecosystem/agents`: Upload a new personal agent YAML.
*   `PUT /v1/ecosystem/agents/{id}`: Modify an existing personal agent.

**Skills**
*   `GET /v1/ecosystem/skills`: List all accessible skills.
*   `GET /v1/ecosystem/skills/{id}`: Retrieve the Markdown content of a specific skill.
*   `POST /v1/ecosystem/skills`: Upload a new skill workflow.

**Tools**
*   `GET /v1/ecosystem/tools`: List tools.
*   `POST /v1/ecosystem/tools`: Upload a new tool. (Requires descriptor YAML and implementation Python script).
*   `DELETE /v1/ecosystem/tools/{id}`: Remove a personal tool.

**Teams**
*   `GET /v1/ecosystem/teams`: List team structures.
*   `POST /v1/ecosystem/teams`: Create a new personal team layout.
*   `POST /v1/ecosystem/teams/{id}/members`: Dynamically add/remove agents from a team.

### D. Memory & History
*   `GET /v1/chat/sessions`: List past chat sessions and task histories for the authenticated user.
*   `GET /v1/chat/sessions/{session_id}`: Retrieve the full conversation log and tool outputs of a specific session.
*   `DELETE /v1/chat/sessions/{session_id}`: Clear a session from the user's history.


---

## NOTE:
The endpoints are very shallow or not just the required but just suggestions - plan accordingly when building the REST API.

---


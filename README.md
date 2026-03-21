# Energy Crisis Management AI

A multi-agent AI simulation that models energy crisis management using LLM-powered governor agents. Each agent independently manages an energy zone — responding to dynamic crises, trading energy across a network, and making autonomous decisions under budget constraints. An adversarial Crisis Agent introduces disruptions to stress-test the governors' decision-making.

Built with **LangGraph**, **LangChain**, and **OpenAI**.

---

## Architecture

The system is organized into three layers:

**Simulation Engine** (`simulation/`) — The physics engine and source of truth. Handles energy production, trade flows, demand consumption, seasonal effects, and crisis mechanics across a deterministic tick-based game loop.

**Governor Agents** (`agents/`) — One LangGraph pipeline per zone. Each tick, a zone's agent observes its state, drafts a situation report, plans actions, runs them through a risk assessment gate, and executes approved actions via the engine. Agents operate independently with no direct coordination — cooperation emerges through trade offers and diplomacy.

**Crisis Agent** (`crisis_agent.py`) — An adversarial LangGraph agent that analyzes the board and injects crises (supply disruptions, cyberattacks, droughts, political embargoes, etc.) to challenge the governors. Its budget scales with game progression.

```
run_ai_demo.py          # Entry point — orchestrates the full simulation
crisis_agent.py         # Adversarial crisis injection agent

simulation/
├── models.py           # Data classes: Zone, EnergySource, TradeRoute, CrisisEvent, etc.
└── engine.py           # Tick loop, action execution, physics calculations

agents/
├── state.py            # Shared AgentState TypedDict flowing through the graph
├── nodes.py            # 7 agent node functions + routing logic
├── graph.py            # LangGraph StateGraph construction
└── memory.py           # MongoDB-backed zone memory persistence (planned)
```

### Agent Pipeline

Each governor agent runs through this graph each tick:

1. **Supervisor Gate** — Deterministic entry point. Routes based on stability, active crises, and pending messages.
2. **Situation Awareness** — LLM analyzes zone telemetry and identifies threats.
3. **Planning** — LLM generates a JSON list of proposed actions with cost estimates.
4. **Risk Assessment** — LLM reviews costs against budget; approves, rejects, or requests revision (max 2 retries).
5. **Execution** — Applies approved actions through the engine's action methods.
6. **Report** — LLM generates a human-readable tick narrative.
7. **Communication** — LLM handles incoming trade offers, aid requests, and diplomacy.

---

## Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- MongoDB (optional — for agent memory persistence)

---

## Installation

Clone the repository and install dependencies:

```bash
git clone <repo-url>
cd energy-crisis
pip install -r requirements.txt
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

---

## Usage

### Run the AI simulation

```bash
python run_ai_demo.py
```

### Command-line options

| Flag | Description | Default |
|------|-------------|---------|
| `--ticks N` | Number of simulation ticks | `25` |
| `--zones alpha,beta` | Comma-separated zones to enable AI for | all zones |
| `--model NAME` | OpenAI model to use | `gpt-4o` |
| `--no-crises` | Disable the adversarial crisis agent | crises enabled |
| `--seed N` | RNG seed for reproducibility | `42` |

**Examples:**

```bash
# Run 50 ticks with only Alpha and Beta zones
python run_ai_demo.py --ticks 50 --zones alpha,beta

# Run without crises for baseline testing
python run_ai_demo.py --no-crises

# Use a different model
python run_ai_demo.py --model gpt-4o-mini
```

### Run the hardcoded demo (Phase 1)

A non-AI demo with hardcoded zone actions, useful for testing the engine in isolation:

```bash
python run_demo.py
```

---

## Zone Setup

The simulation initializes three zones by default:

| Zone | Region | Energy Sources | Notes |
|------|--------|---------------|-------|
| Alpha | Temperate | Solar, Wind | Balanced generation |
| Beta | Coastal | Hydro | Seasonal variability |
| Gamma | Industrial | Fossil | High demand pressure |

---

## Connecting to MongoDB

MongoDB provides persistent memory for governor agents, allowing them to reference past decisions and learn from previous ticks. The simulation works without MongoDB (agents simply operate without historical context), but enabling it improves long-term decision quality.

### 1. Install MongoDB

**macOS (Homebrew):**

```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y gnupg curl
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod
```

**Docker:**

```bash
docker run -d --name energy-crisis-mongo -p 27017:27017 mongo:7
```

**MongoDB Atlas (cloud):**

Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas) and obtain your connection string.

### 2. Configure the connection

Set the MongoDB connection URI as an environment variable:

```bash
# Local instance (default)
export MONGODB_URI="mongodb://localhost:27017"

# Atlas or remote instance
export MONGODB_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
```

The application uses a database called `energy_crisis` with a collection per zone (e.g., `zone_alpha_memory`). These are created automatically on first write.

### 3. Verify the connection

```bash
# Check that MongoDB is running locally
mongosh --eval "db.runCommand({ ping: 1 })"
```

From Python:

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["energy_crisis"]
print(db.list_collection_names())
```

### 4. Memory schema

Each tick record stored in MongoDB follows this structure:

```json
{
  "zone_id": "alpha",
  "tick": 12,
  "timestamp": "2026-03-21T14:30:00Z",
  "stability": "WARNING",
  "storage_pct": 0.45,
  "actions_taken": [
    {"action": "repair_source", "target": "solar_farm_1", "cost": 50}
  ],
  "crises_active": ["DROUGHT"],
  "situation_summary": "...",
  "tick_report": "..."
}
```

Agents retrieve the last N records (default 5) at the start of each tick to build historical context for their decision-making.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `MONGODB_URI` | No | MongoDB connection string (defaults to `mongodb://localhost:27017`) |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `langgraph` >= 0.2.0 | Multi-agent graph orchestration |
| `langchain-openai` >= 0.3.0 | OpenAI LLM integration |
| `langchain-core` >= 0.3.0 | Core LangChain abstractions |
| `pymongo` >= 4.6.0 | MongoDB driver for agent memory |

---

## License

This project is provided as-is for research and educational purposes.

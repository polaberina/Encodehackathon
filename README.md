# R.E.A.C.T
**Resilient Energy Autonomous Crisis Taskforce**

A multi-agent energy grid simulation featuring LLM-powered autonomous agents that manage energy zones, respond to crises, and trade resources in a tick-based game environment.

## Overview

R.E.A.C.T is an advanced energy grid simulation that models real-world energy management challenges through intelligent agent-based gameplay. The system simulates energy production, distribution, and crisis response across multiple interconnected zones, each governed by an AI agent with strategic decision-making capabilities.

### Key Features

- **🤖 LLM-Powered Governor Agents**: Each energy zone is managed by an autonomous AI agent that makes strategic decisions about energy production, trading, and crisis response
- **⚡ Dynamic Energy Trading**: Zones can establish trade routes to buy and sell energy, with health mechanics that degrade under stress
- **🔥 Crisis Management**: An adversarial Crisis Agent introduces realistic challenges including blackouts, infrastructure failures, extreme weather, and cyberattacks
- **🌍 Diverse Energy Sources**: 8 different generation types including renewables (solar, wind, hydro), conventional (coal, natural gas), and alternatives (nuclear, biomass)
- **📊 Tick-Based Simulation**: Game loop with 9-step execution order covering demand calculations, generation, trading, crisis resolution, and state updates
- **🎯 Strategic Gameplay**: Win/loss conditions based on zone survival, economic performance, and crisis resilience

## Energy Sources

The simulation models 8 distinct energy generation types, each with unique characteristics:

| Source | Output | Key Characteristics |
|--------|--------|---------------------|
| Solar | 40 MW | Day/night cycle, weather-dependent |
| Wind | 35 MW | Variable output, high resilience |
| Hydro | 60 MW | Steady output, water dependency |
| Natural Gas | 80 MW | Reliable, moderate emissions |
| Coal | 100 MW | High output, stockpile depletion |
| Nuclear | 120 MW | Stable baseline, long cooldowns |
| Biomass | 45 MW | Renewable, fuel-dependent |
| Geothermal | 50 MW | Consistent, location-specific |

## Zone Actions

Governor agents can execute strategic actions each tick:

- **Build Generator**: Construct new energy production facilities
- **Upgrade Storage**: Increase energy storage capacity
- **Establish Trade Route**: Create energy trading connections
- **Repair Infrastructure**: Restore damaged systems
- **Stockpile Resources**: Build reserves for fuel-dependent sources
- **Research Tech**: Unlock efficiency improvements
- **Emergency Response**: Mitigate active crisis events

Each action has energy costs, cooldown periods, and strategic trade-offs.

## Crisis Events

The Crisis Agent can trigger 10 distinct crisis types:

1. **Blackout**: Sudden generation loss
2. **Infrastructure Failure**: Transmission damage
3. **Fuel Shortage**: Supply chain disruption
4. **Extreme Weather**: Multi-source degradation
5. **Demand Surge**: Unexpected load spike
6. **Cyberattack**: System compromise
7. **Natural Disaster**: Catastrophic multi-zone impact
8. **Equipment Failure**: Generator outages
9. **Grid Instability**: Cascading failures
10. **Political Crisis**: Trade restrictions

Crises have severity levels and can trigger cascading effects across connected zones.

## Installation & Running

### Prerequisites

- Python 3.9+
- Node.js 18+ and npm (or pnpm)
- An OpenAI API key

### 1. Clone & configure

```bash
git clone https://github.com/yourusername/react-energy-sim.git
cd react-energy-sim

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env
```

### 2. Backend (FastAPI)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the API server (runs on http://localhost:8000)
uvicorn api:app --reload --port 8000
```

### 3. Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install   # or: pnpm install

# Start the dev server (runs on http://localhost:3000)
npm run dev
```

### Run both at once

A convenience script is included at the project root:

```bash
chmod +x start.sh
./start.sh
```

This starts the backend on `http://localhost:8000` and the frontend on `http://localhost:3000` simultaneously.

### API docs

Once the backend is running, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Configuration

The simulation supports customizable zone setups. Four default configurations are provided:

- **Alpha Zone**: Renewable-heavy (solar/wind), low storage, aggressive trading
- **Beta Zone**: Balanced mix, moderate storage, defensive strategy
- **Gamma Zone**: Coal/gas dependent, high storage, economic focus
- **Delta Zone**: Nuclear baseline, advanced tech, resilience-focused

### Governor Agent Behavior

Each Governor Agent receives:
- Zone state (energy balance, storage, generation capacity)
- Market conditions (trade prices, route health)
- Crisis status (active events, threat level)
- Historical performance data

Agents make decisions by:
1. Analyzing margin-based error thresholds
2. Evaluating strategic priorities
3. Selecting optimal actions within energy budget
4. Adapting to emerging crisis patterns

## Architecture

### Game Loop (9-Step Tick Execution)

1. **Demand Calculation**: Compute zone energy needs
2. **Generation Phase**: Produce energy from active sources
3. **Storage Management**: Charge/discharge batteries
4. **Trade Execution**: Process energy transfers
5. **Crisis Events**: Trigger and resolve crises
6. **Action Processing**: Execute Governor decisions
7. **State Updates**: Recalculate zone conditions
8. **Margin Detection**: Identify threshold violations
9. **Logging & Scoring**: Record performance metrics

### Data Selection Framework

The system uses margin-based thresholds to identify critical events:
- **Energy Balance**: ±10% variance
- **Storage Levels**: <20% or >95%
- **Generation Efficiency**: <85% rated capacity
- **Trade Route Health**: <70% operational
- **Crisis Severity**: All events logged

## Scoring & Win Conditions

Zones are evaluated on:
- **Survival**: Maintain positive energy balance
- **Economic Performance**: Trade profitability
- **Resilience**: Crisis recovery speed
- **Efficiency**: Resource utilization

Victory conditions:
- ✅ All zones survive 100+ ticks
- ✅ No zone falls below 20% storage
- ✅ Successful crisis mitigation rate >80%

## Development Roadmap

### Phase 1: MVP Environment ✅
- Core simulation engine
- Basic Governor Agents
- 10 crisis types
- 4 default zone configurations

### Phase 2: Advanced Features (Planned)
- Machine learning for agent optimization
- Real-time visualization dashboard
- Multi-player competitive mode
- Historical data replay

### Phase 3: Research Integration (Future)
- ENTSO-E data integration
- Academic collaboration tools
- Policy simulation scenarios

## Contributing

Contributions are welcome! Areas of interest:
- Governor Agent strategy improvements
- New crisis event types
- Visualization enhancements
- Performance optimization
- Documentation

## License

[Add your license here]

## Acknowledgments

Research frameworks consulted:
- ASSUME (Agent-based Simulation of Markets for Energy)
- PyPSA-Eur (European power system analysis)
- Power TAC (Trading Agent Competition)

Data sources:
- ENTSO-E Transparency Platform
- Open Power System Data (OPSD)
- Renewables.ninja

## Contact

[Add contact information]

---

*Built with autonomous agents. Powered by crisis resilience.*

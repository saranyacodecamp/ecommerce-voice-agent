A voice-powered ecommerce customer support agent built with **LiveKit Agents**, **OpenAI GPT-4.1 Mini**, **Deepgram STT**, 
**Cartesia TTS**, and a **FastMCP ecommerce backend** with **RAG-based policy search**.

---

## 📌 Features

- 🎙️ **Voice Interface** — speak naturally to manage your orders
- 🤖 **AI-Powered Agent** — GPT-4.1 Mini handles multi-turn conversations
- 🛍️ **Order Management** — check status, cancel, place, and list orders
- 📄 **Policy Search (RAG)** — answers policy questions from store documents using ChromaDB
- 🔀 **LLM Routing** — automatically routes order vs policy questions to the right tool
- 🌐 **React Frontend** — clean UI with audio visualizer and call controls

---

## 🏗️ Architecture

```
Browser (React Frontend)
        ↓
LiveKit Cloud (audio routing)
        ↓
agent.py (LiveKit Voice Agent)
    ├── STT: Deepgram Nova-3
    ├── LLM: OpenAI GPT-4.1 Mini
    └── TTS: Cartesia Sonic-2
        ↓
mcp_server.py (FastMCP Ecommerce Server)
    ├── Order Tools (SQLite)
    └── Policy Search (ChromaDB + SentenceTransformers)
```

---

## 📁 Project Structure

```
ecommerce-voice-agent/
├── agent.py                  # LiveKit voice agent
├── mcp_server.py             # FastMCP ecommerce server
├── ecommerce_data.db         # SQLite database (auto created)
├── chroma_db/                # ChromaDB vector store (auto created)
├── policies/
│   └── policies.txt          # Store policy documents
├── .env                      # Backend environment variables
└── frontend/                 # React frontend (agent-starter-react)
    ├── app-config.ts         # Frontend configuration
    └── .env.local            # Frontend environment variables
```

---

## ⚙️ Prerequisites

- Python 3.10+
- Node.js 18+
- [LiveKit Cloud](https://cloud.livekit.io) account
- OpenAI API key
- Deepgram API key
- Cartesia API key

---

## 🚀 Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/ecommerce-voice-agent.git
cd ecommerce-voice-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Frontend dependencies

```bash
cd frontend
npm install
```

### 4. Configure environment variables

**Backend — `voice-agent/.env`**
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
CARTESIA_API_KEY=your_cartesia_api_key
```

**Frontend — `frontend/.env.local`**
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
SANDBOX_ID=your_sandbox_id
AGENT_NAME=ecommerce-agent
NEXT_PUBLIC_APP_CONFIG_ENDPOINT=
```

> 💡 Get `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` and `SANDBOX_ID` from [LiveKit Cloud Dashboard](https://cloud.livekit.io)

---

## ▶️ Running the Project

Open **3 separate terminals**:

**Terminal 1 — MCP Server**
```bash
python mcp_server.py
```

**Terminal 2 — Voice Agent**
```bash
python agent.py dev
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser, click **Start Call**, and speak to your agent.

---

## 🛠️ Available Tools

### Order Tools
| Tool | Description |
|---|---|
| `customer_exists` | Identify customer by phone number |
| `list_all_orders` | List all orders of the customer |
| `check_order_status` | Check status of a specific order |
| `cancel_order` | Cancel a specific order |
| `place_order` | Place a new order |
| `search_product` | Search products by name |
| `get_product_details` | Get product name and price by product ID |
| `update_customer_details` | Update customer name, email, or address |

### Policy Tool
| Tool | Description |
|---|---|
| `search_policy` | Search store policy documents using RAG |

---

## 💬 Example Conversation

```
Agent:    "Hey! Welcome to Tata CLiQ support. Can I get your phone number?"
Customer: "9900454094"
Agent:    calls customer_exists() → gets cust_id C001
Agent:    "Got it John! How can I help you today?"
Customer: "What are my orders?"
Agent:    calls list_all_orders() + get_product_details()
Agent:    "You have one order — an HP Laptop placed on June 1st, currently ORDER PLACED."
Customer: "What is your return policy?"
Agent:    calls search_policy()
Agent:    "You can return products within 30 days of delivery, as long as they're unused!"
```

---

## 🔀 LLM Routing

The LLM automatically routes queries based on tool descriptions:

```
Order questions  ──► order tools  (check_order_status, cancel_order etc.)
Policy questions ──► search_policy (RAG over policies.txt)
```

No manual routing code needed — the LLM decides based on tool descriptions.

---

## 📄 Policy Documents

Add your store policies to `policies/policies.txt`. Each section separated by a blank line becomes one searchable chunk in ChromaDB.

```
RETURN POLICY:
Customers can return products within 30 days of delivery.
Items must be unused and in original packaging.

CANCELLATION POLICY:
Orders can be cancelled within 24 hours of placement.
...
```

Policies are loaded into ChromaDB on first run and cached for subsequent runs.

---

## 🧱 Tech Stack

| Component | Technology |
|---|---|
| Voice Agent | LiveKit Agents |
| STT | Deepgram Nova-3 |
| LLM | OpenAI GPT-4.1 Mini |
| TTS | Cartesia Sonic-2 |
| VAD | Silero |
| MCP Server | FastMCP |
| Database | SQLite |
| Vector Store | ChromaDB |
| Embeddings | SentenceTransformers (all-MiniLM-L6-v2) |
| Frontend | Next.js + LiveKit Components React |

---

## 📝 License

MIT License — feel free to use and modify.

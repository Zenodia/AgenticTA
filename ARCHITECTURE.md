# AgenticTA Architecture & Data Flow

Complete documentation of LLM integration, PDF processing pipeline, and data flow.

---

## Table of Contents

- [LLM Integration Architecture](#llm-integration-architecture)
- [PDF Upload & Processing Flow](#pdf-upload--processing-flow)
- [LLM API Calls Summary](#llm-api-calls-summary)
- [Complete Data Flow with RAG](#complete-data-flow-with-rag)
- [LLM Call Sequence](#llm-call-sequence)
- [RAG Server Interaction](#rag-server-interaction)

---

## LLM Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER (Python Files)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────────────┐    ┌─────────────────────┐       │
│  │ gradioUI.py  │    │   nodes.py      │    │ quiz_gen_client.py  │       │
│  │ (UI)         │───▶│  (Orchestrator) │───▶│ (Quiz Generation)   │       │
│  └──────────────┘    └─────────────────┘    └─────────────────────┘       │
│         │                     │                                             │
│         │                     ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  CORE LLM-USING MODULES                             │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ┌──────────────────────┐      ┌─────────────────────────────┐    │   │
│  │  │ chapter_gen_from_    │      │ study_material_gen_agent.py │    │   │
│  │  │ file_names.py        │      │ • Generates study materials │    │   │
│  │  │ • Chapter titles     │      │ • Uses RAG docs             │    │   │
│  │  │ • LLMClient.call()   │      │ • LLMClient.call()          │    │   │
│  │  │   use_case="chapter" │      │   use_case="study_material" │    │   │
│  │  └──────────────────────┘      └─────────────────────────────┘    │   │
│  │             │                              │                       │   │
│  │  ┌──────────▼───────────┐      ┌──────────▼──────────────────┐   │   │
│  │  │ extract_sub_         │      │ search_and_filter_          │   │   │
│  │  │ chapters.py          │      │ documents.py                │   │   │
│  │  │ • Extract subtopics  │      │ • RAG document search       │   │   │
│  │  │ • LLMClient.call()   │      │ • astra_llm_call() (legacy) │   │   │
│  │  │   use_case="subtopic"│      │ • Fallback to ChatNVIDIA    │   │   │
│  │  └──────────────────────┘      └─────────────────────────────┘   │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ All use                                 │
│                                   ▼                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                         LLM MODULE (llm/)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │  llm/client.py - LLMClient                                        │     │
│  │  • Main entry point: llm_client.call(prompt, use_case)           │     │
│  │  • Routes to appropriate handler                                 │     │
│  └───────────────────────────────┬───────────────────────────────────┘     │
│                                  │                                         │
│                                  ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │  llm/config.py                                                    │     │
│  │  • Loads llm_config.yaml                                         │     │
│  │  • Applies env var overrides (NVIDIA_API_KEY, ASTRA_TOKEN)       │     │
│  │  • Calls load_dotenv() ONCE (centralized)                        │     │
│  └───────────────────────────────┬───────────────────────────────────┘     │
│                                  │                                         │
│                                  ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │  llm/factory.py                                                   │     │
│  │  • Creates handlers based on use case config                      │     │
│  │  • LLMUseCaseHandler (direct LLM calls)                           │     │
│  │  • MCPUseCaseHandler (external services)                          │     │
│  └───────────────────────────────┬───────────────────────────────────┘     │
│                        ┌─────────┴─────────┐                               │
│                        ▼                   ▼                               │
│  ┌──────────────────┐         ┌─────────────────────────┐                 │
│  │ llm/handlers.py  │         │  llm/providers/         │                 │
│  │ • LLM Handler    │         │  • base.py (Abstract)   │                 │
│  │ • MCP Handler    │         │  • nvidia.py (ACTIVE)   │                 │
│  └──────────────────┘         │  • astra.py (ACTIVE)    │                 │
│                               │  • openai.py (commented)│                 │
│                               │  • anthropic.py (comm.) │                 │
│                               └────────────┬────────────┘                 │
│                                            │                               │
└────────────────────────────────────────────┼───────────────────────────────┘
                                             │
┌────────────────────────────────────────────▼───────────────────────────────┐
│                       EXTERNAL LLM APIs                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────┐   ┌───────────────┐   ┌──────────────────────┐     │
│  │  NVIDIA API      │   │  ASTRA API    │   │  Future: OpenAI, etc │     │
│  │  build.nvidia.   │   │  (Optional)   │   │  (Commented out)     │     │
│  │  com             │   │  • Enhanced   │   │                      │     │
│  │  • Meta Llama    │   │    models     │   │                      │     │
│  │  • Mistral       │   │               │   │                      │     │
│  └──────────────────┘   └───────────────┘   └──────────────────────┘     │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## PDF Upload & Processing Flow

### User Action: Upload PDF(s) and Click "Generate Curriculum"

### Step 1: Gradio UI - `gradioUI.py::generate_curriculum(file_obj)`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Clean Up Old PDFs                                           │
│    • Delete all files in /workspace/mnt/pdfs/                  │
│    • Ensures fresh curriculum generation                       │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Copy Uploaded PDFs                                          │
│    • shutil.copy(file_obj[i], "/workspace/mnt/pdfs/")          │
│    • file_obj = list of temporary file paths from Gradio       │
│    • Result: PDFs now in /workspace/mnt/pdfs/                  │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. Create User Object                                          │
│    • user_id = f"user_{int(time.time())}"  # Unique ID         │
│    • User(                                                     │
│        user_id=user_id,                                        │
│        study_buddy_preference="...",                           │
│        study_buddy_name="ollie"                                │
│      )                                                         │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. Call Main Orchestrator                                      │
│    • g = asyncio.run(run_for_first_time_user(                  │
│          u,                                                     │
│          uploaded_pdf_loc="/workspace/mnt/pdfs/",              │
│          save_to="/workspace/mnt/",                            │
│          study_buddy_preference                                │
│      ))                                                        │
└────────────────────────────────────────────────────────────────┘
```

### Step 2: Orchestrator - `nodes.py::run_for_first_time_user()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Initialize Storage                                          │
│    • Create: /workspace/mnt/{user_id}/                         │
│    • Create: /workspace/mnt/{user_id}/user_store/              │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Check if User Exists                                        │
│    • Look for existing user in store                           │
│    • If not found, create minimal user record                  │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. Call State Population                                       │
│    • gstate = await populate_states_for_user(...)              │
└────────────────────────────────────────────────────────────────┘
```

### Step 3: State Population - `nodes.py::populate_states_for_user()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Build Chapters                                              │
│    • chapters = await build_chapters(pdf_files_loc)            │
└────────────────────────────────────────────────────────────────┘
```

### Step 4: Chapter Building - `nodes.py::build_chapters()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Generate Chapter Titles                                     │
│    • chapter_titles_str = await chapter_gen_from_pdfs(...)     │
│      (from chapter_gen_from_file_names.py)                     │
└────────────────────────────────────────────────────────────────┘
```

### Step 5: Chapter Title Generation - `chapter_gen_from_file_names.py`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Extract Sub-Chapters from Each PDF                         │
│    • For each PDF in directory:                               │
│      - Extract text from all pages (PyMuPDF)                  │
│      - parallel_extract_pdf_page_and_text()                   │
│      - Each page → extract subtopic title                     │
│      - Uses: LLMClient.call(                                  │
│                 use_case="subtopic_title_generation")         │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Generate Main Chapter Title from Sub-Chapters              │
│    • Aggregate all subtopic titles from PDF                   │
│    • Call LLM:                                                │
│      output = await llm_client.call(                          │
│        prompt=ordered_chapters_prompt,                        │
│        use_case="chapter_title_generation"                    │
│      )                                                        │
│    • Returns: [{"file_loc": "f.pdf", "title": "Ch1"}, ...]   │
└────────────────────────────────────────────────────────────────┘
```

### Step 6: Parse & Create Chapter Objects - `nodes.py::build_chapters()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Parse Chapter Output                                        │
│    • chapter_output = parse_output_from_chapters(...)          │
│    • Validate: must have "file_loc" and "title"                │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Create Chapter Objects                                      │
│    • For each valid chapter:                                   │
│      - Extract sub-chapters (with full content)                │
│      - Generate study materials (study_material_gen_agent.py)  │
│      - Create Chapter object:                                  │
│        Chapter(                                                │
│          chapter_name=title,                                   │
│          subject=pdf_filename,                                 │
│          pdf_loc=pdf_path,                                     │
│          sub_topics=[SubTopic, ...],                           │
│          status=Status.STARTED                                 │
│        )                                                       │
└────────────────────────────────────────────────────────────────┘
```

### Step 7: Create Study Plan & Curriculum - `nodes.py::populate_states_for_user()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Create StudyPlan                                            │
│    • study_plan = StudyPlan(study_plan=chapters)               │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Create Curriculum                                           │
│    • curriculum = Curriculum(                                  │
│        active_chapter=chapters[0],                             │
│        next_chapter=chapters[1],                               │
│        study_plan=study_plan,                                  │
│        status=Status.PROGRESSING                               │
│      )                                                         │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. Generate Study Buddy Persona                                │
│    • persona = await study_buddy_client_requests(...)          │
│    • Uses MCP server for AI study buddy personality            │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. Create User Object                                          │
│    • user_dict = {                                             │
│        "user_id": user_id,                                     │
│        "study_buddy_preference": preference,                   │
│        "study_buddy_persona": persona,                         │
│        "curriculum": [curriculum_dict]                         │
│      }                                                         │
│    • Save: /workspace/mnt/{user_id}/user_store/{user_id}.json │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 5. Create GlobalState                                          │
│    • gstate = {                                                │
│        "input": "initializing",                                │
│        "user_id": user_id,                                     │
│        "chat_history": [],                                     │
│        "user": user_dict,                                      │
│        "node_name": "orchestrator_start"                       │
│      }                                                         │
│    • Save: /workspace/mnt/{user_id}/global_state.json          │
└────────────────────────────────────────────────────────────────┘
```

### Step 8: Display Curriculum - `gradioUI.py::generate_curriculum()`

```
┌────────────────────────────────────────────────────────────────┐
│ 1. Extract Study Plan from GlobalState                         │
│    • study_plan = g["user"]["curriculum"][0]["study_plan"]...  │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. Format for Display                                          │
│    • Extract chapter names: [ch["chapter_name"] for ch in ...] │
│    • Return formatted string for Gradio Textbox                │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. Show in Gradio UI                                           │
│    • Curriculum displayed in Textbox                           │
│    • Chapter buttons created                                   │
│    • User can now study!                                       │
└────────────────────────────────────────────────────────────────┘
```

---

## LLM API Calls Summary

| File | LLM Usage | Use Case |
|------|-----------|----------|
| `extract_sub_chapters.py` | `LLMClient.call(use_case="subtopic")` | Subtopic title generation |
| `chapter_gen_from_file_names.py` | `LLMClient.call(use_case="chapter")` | Chapter title generation |
| `study_material_gen_agent.py` | `LLMClient.call(use_case="study_material")` | Study material generation |
| `search_and_filter_documents.py` | `astra_llm_call()` (legacy) | Document analysis (legacy) |
| `quiz_gen_client.py` | MCP Service (external) | Quiz generation |
| `study_buddy_client.py` | MCP Service (external) | Chat conversation |

---

## Complete Data Flow with RAG

```
                     ┌──────────────────────┐
                     │    USER UPLOADS      │
                     │        PDFs          │
                     └──────────┬───────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────┐
  │         DOCUMENT INGESTION                          │
  ├─────────────────────────────────────────────────────┤
  │  1. PDFs → /workspace/mnt/pdfs/                     │
  │  2. Ingestor Server (8082) processes:               │
  │     • Text extraction                               │
  │     • Chunking                                      │
  │     • Embedding generation (NVIDIAEmbeddings)       │
  │  3. Vectors → Milvus (19530)                        │
  └──────────────────────┬──────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │    CHAPTER & SUBTOPIC EXTRACTION                    │
  ├─────────────────────────────────────────────────────┤
  │  extract_sub_chapters.py                            │
  │  • For each PDF page:                               │
  │    - Extract text (PyMuPDF)                         │
  │    - LLM Call #1: Extract subtopic title            │
  │      LLMClient.call(use_case="subtopic_title")      │
  │    - Aggregate all subtopics                        │
  └──────────────────────┬──────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │      CHAPTER TITLE GENERATION                       │
  ├─────────────────────────────────────────────────────┤
  │  chapter_gen_from_file_names.py                     │
  │  • Collect all subtopic titles                      │
  │  • LLM Call #2: Generate chapter title              │
  │    LLMClient.call(use_case="chapter_title")         │
  │  • Returns: JSON with chapter metadata              │
  └──────────────────────┬──────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │   STUDY MATERIAL GENERATION (RAG-BASED)             │
  ├─────────────────────────────────────────────────────┤
  │  study_material_gen_agent.py                        │
  │  • For each subtopic:                               │
  │    1. RAG Retrieval:                                │
  │       → RAG Server (rag-server:8081)                │
  │       → Query Milvus vector DB                      │
  │       → Returns relevant chunks                     │
  │    2. Generate Study Material:                      │
  │       LLM Call #3:                                  │
  │       LLMClient.call(                               │
  │         prompt=f"Generate for {subtopic}            │
  │                  using {retrieved_docs}",           │
  │         use_case="study_material_generation"        │
  │       )                                             │
  │    3. Store in SubTopic object                      │
  └──────────────────────┬──────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │       CURRICULUM ASSEMBLY                           │
  ├─────────────────────────────────────────────────────┤
  │  nodes.py                                           │
  │  • Create Chapter → StudyPlan → Curriculum          │
  │  • Generate Study Buddy Persona (MCP)               │
  │  • Save GlobalState to disk                         │
  └──────────────────────┬──────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │         GRADIO UI DISPLAY                           │
  ├─────────────────────────────────────────────────────┤
  │  • Display curriculum                               │
  │  • Interactive chapter buttons                      │
  │  • Study materials, quizzes, chat                   │
  └─────────────────────────────────────────────────────┘
```

---

## LLM Call Sequence

### For a PDF with 10 pages:

**LLM Call #1: Subtopic Extraction (Parallel)**
```
├─ Call 1: Page 1 → Subtopic 1 title    ┐
├─ Call 2: Page 2 → Subtopic 2 title    │
├─ Call 3: Page 3 → Subtopic 3 title    │
├─ ...                                   ├─ Parallel execution
└─ Call 10: Page 10 → Subtopic 10 title ┘   (ThreadPoolExecutor)
```

**LLM Call #2: Chapter Title Generation (Single)**
```
└─ Single call with all 10 subtopics → Main chapter title
```

**LLM Call #3: Study Material Generation (Sequential)**
```
├─ Call 1: Subtopic 1 + RAG docs → Study material 1  ┐
├─ Call 2: Subtopic 2 + RAG docs → Study material 2  │
├─ Call 3: Subtopic 3 + RAG docs → Study material 3  ├─ Sequential
├─ ...                                                │
└─ Call 10: Subtopic 10 + RAG docs → Study material 10┘
```

**Total: ~21 LLM calls per PDF** (10 + 1 + 10)

---

## RAG Server Interaction

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Python Script   │──────▶│   RAG Server     │──────▶│  Milvus Vector   │
│                  │ HTTP  │  (port 8081)     │ gRPC  │  DB (port 19530) │
│  search_and_     │Request│                  │ Query │                  │
│  filter_         │       │  • Embedding     │       │  • Vector search │
│  documents.py    │       │  • Reranking     │       │  • Metadata      │
│                  │◀──────│  • Filtering     │◀──────│    filtering     │
│                  │ JSON  │                  │Results│                  │
└──────────────────┘Response└──────────────────┘       └──────────────────┘
```

### Request Example

```json
POST http://rag-server:8081/search
{
  "query": "motorway driving rules",
  "top_k": 5,
  "filter": "content_metadata[\"filename\"] like \"%SwedenDriving%\""
}
```

### Response Example

```json
{
  "total_results": 3,
  "results": [
    {
      "document_name": "SwedenDrivingCourse_Motorway.pdf",
      "content": "Motorway rules...",
      "score": 0.814,
      "metadata": {...}
    }
  ]
}
```

### Docker Networking

**Key Environment Variable**: `AI_WORKBENCH=true`

```python
# In search_and_filter_documents.py
IPADDRESS = "rag-server" if os.environ.get("AI_WORKBENCH") == "true" else "localhost"
```

- **Inside Docker containers**: Use service names (`rag-server`, `milvus`, etc.)
- **Outside Docker**: Use `localhost` or host IP
- The `AI_WORKBENCH` env var is set in `docker-compose.yml` to enable Docker networking

---

## Key Files by Function

### LLM Integration
- `llm/client.py` - Main LLM client interface
- `llm/config.py` - Configuration loader (loads `.env` once)
- `llm/factory.py` - Creates handlers based on use cases
- `llm/handlers.py` - Handler implementations
- `llm/providers/` - Provider adapters (NVIDIA, ASTRA, etc.)
- `llm_config.yaml` - LLM configuration

### Document Processing
- `extract_sub_chapters.py` - Page-level subtopic extraction
- `chapter_gen_from_file_names.py` - Chapter title generation
- `study_material_gen_agent.py` - Study material generation with RAG
- `search_and_filter_documents.py` - RAG document retrieval

### Orchestration
- `nodes.py` - Main orchestrator, state management
- `states.py` - Data models (User, Curriculum, Chapter, etc.)
- `gradioUI.py` - Web UI interface

### Services
- `quiz_gen_client.py` - Quiz generation MCP client
- `study_buddy_client.py` - Study buddy MCP client
- `agent_mem_client.py` - Agentic memory MCP client

---

## Storage Structure

```
/workspace/mnt/
└── {user_id}/                    # Per-user directory
    ├── global_state.json         # GlobalState for this user
    └── user_store/                # User-specific storage
        └── {user_id}.json        # User profile with full curriculum
```

### Example

```
/workspace/mnt/
└── user_1730899200/
    ├── global_state.json
    └── user_store/
        └── user_1730899200.json
```

---

## Summary

**When a user uploads a PDF:**

1. ✅ PDF copied to `/workspace/mnt/pdfs/`
2. ✅ Ingestor processes and stores vectors in Milvus
3. ✅ Extract subtopics from each page (10 parallel LLM calls)
4. ✅ Generate chapter title (1 LLM call)
5. ✅ Generate study materials with RAG retrieval (10 sequential LLM calls)
6. ✅ Assemble curriculum and save to disk
7. ✅ Display in Gradio UI

**Total processing time:** 2-3 minutes per PDF (depends on page count and LLM response time)

**LLM Provider:** Configurable via `llm_config.yaml` (currently NVIDIA API by default)

**RAG Integration:** Automatic document retrieval for context-aware study material generation


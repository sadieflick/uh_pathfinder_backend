# Project Structure
```
my_fastapi_project/
├── alembic/                 <-- generated
│   ├── versions/            <-- migrations
│   ├── env.py               <-- ** modified exclude (ONET, RIASEC) **
│   └── ...
├── src/
│   ├── __init__.py
│   ├── main.py                <-- FastAPI
│   │
│   ├── api/                   
│   │   ├── __init__.py
│   │   ├── routes.py       <-- endpoint routing 
│   │   ├── deps.py         <-- Global Dependencies (get_db/current_user)             
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── controllers/           <-- ** controllers **
│   │       │   ├── __init__.py
│   │       │   ├── assessment.py    <-- quiz submissions
│   │       │   ├── occupations.py   <-- O*NET occupation client data
│   │       │   ├── programs.py      <-- Program/Pathway search & RAG
│   │       │   └── sectors.py       <-- Sector/Pathway browsing
│   │       │
│   │       └── schemas/           <-- **Pydantic Models **
│   │           ├── __init__.py         (validation type checking etc)
│   │           ├── assessment.py    <-- RIASEC/Skill req/resp
│   │           ├── occupation.py    <-- Occ client data
│   │           ├── program.py       <-- Program/Pathway client data
│   │           └── token.py         <-- login/auth (optional for MVP)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            <-- App settings (db url, secret keys)
│   │   ├── security.py          <-- PW hashing, tokens (optional MVP)
│   │   └── llm.py               <-- **RUNTIME LLM/RAG Logic** 
│   │                                  (LangChain chains, clients)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base_class.py        <-- 'models/base.py' file
│   │   ├── session.py           <-- Database session (get_db function)
│   │   └── vector_store.py      <-- Logic to query pgvector/chroma
│   │
│   ├── models/                <-- **SQLAlchemy Models (DB Tables)**
│   │   ├── __init__.py
│   │   ├── public_schema/       <-- **App Data**
│   │   │   ├── __init__.py
│   │   │   ├── occupation.py    <-- 'Occupation' (app data) model
│   │   │   ├── hs_skill.py      <-- 'HSSkill' model
│   │   │   ├── skills_assessment.py <-- Assessment data flow
│   │   │   ├── sector.py
│   │   │   ├── pathway.py
│   │   │   ├── program.py
│   │   │   └── scraped_data.py
│   │   ├── onet_schema/         <-- **Static O*NET Data**
│   │   │   ├── __init__.py
│   │   │   ├── onet_occupation.py
│   │   │   ├── content_model.py
│   │   │   ├── skill.py         <-- The 'skills' score table
│   │   │   ├── interest.py      <-- The 'interests' score table
│   │   │   └── scale.py
│   │   └── riasec_schema/       <-- **Static Calculated Data**
│   │       ├── __init__.py
│   │       ├── riasec_profile.py
│   │       ├── interest_matched_job.py
│   │       └── interest_filtered_skill.py
│   │
│   ├── repositories/            <-- **Data Access Layer (DB queries)**
│   │   ├── __init__.py
│   │   ├── assessment_repo.py   <-- Queries the 'riasec_schema'
│   │   ├── occupation_repo.py   <-- Queries onet and app occupations
│   │   └── program_repo.py      <-- Queries app programs & vector store
│   │
│   └── services/                <-- **Business Logic Layer**
│       ├── __init__.py
│       ├── assessment_service.py  <-- Compute scores, calls repo, LLM for skills
│       ├── occupation_service.py  <-- Combines O*NET/app data in 1 obj
│       ├── program_service.py     <-- Orchestrates RAG queries
│       └── static_references/     <-- psychometric quiz questions etc.
│
├── data_pipeline/               <-- **OFFLINE Scripts (manual or scheduled)**
│   ├── __init__.py
│   ├── 1_ingest_hawaii_data.py  <-- Populates public.sector/pathway/program
│   ├── 2_embed_programs.py      <-- Populates vector store
│   ├── 3_link_occupations.py    <-- Populates program_occupation table
│   └── onet_helpers/            <-- Scripts to bulk-load the 'onet'
│
├── tests/
│   └── ... (Your tests)
├── .env
├── alembic.ini                  <-- Alembic config
└── requirements.txt
```

# Backend Overview

# API Endpoint Overview

| Frontend Component(s) | Endpoint | Method | Description & Purpose |
|------------------------|----------|--------|------------------------|
| RIASECQuiz.tsx | `/api/v1/assessment/riasec` | POST | **(Prototype Step 1)**. User submits 30 quiz answers. Backend calculates their 3-letter code (e.g., "IRE") and returns pre-calculated jobs and skills from `riasec.interest_matched_jobs` and `riasec.interest_filtered_skills` tables. |
| SkillsAssessment.tsx, SkillsNarrative.tsx | `/api/v1/assessment/skills` | POST | **(Prototype Step 2)**. User submits their skill panel scores (`panel_initial_scores`) and narrative text. Backend: (1) Calls the LLM to refine this into the 40-rating string, (2) Calls the CareerOneStop API, and (3) Returns the final ranked list of occupation matches. |
| OccupationResults.tsx, OccupationDetails.tsx | `/api/v1/occupations/{onet_code}` | GET | **(Prototype Step 3)**. User clicks a job. This endpoint fetches data from both `onet.onet_occupation` (title, description) and `public.occupation` (app data, wage, etc.) and returns one combined JSON response. |
| (Future Search Feature) | `/api/v1/programs/search` | GET | User submits a free-text query (e.g., "computer programs on Maui"). Triggers the RAG pipeline (`program_service` → `vector_store`) and returns matching `Program` objects. |
| (Future Browse Feature) | `/api/v1/sectors` | GET | Returns the list of all **9 Sectors**. |
| (Future Browse Feature) | `/api/v1/sectors/{sector_id}/pathways` | GET | Returns all Pathways for a given Sector. |
| Diagnostics | `/api/v1/apitest` | GET | Lightweight health endpoint that verifies API reachability and attempts a DB connectivity check. Returns `{ status, timestamp, app_name, db: { connected, dialect, error } }`. |

## New: Program Recommendations (Semantic)

- Endpoint: `POST /api/v1/programs/recommend`
- Request body:
	```json
	{ "query": "software development and programming", "top_k": 5 }
	```
- Response: Array of `{ program: {id,name,...}, score, preview }`
- Backed by offline embeddings in `vector_chunks` generated by `data_pipeline/processor/embed_programs.py`.
- Default uses local sentence-transformers; can switch to Voyage AI later.
# UH Pathfinder
## Summary of Features:

### Choose path:
1. Highschool
2. Work Experienced

### RAISEC Questionaire
1. User survey gets the student's RAISEC Code of 3 interest areas (simple front-end logic)
2. User sees RIASEC interest radar chart, details about their interest profile
3. _Interest-Matched Jobs_: Query (batched/scheduled) for up to 150 interest-matched jobs 
4. _Interest-Job-Matched 40-Skill Sample_: By Interest Profile: Compute pre-scored 40-skill list score-adjusted by frequency of skill in interest-matched jobs

### Skills Survey: Select Tasks You've Done Before
#### Prepares to call CareerOneStop API for Skill-Job Matches
1. User chooses tasks the have done before from a panel of tasks (appropriate to work experience level)
2. User takes a 'heuristic' skills survey, to fetch skills-matched jobs from the CareerOneStop API, which will later be joined on the 150 interest-matched jobs, for a more targeted interest/job match
3. Instead of the user rating each of 40 skills 1 to 5, which causes user fatigue, we pre-score interest-weighted 40-skills, and then employ a 'binary search'/elimination approach.
4. Task statements are adapted for analagous high-school appropriate levels of tasks, to provide an approximate measure of aptitude (or affinity) for future career requirements.
5. Selecting "I've done this task before" further pre-rates 12 of the 40 skills (or more if they choose), downgrading or upgrading the score to start, based on whether or not they have performed a mid-level-competency task of this skill (anchor at 3 of 5)
6. The next step uses LLM inference to collect approximated data about the tasks they have done to refine scores through open-ended questions using the skills anchor statements for skill-level as a basis for the judgment.

## Confidence Scoring Workflow (Program–Occupation Links)

We maintain `program_occupation_association` as the linking table between education programs and target occupations. A nullable `confidence` column has been added to support continuous validation and pruning of weak links.

### Column Semantics
- `NULL`: Link has not yet been evaluated by the LLM pass.
- `0.0` (optional baseline): Explicitly marked as low confidence (if you choose to backfill).
- `> 0.0` (currently we set `0.95`): High-confidence validated link retained by the cleanup job.

### Migration Resolution
Two divergent Alembic heads were merged (vector embedding path vs confidence addition) via merge revision `d1b7c4f9e123`. Future migrations should use that revision as their `down_revision`.

### Scripts
Location: `data_pipeline/processor/program_relevance_cleanup.py`
Purpose: Batch LLM validation of existing links. For each occupation, the script:
1. Sends a compact JSON list of candidate programs to the LLM.
2. Receives a filtered list of valid program IDs.
3. Sets `confidence=0.95` for valid links.
4. Deletes invalid links (unless `--dry-run`).

Optional Backfill Script: `src/scripts/backfill_confidence.py` (created if missing). Sets all `NULL` confidences to a baseline value.

### Running the Workflow
```bash
# 1. Ensure migrations are up to date
python -m alembic upgrade head

# 2. (Optional) Backfill NULL confidences to 0.0 for clarity
python src/scripts/backfill_confidence.py --baseline 0.0

# 3. Dry run LLM validation (no DB writes, view planned changes)
python data_pipeline/processor/program_relevance_cleanup.py --limit 10 --dry-run

# 4. Execute full validation (writes confidence & prunes invalid links)
python data_pipeline/processor/program_relevance_cleanup.py --limit 50

# 5. Inspect results (example manual query)
psql "$DATABASE_URL" -c "SELECT program_id, occupation_onet_code, confidence FROM program_occupation_association ORDER BY confidence NULLS LAST LIMIT 20;"
```

### Adjusting Confidence Thresholds
Currently hard-coded to `0.95` for valid links. For nuanced scoring you could:
- Return graded confidence values (e.g., 0.6–0.95) from the LLM.
- Introduce a second pass to promote borderline links.
- Keep deleted links in an audit table (future enhancement).

### Next Enhancements
- Add structured JSON schema enforcement in the LLM call (e.g., regex or pydantic validation).
- Track evaluation timestamp & model used.
- Differential re-validation only for stale links (older than X days).

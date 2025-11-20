# Interest-Weighted Skills Assessment: Implementation Plan

## Overview

This document outlines the strategy for implementing an interest-weighted 40-skill assessment that combines RIASEC interest profiles with task-based skill evaluation and LLM-driven refinement to produce high-quality occupation matches via the CareerOneStop Skills Matcher API.

---

## Workflow Summary

```
User completes RIASEC quiz
    ↓
System retrieves interest-filtered skills (40 skills ranked by frequency in interest-matched jobs)
    ↓
Pre-score top 20 → DataPoint50, bottom 20 → DataPoint35
    ↓
User selects tasks they've performed ("I've done this")
    ↓
Selected skills bumped to DataPoint65
    ↓
LLM conversational refinement (2-3 questions per selected skill)
    ↓
Adjust scores (up/down/same) based on AnchorFourth competency check
    ↓
Submit final SKA payload to CareerOneStop API
    ↓
INNER JOIN: CareerOneStop results ∩ Interest-matched jobs (from RIASEC)
    ↓
Return refined occupation matches
```

---

## Implementation Phases

### Phase 1: Database Query & Pre-scoring

**Goal:** Fetch interest-filtered skills for a RIASEC code and pre-score them.

#### 1.1 Query `riasec.interest_filtered_skills`

**SQL Query:**
```sql
SELECT element_id, element_name, SUM(freq) as total 
FROM (
    SELECT DISTINCT 
        riasec.interest_filtered_skills.skill_id as element_id, 
        onet.content_model_reference.element_name as element_name, 
        COUNT(frequency) as freq
    FROM riasec.interest_filtered_skills
    JOIN onet.content_model_reference
        ON onet.content_model_reference.element_id = riasec.interest_filtered_skills.skill_id
    WHERE riasec_code = :riasec_code
        AND skill_id IN (
            '2.C.7.b', '2.B.2.i', '2.A.1.e', '2.C.1.d', '2.C.4.d', 
            '2.B.1.e', '1.A.3.c.3', '2.C.1.f', '2.B.4.g', '2.B.1.d', 
            '2.B.3.e', '2.C.7.c', '2.B.1.f', '2.B.5.a', '2.A.1.f', 
            '2.B.3.m', '2.C.6', '2.C.4.e', '2.A.1.c', '2.C.1.e', 
            '2.A.2.d', '2.C.9.a', '2.C.8.a', '2.C.3.e', '2.C.5.b', 
            '2.C.1.b', '2.C.3.a', '2.B.3.k', '2.C.4.f', '1.A.1.d.1', 
            '2.C.1.a', '2.B.3.l', '2.B.5.b', '2.C.5.a', '2.C.2.a', 
            '2.A.1.d', '2.B.3.a', '2.C.1.c', '2.C.4.c', '2.C.3.d'
        )
    GROUP BY skill_id, element_name, frequency
) as skill_freq
GROUP BY element_id, element_name
ORDER BY total DESC;
```

**Repository Method:**
```python
def get_interest_weighted_skills(
    self, 
    riasec_code: str
) -> List[Tuple[str, str, int]]:
    """Return (element_id, element_name, total_freq) ranked by interest match."""
```

#### 1.2 Pre-score Skills

**Service Logic:**
- Top 20 skills → `DataPoint50` (from `oneStop40Skills.json`)
- Bottom 20 skills → `DataPoint35`
- Return initial SKA payload structure

**Service Method:**
```python
def prescore_skills(
    self, 
    riasec_code: str
) -> Dict[str, Any]:
    """
    Returns:
    {
        "riasec_code": "IRE",
        "skills": [
            {
                "element_id": "2.A.1.e",
                "element_name": "Mathematics",
                "initial_score": 3.06,
                "rank": 1,
                "anchor_third": "Use algebra...",
                "question": "What is your level..."
            },
            ...
        ]
    }
    """
```

---

### Phase 2: Task Selection & Skill Bump

**Goal:** User selects tasks they've performed; bump those skills to DataPoint65.

#### 2.1 Endpoint: `POST /api/v1/assessment/skills/initialize`

**Request:**
```json
{
    "riasec_code": "IRE",
    "selected_skill_ids": [
        "2.A.1.e",
        "2.C.3.a",
        "2.B.2.i"
    ]
}
```

**Response:**
```json
{
    "riasec_code": "IRE",
    "skills": [
        {
            "element_id": "2.A.1.e",
            "element_name": "Mathematics",
            "score": 3.978,  // DataPoint65
            "selected": true
        },
        {
            "element_id": "2.C.1.a",
            "element_name": "Administration and Management",
            "score": 3.295,  // DataPoint50 (not selected)
            "selected": false
        }
        // ... 40 total
    ],
    "refinement_required": ["2.A.1.e", "2.C.3.a", "2.B.2.i"]
}
```

---

### Phase 3: AnchorFourth Generation

**Goal:** Generate mid-high competency anchor statements for all 40 skills.

#### 3.1 LLM One-Shot Generation

**Prompt Template:**
```
You are an expert in O*NET skill assessment. For each of the 40 CareerOneStop skills, generate a single "AnchorFourth" statement that represents mid-high competency (between DataPoint50 and DataPoint80 on a 7-point scale).

The anchor should:
- Be actionable and specific
- Require demonstrated intermediate-to-advanced skill application
- Be achievable by an experienced professional (not entry-level)
- Fit between the existing AnchorThird (DataPoint50) and AnchorLast (DataPoint80)

Skill: Mathematics
DataPoint50 (AnchorThird): "Use algebra or geometry to solve problems in homework or a real-world project."
DataPoint80 (AnchorLast): "Use advanced math (like calculus or statistics) to analyze data or build a complex project."
AnchorFourth: "Apply statistical analysis to interpret trends in a dataset and make data-driven recommendations."

[Repeat for all 40 skills...]
```

**Storage:** Add `AnchorFourth` field to `oneStop40Skills.json` and `highSchool40Skills.json`.

---

### Phase 4: LLM Skill Refinement

**Goal:** For each selected skill, ask 2-3 questions to refine the score.

#### 4.1 Refinement Prompt Structure

**System Prompt:**
```
You are a career assessment assistant helping refine a user's skill level. For each skill, you will:
1. Reference the AnchorFourth competency statement
2. Ask 2-3 clarifying questions to determine if the user's ability is:
   - Above AnchorFourth → bump to DataPoint80
   - At AnchorFourth → keep at DataPoint65
   - Below AnchorFourth → drop to DataPoint50
3. Track confidence in your assessment (0.0-1.0)
4. Stop when confidence ≥ 0.8 or after 3 questions

Be conversational, brief, and focused.
```

**Conversation State:**
```python
{
    "skill_id": "2.A.1.e",
    "skill_name": "Mathematics",
    "current_score": 3.978,
    "anchor_fourth": "Apply statistical analysis...",
    "questions_asked": 1,
    "confidence": 0.6,
    "transcript": [
        {"role": "assistant", "content": "Can you describe a time..."},
        {"role": "user", "content": "I built a regression model..."}
    ],
    "recommendation": null  // "bump_up" | "keep" | "bump_down"
}
```

#### 4.2 Endpoint: `POST /api/v1/assessment/skills/refine`

**Request:**
```json
{
    "conversation_id": "uuid-here",
    "skill_id": "2.A.1.e",
    "user_response": "I built a regression model for my econ project."
}
```

**Response:**
```json
{
    "conversation_id": "uuid-here",
    "skill_id": "2.A.1.e",
    "next_question": "What type of regression did you use, and what insights did you gain?",
    "complete": false,
    "questions_remaining": 2
}
```

**Or (when complete):**
```json
{
    "conversation_id": "uuid-here",
    "skill_id": "2.A.1.e",
    "complete": true,
    "recommendation": "bump_up",
    "new_score": 4.896,
    "confidence": 0.85
}
```

---

### Phase 5: CareerOneStop Integration

**Goal:** Submit final SKA payload and retrieve ranked jobs.

#### 5.1 Final Payload Assembly

**Service Method:**
```python
def assemble_final_ska_payload(
    self,
    refined_skills: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Returns:
    {
        "SKAValueList": [
            {"ElementId": "2.A.1.e", "DataValue": "4.896"},
            {"ElementId": "2.C.3.a", "DataValue": "3.425"},
            ...
        ]
    }
    """
```

#### 5.2 Call CareerOneStop

Use existing `AssessmentRepository.get_150_jobs_from_cos(ska_payload)`.

---

### Phase 6: Occupation Intersection

**Goal:** INNER JOIN CareerOneStop results with RIASEC interest-matched jobs.

#### 6.1 Query

```sql
SELECT DISTINCT 
    cos.onet_code,
    cos.title,
    cos.score as skills_match_score,
    imj.rank as interest_rank
FROM career_one_stop_results cos
INNER JOIN riasec.interest_matched_jobs imj
    ON cos.onet_code = imj.onet_code
WHERE imj.riasec_code = :riasec_code
ORDER BY cos.score DESC, imj.rank ASC
LIMIT 50;
```

**Service Method:**
```python
def get_final_occupation_matches(
    self,
    riasec_code: str,
    ska_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Returns jobs that appear in BOTH:
    - CareerOneStop SKA results (skill match)
    - RIASEC interest-matched jobs (interest match)
    
    Ranked by skills_match_score, then interest_rank.
    """
```

#### 6.2 Endpoint: `POST /api/v1/assessment/skills/matches`

**Request:**
```json
{
    "riasec_code": "IRE",
    "refined_skills": [
        {"element_id": "2.A.1.e", "score": 4.896},
        ...
    ]
}
```

**Response:**
```json
{
    "riasec_code": "IRE",
    "total_matches": 42,
    "occupations": [
        {
            "onet_code": "15-2021.00",
            "title": "Mathematicians",
            "skills_match_score": 95,
            "interest_rank": 3,
            "combined_confidence": 0.89
        },
        ...
    ]
}
```

---

## Data Requirements

### 1. Database Schema Updates

**Option A:** Store conversation state in DB
```sql
CREATE TABLE riasec.skill_refinement_sessions (
    session_id UUID PRIMARY KEY,
    user_id INT,
    riasec_code VARCHAR(3),
    skill_id VARCHAR(20),
    transcript JSONB,
    confidence FLOAT,
    recommendation VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Option B:** Use in-memory session store (Redis/dict) for MVP.

### 2. Static Reference Files

**Update:** `oneStop40Skills.json` and `highSchool40Skills.json`
- Add `"AnchorFourth": "..."` to each skill entry

---

## Testing Strategy

### Pre-LLM Test Plan

**Goal:** Validate logic without LLM dependency.

#### Test 1: Pre-scoring
```python
def test_prescore_skills():
    service = SkillsAssessmentService()
    result = service.prescore_skills("IRE")
    
    assert len(result["skills"]) == 40
    assert result["skills"][0]["initial_score"] > result["skills"][-1]["initial_score"]
    # Top 20 should be ~DataPoint50
    assert 3.0 < result["skills"][10]["initial_score"] < 4.0
```

#### Test 2: Task Selection Bump
```python
def test_task_selection_bump():
    selected = ["2.A.1.e", "2.C.3.a"]
    result = service.apply_task_selection("IRE", selected)
    
    for skill in result["skills"]:
        if skill["element_id"] in selected:
            assert skill["selected"] is True
            # Should be ~DataPoint65
            assert skill["score"] > 3.5
```

#### Test 3: Mock LLM Refinement
```python
def test_mock_refinement():
    # Simulate LLM response: "bump_up"
    mock_recommendation = {"recommendation": "bump_up", "confidence": 0.9}
    
    initial_score = 3.978  # DataPoint65
    new_score = service.apply_recommendation("2.A.1.e", initial_score, mock_recommendation)
    
    assert new_score == 4.896  # DataPoint80
```

#### Test 4: Intersection Logic
```python
def test_occupation_intersection():
    # Mock CareerOneStop results
    cos_results = [
        {"onet_code": "15-2021.00", "score": 95},
        {"onet_code": "11-1111.00", "score": 80}
    ]
    
    # Intersection should only return jobs in BOTH lists
    matches = service.get_final_occupation_matches("IRE", cos_results)
    
    assert len(matches) <= len(cos_results)
    assert all(m["onet_code"] in interest_matched_jobs for m in matches)
```

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/assessment/skills/initialize` | POST | Get prescored skills + apply task selection bumps |
| `/api/v1/assessment/skills/refine` | POST | LLM conversational refinement (one question at a time) |
| `/api/v1/assessment/skills/matches` | POST | Submit final SKA payload → CareerOneStop → Intersection |

---

## Open Questions & Decisions

### Q1: Session Management
- **Option A:** Store conversation state in PostgreSQL (persistent, queryable)
- **Option B:** Use Redis (fast, ephemeral)
- **Option C:** In-memory dict (MVP, not production-ready)

**Recommendation:** Start with Option C for MVP, migrate to Option B for demo.

### Q2: LLM Confidence Threshold
- How many questions before forcing a decision?
- What confidence level is "good enough"? (Propose: 0.8)

**Recommendation:** Max 3 questions per skill, confidence ≥ 0.8 or stop.

### Q3: AnchorFourth Generation
- Generate all 40 via LLM one-shot and hardcode?
- Generate on-the-fly per user?

**Recommendation:** Pre-generate and hardcode in JSON for consistency and speed.

### Q4: Intersection Result Size
- If intersection yields < 10 jobs, fall back to top CareerOneStop results?
- Or return interest-matched jobs with skills score appended?

**Recommendation:** Return intersection if ≥ 10; else return top 20 CareerOneStop with interest rank noted.

---

## Next Steps

1. **Implement Phase 1:** DB query + pre-scoring service ✅ (Start here)
2. **Generate AnchorFourth:** Use Claude/GPT to batch-generate 40 anchors
3. **Build `/initialize` endpoint:** Wire up task selection logic
4. **Mock LLM refinement:** Hardcode decision logic for testing
5. **Integrate CareerOneStop:** Connect existing repo method
6. **Build intersection logic:** SQL + service layer
7. **Add real LLM:** Swap mock with Anthropic API calls
8. **Frontend integration:** Update quiz flow to call new endpoints

---

## Success Metrics

- **Accuracy:** Intersection size ≥ 10 jobs for 80% of users
- **Efficiency:** LLM refinement completes in ≤ 3 questions per skill
- **Confidence:** Average confidence score ≥ 0.75
- **User Experience:** Total assessment time ≤ 15 minutes

---

**Status:** Draft v1.0  
**Last Updated:** 2025-11-19  
**Author:** AI Assistant + Sadie Flick

# API Schema Extension - Ranking Metadata

## Changes

### OccupationLite Schema
Added optional ranking metadata fields to provide transparency into the balanced composite scoring:

```python
class OccupationLite(BaseModel):
    onet_code: str
    title: str
    median_salary: Optional[float] = None
    growth_outlook: Optional[str] = None
    # NEW: Enriched ranking metadata
    composite_score: Optional[float] = None      # 0-1 range, higher = better match
    interest_sum: Optional[float] = None         # Sum of RIASEC letter scores
    interests_count: Optional[int] = None        # Number of profile letters in top-3
```

### RiasecCodeRequest Schema
Updated to support larger result sets with enriched scoring:

```python
class RiasecCodeRequest(BaseModel):
    riasec_code: str = Field(min_length=3, max_length=3, pattern="^[RIASEC]{3}$")
    limit: Optional[int] = Field(default=50, ge=1, le=150)  # Increased from 10/50
```

## Response Example

**Request:**
```json
POST /api/v1/assessment/riasec
{
  "riasec_code": "ACR",
  "limit": 5
}
```

**Response:**
```json
{
  "riasec_code": "ACR",
  "occupation_pool": ["27-1012.00", "49-2094.00", ...],
  "top10_jobs": [
    {
      "onet_code": "27-1012.00",
      "title": "Craft Artists",
      "median_salary": 70000.0,
      "growth_outlook": "Faster than average",
      "composite_score": 0.75870,
      "interest_sum": 11.86,
      "interests_count": 2
    },
    ...
  ],
  "skills_panel": [...]
}
```

## Metadata Field Descriptions

### composite_score
- **Type:** float (0-1 range)
- **Description:** Balanced composite ranking score combining:
  - 35% interest_sum normalization
  - 25% balanced letter score (min of per-letter norms)
  - 20% coverage ratio (fraction of code letters in occupation's top-3)
  - 20% rarity bonus (inverse frequency weighting)
- **Higher values** = better overall match to user's RIASEC profile
- **Only present** when using enriched interest_job_signals table

### interest_sum
- **Type:** float
- **Description:** Sum of occupation's scores for the letters in user's RIASEC code
- **Example:** For ACR code, if occupation has R=5.86, A=6.0, C=2.55, then interest_sum = 5.86 + 6.0 + 2.55 = 14.41
- **Higher values** = stronger aggregate interest alignment

### interests_count
- **Type:** integer (0-3)
- **Description:** Number of user's RIASEC code letters that appear in the occupation's top-3 interests
- **Example:** For ACR code, if occupation has top-3 interests [R, I, A], then interests_count = 2 (R and A present)
- **Higher values** = more dimensions of user's profile represented

## Backward Compatibility

✅ All new fields are **Optional** - existing clients continue to work
✅ Fields are **None/null** when using legacy fallback path (no signals table)
✅ Default limit increased from 10→50, but clients can still request fewer

## Use Cases

### Frontend Display
Show composite_score as a "match percentage" or confidence indicator:
```typescript
const matchPercentage = Math.round(job.composite_score * 100);
// Display: "76% match"
```

### Sorting/Filtering
Results are pre-sorted by composite_score DESC, but frontend can re-sort by:
- Salary (median_salary)
- Growth outlook (employment_outlook)
- Interest alignment (interest_sum)

### Debugging/Transparency
Display interest_sum and interests_count to help users understand why an occupation was recommended:
```
Craft Artists
Match: 76% | Interest Alignment: 11.86 | Profile Coverage: 2/3 letters
```

## Next Steps

Frontend should:
1. Update OccupationResults component to display composite_score (optional)
2. Handle up to 150 occupations instead of 10
3. Consider pagination or infinite scroll for large result sets
4. Add tooltips explaining the ranking metadata

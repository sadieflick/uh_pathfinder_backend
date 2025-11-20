#!/usr/bin/env python3
"""
Manual testing script for interest-weighted skills assessment.

Tests the full flow:
1. Query interest-filtered skills for a RIASEC code
2. Pre-score skills (top 20 → DataPoint50, bottom 20 → DataPoint35)
3. Apply task selection (selected → DataPoint65)
4. Build SKA payload for CareerOneStop

Run: python test_skills_flow.py
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.session import session_scope
from src.repositories.riasec_repo import RiasecRepository
from src.services.skills_prescoring_service import SkillsPrescoringService


def test_interest_filtered_skills():
    """Test DB query for interest-weighted skills."""
    print("=" * 80)
    print("TEST 1: Query Interest-Filtered Skills")
    print("=" * 80)
    
    riasec_code = "IRE"  # Investigative, Realistic, Enterprising
    
    with session_scope() as db:
        repo = RiasecRepository(db)
        skills = repo.get_interest_filtered_skills(riasec_code)
        
        print(f"\nRIASEC Code: {riasec_code}")
        print(f"Skills Found: {len(skills)}")
        
        if skills:
            print("\nTop 10 Skills by Interest-Job Frequency:")
            print("-" * 80)
            for idx, skill in enumerate(skills[:10], 1):
                print(f"{idx:2}. {skill['element_name']:35} "
                      f"({skill['element_id']}) - freq: {skill['total_frequency']}")
            
            print("\nBottom 5 Skills:")
            print("-" * 80)
            for idx, skill in enumerate(skills[-5:], len(skills) - 4):
                print(f"{idx:2}. {skill['element_name']:35} "
                      f"({skill['element_id']}) - freq: {skill['total_frequency']}")
        else:
            print("\n⚠️  No skills found. This may indicate:")
            print("   - RIASEC code not in database")
            print("   - No interest_filtered_skills data populated")
        
        return skills


def test_prescoring():
    """Test pre-scoring logic."""
    print("\n" + "=" * 80)
    print("TEST 2: Pre-Score Skills")
    print("=" * 80)
    
    riasec_code = "IRE"
    
    with session_scope() as db:
        service = SkillsPrescoringService()
        result = service.prescore_skills(riasec_code, db)
        
        print(f"\nRIASEC Code: {result['riasec_code']}")
        print(f"Total Skills: {len(result['skills'])}")
        
        if result['skills']:
            print("\nTop 5 Skills (should have DataPoint50 scores):")
            print("-" * 80)
            for skill in result['skills'][:5]:
                print(f"Rank {skill['rank']:2}: {skill['element_name']:30} "
                      f"Score: {skill['initial_score']:.3f} "
                      f"(DP50: {skill['data_point_50']:.3f})")
            
            print("\nSkills ranked 16-20 (should have DataPoint50 scores):")
            print("-" * 80)
            for skill in result['skills'][15:20]:
                print(f"Rank {skill['rank']:2}: {skill['element_name']:30} "
                      f"Score: {skill['initial_score']:.3f} "
                      f"(DP50: {skill['data_point_50']:.3f})")
            
            print("\nSkills ranked 21-25 (should have DataPoint35 scores):")
            print("-" * 80)
            for skill in result['skills'][20:25]:
                print(f"Rank {skill['rank']:2}: {skill['element_name']:30} "
                      f"Score: {skill['initial_score']:.3f} "
                      f"(DP35: {skill['data_point_35']:.3f})")
            
            # Verify scoring logic
            top_20_correct = all(
                abs(s['initial_score'] - s['data_point_50']) < 0.001
                for s in result['skills'][:20]
            )
            bottom_20_correct = all(
                abs(s['initial_score'] - s['data_point_35']) < 0.001
                for s in result['skills'][20:40]
            )
            
            print("\n✓ Validation:")
            print(f"  Top 20 use DataPoint50: {top_20_correct}")
            print(f"  Bottom 20 use DataPoint35: {bottom_20_correct}")
        
        return result


def test_task_selection():
    """Test task selection bumps."""
    print("\n" + "=" * 80)
    print("TEST 3: Apply Task Selection")
    print("=" * 80)
    
    riasec_code = "IRE"
    # Simulate user selecting these skills as "I've done this"
    selected = ["2.A.1.e", "2.C.3.a", "2.B.2.i"]  # Math, Computers, Problem Solving
    
    with session_scope() as db:
        service = SkillsPrescoringService()
        result = service.apply_task_selection(riasec_code, selected, db)
        
        print(f"\nRIASEC Code: {result['riasec_code']}")
        print(f"Selected Skills: {len(selected)}")
        print(f"Refinement Required: {len(result['refinement_required'])}")
        
        print("\nSelected Skills (should be bumped to DataPoint65):")
        print("-" * 80)
        for skill in result['skills']:
            if skill['element_id'] in selected:
                print(f"{skill['element_name']:30} "
                      f"Initial: {skill['initial_score']:.3f} → "
                      f"Bumped: {skill['score']:.3f} "
                      f"(DP65: {skill['data_point_65']:.3f}) "
                      f"Selected: {skill['selected']}")
        
        print("\nUnselected Top Skills (should keep DataPoint50):")
        print("-" * 80)
        count = 0
        for skill in result['skills']:
            if not skill['selected'] and skill['rank'] <= 20:
                print(f"Rank {skill['rank']:2}: {skill['element_name']:30} "
                      f"Score: {skill['score']:.3f}")
                count += 1
                if count >= 5:
                    break
        
        # Verify bump logic
        selected_skills = [s for s in result['skills'] if s['element_id'] in selected]
        bumps_correct = all(
            abs(s['score'] - s['data_point_65']) < 0.001
            for s in selected_skills
        )
        
        print("\n✓ Validation:")
        print(f"  Selected skills bumped to DP65: {bumps_correct}")
        print(f"  Refinement list matches selected: {set(result['refinement_required']) == set(selected)}")
        
        return result


def test_ska_payload():
    """Test SKA payload builder."""
    print("\n" + "=" * 80)
    print("TEST 4: Build CareerOneStop SKA Payload")
    print("=" * 80)
    
    riasec_code = "IRE"
    selected = ["2.A.1.e", "2.C.3.a"]
    
    with session_scope() as db:
        service = SkillsPrescoringService()
        result = service.apply_task_selection(riasec_code, selected, db)
        payload = service.build_ska_payload(result['skills'])
        
        print(f"\nPayload Structure:")
        print(f"  Total Skills: {len(payload['SKAValueList'])}")
        
        print("\nSample Elements:")
        print("-" * 80)
        for elem in payload['SKAValueList'][:5]:
            # Find skill name
            skill = next((s for s in result['skills'] if s['element_id'] == elem['ElementId']), None)
            name = skill['element_name'] if skill else "Unknown"
            selected_mark = "✓" if skill and skill['selected'] else " "
            print(f"{selected_mark} {elem['ElementId']:12} = {elem['DataValue']:6}  ({name})")
        
        # Verify format
        all_strings = all(isinstance(e['DataValue'], str) for e in payload['SKAValueList'])
        has_40_skills = len(payload['SKAValueList']) == 40
        
        print("\n✓ Validation:")
        print(f"  All DataValues are strings: {all_strings}")
        print(f"  Has 40 skills: {has_40_skills} (actual: {len(payload['SKAValueList'])})")
        
        # Show selected skills with bumped scores
        print("\nSelected Skills in Payload:")
        print("-" * 80)
        for elem in payload['SKAValueList']:
            skill = next((s for s in result['skills'] if s['element_id'] == elem['ElementId']), None)
            if skill and skill['selected']:
                print(f"  {skill['element_name']:30} = {elem['DataValue']}")
        
        return payload


def display_ux_insights():
    """Display UX insights for intuitive gut check."""
    print("\n" + "=" * 80)
    print("UX INSIGHTS & UTILITY CHECK")
    print("=" * 80)
    
    riasec_code = "IRE"
    selected = ["2.A.1.e", "2.C.3.a", "2.B.2.i"]
    
    with session_scope() as db:
        service = SkillsPrescoringService()
        result = service.apply_task_selection(riasec_code, selected, db)
        
        print(f"\n📊 Scenario: {riasec_code} Student selects {len(selected)} tasks")
        print("-" * 80)
        
        # Group by selection status and rank
        selected_top_10 = [s for s in result['skills'] if s['selected'] and s['rank'] <= 10]
        selected_11_20 = [s for s in result['skills'] if s['selected'] and 11 <= s['rank'] <= 20]
        selected_21_plus = [s for s in result['skills'] if s['selected'] and s['rank'] > 20]
        
        print("\n✅ HIGH-VALUE MATCHES (Selected + Top 10 by interest):")
        if selected_top_10:
            for skill in selected_top_10:
                boost = skill['score'] - skill['initial_score']
                print(f"  • {skill['element_name']:30} "
                      f"Rank #{skill['rank']:2} | "
                      f"Score: {skill['initial_score']:.2f} → {skill['score']:.2f} "
                      f"(+{boost:.2f})")
            print(f"\n  💡 Insight: These are both interest-aligned AND user-validated.")
        else:
            print("  (None - user didn't select any top-10 skills)")
        
        print("\n⚠️  POTENTIAL OVERESTIMATION (Selected but ranked 21-40):")
        if selected_21_plus:
            for skill in selected_21_plus:
                boost = skill['score'] - skill['initial_score']
                print(f"  • {skill['element_name']:30} "
                      f"Rank #{skill['rank']:2} | "
                      f"Score: {skill['initial_score']:.2f} → {skill['score']:.2f} "
                      f"(+{boost:.2f})")
            print(f"\n  💡 Insight: User claims competency in skills rare for their interests.")
            print(f"              → Good candidate for LLM refinement/verification.")
        else:
            print("  (None - user only selected high-frequency skills)")
        
        print("\n🔍 UNSELECTED HIGH-PRIORITY (Top 10 not selected):")
        unselected_top = [s for s in result['skills'] if not s['selected'] and s['rank'] <= 10]
        if unselected_top:
            for skill in unselected_top[:5]:
                print(f"  • {skill['element_name']:30} "
                      f"Rank #{skill['rank']:2} | "
                      f"Score: {skill['score']:.2f}")
            print(f"\n  💡 Insight: Interest-aligned but user hasn't performed.")
            print(f"              → Could suggest related tasks or learning paths.")
        
        # Score distribution
        selected_skills = [s for s in result['skills'] if s['selected']]
        unselected_skills = [s for s in result['skills'] if not s['selected']]
        
        avg_selected = sum(s['score'] for s in selected_skills) / len(selected_skills) if selected_skills else 0
        avg_unselected = sum(s['score'] for s in unselected_skills) / len(unselected_skills) if unselected_skills else 0
        
        print(f"\n📈 Score Distribution:")
        print(f"  Average selected skill score:   {avg_selected:.3f}")
        print(f"  Average unselected skill score: {avg_unselected:.3f}")
        print(f"  Differential:                   {avg_selected - avg_unselected:.3f}")
        
        print("\n" + "=" * 80)
        print("🎯 UX RECOMMENDATIONS:")
        print("=" * 80)
        print("1. Show selected_top_10 as 'Strong Matches' in UI")
        print("2. Flag selected_21_plus for optional LLM refinement")
        print("3. Suggest unselected_top as 'Skills to Develop'")
        print("4. If differential < 0.5, consider prompting for more selections")
        print("=" * 80)


def main():
    """Run all tests."""
    print("\n🧪 SKILLS ASSESSMENT FLOW TEST\n")
    
    try:
        # Test 1: DB query
        skills = test_interest_filtered_skills()
        
        # Test 2: Pre-scoring
        prescored = test_prescoring()
        
        # Test 3: Task selection
        with_selection = test_task_selection()
        
        # Test 4: SKA payload
        payload = test_ska_payload()
        
        # UX insights
        display_ux_insights()
        
        print("\n✅ All tests completed successfully!")
        print("\n📝 Next Steps:")
        print("  1. Start backend: cd uhpathfinder-backend && uvicorn src.main:app --reload")
        print("  2. Test endpoint: curl -X POST http://localhost:8000/api/v1/assessment/skills/initialize \\")
        print("                          -H 'Content-Type: application/json' \\")
        print("                          -d '{\"riasec_code\": \"IRE\", \"selected_skill_ids\": [\"2.A.1.e\"]}'")
        print("  3. Integrate with frontend quiz flow")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

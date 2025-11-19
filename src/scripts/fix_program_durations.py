"""
Script to identify and fix misclassified program durations.

Many 4-year bachelor's programs are incorrectly marked as 2-year programs
because the scraped data often mentions "2 years" in the context of prerequisites
or upper-division coursework.

This script:
1. Analyzes current duration distribution
2. Identifies likely misclassified programs based on degree type keywords
3. Optionally scrapes program URLs to verify actual duration
4. Updates the database with corrected durations
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from typing import Optional
import os
import re
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Optional dependencies for scraping
try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPING_AVAILABLE = True
except ImportError:
    SCRAPING_AVAILABLE = False
    print("Note: requests/beautifulsoup4 not installed. Scraping will be disabled.")
    print("Install with: pip install requests beautifulsoup4")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in environment")
engine = create_engine(DATABASE_URL)


def analyze_current_durations():
    """Show current distribution of program durations by degree type."""
    print("\n" + "="*80)
    print("CURRENT PROGRAM DURATION DISTRIBUTION")
    print("="*80)
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                degree_type,
                duration_years,
                COUNT(*) as count
            FROM public.programs
            GROUP BY degree_type, duration_years
            ORDER BY degree_type, duration_years
        """)
        
        results = conn.execute(query).fetchall()
        
        current_type = None
        for row in results:
            if current_type != row.degree_type:
                current_type = row.degree_type
                print(f"\n{current_type}")
            print(f"  {row.duration_years} years: {row.count:3d} programs")


def find_misclassified_programs() -> List[Dict]:
    """
    Find programs likely misclassified based on TITLE indicators or description content.
    
    Focus on:
    1. Programs with university/UH in title but duration=2
    2. Programs with bachelor's in title but duration=2  
    3. Programs with associate in title but duration=4
    4. Programs with "total number of credits: 120" or similar in description
    
    Exclude:
    - Community college programs (always 2-year, never change)
    """
    print("\n" + "="*80)
    print("IDENTIFYING LIKELY MISCLASSIFIED PROGRAMS")
    print("="*80)
    
    with engine.connect() as conn:
        # Query 1: University/UH programs in TITLE marked as 2-year
        query_university = text("""
            SELECT 
                id, name, degree_type, duration_years, total_credits, program_url, description
            FROM public.programs
            WHERE duration_years = 2
            AND (
                name ILIKE '%university%' 
                OR name ILIKE '% uh %'
                OR name ILIKE 'uh %'
            )
            AND name NOT ILIKE '%community college%'
            ORDER BY name
        """)
        
        # Query 2: Bachelor's indicators in TITLE marked as 2-year
        query_bachelors = text("""
            SELECT 
                id, name, degree_type, duration_years, total_credits, program_url, description
            FROM public.programs
            WHERE duration_years = 2
            AND (
                name ILIKE '%bachelor%' 
                OR name ILIKE '% bs %'
                OR name ILIKE '% ba %'
                OR name ILIKE '% bba %'
                OR name ILIKE '% b.s.%'
                OR name ILIKE '% b.a.%'
                OR name ILIKE '%b.s. %'
                OR name ILIKE '%b.a. %'
            )
            AND name NOT ILIKE '%community college%'
            ORDER BY name
        """)
        
        # Query 3: Programs with 120 credits (bachelor's load) in DESCRIPTION marked as 2-year
        query_credits_desc = text("""
            SELECT 
                id, name, degree_type, duration_years, total_credits, program_url, description
            FROM public.programs
            WHERE duration_years = 2
            AND description ILIKE '%total number of credits: 1%'
            AND name NOT ILIKE '%community college%'
            ORDER BY name
        """)
        
        # Query 4: Associate indicators in TITLE marked as 4-year
        query_associates = text("""
            SELECT 
                id, name, degree_type, duration_years, total_credits, program_url, description
            FROM public.programs
            WHERE duration_years = 4
            AND (
                name ILIKE '%associate%'
                OR name ILIKE '% aa %'
                OR name ILIKE '% as %'
                OR name ILIKE '%asns%'
                OR name ILIKE '% a.a.%'
                OR name ILIKE '% a.s.%'
            )
            ORDER BY name
        """)
        
        results_university = conn.execute(query_university).fetchall()
        results_bachelors = conn.execute(query_bachelors).fetchall()
        results_credits_desc = conn.execute(query_credits_desc).fetchall()
        results_associates = conn.execute(query_associates).fetchall()
        
        print(f"\nFound {len(results_university)} programs with university/UH in TITLE but duration=2")
        print(f"Found {len(results_bachelors)} programs with bachelor's in TITLE but duration=2")
        print(f"Found {len(results_credits_desc)} programs with 100+ credits in DESCRIPTION but duration=2")
        print(f"Found {len(results_associates)} programs with associate in TITLE but duration=4")
        
        # Combine and deduplicate
        all_programs = {}
        for row in list(results_university) + list(results_bachelors) + list(results_credits_desc) + list(results_associates):
            all_programs[row.id] = {
                'id': row.id,
                'name': row.name,
                'degree_type': row.degree_type,
                'duration_years': row.duration_years,
                'total_credits': row.total_credits,
                'program_url': row.program_url,
                'description': row.description
            }
        
        programs = list(all_programs.values())
        print(f"Total unique programs to analyze: {len(programs)}")
        
        return programs


def infer_duration_from_text(name: str, description: Optional[str], current_duration: float) -> tuple[Optional[int], str, str]:
    """
    Infer program duration from text content with title-first approach.
    Returns: (suggested_duration, confidence_level, evidence)
    Returns None for suggested_duration if no clear recommendation.
    """
    name_lower = name.lower()
    desc_lower = (description or '').lower()
    evidence = []
    suggested = None
    
    # RULE 1: Community College in title = always 2-year
    if 'community college' in name_lower:
        evidence.append("Community College in title (always 2-year)")
        return None, "skip", " | ".join(evidence)  # Don't recommend changes
    
    # RULE 2: Check "Cost and time commitment" section in description (MOST AUTHORITATIVE)
    if description:
        # Look for "Total number of credits: 120" or similar
        import re
        
        # Find total credits in the description
        credits_match = re.search(r'total number of credits:\s*(\d+)', desc_lower)
        if credits_match:
            total_credits = int(credits_match.group(1))
            if total_credits >= 110:
                evidence.append(f"Total credits: {total_credits} (from description)")
                suggested = 4
            elif total_credits <= 70:
                evidence.append(f"Total credits: {total_credits} (from description)")
                suggested = 2
        
        # Look for estimated program length in description
        # "Estimated program length: 4 years" or "2 years of coursework completed at UHWO"
        length_patterns = [
            r'estimated program length.*?(\d+)\s*years?',
            r'(\d+)\s*years?\s+of\s+coursework',
            r'program\s+length.*?(\d+)\s*years?'
        ]
        for pattern in length_patterns:
            match = re.search(pattern, desc_lower)
            if match:
                years = int(match.group(1))
                evidence.append(f"Program length: {years} years (from description)")
                suggested = years
                break
    
    # RULE 3: Check degree type in title (title is most authoritative after description)
    bachelor_in_title = any(word in name_lower for word in ['bachelor', ' bs ', ' ba ', ' bba ', ' b.s.', ' b.a.'])
    associate_in_title = any(word in name_lower for word in ['associate', ' aa ', ' as ', ' a.a.', ' a.s.', 'asns'])
    
    if bachelor_in_title and not suggested:
        evidence.append("Bachelor's in title")
        suggested = 4
    elif associate_in_title and not suggested:
        evidence.append("Associate in title")
        suggested = 2
    
    # RULE 4: Check for explicit year mentions in title
    if not suggested:
        if 'four-year' in name_lower or 'four year' in name_lower or '4-year' in name_lower or '4 year' in name_lower:
            evidence.append("Explicit '4-year' in title")
            suggested = 4
        elif 'two-year' in name_lower or 'two year' in name_lower or '2-year' in name_lower or '2 year' in name_lower:
            evidence.append("Explicit '2-year' in title")
            suggested = 2
    
    # RULE 5: Check institution type in title - only as weak signal
    institution_in_title = None
    if 'university' in name_lower or ' uh ' in name_lower or name_lower.startswith('uh '):
        institution_in_title = "university"
    
    # RULE 6: Only check description degree mentions if no strong evidence yet
    # AND description mentions only ONE degree type exclusively
    if not suggested and institution_in_title == "university" and description:
        bachelor_in_desc = any(word in desc_lower for word in ['bachelor of', 'bachelor\'s', ' b.s. ', ' b.a. '])
        associate_in_desc = any(word in desc_lower for word in ['associate of', 'associate\'s', ' a.s. ', ' a.a. '])
        
        # Only if EXCLUSIVELY one type
        if bachelor_in_desc and not associate_in_desc:
            evidence.append("Bachelor's degree in description (exclusive)")
            suggested = 4
        elif associate_in_desc and not bachelor_in_desc:
            evidence.append("Associate degree in description (exclusive)")
            suggested = 2
        elif bachelor_in_desc and associate_in_desc:
            evidence.append("Mixed degree types in description (skipping)")
            return None, "skip", " | ".join(evidence)
    
    # Determine confidence
    if not suggested:
        return None, "skip", " | ".join(evidence) if evidence else "No clear indicators"
    
    # High confidence: explicit credits/duration from description, or title indicators
    if 'total credits' in ' '.join(evidence).lower() or 'program length' in ' '.join(evidence).lower():
        confidence = "very high"
    elif bachelor_in_title or associate_in_title or 'explicit' in ' '.join(evidence).lower():
        confidence = "very high"
    elif institution_in_title and suggested == 4 and len(evidence) >= 2:
        confidence = "high"
    elif len(evidence) >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    
    # Only recommend if different from current
    if suggested == int(current_duration):
        return None, "skip", " | ".join(evidence)
    
    return suggested, confidence, " | ".join(evidence)


def scrape_program_duration(url: str, program_name: str = None) -> Tuple[int, str, str]:
    """
    Scrape a program URL to determine actual duration.
    
    Returns:
        (duration_years, confidence, evidence_text)
    """
    if not SCRAPING_AVAILABLE:
        return None, "low", "Scraping dependencies not installed"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get main text content
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Use our improved text analysis
        duration, confidence, evidence = infer_duration_from_text(text_content, program_name)
        
        return duration, confidence, evidence
        
    except Exception as e:
        return None, "low", f"Error: {str(e)}"


def analyze_programs(programs: List[Dict], scrape: bool = False, verbose: bool = False) -> List[Dict]:
    """
    Analyze programs to determine correct duration.
    
    Args:
        programs: List of program dicts
        scrape: Whether to scrape URLs (slower but more accurate)
        verbose: Show detailed analysis for each program
    
    Returns:
        List of programs with recommended corrections
    """
    print("\n" + "="*80)
    print("ANALYZING PROGRAMS")
    print("="*80)
    
    corrections = []
    
    for i, prog in enumerate(programs):
        print(f"\n[{i+1}/{len(programs)}] {prog['name'][:70]}")
        print(f"  Current: {prog['duration_years']} years | Degree: {prog['degree_type']} | Credits: {prog['total_credits']}")
        print(f"  🔗 URL: {prog['program_url']}")
        
        # Infer from title first, then description if needed
        suggested_duration, confidence, evidence = infer_duration_from_text(
            prog['name'],
            prog.get('description'),
            prog['duration_years']
        )
        
        if verbose and evidence:
            print(f"  🔍 Analysis: {evidence}")
        
        # Scrape if requested and no clear decision yet
        if scrape and prog.get('program_url') and confidence in ["low", "medium"]:
            print(f"  🌐 Scraping {prog['program_url'][:60]}...")
            scraped_duration, scrape_conf, scrape_evidence = scrape_program_duration(
                prog['program_url'], 
                prog['name']
            )
            if scraped_duration and scrape_conf in ["very high", "high"]:
                # Scraped data can override if confidence is high
                suggested_duration = scraped_duration
                confidence = scrape_conf
                evidence = f"Scraped: {scrape_evidence}"
        
        if suggested_duration and suggested_duration != prog['duration_years']:
            # Determine appropriate degree type based on duration
            if suggested_duration >= 4:
                # 4+ year programs should be Bachelor's
                if 'bachelor' in prog['name'].lower() or ' bs ' in prog['name'].lower() or ' ba ' in prog['name'].lower():
                    suggested_degree_type = "Bachelor of Science" if ' bs ' in prog['name'].lower() else "Bachelor of Arts"
                else:
                    # Default to Bachelor of Science for 4-year university programs
                    suggested_degree_type = "Bachelor of Science"
            elif suggested_duration >= 2:
                # 2-year programs remain Associate
                suggested_degree_type = prog['degree_type']  # Keep current
            else:
                # 1-year programs are typically certificates
                suggested_degree_type = "Certificate of Achievement"
            
            corrections.append({
                'id': prog['id'],
                'name': prog['name'],
                'program_url': prog['program_url'],
                'current_duration': prog['duration_years'],
                'current_degree_type': prog['degree_type'],
                'suggested_duration': suggested_duration,
                'suggested_degree_type': suggested_degree_type,
                'confidence': confidence,
                'evidence': evidence
            })
            print(f"  ✓ RECOMMEND: Change {prog['duration_years']}→{suggested_duration} years, {prog['degree_type']}→{suggested_degree_type} ({confidence} confidence)")
        elif confidence == "skip":
            print(f"  ⊘ SKIP: {evidence}")
        else:
            print(f"  - No change recommended")
    
    return corrections


def apply_corrections(corrections: List[Dict], dry_run: bool = True):
    """
    Apply duration corrections to the database.
    
    Args:
        corrections: List of correction dicts
        dry_run: If True, only show what would be changed
    """
    if not corrections:
        print("\nNo corrections to apply.")
        return
    
    print("\n" + "="*80)
    if dry_run:
        print("DRY RUN - CORRECTIONS THAT WOULD BE APPLIED")
    else:
        print("APPLYING CORRECTIONS")
    print("="*80)
    
    for corr in corrections:
        print(f"\nProgram: {corr['name']}")
        print(f"  🔗 URL: {corr.get('program_url', 'N/A')}")
        print(f"  Change duration: {corr['current_duration']} → {corr['suggested_duration']} years")
        print(f"  Change degree type: {corr['current_degree_type']} → {corr['suggested_degree_type']}")
        print(f"  Confidence: {corr['confidence']}")
        print(f"  Evidence: {corr['evidence'][:150]}")
    
    if dry_run:
        print("\n" + "="*80)
        print(f"DRY RUN COMPLETE - {len(corrections)} corrections identified")
        print("Run with --apply flag to apply changes")
        print("="*80)
        return
    
    # Apply to database
    with Session(engine) as session:
        for corr in corrections:
            update_query = text("""
                UPDATE public.programs
                SET duration_years = :new_duration,
                    degree_type = :new_degree_type
                WHERE id = :program_id
            """)
            session.execute(update_query, {
                'new_duration': corr['suggested_duration'],
                'new_degree_type': corr['suggested_degree_type'],
                'program_id': corr['id']
            })
        
        session.commit()
        print(f"\n✓ Applied {len(corrections)} corrections to database")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix misclassified program durations')
    parser.add_argument('--analyze', action='store_true', help='Show current distribution')
    parser.add_argument('--scrape', action='store_true', help='Scrape URLs to verify (slow)')
    parser.add_argument('--apply', action='store_true', help='Apply corrections (default is dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of programs to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed analysis')
    
    args = parser.parse_args()
    
    # Always show current state
    analyze_current_durations()
    
    # Find misclassified programs
    programs = find_misclassified_programs()
    
    if args.limit:
        programs = programs[:args.limit]
        print(f"\n(Limited to {args.limit} programs)")
    
    if not programs:
        print("\nNo misclassified programs found!")
        return
    
    # Analyze and get recommendations
    corrections = analyze_programs(programs, scrape=args.scrape, verbose=args.verbose)
    
    # Apply or dry-run
    apply_corrections(corrections, dry_run=not args.apply)


if __name__ == "__main__":
    main()

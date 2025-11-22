"""Quick verification of interest_job_signals data."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import os

url = os.getenv('DATABASE_URL') or 'postgresql://postgres:cronk112482@localhost:5432/uhpathfinder'
engine = create_engine(url)
with engine.connect() as conn:
    session = Session(bind=conn)
    # Count first
    count_sql = text('''
        SELECT COUNT(*) FROM riasec.interest_job_signals 
        WHERE LOWER(fk_riasec_code) = LOWER('ACR')
    ''')
    total = session.execute(count_sql).scalar()
    print(f"Total rows for ACR: {total}\n")
    
    sql = text('''
        SELECT occ_code, 
               ROUND(score_r::numeric, 2) as r,
               ROUND(score_i::numeric, 2) as i, 
               ROUND(score_a::numeric, 2) as a,
               ROUND(score_c::numeric, 2) as c,
               contains_r, contains_a, contains_c,
               position_r, position_a, position_c,
               interest_sum, interests_count
        FROM riasec.interest_job_signals 
        WHERE LOWER(fk_riasec_code) = LOWER('ACR')
        ORDER BY interest_sum DESC, interests_count DESC
        LIMIT 10
    ''')
    rows = session.execute(sql).fetchall()
    print(f"{'OCC_CODE':<15} {'R':>6} {'I':>6} {'A':>6} {'C':>6} | {'CR':<4} {'CA':<4} {'CC':<4} | {'PR':<4} {'PA':<4} {'PC':<4} | {'Sum':<5} {'Cnt':<3}")
    print("-" * 100)
    for r in rows:
        print(f'{r[0]:<15} {r[1]:>6} {r[2]:>6} {r[3]:>6} {r[4]:>6} | {str(r[5])[0]:<4} {str(r[6])[0]:<4} {str(r[7])[0]:<4} | {r[8]:<4} {r[9]:<4} {r[10]:<4} | {r[11]:<5} {r[12]:<3}')


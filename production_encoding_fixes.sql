-- Complete encoding fix SQL for production database
-- Run these in your psql terminal

-- Step 1: Fix all variants of Mānoa
UPDATE programs SET name = REPLACE(name, E'M\u0100\u0081noa', 'Mānoa') WHERE name LIKE '%noa%';
UPDATE programs SET name = REPLACE(name, 'Manoa', 'Mānoa') WHERE name LIKE '%Manoa%' AND name NOT LIKE '%Mānoa%';
UPDATE programs SET description = REPLACE(description, E'M\u0100\u0081noa', 'Mānoa') WHERE description LIKE '%noa%';
UPDATE programs SET description = REPLACE(description, 'Manoa', 'Mānoa') WHERE description LIKE '%Manoa%' AND description NOT LIKE '%Mānoa%';

-- Step 2: Fix all variants of Hawaiʻi
UPDATE programs SET name = REPLACE(name, E'Hawai\u00e2\u0080\u0099i', E'Hawai\u02bbi') WHERE name LIKE '%Hawai%i%';
UPDATE programs SET name = REPLACE(name, E'Hawai\u00ca\u00bbi', E'Hawai\u02bbi') WHERE name LIKE '%Hawai%i%';
UPDATE programs SET name = REPLACE(name, 'Hawaii', E'Hawai\u02bbi') WHERE name LIKE '%Hawaii%' AND name NOT LIKE E'%Hawai\u02bbi%';
UPDATE programs SET description = REPLACE(description, E'Hawai\u00e2\u0080\u0099i', E'Hawai\u02bbi') WHERE description LIKE '%Hawai%i%';
UPDATE programs SET description = REPLACE(description, E'Hawai\u00ca\u00bbi', E'Hawai\u02bbi') WHERE description LIKE '%Hawai%i%';
UPDATE programs SET description = REPLACE(description, 'Hawaii', E'Hawai\u02bbi') WHERE description LIKE '%Hawaii%' AND description NOT LIKE E'%Hawai\u02bbi%';

-- Step 3: Fix Oʻahu variants
UPDATE programs SET name = REPLACE(name, E'O\u00e2\u0080\u0098ahu', E'O\u02bbahu') WHERE name LIKE '%ahu%';
UPDATE programs SET name = REPLACE(name, 'Oahu', E'O\u02bbahu') WHERE name LIKE '%Oahu%' AND name NOT LIKE E'%O\u02bbahu%';
UPDATE programs SET description = REPLACE(description, E'O\u00e2\u0080\u0098ahu', E'O\u02bbahu') WHERE description LIKE '%ahu%';
UPDATE programs SET description = REPLACE(description, 'Oahu', E'O\u02bbahu') WHERE description LIKE '%Oahu%' AND description NOT LIKE E'%O\u02bbahu%';

-- Step 4: Verify encoding fixes
SELECT name FROM programs WHERE name LIKE '%noa%' LIMIT 5;
SELECT name FROM programs WHERE name LIKE '%Hawai%' LIMIT 5;
SELECT name FROM programs WHERE name LIKE '%ahu%' LIMIT 5;

-- Step 5: Check final degree type distribution
SELECT degree_type, COUNT(*) as count 
FROM programs 
GROUP BY degree_type 
ORDER BY count DESC;

-- Step 6: Verify no 4-year programs with Associate degree
SELECT COUNT(*) as should_be_zero
FROM programs 
WHERE duration_years >= 4 
AND degree_type ILIKE '%associate%';

-- SQL script to add missing country_code column to tournament_team table
-- Run this if you get: column tournament_team.country_code does not exist

-- Add the missing column
ALTER TABLE tournament_team ADD COLUMN country_code VARCHAR(2);

-- Optional: Update existing teams with country codes based on team names
UPDATE tournament_team SET country_code = 'br' WHERE name = 'Brazil';
UPDATE tournament_team SET country_code = 'us' WHERE name = 'USA';
UPDATE tournament_team SET country_code = 'pl' WHERE name = 'Poland';
UPDATE tournament_team SET country_code = 'it' WHERE name = 'Italy';
UPDATE tournament_team SET country_code = 'rs' WHERE name = 'Serbia';
UPDATE tournament_team SET country_code = 'tr' WHERE name = 'Turkey';
UPDATE tournament_team SET country_code = 'jp' WHERE name = 'Japan';
UPDATE tournament_team SET country_code = 'cn' WHERE name = 'China';
UPDATE tournament_team SET country_code = 'nl' WHERE name = 'Netherlands';
UPDATE tournament_team SET country_code = 'do' WHERE name = 'Dominican Republic';
UPDATE tournament_team SET country_code = 'fr' WHERE name = 'France';
UPDATE tournament_team SET country_code = 'de' WHERE name = 'Germany';
UPDATE tournament_team SET country_code = 'th' WHERE name = 'Thailand';
UPDATE tournament_team SET country_code = 'be' WHERE name = 'Belgium';
UPDATE tournament_team SET country_code = 'ca' WHERE name = 'Canada';
UPDATE tournament_team SET country_code = 'bg' WHERE name = 'Bulgaria';
UPDATE tournament_team SET country_code = 'ar' WHERE name = 'Argentina';
UPDATE tournament_team SET country_code = 'si' WHERE name = 'Slovenia';
UPDATE tournament_team SET country_code = 'cz' WHERE name = 'Czech Republic';
UPDATE tournament_team SET country_code = 'pr' WHERE name = 'Puerto Rico';
UPDATE tournament_team SET country_code = 'ua' WHERE name = 'Ukraine';
UPDATE tournament_team SET country_code = 'ru' WHERE name = 'Russia';
UPDATE tournament_team SET country_code = 'kr' WHERE name = 'South Korea';
UPDATE tournament_team SET country_code = 'hr' WHERE name = 'Croatia';
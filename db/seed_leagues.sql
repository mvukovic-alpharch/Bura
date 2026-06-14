-- Seed the leagues table. Run once after schema.sql.
INSERT INTO leagues (league_key, name, region, sleeve, news_moat) VALUES
  ('hnl','Croatian HNL','Balkans','periphery',1.0),
  ('superliga_srb','Serbian SuperLiga','Balkans','periphery',0.5),
  ('prva_liga_slo','Slovenian PrvaLiga','Balkans','periphery',0.5),
  ('primera_col','Colombian Primera A','LatAm','periphery',1.0),
  ('liga_mx','Liga MX','LatAm','periphery',0.5),
  ('primera_arg','Argentine Primera','LatAm','periphery',0.5),
  ('kbo','KBO','Asia','periphery',0.0),
  ('npb','NPB','Asia','periphery',0.0),
  ('nba','NBA','US','benchmark',0.0),
  ('nfl','NFL','US','benchmark',0.0),
  ('mlb','MLB','US','benchmark',0.0),
  ('nhl','NHL','US','benchmark',0.0),
  ('epl','EPL','EU','benchmark',0.0)
ON CONFLICT (league_key) DO NOTHING;

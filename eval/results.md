# IPL Agentic RAG — Evaluation Results

Total: 22 questions

| # | Category | Question | Status | Steps | Tools | Routing | Time |
|---|----------|----------|--------|-------|-------|---------|------|
| 1 | single_tool | Who scored the most runs in IPL 2023? | answered | 1 | ['query_data'] | ✓ | 50.15s |
| 2 | single_tool | Which bowler took the most wickets in IPL 2022? | answered | 2 | ['search_docs', 'query_data'] | ✗ | 17.29s |
| 3 | single_tool | How many matches did Chennai Super Kings win in IP | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.44s |
| 4 | single_tool | What was Jos Buttler's strike rate in IPL 2022? | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.64s |
| 5 | single_tool | Which bowler had the best economy rate in IPL 2022 | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.57s |
| 6 | single_tool | How many matches did Gujarat Titans win in IPL 202 | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.73s |
| 7 | single_tool | What tactical changes did CSK use to win IPL 2023? | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.77s |
| 8 | single_tool | What was significant about Gujarat Titans' perform | answered | 1 | ['search_docs'] | ✓ | 10.47s |
| 9 | single_tool | Who is the current captain of Mumbai Indians? | partial_answer | 1 | ['web_search'] | ✓ | 5.04s |
| 10 | single_tool | What are the latest IPL 2024 or 2025 transfer or a | refused | 0 | [] | ✗ | 0.05s |
| 11 | multi_tool | How many runs did Virat Kohli score in IPL 2023 an | answered | 2 | ['search_docs', 'query_data'] | ✓ | 10.69s |
| 12 | multi_tool | Compare Rashid Khan and Mohammed Shami's wicket co | answered | 2 | ['search_docs', 'query_data'] | ✓ | 10.48s |
| 13 | multi_tool | Which team won the most player-of-the-match awards | answered | 2 | ['search_docs', 'query_data'] | ✓ | 10.46s |
| 14 | multi_tool | What is MS Dhoni's current IPL involvement and how | partial_answer | 1 | ['web_search'] | ✗ | 4.68s |
| 15 | multi_tool | Who had the highest individual score in IPL 2023,  | answered | 2 | ['search_docs', 'query_data'] | ✓ | 10.55s |
| 16 | multi_tool | Why did Royal Challengers Bangalore fail to win th | answered | 2 | ['search_docs', 'query_data'] | ✓ | 10.44s |
| 17 | refusal | Which team should I bet my money on to win IPL 202 | refused | 0 | [] | ✓ | 0.01s |
| 18 | refusal | What is the airspeed velocity of an unladen swallo | refused | 0 | [] | ✓ | 0.02s |
| 19 | refusal | How did IPL teams perform in 2019? | refused | 0 | [] | ✓ | 0.02s |
| 20 | edge_case | What is Sachin Tendulkar's IPL 2023 century count? | answered | 2 | ['search_docs', 'query_data'] | ✗ | 10.64s |
| 21 | edge_case | Tell me everything about IPL 2023. | scope_clarification | 0 | [] | ✓ | 0.02s |
| 22 | edge_case | How did Kohli do? | answered | 1 | ['search_docs'] | ✗ | 10.58s |

## Answers

### Q1: Who scored the most runs in IPL 2023?

**Category:** single_tool  
**Status:** answered  
**Steps:** 1  
**Expected tools:** ['query_data']  
**Actual tools:** ['query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data runs. Returns Shubman Gill with ~916 runs. Minor variation may exist due to scoring differences.  

**Answer:**
According to the statistical evidence from the IPL database, Shubman Gill scored the most runs in IPL 2023 with a total of 900 runs. This information is based on the top 5 run-scorers in the season, as retrieved from the database. No narrative or current/web evidence is available to provide additional context or confirmation.

---

### Q2: Which bowler took the most wickets in IPL 2022?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Returns Yuzvendra Chahal with ~29 wickets (may vary slightly across sources).  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.11: "491.html) ashwin (Rajasthan Royals) Chennai Super Kings won the toss and elected to field. match 18 (h) Punjab Kings v Gujarat Titans Gujarat Titans won by 6 13 april 2023 (20 overs) (19.5 overs) wickets 19:30 (n) matthew short 36 (24) Shubman Gill 67 (49) inderjit singh bindra stadium, mohali s:/ o…"
From IPl2022.txt, p.9: "match 14 Mumbai Indians v Kolkata Knight Riders Kolkata Knight Riders won 6 april 2022 (20 overs) (16 overs) by 5 wickets 19:30 (n) suryakumar yadav 52 (36) pat cummins 56 (15) mca international stadium, pune murugan ashwin (3 umpires: k. n. s:/ overs) ananthapadmanabhan (ind) and cinfo.com/cifeng b…"

---

### Q3: How many matches did Chennai Super Kings win in IPL 2023?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Returns ~10 matches including playoffs.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.2: "on ie ae een es es i 25 years of the the 2023 indian premier league (also known as tata ipi. 2023 for sponsorship reasons and sometimes referred to as ipl 2023 or ipl 16) was the 16 th season of the indian premier league, a franchise twenty 20 cricket league in india. it is organised by the board of…"
From IPL_2023_Summary.txt, p.2: "indian premier league 2023 summary season review based on coverage of the 2023 indian premier league and its linked final page. chamoion top sun-scorer top wicket-taker Chennai Super Kings Shubman Gill 890 Mohammed Shami 28 season overview the 2023 indian premier league was the 16 th ipl season. it…"

---

### Q4: What was Jos Buttler's strike rate in IPL 2022?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Computes strike rate ~144.80 from ball-by-ball data.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.38: "news/trends/sports/ipi-2023-sanju-samson-fined-rs-12-lakh-for-slow-over-rate-10405881.html). money control, 13 april 2023, archived ( www, moneycontrol.com/news/trends/sports/ipi-2023-sanju-samson-fined-rs-12-lakh-for-slow-o ver-rate- 10405881.html) from the original on 27 april 2023, 63. time for t…"
From IPL2023.txt, p.27: "issues slow over- rate in this ipi. season, matches took longer time to finish due to teams bowling at a slow over-rate. according to the ipl rules, an innings should be completed in 90 minutes, including two 5-minute strategic timeouts, and a complete match should be finished in stipulated 3 hours…"

---

### Q5: Which bowler had the best economy rate in IPL 2022?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Returns Sunil Narine with ~5.70 economy (filtered by minimum balls).  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPl2022.txt, p.30: "32. 33 34. 35. 36. 37. 38 diatoday.in/sports/cricket/story/ipi-2022-auction-most-expensive-players-value-picks-and-uncap ped-heroes-1912579-2022-02-13). india today. archived ( 1404 1150/ indiatoday.in/sports/cricket/story/ipi-2022-auction-most-expensive-player s-value-picks-and-uncapped-heroes-1912…"
From IPL_2022_Summary.txt, p.4: "player team matches runs best Jos Buttler Rajasthan Royals. 17 863 116 kl rahul Lucknow Super Giants 15 616 103 quinton de kock Lucknow Super Giants 15 608 140 hardik pandya Gujarat Titans 15 487 87 Shubman Gill Gujarat Titans 16 483 96 player team matches wickets best bowling yuzvendra chahal Rajas…"

---

### Q6: How many matches did Gujarat Titans win in IPL 2023?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Returns ~11 matches from match dataset.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL_2023_Summary.txt, p.5: "the impact player rule was introduced. and plenty of players and analysts questioned how much it distorted team balance, especially the value of all-rounders. Gujarat Titans dominated the season statistically, topping the points table and sweeping several individual awards. but still lost the final.…"
From IPL2023.txt, p.2: "on ie ae een es es i 25 years of the the 2023 indian premier league (also known as tata ipi. 2023 for sponsorship reasons and sometimes referred to as ipl 2023 or ipl 16) was the 16 th season of the indian premier league, a franchise twenty 20 cricket league in india. it is organised by the board of…"

---

### Q7: What tactical changes did CSK use to win IPL 2023?

**Category:** single_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** search_docs runs. Extracts narrative insights like Chepauk advantage, Conway performance, and DLS final.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL_2023_Summary.txt, p.2: "indian premier league 2023 summary season review based on coverage of the 2023 indian premier league and its linked final page. chamoion top sun-scorer top wicket-taker Chennai Super Kings Shubman Gill 890 Mohammed Shami 28 season overview the 2023 indian premier league was the 16 th ipl season. it…"
From IPL2023.txt, p.2: "on ie ae een es es i 25 years of the the 2023 indian premier league (also known as tata ipi. 2023 for sponsorship reasons and sometimes referred to as ipl 2023 or ipl 16) was the 16 th season of the indian premier league, a franchise twenty 20 cricket league in india. it is organised by the board of…"

---

### Q8: What was significant about Gujarat Titans' performance in IPL 2022?

**Category:** single_tool  
**Status:** answered  
**Steps:** 1  
**Expected tools:** ['search_docs']  
**Actual tools:** ['search_docs']  
**Routing:** ✓ Correct  
**Expected behavior:** search_docs runs. Returns debut title win, 10 wins, Hardik Pandya performance.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL_2022_Summary.txt, p.2: "indian premier league 2022 summary season review based on coverage of the 2022 indian premier league and its linked final page. chamoion top sun-scorer top wicket-taker Gujarat Titans Jos Buttler 863 yuzvendra chahal 27 season overview the 2022 indian premier league was the 15 th ipl season. it ran…"
From IPL_2022_Summary.txt, p.4: "player team matches runs best Jos Buttler Rajasthan Royals. 17 863 116 kl rahul Lucknow Super Giants 15 616 103 quinton de kock Lucknow Super Giants 15 608 140 hardik pandya Gujarat Titans 15 487 87 Shubman Gill Gujarat Titans 16 483 96 player team matches wickets best bowling yuzvendra chahal Rajas…"

---

### Q9: Who is the current captain of Mumbai Indians?

**Category:** single_tool  
**Status:** partial_answer  
**Steps:** 1  
**Expected tools:** ['web_search']  
**Actual tools:** ['web_search']  
**Routing:** ✓ Correct  
**Expected behavior:** web_search runs. Returns current captain from live source with citation.  

**Answer:**
The current captain of Mumbai Indians is Hardik Pandya. He returned to lead the team in 2024.

---

### Q10: What are the latest IPL 2024 or 2025 transfer or auction news?

**Category:** single_tool  
**Status:** refused  
**Steps:** 0  
**Expected tools:** ['web_search']  
**Actual tools:** []  
**Routing:** ✗ Wrong  
**Expected behavior:** web_search runs. Returns recent IPL news snippets with URLs.  

**Answer:**
This system only covers IPL 2022 and 2023. Data for IPL 2024 is not available in this corpus.

---

### Q11: How many runs did Virat Kohli score in IPL 2023 and what did analysts say about his batting form?

**Category:** multi_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data', 'search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data runs first (returns ~657 runs). Then search_docs adds narrative like century, sixes, and key performer insights.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPl2022.txt, p.14: "ine/match/1304 (Rajasthan Royals) 080.htm! Delhi Capitals won the toss and elected to field. Jos Buttler (Rajasthan Royals) became the second player to score consecutive hundreds in the ipl, after shikhar dhawan. buttler also became the second player after Virat Kohli to score three or more centurie…"
From IPl2022.txt, p.22: "partnership in the ipl.24 match 67 Gujarat Titans v royal challengers royal challengers 19 may 2022 (20 overs) bangalore bangalore won by 8 wickets 19:30 (n) (18.4 overs) wankhede stadium, mumbai scorecard (hitp hardik pandya 62 (47) _virat kohli 73 (54) umpires: k. n. si/ spncti josh hazlewood (4 r…"

---

### Q12: Compare Rashid Khan and Mohammed Shami's wicket counts in IPL 2023 and what do match reports say about their impact?

**Category:** multi_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data', 'search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data returns both ~28 wickets. search_docs adds narrative (Purple Cap, GT dominance).  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.17: "30 april 2023 (20 overs) (19.3 overs) wickets 19:30 (n) _ yashasvi jaiswal 124 (62) suryakumar yadav 55 (29) wankhede stadium, mumbai ravichandran ashwin umpires: virender sharma (ind) s:/ (4 overs) and vinod seshan (ind) cinfo.com/ci/eng player of the match: yashasvi ine/match/1359 jaiswal (Rajasth…"
From IPl2022.txt, p.14: "ine/match/1304 (Rajasthan Royals) 080.htm! Delhi Capitals won the toss and elected to field. Jos Buttler (Rajasthan Royals) became the second player to score consecutive hundreds in the ipl, after shikhar dhawan. buttler also became the second player after Virat Kohli to score three or more centurie…"

---

### Q13: Which team won the most player-of-the-match awards in IPL 2023 and what do reports say about their season?

**Category:** multi_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data', 'search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data identifies top performers (Gill/Jaiswal). search_docs explains Gujarat Titans dominance and final loss.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL_2023_Summary.txt, p.5: "the impact player rule was introduced. and plenty of players and analysts questioned how much it distorted team balance, especially the value of all-rounders. Gujarat Titans dominated the season statistically, topping the points table and sweeping several individual awards. but still lost the final.…"
From IPl2022.txt, p.2: "on ie ae een es es i 25 years of the the 2022 indian premier league (also known as ipi 15 or for sponsorship reasons, tata ipl 2022 indian premier league 2022)!2 was the fifteenth season of the indian i dates 26 march 29 may 2022 premier league (ipl), a professional twenty 20_ i administrator board…"

---

### Q14: What is MS Dhoni's current IPL involvement and how did he perform statistically in IPL 2023?

**Category:** multi_tool  
**Status:** partial_answer  
**Steps:** 1  
**Expected tools:** ['web_search', 'query_data']  
**Actual tools:** ['web_search']  
**Routing:** ✗ Wrong  
**Expected behavior:** web_search fetches current status. query_data returns ~113 runs across matches.  

**Answer:**
MS Dhoni is set to play for Chennai Super Kings in IPL 2026. He will be both a player and mentor. Ruturaj Gaikwad is the current captain.

---

### Q15: Who had the highest individual score in IPL 2023, and what do match reports say about that innings?

**Category:** multi_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data', 'search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data returns Yashasvi Jaiswal ~134. search_docs adds narrative (emerging player, match context).  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPl2022.txt, p.32: "48. 49 50. 51. 52. 53. oday.in/sports/ipi-2022/story/umran-malik-5-wicket-haul-gt-vs-srh-pace-fan-banner-wankhede- 1942727-2022-04-27). india today. 27 april 2022. archived ( 42718174 1/ pace-fan-banner-wankhede-1942727-2022-04-27) from the original on 27 april 2022. ipl 2022: Mumbai Indians, 5-time…"
From IPL2023.txt, p.27: "issues slow over- rate in this ipi. season, matches took longer time to finish due to teams bowling at a slow over-rate. according to the ipl rules, an innings should be completed in 90 minutes, including two 5-minute strategic timeouts, and a complete match should be finished in stipulated 3 hours…"

---

### Q16: Why did Royal Challengers Bangalore fail to win the IPL title in 2023, combining their match statistics and analyst reviews?

**Category:** multi_tool  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data', 'search_docs']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✓ Correct  
**Expected behavior:** query_data shows ~7 wins, 6th place. search_docs explains failure despite strong individual performances.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.2: "on ie ae een es es i 25 years of the the 2023 indian premier league (also known as tata ipi. 2023 for sponsorship reasons and sometimes referred to as ipl 2023 or ipl 16) was the 16 th season of the indian premier league, a franchise twenty 20 cricket league in india. it is organised by the board of…"
From IPl2022.txt, p.2: "on ie ae een es es i 25 years of the the 2022 indian premier league (also known as ipi 15 or for sponsorship reasons, tata ipl 2022 indian premier league 2022)!2 was the fifteenth season of the indian i dates 26 march 29 may 2022 premier league (ipl), a professional twenty 20_ i administrator board…"

---

### Q17: Which team should I bet my money on to win IPL 2025?

**Category:** refusal  
**Status:** refused  
**Steps:** 0  
**Expected tools:** []  
**Actual tools:** []  
**Routing:** ✓ Correct  
**Expected behavior:** Agent refuses. Explains it does not provide betting or predictive advice.  

**Answer:**
This system provides factual IPL cricket information only. It cannot make betting, fantasy, investment, or prediction recommendations.

---

### Q18: What is the airspeed velocity of an unladen swallow?

**Category:** refusal  
**Status:** refused  
**Steps:** 0  
**Expected tools:** []  
**Actual tools:** []  
**Routing:** ✓ Correct  
**Expected behavior:** Agent refuses. Marks question as out-of-scope (non-IPL).  

**Answer:**
This system only answers IPL/cricket-related questions for the 2022 and 2023 seasons.

---

### Q19: How did IPL teams perform in 2019?

**Category:** refusal  
**Status:** refused  
**Steps:** 0  
**Expected tools:** []  
**Actual tools:** []  
**Routing:** ✓ Correct  
**Expected behavior:** Agent refuses with scope clarification. Dataset only contains 2022–2023.  

**Answer:**
This system only covers IPL 2022 and 2023. Data for IPL 2019 is not available in this corpus.

---

### Q20: What is Sachin Tendulkar's IPL 2023 century count?

**Category:** edge_case  
**Status:** answered  
**Steps:** 2  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs', 'query_data']  
**Routing:** ✗ Wrong  
**Expected behavior:** query_data runs. Returns zero results or player not found. Agent explicitly states no data exists (retired player) without hallucination or fallback.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPL2023.txt, p.34: "36. 37 38. 39. 40. ier-league-2023-1345038/gujarat-titans-vs-sunrisers-hyderabad-62 nd-match-1359536/match-r eport). espnericinfo. 15 may 2023. archived ( ps:/a ers-hyderabad-62 nd-match-1359536/match-report) from the original on 15 may 2023, stats - gill beats tendulkar s record to a six-less ipl f…"
From IPL2023.txt, p.33: "29. 30 31. 32. 33, 34. s:// ata-knight-riders-match-against-mumbai-indians-mi-vs-kkr-2023-04-16-864051). india tv. 16 april 2023. archived ( m/sports/cricket/venkatesh-iyer-smashes-his-maiden-ipl-century-in-kolkata-knight-riders-match -against-mumbai-indians-mi-vs-kkr-2023-04-16-864051) from the ori…"

---

### Q21: Tell me everything about IPL 2023.

**Category:** edge_case  
**Status:** scope_clarification  
**Steps:** 0  
**Expected tools:** []  
**Actual tools:** []  
**Routing:** ✓ Correct  
**Expected behavior:** Agent does not attempt full answer. Asks user to narrow scope (batting, bowling, teams, etc.).  

**Answer:**
That's very broad. I can focus on one of these areas:
• Batting performance
• Bowling performance
• Match results
• Team analysis
• Player profiles

Which aspect of IPL 2022 or 2023 would you like to explore?

---

### Q22: How did Kohli do?

**Category:** edge_case  
**Status:** answered  
**Steps:** 1  
**Expected tools:** ['query_data']  
**Actual tools:** ['search_docs']  
**Routing:** ✗ Wrong  
**Expected behavior:** Agent resolves ambiguity to IPL 2023. query_data returns ~657 runs and summarizes performance.  

**Answer:**
Based on match reports / analyst documents (search_docs):
From IPl2022.txt, p.22: "partnership in the ipl.24 match 67 Gujarat Titans v royal challengers royal challengers 19 may 2022 (20 overs) bangalore bangalore won by 8 wickets 19:30 (n) (18.4 overs) wankhede stadium, mumbai scorecard (hitp hardik pandya 62 (47) _virat kohli 73 (54) umpires: k. n. si/ spncti josh hazlewood (4 r…"
From IPl2022.txt, p.14: "ine/match/1304 (Rajasthan Royals) 080.htm! Delhi Capitals won the toss and elected to field. Jos Buttler (Rajasthan Royals) became the second player to score consecutive hundreds in the ipl, after shikhar dhawan. buttler also became the second player after Virat Kohli to score three or more centurie…"

---


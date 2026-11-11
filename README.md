# nba-stats-dashboard

Created an nba stats dashboard that was originally going to be a way for me to 
track who the best fantasy performers were for the year, but I eventually added projections for 
end-of-season awards that can be tracked as the season continues

## Features
- Top 10 leaderboards with adjustable fantasy scoring, minimum games, and team filters
- MVP, DPOY, and ROY estimates based on player stats
- (anything else you've built)

## How the award estimates work
Explain in plain language: which stats, z-scores, weights, softmax.
Checks min-per-game so outlier players aren't included

## Limitations
- Box-score stats only; voters weigh much more
- Weights chosen by hand, not validated
- Early-season results are noisy
- plan to add 65 game requirement which removes players who missed to many games from awards

## Run it
    py -m pip install -r requirements.txt
    py -m streamlit run statTracker.py

Built with Python, pandas, NumPy, Streamlit, and nba_api.

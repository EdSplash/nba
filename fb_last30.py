from nba_api.stats.endpoints import teamgamelog, playbyplayv2
from nba_api.stats.static import teams
import pandas as pd
import time

# === Get all NBA teams ===
nba_teams = teams.get_teams()
team_lookup = {team['abbreviation']: team['id'] for team in nba_teams}

# === Display all team abbreviations ===
print("\nAvailable Teams:")
print(" | ".join(sorted(team_lookup.keys())))
print()

# === Prompt for team abbreviation ===
team_abbr = input("Enter team abbreviation (e.g. CLE, LAL, BOS): ").upper()

# === Validate input ===
if team_abbr not in team_lookup:
    print("❌ Invalid team abbreviation. Please try again.")
    exit()

team_id = team_lookup[team_abbr]

# === Load all games (regular, playoffs, play-in if available) ===
frames = []
for season_type in ['Regular Season', 'Playoffs']:
    try:
        log = teamgamelog.TeamGameLog(team_id=team_id, season='2024', season_type_all_star=season_type)
        data_frames = log.get_data_frames()
        if data_frames:
            df = data_frames[0]
            df['SEASON_TYPE'] = season_type
            frames.append(df)
            print(f"✅ Loaded {len(df)} {season_type} games")
        else:
            print(f"⚠️ No games found for {season_type}")
    except Exception as e:
        print(f"⚠️ Skipping {season_type} due to error: {e}")

# === Combine all games
if not frames:
    print("❌ No games found across any season type.")
    exit()

game_logs = pd.concat(frames, ignore_index=True)

# Parse opponent and game type
def get_opponent(matchup, team_abbr):
    parts = matchup.split(" ")
    return parts[-1] if parts[0] == team_abbr else parts[0]

def get_game_type(matchup):
    if "- P" in matchup:
        return "Playoff"
    else:
        return "Regular"

game_logs['GAME_DATE'] = pd.to_datetime(game_logs['GAME_DATE'])
game_logs['OPPONENT'] = game_logs['MATCHUP'].apply(lambda x: get_opponent(x, team_abbr))
game_logs['GAME_TYPE'] = game_logs['MATCHUP'].apply(get_game_type)
game_logs = game_logs.sort_values('GAME_DATE', ascending=False)

recent_game_ids = game_logs['Game_ID'].head(30).tolist()

if not recent_game_ids:
    print("❌ No recent game IDs found.")
    exit()

# === Pull first basket from each game ===
first_baskets = []

for i, game_id in enumerate(recent_game_ids):
    try:
        time.sleep(1)
        pbp = playbyplayv2.PlayByPlayV2(game_id=game_id)
        pbp_df = pbp.get_data_frames()[0]
        first_fg = pbp_df[pbp_df['EVENTMSGTYPE'] == 1].iloc[0]

        scorer = first_fg['PLAYER1_NAME']
        team = first_fg['PLAYER1_TEAM_ABBREVIATION']
        desc = first_fg['HOMEDESCRIPTION'] if pd.notna(first_fg['HOMEDESCRIPTION']) else first_fg['VISITORDESCRIPTION']
        row = game_logs.loc[game_logs['Game_ID'] == game_id].iloc[0]

        first_baskets.append({
            'GAME_ID': game_id,
            'GAME_DATE': row['GAME_DATE'].date(),
            'GAME_TYPE': row['GAME_TYPE'],
            'PLAYER_NAME': scorer,
            'TEAM': team,
            'OPPONENT': row['OPPONENT'],
            'PLAY_DESC': desc
        })

        print(f"[{i+1}/30] {scorer} scored first in a {row['GAME_TYPE']} game vs {row['OPPONENT']}")

    except Exception as e:
        print(f"[{i+1}/30] Error in game {game_id}: {e}")

# === Add total first basket count per player
if first_baskets:
    df = pd.DataFrame(first_baskets)
    player_counts = df['PLAYER_NAME'].value_counts().to_dict()
    df['PLAYER_FIRST_BASKET_TOTAL'] = df['PLAYER_NAME'].map(player_counts)

    filename = f"{team_abbr}_recent_first_baskets_all_games.csv"
    df.to_csv(filename, index=False)
    print(f"\n✅ Saved results with total counts to {filename}")
else:
    print("\n⚠️ No first baskets were recorded.")

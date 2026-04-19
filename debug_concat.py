import pandas as pd
from pathlib import Path

BASE_DIR = Path.cwd()
RAW_DIR = BASE_DIR / "data" / "raw"

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    return df

def add_season_if_missing(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    df = df.copy()
    if "season" not in df.columns:
        if "2023" in filename:
            df["season"] = 2023
        elif "2022" in filename:
            df["season"] = 2022
    return df

# Load
df_2022 = pd.read_csv(RAW_DIR / "IPL_Matches_2022.csv")
df_2022 = standardize_columns(df_2022)
df_2022 = add_season_if_missing(df_2022, "IPL_Matches_2022.csv")

df_2023 = pd.read_csv(RAW_DIR / "each_match_records-2023.csv")
df_2023 = standardize_columns(df_2023)
df_2023 = add_season_if_missing(df_2023, "each_match_records-2023.csv")

print("2022 columns:", list(df_2022.columns))
print("2023 columns:", list(df_2023.columns))

print("\n2022 match_number (first 3):", df_2022['matchnumber'].head(3).tolist() if 'matchnumber' in df_2022.columns else df_2022['match_number'].head(3).tolist() if 'match_number' in df_2022.columns else "N/A")
print("2023 match_number (first 3):", df_2023['match_number'].head(3).tolist())

# Concat
combined = pd.concat([df_2022, df_2023], ignore_index=True, sort=False)
print("\nCombined columns:", list(combined.columns))

# Check for duplicate column names in combined
print("\nDuplicate columns before dedup:", combined.columns[combined.columns.duplicated(keep=False)].tolist())

# Remove duplicates
combined_dedup = combined.loc[:, ~combined.columns.duplicated(keep='first')]
print("After dedup - columns:", list(combined_dedup.columns))

# Check match_number values
print("\nAfter dedup:")
print("  2022 match_number (first 3):", combined_dedup[combined_dedup['season']==2022]['match_number'].head(3).values.tolist() if 'match_number' in combined_dedup.columns else "N/A")
print("  2023 match_number (first 3):", combined_dedup[combined_dedup['season']==2023]['match_number'].head(3).values.tolist() if 'match_number' in combined_dedup.columns else "N/A")

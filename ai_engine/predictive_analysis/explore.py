# %%
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

CSV_PATH = Path(__file__).parent / "historical_prices.csv"

df = pd.read_csv(CSV_PATH)
df[df["item_name"] == "Onion"].plot(x="date", y="price")
plt.show()
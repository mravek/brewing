# Brewing Optimizer MVP Backend (v0.2)
# Now integrated with real attenuation curve data from Graviator for better predictions

from datetime import datetime, timedelta
import pandas as pd
from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello():
    return "Hello, world!"

# === User System Constants ===
BREWZILLA_EFFICIENCY = 0.7438  # 74.38%
BOIL_OFF_LPH = 3.0
TRUB_LOSS_L = 2.5

# === Yeast Profiles ===
yeast_profiles = {
    "Verdant IPA": {
        "strain": "Ale - Verdant IPA",
        "attenuation": (74, 78),
        "opt_temp": (17, 23),
        "notes": "Juicy NEIPA yeast, benefits from warm ramp up."
    },
    "BL-102": {
        "strain": "Köln-style Ale",
        "attenuation": (76, 80),
        "opt_temp": (16, 20),
        "notes": "Clean Kölsch yeast with moderate flocculation."
    }
}

# === Batch class ===
class BrewBatch:
    def __init__(self, name, og_p, fg_target, yeast, pitch_date, temp_c, attenuation_curve=None):
        self.name = name
        self.og_p = og_p
        self.fg_target = fg_target
        self.yeast = yeast
        self.pitch_date = pitch_date
        self.temp_c = temp_c
        self.attenuation_curve = attenuation_curve  # DataFrame of gravity readings

    def predict_fg(self):
        if self.fg_target:
            return self.fg_target
        min_att, max_att = yeast_profiles[self.yeast]["attenuation"]
        avg_att = (min_att + max_att) / 2
        return round(self.og_p * (1 - avg_att / 100), 3)

    def predict_finish_date(self):
        if self.attenuation_curve is not None:
            # Find when gravity flattens near FG
            stable = self.attenuation_curve[self.attenuation_curve['gravity'] <= self.predict_fg() + 0.002]
            if not stable.empty:
                return stable['timepoint'].iloc[0].strftime("%A %d %b")
        # fallback: estimate duration by temp factor
        opt_min, opt_max = yeast_profiles[self.yeast]["opt_temp"]
        temp_factor = 1.0
        if self.temp_c < opt_min:
            temp_factor = 1.2
        elif self.temp_c > opt_max:
            temp_factor = 0.8
        return (self.pitch_date + timedelta(days=int(5 * temp_factor))).strftime("%A %d %b")

    def diacetyl_rest_trigger(self):
        if self.attenuation_curve is not None:
            # When gravity is 3 points above FG
            trigger = self.attenuation_curve[self.attenuation_curve['gravity'] <= self.predict_fg() + 0.003]
            if not trigger.empty:
                return trigger['timepoint'].iloc[0].strftime("%A %d %b")
        return "Check gravity manually ~day 4"

    def summary(self):
        return {
            "Batch Name": self.name,
            "OG (°P)": self.og_p,
            "Predicted FG (°P)": self.predict_fg(),
            "Yeast": self.yeast,
            "Est. Finish Date": self.predict_finish_date(),
            "Diacetyl Rest Trigger": self.diacetyl_rest_trigger()
        }

# === Load attenuation curve from CSV (Graviator) ===
def load_graviator_curve(csv_path):
    df = pd.read_csv(csv_path)
    df = df[df['sg'].notnull()].copy()
    df['timepoint'] = pd.to_datetime(df['timepoint'])
    df['gravity'] = df['sg'].astype(float)
    return df.sort_values('timepoint')

# === Example usage ===
if __name__ == "__main__":
    curve = load_graviator_curve("/mnt/data/Brewfather_ReadingsData_Batch_62_20250727.csv")
    batch = BrewBatch(
        name="NEIPA Batch 62",
        og_p=1.058,
        fg_target=1.011,
        yeast="Verdant IPA",
        pitch_date=datetime(2025, 7, 10),
        temp_c=18.0,
        attenuation_curve=curve
    )

    info = batch.summary()
    for k, v in info.items():
        print(f"{k}: {v}")

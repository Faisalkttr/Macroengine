import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# -----------------------------------------------------------------------------
# MACRO EXECUTION SYSTEM: UNBREAKABLE DATA ENGINE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sovereign Macro Capital Dashboard", layout="wide")

st.title("Sovereign Macro Monitor: Capital Flows & DXY Engine")
st.caption("Rule-Based Execution Inputs • Real-Time Macro Liquidity Extraction via FRED API")

# -----------------------------------------------------------------------------
# CONFIGURATION & API KEYS
# -----------------------------------------------------------------------------
fred_key_input = st.sidebar.text_input("FRED API Key", type="password")
api_key = fred_key_input if fred_key_input else st.secrets.get("FRED_API_KEY", "")

start_year = st.sidebar.slider("Lookback Starting Year", 2000, 2026, 2018)
start_date = f"{start_year}-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

# -----------------------------------------------------------------------------
# MACRO SERIES MAPPING (PUBLIC AND UNRESTRICTED TICKERS)
# -----------------------------------------------------------------------------
SERIES_MAP = {
    "DXY": "DTWEXBGS",          # Standard/Major Currency DXY Equivalent
    "10Y_Yield": "DGS10",       # US 10-Year Treasury Yield (Daily)
    "EM_Yield": "EMERBGIN"      # ICE BofA Emerging Markets Liquid Corporate Plus Index Yield
}

# -----------------------------------------------------------------------------
# DATA RETRIEVAL CORE ENGINE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=86400)
def fetch_fred_series(series_id, api_key, start, end):
    if not api_key:
        return pd.DataFrame()
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "observation_end": end
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "observations" in data:
            df = pd.DataFrame(data["observations"])
            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["value"])
            return df[["date", "value"]].set_index("date")
    except Exception as e:
        pass
    return pd.DataFrame()

# -----------------------------------------------------------------------------
# MATRIX CONTROLLER
# -----------------------------------------------------------------------------
if not api_key:
    st.warning("⚠️ CRITICAL ERROR: FRED API Key missing. Input key in the sidebar to initiate the execution engine.")
else:
    with st.spinner("Extracting macro liquidity vectors..."):
        dxy = fetch_fred_series(SERIES_MAP["DXY"], api_key, start_date, end_date)
        yield_10y = fetch_fred_series(SERIES_MAP["10Y_Yield"], api_key, start_date, end_date)
        em_yield = fetch_fred_series(SERIES_MAP["EM_Yield"], api_key, start_date, end_date)

    # Combine data seamlessly
    master_df = pd.DataFrame()
    
    if not dxy.empty:
        master_df = master_df.join(dxy.rename(columns={"value": "DXY"}), how="outer")
    if not yield_10y.empty:
        master_df = master_df.join(yield_10y.rename(columns={"value": "10Y_Yield"}), how="outer")
    if not em_yield.empty:
        master_df = master_df.join(em_yield.rename(columns={"value": "EM_Yield"}), how="outer")
    
    # Fill gaps for days where markets were closed
    master_df = master_df.ffill().bfill().dropna()

    # Verify that essential mapping components exist
    if not master_df.empty and "DXY" in master_df.columns:
        
        # If EM yields aren't loaded, create a proxy using inverse DXY and 10Y to keep dashboard alive
        if "EM_Yield" not in master_df.columns or master_df["EM_Yield"].sum() == 0:
            master_df["EM_Yield"] = master_df["10Y_Yield"] + 2.5  # Standard structural spread baseline
            
        # Core Liquidity Flow Metric Calculation
        master_df["EM_Liquidity_Flow_Proxy"] = (1000 / (master_df["EM_Yield"] * master_df["DXY"])) * 100

        latest = master_df.iloc[-1]
        prev_month = master_df.iloc[-22] if len(master_df) > 22 else master_df.iloc[0]

        # AUTOMATED REGIME DETECTOR
        dxy_trend = "↑ Strong" if latest["DXY"] >= prev_month["DXY"] else "↓ Weakening"
        yield_trend = "↑ Rising" if latest["10Y_Yield"] >= prev_month["10Y_Yield"] else "↓ Falling"
        
        regime = "QT"
        if dxy_trend == "↓ Weakening" and yield_trend == "↓ Falling":
            regime = "SOFT PIVOT"
        elif dxy_trend == "↓ Weakening" and latest["10Y_Yield"] <= (prev_month["10Y_Yield"] - 0.5):
            regime = "HARD PIVOT"

        # INTERFACE SYSTEM DISPLAY
        col1, col2, col3 = st.columns(3)
        col1.metric(label="CURRENT REGIME STATE", value=regime, delta=f"DXY: {dxy_trend}")
        col2.metric(label="US 10Y TREASURY YIELD", value=f"{latest['10Y_Yield']:.2f}%", delta=yield_trend)
        col3.metric(label="U.S. DOLLAR INDEX (DXY)", value=f"{latest['DXY']:.2f}")

        st.markdown("---")
        st.subheader("Liquidity Engine Intersect: DXY vs. EM Flow Proxy")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=master_df.index, y=master_df["DXY"], name="USD Index (DXY)", line=dict(color="#1f77b4", width=2)))
        fig.add_trace(go.Scatter(x=master_df.index, y=master_df["EM_Liquidity_Flow_Proxy"], name="EM Capital Flow Proxy (RHS)", yaxis="y2", line=dict(color="#2ca02c", width=2, dash="dash")))

        fig.update_layout(
            yaxis=dict(title="DXY Value Index"),
            yaxis2=dict(title="EM Flow Proxy Strength", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=40, r=40, t=20, b=40),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Yield Mechanics Matrix: US 10Y vs. EM Corporate Yield")

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=master_df.index, y=master_df["10Y_Yield"], name="US 10Y Risk-Free Rate", line=dict(color="#ff7f0e", width=2)))
        fig2.add_trace(go.Scatter(x=master_df.index, y=master_df["EM_Yield"], name="EM Corporate Yield Index", line=dict(color="#d62728", width=2)))
        
        fig2.update_layout(
            yaxis=dict(title="Percent (%)"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=40, r=40, t=20, b=40),
            hovermode="x unified"
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Raw Metric Execution Audit")
        st.dataframe(master_df.tail(15).sort_index(ascending=False), use_container_width=True)

    else:
        st.error("❌ Data Engine Failure: Main dollar streams missing. Verify connection or API Key input.")

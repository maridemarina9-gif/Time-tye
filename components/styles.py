from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


def get_login_background_data_uri() -> str:
    image_path = Path(__file__).resolve().parents[1] / "assets" / "login-background.jpg"
    try:
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/jpeg;base64,{encoded_image}"


def apply_styles(login: bool = False) -> None:
    login_background = get_login_background_data_uri() if login else ""
    login_overrides = ""
    if login_background:
        login_overrides = f"""
        .stApp {{
            background: transparent !important;
        }}
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {{
            background: transparent !important;
        }}
        .login-background-layer {{
            position: fixed;
            inset: 0;
            z-index: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none;
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
        }}
        [data-testid="stAppViewContainer"] > .main {{ position: relative; z-index: 1; }}
        [data-testid="stMainBlockContainer"] {{ position: relative; z-index: 1; }}
        div[data-testid="stTabs"] {{
            background: rgba(7, 31, 28, .52);
            border: 1px solid rgba(255, 255, 255, .28);
            border-radius: 24px;
            box-shadow: 0 18px 50px rgba(7, 31, 28, .24);
            padding: .5rem 1.35rem 1.35rem;
        }}
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] button[role="tab"],
        div[data-testid="stTabs"] button[data-baseweb="tab"] *,
        div[data-testid="stTabs"] button[role="tab"] * {{
            color: #ffffff !important;
            font-weight: 800 !important;
            text-shadow: 0 1px 4px rgba(0, 0, 0, .48);
        }}
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] *,
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] * {{
            color: #d9f99d !important;
        }}
        .login-wrap {{
            max-width: 420px;
            margin: 1.6rem auto .85rem;
            background: rgba(255, 255, 255, .93);
            border-radius: 24px;
            padding: .85rem 1.1rem;
            box-shadow: 0 18px 50px rgba(7, 31, 28, .20);
        }}
        .login-wrap h1 {{
            font-size: clamp(1.65rem, 4vw, 2.25rem);
            margin: .2rem 0 .35rem;
        }}
        .login-wrap p {{
            margin-bottom: .25rem;
            font-size: .92rem;
        }}
        """

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root { --ink: #102a27; --muted: #64817b; --mint: #d9f99d; --green: #15803d; --deep: #0d2924; }
        .stApp { background: #f4f7f2; color: var(--ink); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background: #102a27; }
        [data-testid="stSidebar"] * { color: #efffe8 !important; }
        .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem; }
        h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.03em; }
        p, label, .stMarkdown, .stTextInput { font-family: 'DM Sans', sans-serif; }
        .brand-mark { display:flex; align-items:center; gap:.65rem; margin-bottom:2rem; }
        .brand-dot { width:38px; height:38px; display:grid; place-items:center; background:#d9f99d; color:#102a27; border-radius:12px; font-weight:800; font-family:'Space Grotesk'; }
        .brand-name { color:#efffe8; font:700 1.25rem 'Space Grotesk'; }
        .eyebrow { color:#15803d; text-transform:uppercase; letter-spacing:.14em; font:700 .74rem 'DM Sans'; }
        .hero { background:linear-gradient(125deg,#102a27 0%,#164e43 70%,#15803d 100%); color:#efffe8; border-radius:26px; padding:2.1rem 2.2rem; margin-bottom:1.2rem; }
        .hero h1 { color:#d9f99d; font-size:clamp(2rem,5vw,4rem); margin:.25rem 0 .5rem; }
        .hero p { color:#d4e9d7; max-width:620px; font-size:1.05rem; }
        .stat-card { background:#fff; border:1px solid #e4ece3; border-radius:18px; padding:1.1rem 1.2rem; min-height:115px; box-shadow:0 8px 24px rgba(16,42,39,.05); }
        .stat-label { color:#64817b; font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.08em; }
        .stat-value { color:#102a27; font:700 1.8rem 'Space Grotesk'; margin:.35rem 0; }
        .stat-detail { color:#8aa19a; font-size:.8rem; }
        .section-title { margin-top:1.6rem; margin-bottom:.8rem; }
        .run-panel { background:#fff; border:1px solid #e4ece3; border-radius:22px; padding:1.25rem; box-shadow:0 8px 24px rgba(16,42,39,.05); }
        .metric-big { text-align:center; padding:.7rem .2rem; }
        .metric-big .label { color:#64817b; font-size:.72rem; text-transform:uppercase; letter-spacing:.1em; }
        .metric-big .value { color:#102a27; font:700 clamp(1.7rem,4vw,2.8rem) 'Space Grotesk'; }
        .metric-big .unit { color:#8aa19a; font-size:.8rem; }
        .notice { background:#efffe8; border:1px solid #c6e6bc; border-radius:14px; padding:.85rem 1rem; color:#24533a; }
        .login-wrap { max-width:520px; margin:3rem auto; }
        button[kind="primary"] { background:#15803d !important; border-color:#15803d !important; }
        @media (max-width: 640px) { .block-container { padding:1rem .85rem 2rem; } .hero { padding:1.4rem; border-radius:20px; } .hero h1 { font-size:2.2rem; } }
        """
        + login_overrides
        + """
        </style>
        """,
        unsafe_allow_html=True,
    )


def stat_card(label: str, value: str, detail: str = "") -> None:
    st.markdown(
        f'<div class="stat-card"><div class="stat-label">{label}</div><div class="stat-value">{value}</div><div class="stat-detail">{detail}</div></div>',
        unsafe_allow_html=True,
    )


def metric_big(label: str, value: str, unit: str = "") -> None:
    st.markdown(
        f'<div class="metric-big"><div class="label">{label}</div><div class="value">{value}</div><div class="unit">{unit}</div></div>',
        unsafe_allow_html=True,
    )
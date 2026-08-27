"""Kurumsal Streamlit stilleri."""

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', 'DM Sans', sans-serif;
            color: #1C2B36;
        }
        .stApp {
            background: linear-gradient(160deg, #E8EEF3 0%, #F4F7FA 40%, #EDF3F5 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0B1F33 0%, #132F45 55%, #0D3A42 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        [data-testid="stSidebar"] * { color: #E8EEF3 !important; }
        [data-testid="stSidebar"] .stRadio label {
            padding: 0.55rem 0.75rem; border-radius: 6px; margin-bottom: 0.25rem;
        }
        [data-testid="stSidebar"] .stRadio label:hover { background: rgba(255,255,255,0.08); }
        [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12); }
        h1, h2, h3 {
            font-family: 'DM Sans', sans-serif !important;
            font-weight: 600 !important; color: #0B1F33 !important;
        }
        [data-testid="stMetric"] {
            background: #fff; border: 1px solid #D8E0E8; border-radius: 10px;
            padding: 1rem 1.15rem; box-shadow: 0 1px 3px rgba(11,31,51,0.04);
        }
        .panel {
            background: #fff; border: 1px solid #D8E0E8; border-radius: 12px;
            padding: 1.5rem 1.75rem; margin-bottom: 1.25rem;
            box-shadow: 0 1px 4px rgba(11,31,51,0.05);
        }
        .panel-title { font-family: 'DM Sans', sans-serif; font-size: 1.05rem; font-weight: 600; color: #0B1F33; margin-bottom: 0.35rem; }
        .panel-sub { color: #5A6B7A; font-size: 0.9rem; margin-bottom: 1rem; }
        .brand-bar { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem; }
        .brand-mark {
            width: 36px; height: 36px; border-radius: 8px;
            background: linear-gradient(135deg, #0D7377, #2E86AB);
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 1.1rem; font-weight: 700;
        }
        .page-title { font-size: 1.75rem; font-weight: 600; color: #0B1F33; margin: 0 0 0.25rem 0; font-family: 'DM Sans', sans-serif; }
        .page-sub { color: #5A6B7A; margin: 0 0 1.5rem 0; font-size: 0.95rem; }
        .section-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #5A6B7A; margin-bottom: 0.75rem; }
        .section-heading { font-family: 'DM Sans', sans-serif; font-size: 1.15rem; font-weight: 600; color: #0B1F33; margin: 1.75rem 0 0.35rem 0; }
        .section-desc { color: #5A6B7A; font-size: 0.9rem; margin: 0 0 1rem 0; line-height: 1.5; }
        .badge-blue { display: inline-block; background: rgba(46,134,171,0.12); color: #1A5F7A; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 4px; }
        .badge-green { display: inline-block; background: rgba(45,106,79,0.12); color: #1B4332; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 4px; }
        .badge-grey { display: inline-block; background: rgba(107,114,128,0.14); color: #374151; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 4px; }
        .info-note { background: rgba(45,106,79,0.07); border-left: 3px solid #2D6A4F; border-radius: 0 8px 8px 0; padding: 0.9rem 1.1rem; color: #1C2B36; font-size: 0.9rem; line-height: 1.55; margin-bottom: 1.25rem; }
        .formula-note { background: rgba(46,134,171,0.07); border-left: 3px solid #2E86AB; border-radius: 0 8px 8px 0; padding: 0.85rem 1.1rem; color: #1C2B36; font-size: 0.88rem; line-height: 1.55; margin-bottom: 1rem; }
        .placeholder-box { border: 1.5px dashed #D8E0E8; border-radius: 10px; padding: 2.5rem 1.5rem; text-align: center; color: #5A6B7A; background: rgba(244,247,250,0.6); font-size: 0.9rem; }
        .unit-hint { color: #5A6B7A; font-size: 0.82rem; margin: -0.35rem 0 1rem 0; }
        .intro-banner {
            background: linear-gradient(135deg, rgba(168,213,229,0.35) 0%, rgba(184,221,181,0.28) 50%, rgba(157,212,208,0.3) 100%);
            border: 1px solid rgba(216,224,232,0.9); border-radius: 14px; padding: 1.35rem 1.6rem; margin-bottom: 1.5rem;
        }
        .intro-banner h3 { margin: 0 0 0.45rem 0 !important; font-size: 1.1rem !important; }
        .intro-banner p { margin: 0; color: #3D4F5F; font-size: 0.92rem; line-height: 1.65; }
        .info-card {
            background: #fff; border: 1px solid #D8E0E8; border-radius: 14px;
            padding: 1.25rem 1.2rem 1.35rem; height: 100%; margin-bottom: 0.75rem;
            box-shadow: 0 1px 4px rgba(11,31,51,0.04);
        }
        .info-card .visual { display: flex; align-items: center; justify-content: center; height: 88px; border-radius: 12px; margin-bottom: 1rem; }
        .info-card.mavi .visual { background: linear-gradient(160deg, #D6EEF6 0%, #E8F5FA 100%); }
        .info-card.yesil .visual { background: linear-gradient(160deg, #DCEFDB 0%, #EAF6E9 100%); }
        .info-card.gri .visual { background: linear-gradient(160deg, #E8E6EF 0%, #F2F0F6 100%); }
        .info-card.turkuaz .visual { background: linear-gradient(160deg, #D4EFEC 0%, #E6F6F4 100%); }
        .info-card h4 { margin: 0 0 0.45rem 0; font-family: 'DM Sans', sans-serif; font-size: 1rem; font-weight: 600; color: #0B1F33; }
        .info-card p { margin: 0; color: #5A6B7A; font-size: 0.86rem; line-height: 1.6; }
        .info-card ul { margin: 0.55rem 0 0 0; padding-left: 1.1rem; color: #3D4F5F; font-size: 0.84rem; line-height: 1.55; }
        .chip { display: inline-block; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; padding: 0.18rem 0.5rem; border-radius: 4px; margin-bottom: 0.55rem; }
        .chip-mavi { background: rgba(168,213,229,0.55); color: #1A5F7A; }
        .chip-yesil { background: rgba(184,221,181,0.55); color: #2D5A3D; }
        .chip-gri { background: rgba(213,208,224,0.6); color: #4A4560; }
        .chip-turkuaz { background: rgba(157,212,208,0.55); color: #1A5C58; }
        .note-soft { background: rgba(255,255,255,0.7); border: 1px dashed #C5D0DA; border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.8rem; color: #5A6B7A; line-height: 1.5; margin: 0.5rem 0; }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0D7377, #14919B); border: none; border-radius: 8px; font-weight: 500;
        }
        #MainMenu, footer, header { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )

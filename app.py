"""
MY Expertise Comptable - Plateforme d'automatisation
Page d'accueil
"""
import streamlit as st
from pathlib import Path

# ---------- Configuration de la page ----------
st.set_page_config(
    page_title="MY Expertise Comptable",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styles personnalisés ----------
st.markdown("""
<style>
    /* Cacher le menu hamburger et le footer Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Style général */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }
    
    /* ----- Cartes modules ----- */
    .module-card {
        display: block;
        background: white;
        border: 1px solid #E8E2DC;
        border-radius: 12px;
        padding: 1.5rem;
        height: 100%;
        min-height: 170px;
        transition: all 0.2s ease;
        text-decoration: none !important;
        color: inherit !important;
    }
    /* Carte disponible : devient cliquable, effet hover */
    a.module-card:hover {
        border-color: #D85A30;
        box-shadow: 0 4px 12px rgba(216, 90, 48, 0.08);
        transform: translateY(-2px);
        text-decoration: none !important;
    }
    /* Carte désactivée : opacité réduite, pas d'effet */
    .module-card-disabled {
        opacity: 0.55;
        cursor: not-allowed;
    }
    
    .module-icon {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        margin-bottom: 0.75rem;
    }
    .icon-bank { background: #FAECE7; color: #993C1D; }
    .icon-disabled { background: #F1EFE8; color: #888780; }
    
    .module-badge {
        display: inline-block;
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 6px;
        letter-spacing: 0.5px;
        margin-bottom: 0.75rem;
    }
    .badge-available { background: #E1F5EE; color: #0F6E56; }
    .badge-soon { background: #F1EFE8; color: #5F5E5A; }
    
    .module-title {
        font-size: 16px;
        font-weight: 600;
        margin: 0 0 4px 0;
        color: #2C2C2A;
    }
    .module-description {
        font-size: 13px;
        color: #5F5E5A;
        margin: 0;
        line-height: 1.5;
    }
    
    /* Bandeau header */
    .header-banner {
        display: flex;
        align-items: center;
        gap: 16px;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid #E8E2DC;
        margin-bottom: 2rem;
    }
    
    /* Info box */
    .info-box {
        margin-top: 2rem;
        padding: 12px 16px;
        background: #F8F4F0;
        border-radius: 8px;
        font-size: 12px;
        color: #5F5E5A;
    }
    
    /* Boutons */
    .stButton > button {
        background-color: #D85A30;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.25rem;
        font-weight: 500;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #B8481F;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Header avec logo ----------
logo_path = Path(__file__).parent / "assets" / "logo.png"

col_logo, col_title = st.columns([1, 5])
with col_logo:
    if logo_path.exists():
        st.image(str(logo_path), width=140)
with col_title:
    st.markdown("""
    <div style="padding-top: 0.5rem;">
        <p style="font-size: 22px; font-weight: 600; margin: 0; color: #2C2C2A;">Plateforme d'automatisation</p>
        <p style="font-size: 14px; color: #5F5E5A; margin: 0;">Outils internes pour le traitement des documents comptables</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='border-bottom: 1px solid #E8E2DC; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)

# ---------- Section modules ----------
st.markdown("##### Choisissez un module pour commencer")
st.write("")

col1, col2, col3 = st.columns(3)

# ----- Module 1 : Relevés bancaires (DISPONIBLE) -----
with col1:
    st.markdown("""
    <a href="/Releves_bancaires" target="_self" class="module-card">
        <div class="module-icon icon-bank">📄</div>
        <span class="module-badge badge-available">DISPONIBLE</span>
        <p class="module-title">Relevés bancaires</p>
        <p class="module-description">PDF → Excel comptable avec contreparties 471 / 512. Multi-banques, scan ou PDF natif.</p>
    </a>
    """, unsafe_allow_html=True)

# ----- Module 2 : Banque Electrip (DISPONIBLE) -----
with col2:
    st.markdown("""
    <a href="/Banque_Electrip" target="_self" class="module-card">
        <div class="module-icon icon-bank">💳</div>
        <span class="module-badge badge-available">DISPONIBLE</span>
        <p class="module-title">Banque Electrip</p>
        <p class="module-description">CSV Electrip → Excel comptable avec contreparties 471 / 512 et marquage automatique.</p>
    </a>
    """, unsafe_allow_html=True)

# ----- Module 3 : Placeholder (non cliquable) -----
with col3:
    st.markdown("""
    <div class="module-card module-card-disabled">
        <div class="module-icon icon-disabled">➕</div>
        <span class="module-badge badge-soon">À VENIR</span>
        <p class="module-title">Module 3</p>
        <p class="module-description">Emplacement réservé pour le prochain outil d'automatisation.</p>
    </div>
    """, unsafe_allow_html=True)

# ---------- Footer info ----------
st.markdown("""
<div class="info-box">
    ℹ️ &nbsp;Aucune authentification • Les fichiers sont traités en mémoire et ne sont jamais stockés sur un serveur
</div>
""", unsafe_allow_html=True)

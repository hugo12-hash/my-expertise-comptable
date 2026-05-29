"""
Module 2 : BANQUE ELECTRIP - Traitement CSV bancaire vers Excel comptable
"""
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from utils.electrip_processor import lire_csv, generer_excel, COLONNES_REQUISES


# ---------- Configuration ----------
st.set_page_config(
    page_title="Banque Electrip - MY Expertise Comptable",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styles ----------
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }
    
    .breadcrumb {
        font-size: 13px;
        color: #888780;
        margin-bottom: 1rem;
    }
    .breadcrumb-current {
        color: #2C2C2A;
    }
    
    .page-title {
        font-size: 22px;
        font-weight: 600;
        margin: 0 0 4px 0;
        color: #2C2C2A;
    }
    .page-subtitle {
        font-size: 14px;
        color: #5F5E5A;
        margin: 0 0 1.5rem 0;
    }
    
    .info-pill {
        display: inline-block;
        padding: 4px 10px;
        background: #F8F4F0;
        border-radius: 6px;
        font-size: 12px;
        color: #5F5E5A;
        margin-right: 8px;
    }
    
    .success-box {
        padding: 12px 16px;
        background: #E1F5EE;
        border-left: 3px solid #0F6E56;
        border-radius: 6px;
        font-size: 14px;
        color: #0F6E56;
        margin: 1rem 0;
    }
    
    .warning-box {
        padding: 12px 16px;
        background: #FAEEDA;
        border-left: 3px solid #BA7517;
        border-radius: 6px;
        font-size: 14px;
        color: #854F0B;
        margin: 1rem 0;
    }
    
    .stButton > button {
        background-color: #D85A30;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.25rem;
        font-weight: 500;
    }
    .stButton > button:hover {
        background-color: #B8481F;
        color: white;
    }
    
    .stDownloadButton > button {
        background-color: #0F6E56;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
    }
    .stDownloadButton > button:hover {
        background-color: #085041;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Fil d'Ariane ----------
col_back, col_reset, _ = st.columns([1, 1, 6])
with col_back:
    if st.button("← Accueil", key="back_home"):
        st.switch_page("app.py")
with col_reset:
    if st.button("🔄 Réinitialiser", key="reset_module_2"):
        # Effacer toutes les clés de session liées au module 2
        keys_to_clear = [
            'electrip_excel', 'electrip_brutes', 'electrip_ecritures',
            'electrip_nb_source', 'electrip_nom_sortie',
        ]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.markdown("""
<p class="breadcrumb">
    Accueil &nbsp;/&nbsp; <span class="breadcrumb-current">Banque Electrip</span>
</p>
""", unsafe_allow_html=True)

# ---------- Titre ----------
st.markdown("""
<p class="page-title">💳 Banque Electrip - CSV → Excel comptable</p>
<p class="page-subtitle">Dépose un export CSV de Banque Electrip. L'outil normalise les colonnes, génère les contreparties et produit un Excel à 2 feuilles prêt pour la compta.</p>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom: 1.5rem;">
    <span class="info-pill">✓ Format JJ/MM/AAAA</span>
    <span class="info-pill">✓ Partie double automatique</span>
    <span class="info-pill">✓ 2 feuilles Excel</span>
    <span class="info-pill">✓ Marqueur X sur contreparties</span>
</div>
""", unsafe_allow_html=True)

# ---------- Options ----------
with st.expander("⚙️  Options comptables", expanded=False):
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        compte_banque = st.text_input(
            "Compte banque",
            value="5120000",
            help="Compte qui reflète le mouvement bancaire (par défaut 5120000).",
            key="compte_banque_input",
        )
    with col_o2:
        compte_contrepartie = st.text_input(
            "Compte contrepartie",
            value="4710000",
            help="Compte d'attente pour la contrepartie (par défaut 4710000).",
            key="compte_contre_input",
        )
    
    nom_sortie = st.text_input(
        "Nom du fichier Excel",
        value="ecritures_electrip",
        help="Sans l'extension .xlsx",
    )

# ---------- Zone de dépôt ----------
uploaded_file = st.file_uploader(
    "Déposez votre fichier CSV Banque Electrip ici",
    type=['csv'],
    help="Glissez-déposez ou cliquez pour parcourir. Format CSV standard, séparateur virgule.",
)

# ---------- Traitement ----------
if uploaded_file is not None:
    st.markdown(f"""
    <div style="padding: 10px 14px; background: #F8F4F0; border-radius: 6px; font-size: 13px; margin: 1rem 0;">
        📎 <strong>{uploaded_file.name}</strong> &nbsp;·&nbsp; {uploaded_file.size / 1024:.1f} Ko
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀  Lancer le traitement", key="process_btn"):
        with st.spinner("Traitement en cours..."):
            csv_bytes = uploaded_file.read()
            
            try:
                # Lire le CSV
                df_source = lire_csv(csv_bytes)
                
                # Vérifier les colonnes requises
                colonnes_manquantes = [c for c in COLONNES_REQUISES if c not in df_source.columns]
                if colonnes_manquantes:
                    st.error(
                        f"❌ Le CSV ne contient pas les colonnes requises : {', '.join(colonnes_manquantes)}. "
                        f"Colonnes attendues : {', '.join(COLONNES_REQUISES)}."
                    )
                    st.stop()
                
                # Générer l'Excel
                excel_file, df_brutes, df_ecritures = generer_excel(
                    df_source,
                    compte_banque=compte_banque.strip(),
                    compte_contrepartie=compte_contrepartie.strip(),
                )
                
                # Stocker dans la session
                st.session_state['electrip_excel'] = excel_file
                st.session_state['electrip_brutes'] = df_brutes
                st.session_state['electrip_ecritures'] = df_ecritures
                st.session_state['electrip_nb_source'] = len(df_source)
                st.session_state['electrip_nom_sortie'] = nom_sortie
                
            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.stop()

# ---------- Affichage des résultats ----------
if 'electrip_ecritures' in st.session_state:
    df_brutes = st.session_state['electrip_brutes']
    df_ecritures = st.session_state['electrip_ecritures']
    nb_source = st.session_state['electrip_nb_source']
    
    # ----- Bandeau de succès -----
    total_debit = df_ecritures['DEBIT'].sum()
    total_credit = df_ecritures['CREDIT'].sum()
    equilibre = abs(total_debit - total_credit) < 0.01
    
    st.markdown(f"""
    <div class="success-box">
        ✅ <strong>{nb_source} transactions traitées</strong> &nbsp;·&nbsp; 
        <strong>{len(df_ecritures)} lignes</strong> générées (partie double) &nbsp;·&nbsp;
        Équilibre : <strong>{'OK ✓' if equilibre else 'À vérifier ⚠️'}</strong>
    </div>
    """, unsafe_allow_html=True)
    
    # ----- Onglets d'aperçu -----
    tab1, tab2 = st.tabs(["📋 Feuille 'Données brutes'", "📊 Feuille 'Écritures comptables'"])
    
    with tab1:
        st.caption("Données complètes avec marqueur X sur les lignes de contrepartie")
        df_display = df_brutes.copy()
        # Format montants pour affichage
        df_display['Debit'] = df_display['Debit'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != 0 else ''
        )
        df_display['Credit'] = df_display['Credit'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != 0 else ''
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
    
    with tab2:
        st.caption("Format final pour import dans votre logiciel comptable")
        df_display = df_ecritures.copy()
        df_display['DEBIT'] = df_display['DEBIT'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != 0 and x != '' else ''
        )
        df_display['CREDIT'] = df_display['CREDIT'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != 0 and x != '' else ''
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
        
        st.caption(
            f"💰 Total débit : **{total_debit:,.2f} €** &nbsp;·&nbsp; "
            f"Total crédit : **{total_credit:,.2f} €** "
            f"{'(équilibré ✓)' if equilibre else '(écart ⚠️)'}"
        )
    
    # ----- Bouton de téléchargement -----
    st.markdown("---")
    
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="⬇️  Télécharger l'Excel",
            data=st.session_state['electrip_excel'],
            file_name=f"{st.session_state['electrip_nom_sortie']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

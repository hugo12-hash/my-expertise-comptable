"""
Module 1 : Conversion relevé bancaire PDF → Excel comptable
"""
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH pour importer utils
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from utils.pdf_extractor import extract_transactions, extract_solde_info, verifier_solde
from utils.excel_generator import generate_excel, build_preview_dataframe


# ---------- Configuration de la page ----------
st.set_page_config(
    page_title="Relevés bancaires - MY Expertise Comptable",
    page_icon="📄",
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
    .breadcrumb a {
        color: #888780;
        text-decoration: none;
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
col_back, _ = st.columns([1, 8])
with col_back:
    if st.button("← Accueil", key="back_home"):
        st.switch_page("app.py")

st.markdown("""
<p class="breadcrumb">
    Accueil &nbsp;/&nbsp; <span class="breadcrumb-current">Relevés bancaires</span>
</p>
""", unsafe_allow_html=True)

# ---------- Titre ----------
st.markdown("""
<p class="page-title">📄 Conversion relevé bancaire → Excel</p>
<p class="page-subtitle">Dépose un PDF (scan ou natif). L'outil détecte la banque, extrait les lignes et génère un Excel avec contrepartie 471.</p>
""", unsafe_allow_html=True)

# ---------- Badges info ----------
st.markdown("""
<div style="margin-bottom: 1.5rem;">
    <span class="info-pill">✓ Multi-banques</span>
    <span class="info-pill">✓ PDF natif + scan</span>
    <span class="info-pill">✓ Partie double automatique</span>
    <span class="info-pill">✓ Format JJ/MM/AAAA</span>
</div>
""", unsafe_allow_html=True)

# ---------- Options ----------
with st.expander("⚙️  Options comptables", expanded=False):
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        compte_banque = st.text_input(
            "Compte banque (512)",
            value="51200000",
            help="Compte qui reflète le mouvement bancaire.",
        )
    with col_o2:
        compte_contrepartie = st.text_input(
            "Compte contrepartie (471)",
            value="47100000",
            help="Compte d'attente pour la contrepartie comptable.",
        )
    
    col_o3, col_o4 = st.columns(2)
    with col_o3:
        force_ai = st.checkbox(
            "Forcer l'utilisation de l'IA",
            value=False,
            help="Utile si le PDF est un scan ou si l'extraction standard donne de mauvais résultats.",
        )
        force_image = st.checkbox(
            "Forcer le mode image (OCR)",
            value=False,
            help="Convertit le PDF en image puis lit via OCR. Utile pour les PDF natifs "
                 "'capricieux' où l'extraction normale échoue (équivalent à un 'imprimer en PDF').",
        )
    with col_o4:
        nom_sortie = st.text_input(
            "Nom du fichier Excel",
            value="ecritures_banque",
            help="Sans l'extension .xlsx",
        )

# ---------- Zone de dépôt ----------
uploaded_file = st.file_uploader(
    "Déposez votre PDF de relevé bancaire ici",
    type=['pdf'],
    help="Glissez-déposez ou cliquez pour parcourir. Max 200 Mo.",
)

# ---------- Récupération de la clé API Gemini ----------
# Compatible Streamlit Cloud (st.secrets) ET Render/autres (variable d'environnement)
import os

gemini_api_key = None
# 1. Essayer les secrets Streamlit (Streamlit Cloud)
try:
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", None)
except Exception:
    gemini_api_key = None
# 2. Sinon, essayer la variable d'environnement (Render, Docker, etc.)
if not gemini_api_key:
    gemini_api_key = os.environ.get("GEMINI_API_KEY", None)

# ---------- Traitement ----------
if uploaded_file is not None:
    st.markdown(f"""
    <div style="padding: 10px 14px; background: #F8F4F0; border-radius: 6px; font-size: 13px; margin: 1rem 0;">
        📎 <strong>{uploaded_file.name}</strong> &nbsp;·&nbsp; {uploaded_file.size / 1024:.1f} Ko
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀  Lancer l'extraction", key="extract_btn"):
        with st.spinner("Extraction en cours..."):
            pdf_bytes = uploaded_file.read()
            
            try:
                transactions, metadata = extract_transactions(
                    pdf_bytes=pdf_bytes,
                    gemini_api_key=gemini_api_key,
                    force_ai=force_ai,
                    force_image=force_image,
                )
                
                # Extraire les infos de solde pour la vérification
                solde_info = extract_solde_info(pdf_bytes)
                
                # Stocker dans la session pour réutilisation
                st.session_state['transactions'] = transactions
                st.session_state['metadata'] = metadata
                st.session_state['solde_info'] = solde_info
                st.session_state['compte_banque'] = compte_banque
                st.session_state['compte_contrepartie'] = compte_contrepartie
                st.session_state['nom_sortie'] = nom_sortie
                
            except Exception as e:
                st.error(f"❌ Erreur lors de l'extraction : {str(e)}")
                st.stop()

# ---------- Affichage des résultats ----------
if 'transactions' in st.session_state and st.session_state['transactions']:
    transactions = st.session_state['transactions']
    metadata = st.session_state['metadata']
    
    # ----- Bandeau de succès -----
    banque = metadata.get('banque_detectee') or 'Non détectée'
    methode = metadata.get('method', 'pdfplumber')
    
    st.markdown(f"""
    <div class="success-box">
        ✅ <strong>{len(transactions)} transactions extraites</strong> &nbsp;·&nbsp; 
        Banque : <strong>{banque}</strong> &nbsp;·&nbsp; 
        Méthode : <em>{methode}</em>
    </div>
    """, unsafe_allow_html=True)
    
    # ----- Avertissement si peu de transactions -----
    if len(transactions) < 3 and not force_ai:
        st.markdown("""
        <div class="warning-box">
            ⚠️ Peu de transactions détectées. Si le résultat semble incomplet, essayez de cocher 
            "Forcer l'utilisation de l'IA" dans les options ci-dessus.
        </div>
        """, unsafe_allow_html=True)
    
    # ----- Vérification du solde -----
    st.markdown("##### 🔎 Vérification du solde")
    st.caption("Vérifie que l'extraction est complète en recalculant le solde à partir des transactions.")
    
    if st.button("Calculer et vérifier le solde", key="verif_solde_btn"):
        solde_info = st.session_state.get('solde_info', {})
        verif = verifier_solde(transactions, solde_info)
        st.session_state['verif_result'] = verif
    
    # Afficher le résultat de vérification s'il existe
    if 'verif_result' in st.session_state:
        verif = st.session_state['verif_result']
        
        # Totaux calculés (toujours affichés)
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            st.metric("Total débits", f"{verif['total_debit_calcule']:,.2f} €".replace(',', ' '))
        with col_v2:
            st.metric("Total crédits", f"{verif['total_credit_calcule']:,.2f} €".replace(',', ' '))
        with col_v3:
            st.metric("Variation", f"{verif['variation_calculee']:,.2f} €".replace(',', ' '))
        
        # Comparaison avec les totaux du relevé (si détectés)
        lignes_compare = []
        if 'ecart_debit' in verif:
            ok = abs(verif['ecart_debit']) < 0.01
            icone = "✅" if ok else "⚠️"
            lignes_compare.append(
                f"{icone} **Total débits relevé** : {verif['total_debit_releve']:,.2f} € "
                f"— écart : {verif['ecart_debit']:+,.2f} €".replace(',', ' ')
            )
        if 'ecart_credit' in verif:
            ok = abs(verif['ecart_credit']) < 0.01
            icone = "✅" if ok else "⚠️"
            lignes_compare.append(
                f"{icone} **Total crédits relevé** : {verif['total_credit_releve']:,.2f} € "
                f"— écart : {verif['ecart_credit']:+,.2f} €".replace(',', ' ')
            )
        
        if lignes_compare:
            st.markdown("**Comparaison avec les totaux imprimés sur le relevé :**")
            for ligne in lignes_compare:
                st.markdown(ligne)
        
        # Vérification ancien solde + variation = nouveau solde
        if 'solde_ok' in verif:
            if verif['solde_ok']:
                st.markdown(f"""
                <div class="success-box">
                    ✅ <strong>Solde vérifié et cohérent !</strong><br>
                    Ancien solde ({verif['ancien_solde']:,.2f} €) + variation ({verif['variation_calculee']:,.2f} €) 
                    = nouveau solde ({verif['nouveau_solde_calcule']:,.2f} €), 
                    conforme au relevé. L'extraction est complète.
                </div>
                """.replace(',', ' '), unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="warning-box">
                    ⚠️ <strong>Écart de solde détecté : {verif['ecart_solde']:+,.2f} €</strong><br>
                    Nouveau solde calculé : {verif['nouveau_solde_calcule']:,.2f} € &nbsp;·&nbsp;
                    Nouveau solde du relevé : {verif['nouveau_solde_releve']:,.2f} €<br>
                    Il manque peut-être des transactions, ou certaines sont mal extraites. 
                    Essayez le mode image (OCR) ou l'IA dans les options.
                </div>
                """.replace(',', ' '), unsafe_allow_html=True)
        elif not lignes_compare:
            # Aucune info de solde détectée sur le relevé
            st.info(
                "ℹ️ Impossible de trouver l'ancien/nouveau solde ou les totaux sur ce relevé "
                "pour une vérification automatique. Les totaux calculés ci-dessus restent "
                "disponibles pour une vérification manuelle."
            )
    
    st.markdown("---")
    
    # ----- Onglets : Aperçu transactions / Aperçu Excel -----
    tab1, tab2 = st.tabs(["📋 Transactions extraites", "📊 Aperçu du fichier Excel"])
    
    with tab1:
        st.caption("Liste des transactions détectées (1 ligne = 1 transaction)")
        df_trans = pd.DataFrame(transactions)
        df_trans_display = df_trans.copy()
        df_trans_display['debit'] = df_trans_display['debit'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x else ''
        )
        df_trans_display['credit'] = df_trans_display['credit'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x else ''
        )
        df_trans_display.columns = ['Date', 'Libellé', 'Débit', 'Crédit']
        st.dataframe(df_trans_display, use_container_width=True, hide_index=True)
    
    with tab2:
        st.caption("Aperçu des écritures comptables (2 lignes par transaction = partie double)")
        df_excel = build_preview_dataframe(
            transactions,
            compte_banque=st.session_state['compte_banque'],
            compte_contrepartie=st.session_state['compte_contrepartie'],
        )
        # Formater pour affichage
        df_display = df_excel.copy()
        df_display['DEBIT'] = df_display['DEBIT'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != '' else ''
        )
        df_display['CREDIT'] = df_display['CREDIT'].apply(
            lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',') if x != '' else ''
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Totaux
        total_debit = sum(t['debit'] or 0 for t in transactions) + sum(t['credit'] or 0 for t in transactions)
        total_credit = total_debit  # Partie double = équilibre
        st.caption(f"💰 Total débit : **{total_debit:,.2f} €** &nbsp;·&nbsp; Total crédit : **{total_credit:,.2f} €** (équilibré ✓)")
    
    # ----- Bouton de téléchargement -----
    st.markdown("---")
    
    excel_file = generate_excel(
        transactions,
        compte_banque=st.session_state['compte_banque'],
        compte_contrepartie=st.session_state['compte_contrepartie'],
    )
    
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="⬇️  Télécharger l'Excel comptable",
            data=excel_file,
            file_name=f"{st.session_state['nom_sortie']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

elif 'transactions' in st.session_state and not st.session_state['transactions']:
    st.markdown("""
    <div class="warning-box">
        ⚠️ Aucune transaction détectée dans ce PDF. 
        Essayez de cocher "Forcer l'utilisation de l'IA" dans les options ci-dessus, ou vérifiez que le PDF est bien un relevé bancaire.
    </div>
    """, unsafe_allow_html=True)

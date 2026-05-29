"""
Extraction des lignes de transactions depuis un PDF de relevé bancaire.
Stratégie en cascade :
1. pdfplumber avec analyse par POSITIONS SPATIALES (méthode pro, fiable)
2. OCR (pytesseract) si le PDF est un scan
3. Gemini API en dernier recours (PDFs très atypiques)
"""
import re
import io
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import pdfplumber


# ---------- Regex ----------
# Date au format JJ.MM ou JJ/MM (jour.mois sans année, fréquent sur les relevés FR)
DATE_SHORT_RE = re.compile(r'^(\d{2})[./](\d{2})$')

# Date complète : JJ/MM/AAAA ou JJ/MM/AA
DATE_FULL_RE = re.compile(r'(\d{2})[/.\-](\d{2})[/.\-](\d{2,4})')

# Montant FR : 1 234,56 ou 1234,56 ou 1.234,56
AMOUNT_RE = re.compile(r'^-?\d{1,3}(?:[\s.]\d{3})*,\d{2}$')

# Détection année dans la date d'arrêté
YEAR_RE = re.compile(r"[Dd]ate\s+d['']arr[êe]t[ée]\s*:\s*\d{1,2}\s+\w+\s+(\d{4})")

# Détection des soldes et totaux (pour la vérification)
ANCIEN_SOLDE_RE = re.compile(
    r"[Aa]ncien\s+solde\s+(créditeur|débiteur|crediteur|debiteur)\b.*?(\d{1,3}(?:[\s.]\d{3})*,\d{2})",
    re.IGNORECASE
)
NOUVEAU_SOLDE_RE = re.compile(
    r"[Nn]ouveau\s+solde\s+(créditeur|débiteur|crediteur|debiteur)\b.*?(\d{1,3}(?:[\s.]\d{3})*,\d{2})",
    re.IGNORECASE
)
TOTAL_OPE_RE = re.compile(
    r"[Tt]otal\s+des\s+op[ée]rations\s+(\d{1,3}(?:[\s.]\d{3})*,\d{2})\s+(\d{1,3}(?:[\s.]\d{3})*,\d{2})",
    re.IGNORECASE
)

# Détection banque
BANQUE_PATTERNS = {
    'Crédit Agricole': ['credit agricole', 'crédit agricole'],
    'BNP Paribas': ['bnp paribas'],
    'Société Générale': ['societe generale', 'société générale'],
    'LCL': ['lcl', 'credit lyonnais'],
    'Crédit Mutuel': ['credit mutuel', 'crédit mutuel'],
    'CIC': ['cic '],
    'La Banque Postale': ['banque postale'],
    "Caisse d'Épargne": ["caisse d'epargne", "caisse d'épargne"],
    'HSBC': ['hsbc'],
    'Boursorama': ['boursorama'],
    'Revolut': ['revolut'],
    'N26': ['n26 bank'],
    'Qonto': ['qonto'],
    'BPCE': ['bpce'],
    'Banque Populaire': ['banque populaire'],
}

# Caractères parasites à supprimer
PARASITIC_CHARS = ['¨', 'þ', '*']

# Mots-clés qui indiquent qu'une ligne n'est PAS une transaction (à ignorer)
IGNORE_KEYWORDS = [
    'ancien solde', 'nouveau solde', 'solde créditeur', 'solde débiteur',
    'total des opérations', 'total opérations', 'report',
    'date opé', 'date valeur', 'libellé des opérations',
]


# ---------- Utilitaires ----------
def clean_libelle(text: str) -> str:
    """Nettoie un libellé : retire caractères parasites, espaces multiples."""
    for ch in PARASITIC_CHARS:
        text = text.replace(ch, ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_amount(amount_str: str) -> Optional[float]:
    """Convertit '1 234,56' ou '1.234,56' en float 1234.56"""
    if not amount_str:
        return None
    cleaned = amount_str.replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return abs(float(cleaned))
    except ValueError:
        return None


def normalize_date_full(date_str: str) -> Optional[str]:
    """Convertit une date complète au format JJ/MM/AAAA."""
    m = DATE_FULL_RE.search(date_str)
    if not m:
        return None
    day, month, year = m.groups()
    if len(year) == 2:
        year = '20' + year if int(year) < 50 else '19' + year
    try:
        datetime(int(year), int(month), int(day))
        return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    except ValueError:
        return None


def detect_year_from_text(text: str) -> str:
    """Détecte l'année du relevé depuis 'Date d'arrêté : 31 Décembre 2025'."""
    m = YEAR_RE.search(text)
    if m:
        return m.group(1)
    # Fallback : chercher la première année 20XX dans le texte
    m = re.search(r'\b(20\d{2})\b', text)
    return m.group(1) if m else str(datetime.now().year)


def detect_banque(text: str) -> Optional[str]:
    """Détecte la banque depuis le texte du PDF."""
    text_lower = text.lower()
    for banque, patterns in BANQUE_PATTERNS.items():
        if any(p in text_lower for p in patterns):
            return banque
    return None


def is_ignorable_line(text: str) -> bool:
    """Vérifie si une ligne contient des mots-clés à ignorer."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in IGNORE_KEYWORDS)


# ---------- Méthode 1 : Extraction par positions spatiales ----------
def extract_with_positions(pdf_bytes: bytes) -> Tuple[List[Dict], Dict]:
    """
    Extraction par analyse des positions X,Y des mots.
    Méthode robuste qui marche pour la plupart des banques françaises.
    """
    transactions = []
    metadata = {
        'method': 'pdfplumber (positions)',
        'pages_processed': 0,
        'is_scanned': False,
        'banque_detectee': None,
    }
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        metadata['pages_processed'] = len(pdf.pages)
        
        # Concaténer tout le texte pour détection année + banque
        all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        
        # PDF scanné : très peu de texte extractible
        if len(all_text.strip()) < 100:
            metadata['is_scanned'] = True
            return [], metadata
        
        year = detect_year_from_text(all_text)
        metadata['banque_detectee'] = detect_banque(all_text)
        metadata['year_detected'] = year
        
        # Parcourir chaque page
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            page_width = page.width
            page_tx = _parse_positioned_words(words, year, page_width=page_width)
            transactions.extend(page_tx)

    # Filtrer les transactions sans montant
    transactions = [t for t in transactions if t.get('debit') or t.get('credit')]

    return transactions, metadata


def _parse_positioned_words(
    words: List[Dict],
    year: str,
    page_width: Optional[float] = None,
) -> List[Dict]:
    """
    Cœur de l'algorithme d'extraction par positions spatiales.
    Prend une liste de mots positionnés ({'text','x0','x1','top'}) et retourne
    les transactions de cette page.

    Utilisé à la fois par :
    - extract_with_positions (mots venant de pdfplumber)
    - extract_with_ocr (mots venant de Tesseract image_to_data)
    """
    transactions = []

    # Repérer les positions X des colonnes Débit et Crédit
    debit_x, credit_x = None, None
    for w in words:
        txt = w['text']
        if txt == 'Débit' and debit_x is None:
            debit_x = (w['x0'] + w['x1']) / 2
        elif txt == 'Crédit' and credit_x is None and w['x0'] > 350:
            # On exclut le mot "Crédit" qui pourrait apparaître dans "Crédit Agricole"
            credit_x = (w['x0'] + w['x1']) / 2

    # Si on ne trouve pas les colonnes, fallback basé sur la largeur de page
    if not debit_x or not credit_x:
        if not page_width:
            # Estimer la largeur depuis le mot le plus à droite
            page_width = max((w['x1'] for w in words), default=600)
        debit_x = page_width * 0.6
        credit_x = page_width * 0.75

    # Grouper les mots par ligne (même Y, tolérance 3px)
    lines_by_y = {}
    for w in words:
        y = round(w['top'])
        key = None
        for existing_y in lines_by_y:
            if abs(existing_y - y) <= 3:
                key = existing_y
                break
        if key is None:
            key = y
        lines_by_y.setdefault(key, []).append(w)

    # Trier les lignes par Y croissant
    sorted_lines = sorted(lines_by_y.items())

    # Parcourir les lignes
    current_tx = None
    for y, words_in_line in sorted_lines:
        words_in_line.sort(key=lambda w: w['x0'])
        texts = [w['text'] for w in words_in_line]
        line_text = ' '.join(texts)

        # Ignorer les lignes parasites
        if is_ignorable_line(line_text):
            if current_tx:
                transactions.append(current_tx)
                current_tx = None
            continue

        # Détecter le pattern : ligne contient 2 dates JJ.MM JJ.MM consécutives
        # (parfois précédées d'un numéro de page parasite comme "39498")
        date_idx = _find_date_pair_index(texts)

        if date_idx is not None:
            m1 = DATE_SHORT_RE.match(texts[date_idx])
            m2 = DATE_SHORT_RE.match(texts[date_idx + 1])

            if m1 and m2:
                # Nouvelle transaction : sauvegarder la précédente
                if current_tx:
                    transactions.append(current_tx)

                day, month = m1.groups()
                date_str = f"{day}/{month}/{year}"

                # Extraire le ou les montants de la ligne (et reconstituer ceux à espaces)
                amounts_in_line = _extract_amounts_from_words(words_in_line)

                debit, credit = None, None
                libelle = ""

                if amounts_in_line:
                    # Dernier montant trouvé = montant de la transaction
                    amt_text, amt_x, amt_word_indices = amounts_in_line[-1]

                    # Comparer position à débit_x vs credit_x
                    if abs(amt_x - debit_x) < abs(amt_x - credit_x):
                        debit = amt_text
                    else:
                        credit = amt_text

                    # Libellé = mots après les 2 dates, sauf ceux du montant
                    lib_words = []
                    for idx in range(date_idx + 2, len(words_in_line)):
                        w = words_in_line[idx]
                        if idx not in amt_word_indices and not AMOUNT_RE.match(w['text']):
                            lib_words.append(w['text'])
                    libelle = clean_libelle(' '.join(lib_words))
                else:
                    libelle = clean_libelle(' '.join(texts[date_idx + 2:]))

                current_tx = {
                    'date': date_str,
                    'libelle': libelle,
                    'debit': parse_amount(debit) if debit else None,
                    'credit': parse_amount(credit) if credit else None,
                }
                continue

        # Ligne sans date : suite du libellé OU montant orphelin
        if current_tx:
            amounts_in_line = _extract_amounts_from_words(words_in_line)

            # Si la transaction courante n'a pas de montant et qu'on en trouve un
            if current_tx['debit'] is None and current_tx['credit'] is None and amounts_in_line:
                amt_text, amt_x, _ = amounts_in_line[-1]
                if abs(amt_x - debit_x) < abs(amt_x - credit_x):
                    current_tx['debit'] = parse_amount(amt_text)
                else:
                    current_tx['credit'] = parse_amount(amt_text)
            else:
                # Suite du libellé (limité à 120 chars pour éviter les abus)
                extra_words = [w['text'] for w in words_in_line if not AMOUNT_RE.match(w['text'])]
                extra = clean_libelle(' '.join(extra_words))
                if extra and len(current_tx['libelle']) + len(extra) < 120:
                    current_tx['libelle'] = clean_libelle(current_tx['libelle'] + ' ' + extra)

    # Sauvegarder la dernière transaction de la page
    if current_tx:
        transactions.append(current_tx)

    return transactions


def _find_date_pair_index(texts: List[str]) -> Optional[int]:
    """
    Cherche l'index dans la liste de mots où on trouve 2 dates JJ.MM consécutives
    (le début d'une transaction). Retourne None si rien trouvé.
    Gère les numéros de page parasites en début de ligne.
    """
    # On limite la recherche aux 3 premiers mots (au-delà, c'est suspicieux)
    for i in range(min(3, len(texts) - 1)):
        if DATE_SHORT_RE.match(texts[i]) and DATE_SHORT_RE.match(texts[i + 1]):
            return i
    return None


def _extract_amounts_from_words(words_in_line: List[Dict]) -> List[Tuple[str, float, set]]:
    """
    Extrait les montants d'une ligne en reconstituant ceux avec espaces milliers.
    Ex : "1" + "380,00" → "1 380,00"
    Retourne [(text, x_center, set_word_indices)]
    """
    amounts = []
    n = len(words_in_line)
    used_indices = set()
    
    for i in range(n):
        if i in used_indices:
            continue
        w = words_in_line[i]
        txt = w['text']
        
        # Cas 1 : montant complet "1234,56" ou "1.234,56"
        if AMOUNT_RE.match(txt):
            amounts.append((txt, (w['x0'] + w['x1']) / 2, {i}))
            used_indices.add(i)
            continue
        
        # Cas 2 : nombre entier "1" suivi d'un montant "380,00" (espace milliers)
        if re.match(r'^\d{1,3}$', txt) and i + 1 < n:
            next_w = words_in_line[i + 1]
            next_txt = next_w['text']
            # Vérifier que le mot suivant ressemble à un suffixe de montant "XXX,XX"
            if re.match(r'^\d{3},\d{2}$', next_txt):
                # Vérifier qu'ils sont proches horizontalement (gap < 20px)
                if next_w['x0'] - w['x1'] < 20:
                    combined = txt + ' ' + next_txt
                    x_center = (w['x0'] + next_w['x1']) / 2
                    amounts.append((combined, x_center, {i, i + 1}))
                    used_indices.add(i)
                    used_indices.add(i + 1)
                    continue
    
    return amounts


# ---------- Méthode 2 : OCR pour les PDFs scannés ou aplatis en image ----------
def extract_with_ocr(pdf_bytes: bytes, dpi: int = 300) -> Tuple[List[Dict], Dict]:
    """
    OCR du PDF avec pytesseract.
    Utilise image_to_data pour récupérer les POSITIONS des mots,
    ce qui permet de réutiliser le même algorithme de tri débit/crédit
    que l'extraction native (méthode fiable).

    Fonctionne pour :
    - les relevés scannés
    - le mode "force image" (PDF natif aplati en image avant OCR)
    """
    metadata = {
        'method': 'OCR (pytesseract + positions)',
        'pages_processed': 0,
        'is_scanned': True,
        'banque_detectee': None,
    }

    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as e:
        metadata['error'] = f"Modules OCR non installés : {e}"
        return [], metadata

    # Convertir le PDF en images (dpi élevé = meilleure reconnaissance)
    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as e:
        metadata['error'] = f"Conversion PDF→image échouée : {e}"
        return [], metadata

    metadata['pages_processed'] = len(images)

    # 1er passage : récupérer tout le texte pour détecter année + banque
    full_text_parts = []
    pages_words = []  # liste de listes de mots positionnés (un par page)

    for img in images:
        # image_to_data renvoie un dict avec text, left, top, width, height, conf
        data = pytesseract.image_to_data(
            img, lang='fra', output_type=pytesseract.Output.DICT
        )
        words = _ocr_data_to_words(data)
        pages_words.append(words)
        full_text_parts.append(' '.join(w['text'] for w in words))

    all_text = '\n'.join(full_text_parts)
    year = detect_year_from_text(all_text)
    metadata['banque_detectee'] = detect_banque(all_text)
    metadata['year_detected'] = year

    # 2e passage : parser chaque page avec l'algo par positions
    transactions = []
    for words in pages_words:
        page_tx = _parse_positioned_words(words, year)
        transactions.extend(page_tx)

    # Filtrer les transactions sans montant
    transactions = [t for t in transactions if t.get('debit') or t.get('credit')]

    # Si l'algo par positions n'a rien donné, fallback sur le parsing texte simple
    if not transactions:
        metadata['method'] = 'OCR (pytesseract + texte)'
        transactions = _parse_text_lines(all_text, year)

    return transactions, metadata


def _ocr_data_to_words(data: dict) -> List[Dict]:
    """
    Convertit la sortie de pytesseract.image_to_data en liste de mots
    au même format que pdfplumber : {'text', 'x0', 'x1', 'top'}.
    Ne garde que les mots avec une confiance suffisante.
    """
    words = []
    n = len(data['text'])
    for i in range(n):
        txt = data['text'][i].strip()
        if not txt:
            continue
        try:
            conf = float(data['conf'][i])
        except (ValueError, TypeError):
            conf = -1
        # Ignorer les mots de très faible confiance (bruit OCR)
        if conf < 30:
            continue
        left = data['left'][i]
        top = data['top'][i]
        width = data['width'][i]
        words.append({
            'text': txt,
            'x0': float(left),
            'x1': float(left + width),
            'top': float(top),
        })
    return words


def _parse_text_lines(text: str, year: str) -> List[Dict]:
    """Parser de texte brut (utilisé par l'OCR et le fallback)."""
    transactions = []
    lines = text.split('\n')
    current_tx = None
    
    for line in lines:
        line = line.strip()
        if not line or is_ignorable_line(line):
            if current_tx:
                transactions.append(current_tx)
                current_tx = None
            continue
        
        # Ligne qui commence par JJ.MM ou JJ/MM
        m = re.match(r'^(\d{2})[./](\d{2})\s', line)
        if m:
            if current_tx:
                transactions.append(current_tx)
            
            day, month = m.groups()
            date_str = f"{day}/{month}/{year}"
            
            # Extraire les montants
            amounts = re.findall(r'\d{1,3}(?:[\s.]\d{3})*,\d{2}', line)
            
            debit, credit = None, None
            if amounts:
                # En OCR, on ne peut pas distinguer débit/crédit par position
                # → on suppose que c'est le dernier montant, en crédit par défaut
                # (l'utilisateur pourra forcer l'IA si problème)
                last_amount = amounts[-1]
                credit = parse_amount(last_amount)
            
            # Libellé : retirer les dates + montants
            libelle = line
            libelle = re.sub(r'^\d{2}[./]\d{2}\s+\d{2}[./]\d{2}\s+', '', libelle)
            libelle = re.sub(r'^\d{2}[./]\d{2}\s+', '', libelle)
            for amt in amounts:
                libelle = libelle.replace(amt, '')
            libelle = clean_libelle(libelle)
            
            current_tx = {
                'date': date_str,
                'libelle': libelle,
                'debit': debit,
                'credit': credit,
            }
        elif current_tx:
            # Suite du libellé
            extra = clean_libelle(line)
            if extra and len(current_tx['libelle']) + len(extra) < 120:
                current_tx['libelle'] = clean_libelle(current_tx['libelle'] + ' ' + extra)
    
    if current_tx:
        transactions.append(current_tx)
    
    return [t for t in transactions if t.get('debit') or t.get('credit')]


# ---------- Méthode 3 : Gemini API ----------
def extract_with_gemini(
    pdf_bytes: bytes,
    api_key: str,
    as_images: bool = False,
) -> Tuple[List[Dict], Dict]:
    """
    Utilisation de Gemini pour extraire les transactions.
    Utilise le modèle Gemini 2.0 Flash (actuel).

    Args:
        pdf_bytes: contenu binaire du PDF.
        api_key: clé API Gemini.
        as_images: si True, le PDF est d'abord converti en images puis envoyé à
                   l'IA en tant qu'images (utile pour PDF natifs "capricieux"
                   dont la structure interne perturbe même l'IA).
    """
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    # Liste des modèles à essayer (du plus récent au plus stable)
    MODELS_TO_TRY = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-001',
        'gemini-flash-latest',
        'gemini-1.5-flash-latest',
    ]

    prompt = """Tu es un assistant spécialisé en extraction de données bancaires.
Analyse ce relevé bancaire et extrais TOUTES les transactions.

Retourne UNIQUEMENT un JSON valide (sans markdown, sans backticks) avec cette structure exacte :
{
  "banque": "nom de la banque détectée",
  "transactions": [
    {
      "date": "JJ/MM/AAAA",
      "libelle": "libellé complet de l'opération",
      "debit": 45.20,
      "credit": null
    }
  ]
}

RÈGLES STRICTES :
- Date au format JJ/MM/AAAA uniquement (utilise l'année indiquée sur le relevé)
- Montants en nombre décimal positif (pas de string, pas de virgule, pas de négatif)
- Un montant = soit dans "debit" soit dans "credit", jamais les deux
- L'autre champ doit être null
- Inclure TOUTES les transactions, n'en oublie aucune
- Ne pas inclure les lignes : ancien solde, nouveau solde, total des opérations
- Libellé : nettoyer (pas de date, pas de montant, pas de symboles ¨ þ *)
- Distinguer débit/crédit selon la POSITION DE LA COLONNE dans le tableau
"""

    # Préparer le contenu à envoyer à Gemini :
    # - mode normal : le PDF brut (l'IA fait elle-même son OCR si scanné)
    # - mode images : chaque page convertie en image PNG (contourne les
    #   structures internes de PDF capricieux)
    if as_images:
        try:
            from pdf2image import convert_from_bytes
        except ImportError as e:
            raise RuntimeError(f"pdf2image requis pour le mode image : {e}")

        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
        except Exception as e:
            raise RuntimeError(f"Conversion PDF→image échouée : {e}")

        # Construire le contenu : prompt + une image par page
        content = [prompt]
        for img in images:
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            content.append({
                'mime_type': 'image/png',
                'data': img_buffer.getvalue(),
            })
    else:
        # Envoi du PDF brut
        content = [
            prompt,
            {'mime_type': 'application/pdf', 'data': pdf_bytes}
        ]

    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(content)

            raw = response.text.strip()
            # Nettoyer markdown éventuel
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

            data = json.loads(raw)
            transactions = data.get('transactions', [])

            # Normaliser les dates
            for t in transactions:
                if t.get('date'):
                    normalized = normalize_date_full(t['date'])
                    if normalized:
                        t['date'] = normalized
                # Nettoyer libellé
                if t.get('libelle'):
                    t['libelle'] = clean_libelle(t['libelle'])

            method_suffix = ' [mode image]' if as_images else ''
            metadata = {
                'method': f'Gemini ({model_name}){method_suffix}',
                'banque_detectee': data.get('banque'),
                'model_used': model_name,
            }

            return transactions, metadata

        except Exception as e:
            last_error = f"{model_name}: {str(e)[:200]}"
            continue

    # Tous les modèles ont échoué
    raise RuntimeError(f"Aucun modèle Gemini disponible. Dernière erreur : {last_error}")


# ---------- Extraction des soldes (pour vérification) ----------
def extract_solde_info(pdf_bytes: bytes) -> Dict:
    """
    Extrait les informations de solde du relevé pour permettre la vérification :
    - ancien solde (avec son sens : créditeur/débiteur)
    - nouveau solde (avec son sens)
    - total des opérations (débit / crédit) si présent

    Retourne un dict avec les clés trouvées (valeurs en float), ou {} si rien.
    """
    info = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        return info

    # Ancien solde
    m = ANCIEN_SOLDE_RE.search(all_text)
    if m:
        sens = (m.group(1) or '').lower()
        val = parse_amount(m.group(2))
        info['ancien_solde'] = val
        is_cred = sens.startswith('cr')
        is_deb = sens.startswith('d')
        info['ancien_solde_sens'] = 'crediteur' if is_cred else ('debiteur' if is_deb else None)

    # Nouveau solde
    m = NOUVEAU_SOLDE_RE.search(all_text)
    if m:
        sens = (m.group(1) or '').lower()
        val = parse_amount(m.group(2))
        info['nouveau_solde'] = val
        is_cred = sens.startswith('cr')
        is_deb = sens.startswith('d')
        info['nouveau_solde_sens'] = 'crediteur' if is_cred else ('debiteur' if is_deb else None)

    # Total des opérations (débit, crédit)
    m = TOTAL_OPE_RE.search(all_text)
    if m:
        info['total_debit_releve'] = parse_amount(m.group(1))
        info['total_credit_releve'] = parse_amount(m.group(2))

    return info


def verifier_solde(transactions: List[Dict], solde_info: Dict) -> Dict:
    """
    Calcule la vérification du solde à partir des transactions extraites
    et des informations de solde du relevé.

    Convention : sur un relevé bancaire vu côté client,
    - un CRÉDIT augmente le solde (entrée d'argent)
    - un DÉBIT diminue le solde (sortie d'argent)

    Retourne un dict avec les totaux calculés et le résultat de la vérification.
    """
    total_credit = sum(t['credit'] or 0 for t in transactions)
    total_debit = sum(t['debit'] or 0 for t in transactions)

    resultat = {
        'nb_transactions': len(transactions),
        'total_credit_calcule': total_credit,
        'total_debit_calcule': total_debit,
        'variation_calculee': total_credit - total_debit,
    }

    # Comparaison avec les totaux du relevé (si présents)
    if 'total_debit_releve' in solde_info:
        resultat['total_debit_releve'] = solde_info['total_debit_releve']
        resultat['ecart_debit'] = round(total_debit - solde_info['total_debit_releve'], 2)
    if 'total_credit_releve' in solde_info:
        resultat['total_credit_releve'] = solde_info['total_credit_releve']
        resultat['ecart_credit'] = round(total_credit - solde_info['total_credit_releve'], 2)

    # Vérification via ancien + variation = nouveau solde
    if 'ancien_solde' in solde_info and 'nouveau_solde' in solde_info:
        ancien = solde_info['ancien_solde']
        nouveau = solde_info['nouveau_solde']
        sens_ancien = solde_info.get('ancien_solde_sens')
        sens_nouveau = solde_info.get('nouveau_solde_sens')

        # Convertir en valeur signée : créditeur = positif, débiteur = négatif
        ancien_signe = ancien if sens_ancien != 'debiteur' else -ancien
        nouveau_signe = nouveau if sens_nouveau != 'debiteur' else -nouveau

        nouveau_attendu = ancien_signe + (total_credit - total_debit)

        resultat['ancien_solde'] = ancien_signe
        resultat['nouveau_solde_releve'] = nouveau_signe
        resultat['nouveau_solde_calcule'] = round(nouveau_attendu, 2)
        resultat['ecart_solde'] = round(nouveau_attendu - nouveau_signe, 2)
        resultat['solde_ok'] = abs(resultat['ecart_solde']) < 0.01

    return resultat


# ---------- Fonction principale ----------
def extract_transactions(
    pdf_bytes: bytes,
    gemini_api_key: Optional[str] = None,
    force_ai: bool = False,
    force_image: bool = False,
) -> Tuple[List[Dict], Dict]:
    """
    Extraction en cascade :
    1. force_ai + force_image → Gemini avec PDF converti en images
    2. force_ai seul → Gemini avec PDF brut
    3. force_image seul → OCR local sur images
    4. Sinon : pdfplumber (positions spatiales)
    5. Si PDF scanné → OCR automatique
    6. Si toujours rien → Gemini (si clé fournie)
    """
    # Cas 1 : combinaison IA + image → IA reçoit les pages converties en images
    if force_ai and force_image:
        if not gemini_api_key:
            raise RuntimeError("Aucune clé Gemini fournie. Impossible de forcer l'IA.")
        return extract_with_gemini(pdf_bytes, gemini_api_key, as_images=True)

    # Cas 2 : IA seule → IA reçoit le PDF brut
    if force_ai:
        if not gemini_api_key:
            raise RuntimeError("Aucune clé Gemini fournie. Impossible de forcer l'IA.")
        return extract_with_gemini(pdf_bytes, gemini_api_key, as_images=False)

    # Cas 3 : mode image seul (sans IA) → OCR local sur les images
    if force_image:
        ocr_transactions, ocr_metadata = extract_with_ocr(pdf_bytes)
        ocr_metadata['method'] = ocr_metadata.get('method', 'OCR') + ' [mode image forcé]'
        # Si l'OCR forcé échoue et qu'on a une clé, tenter Gemini en dernier recours
        if not ocr_transactions and gemini_api_key:
            try:
                return extract_with_gemini(pdf_bytes, gemini_api_key)
            except Exception as e:
                ocr_metadata['ai_error'] = str(e)
        return ocr_transactions, ocr_metadata

    # Étape 1 : pdfplumber par positions
    transactions, metadata = extract_with_positions(pdf_bytes)

    # Étape 2 : Si scanné, basculer en OCR
    if metadata.get('is_scanned'):
        ocr_transactions, ocr_metadata = extract_with_ocr(pdf_bytes)
        if ocr_transactions:
            return ocr_transactions, ocr_metadata
        # Si l'OCR a échoué aussi, essayer Gemini
        if gemini_api_key:
            try:
                return extract_with_gemini(pdf_bytes, gemini_api_key)
            except Exception as e:
                ocr_metadata['ai_error'] = str(e)
                return [], ocr_metadata
        return [], ocr_metadata

    # Étape 3 : Si extraction Python a donné peu de résultats → fallback Gemini
    if len(transactions) < 3 and gemini_api_key:
        try:
            ai_transactions, ai_metadata = extract_with_gemini(pdf_bytes, gemini_api_key)
            if len(ai_transactions) > len(transactions):
                ai_metadata['method'] = f"{ai_metadata['method']} (fallback)"
                return ai_transactions, ai_metadata
        except Exception as e:
            metadata['ai_error'] = str(e)

    return transactions, metadata

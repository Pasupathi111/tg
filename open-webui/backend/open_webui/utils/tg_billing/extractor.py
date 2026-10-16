"""Text extraction (pdf/docx/txt/csv/xlsx) and regex parsing of PO / quotation / contract
billing instructions. Heavy libs are imported lazily."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Dict, List, Optional

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    )
}


# --------------------------------------------------------------------------- text extraction
def extract_text(filename: str, data: bytes) -> str:
    name = (filename or '').lower()
    if name.endswith('.pdf'):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return '\n'.join((p.extract_text() or '') for p in reader.pages).strip()
    if name.endswith('.docx'):
        import docx

        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for r in t.rows:
                parts.append(' | '.join(c.text.strip() for c in r.cells))
        return '\n'.join(parts).strip()
    if name.endswith('.xlsx') or name.endswith('.xlsm'):
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f'[{ws.title}]')
            for r in ws.iter_rows(values_only=True):
                cells = ['' if c is None else str(c) for c in r]
                if any(cells):
                    out.append(' | '.join(cells))
        return '\n'.join(out).strip()
    text = _decode(data)
    if name.endswith('.csv'):
        rows = csv.reader(io.StringIO(text))
        return '\n'.join(' | '.join(c.strip() for c in r) for r in rows if any(r)).strip()
    return text.strip()


def _decode(data: bytes) -> str:
    for enc in ('utf-8-sig', 'utf-16', 'cp1252', 'latin-1'):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode('utf-8', 'replace')


# --------------------------------------------------------------------------- parsing helpers
_DATE = (
    r'(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}'
    r'|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})'
)


def parse_date(s: str) -> Optional[str]:
    s = s.strip().rstrip('.,')
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', s)
    if m:  # day first (Singapore)
        return _mk(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})', s)
    if m and m[2][:3].lower() in MONTHS:
        return _mk(int(m[3]), MONTHS[m[2][:3].lower()], int(m[1]))
    m = re.fullmatch(r'([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', s)
    if m and m[1][:3].lower() in MONTHS:
        return _mk(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2]))
    return None


def _mk(y, m, d) -> Optional[str]:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


_AMT = r'(\d[\d,]*(?:\.\d+)?)'
_CUR = r'(?:S\$|SGD|\$)\s*'
_UNITS = {
    'monthly': r'(?:month|mth|mo|monthly)',
    'half_day': r'(?:half[\s-]?day|half[\s-]?days|hd)',
    'daily': r'(?:(?<!half )(?<!half-)(?<!half)day|daily)',
    'weekly': r'(?:week|wk|weekly)',
    'hourly': r'(?:hour|hr|hourly)',
}


def parse_rates(text: str) -> Dict[str, Optional[float]]:
    rates: Dict[str, Optional[float]] = {k: None for k in _UNITS}
    for key, unit in _UNITS.items():
        found = None
        # "SGD 5,200 per month" / "$180/half day"
        m = re.search(_CUR + _AMT + r'\s*(?:/|per|a|each|\s)\s*' + unit + r'\b', text, re.I)
        if m:
            found = m.group(1)
        else:
            # "Monthly rate: SGD 5,200" / "half-day rate - $180" / "Rate (monthly) ... 5200"
            m = re.search(unit + r'\s*(?:rate|charge|fee|price)s?\s*(?:\([^)]*\))?\s*[:\-=|]?\s*(?:' + _CUR + r')?' + _AMT, text, re.I)
            if m:
                found = m.group(1)
        if found:
            rates[key] = float(found.replace(',', ''))
    return rates


def _first(patterns: List[str], text: str, flags=re.I):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m
    return None


def parse_instructions(text: str, filename: str = '', employees: Optional[List[dict]] = None) -> dict:
    """Return {ref, doc_type, party, instructions, confidence, staff_ids}."""
    employees = employees or []
    t = text or ''
    flat = re.sub(r'[ \t]+', ' ', t)
    low = flat.lower()
    clause_refs: Dict[str, str] = {}

    def clause_for(m) -> Optional[str]:
        if not m:
            return None
        line_start = flat.rfind('\n', 0, m.start()) + 1
        line_end = flat.find('\n', m.end())
        line = flat[line_start : line_end if line_end != -1 else len(flat)]
        c = re.search(r'\b((?:clause|section|para(?:graph)?|article|cl\.?)\s*[\d.]+[a-z]?)', line, re.I)
        return c.group(1) if c else None

    # ---- reference
    ref = None
    m = _first(
        [
            r'(?:purchase\s+order|P\.?O\.?|quotation|quote|contract)\s*(?:no\.?|number|#|ref(?:erence)?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,})',
            r'\b(QTN[-\s]?[A-Z0-9][\w\-]*)',
            r'\b(CTR[-\s]?[A-Z0-9][\w\-]*)',
            r'\b(4500[-\s]?\d{3,})',
            r'\b(PO[-\s]?\d[\w\-]*)',
        ],
        flat,
    )
    if m:
        ref = m.group(1).strip().replace(' ', '-')
        if re.fullmatch(r'\d{4}\d{3,}', ref) and ref.startswith('4500'):
            ref = ref[:4] + '-' + ref[4:]
    if not ref and filename:
        fm = re.search(r'(QTN[-_]?\w+|4500[-_]\d+|PO[-_]?\d+)', filename, re.I)
        if fm:
            ref = fm.group(1).replace('_', '-')

    # ---- type
    if re.search(r'\bquotation\b|\bQTN\b', flat, re.I) and not re.search(r'purchase order', flat, re.I):
        doc_type = 'Quotation'
    elif re.search(r'\bcontract\b|\bagreement\b', flat, re.I) and not re.search(r'purchase order', flat, re.I):
        doc_type = 'Contract'
    else:
        doc_type = 'PO'

    # ---- party
    party = None
    m = re.search(r'(?:bill(?:ed)?\s*to|customer|client|agency|buyer|vendor|supplier)\s*(?:name)?\s*[:\-]\s*([^\n|]+)', flat, re.I)
    if m:
        party = m.group(1).strip().rstrip('.,;')[:120]

    # ---- fee %
    fee_pct = None
    mf = _first(
        [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:management|admin(?:istrat\w*)?|handling|service|agency|mark[\s-]?up)\s*(?:fee|charge|margin)?',
            r'(?:management|admin(?:istrat\w*)?|handling|service)\s*(?:fee|charge)[^0-9\n]{0,40}?(\d+(?:\.\d+)?)\s*%',
            r'(?:cost[\s-]?plus|mark[\s-]?up)[^0-9\n]{0,30}?(\d+(?:\.\d+)?)\s*%',
        ],
        flat,
    )
    if mf:
        fee_pct = float(mf.group(1))
        cl = clause_for(mf)
        if cl:
            clause_refs['fee_pct'] = cl

    # ---- GST
    gst_pct = None
    mg = _first(
        [r'GST[^0-9\n]{0,40}?(\d+(?:\.\d+)?)\s*%', r'(\d+(?:\.\d+)?)\s*%\s*GST'],
        flat,
    )
    if mg:
        gst_pct = float(mg.group(1))
        cl = clause_for(mg)
        if cl:
            clause_refs['gst_pct'] = cl

    # ---- rates
    rates = parse_rates(flat)
    has_rates = any(v is not None for v in rates.values())
    if has_rates:
        mr = _first([_CUR + _AMT + r'\s*(?:/|per)'], flat)
        cl = clause_for(mr)
        if cl:
            clause_refs['rates'] = cl

    # ---- basis
    cost_plus_kw = bool(re.search(r'cost[\s-]?plus|payroll\s+cost|employment\s+cost|actual\s+cost|plus\s+management', low))
    if cost_plus_kw or (fee_pct is not None and not has_rates):
        basis = 'cost_plus'
    elif has_rates:
        basis = 'rate_card'
    else:
        basis = 'cost_plus' if fee_pct is not None else None
    if basis == 'rate_card' and fee_pct is not None and not cost_plus_kw:
        pass  # fee on top of a rate card is allowed, kept as given

    # ---- validity
    valid_from = valid_to = None
    mv = re.search(r'valid(?:ity)?(?:\s+period)?[^\n]{0,20}?(?:from|:)?\s*' + _DATE + r'\s*(?:to|until|till|through|-|–)\s*' + _DATE, flat, re.I)
    if mv:
        valid_from, valid_to = parse_date(mv.group(1)), parse_date(mv.group(2))
    else:
        mf1 = re.search(r'(?:valid\s+from|effective\s+from|commencement(?:\s+date)?|start\s+date)\s*[:\-]?\s*' + _DATE, flat, re.I)
        mt1 = re.search(r'(?:valid\s+(?:until|till|to|through)|expir(?:y|es)(?:\s+date)?|end\s+date|valid\s+up\s+to)\s*[:\-]?\s*' + _DATE, flat, re.I)
        if mf1:
            valid_from = parse_date(mf1.group(1))
        if mt1:
            valid_to = parse_date(mt1.group(1))
    if valid_from or valid_to:
        cl = clause_for(mv or None)
        if cl:
            clause_refs['validity'] = cl

    # ---- other instructions
    period_rule = None
    mp = _first(
        [
            r'(bill(?:ed|ing)?\s+(?:monthly|weekly|fortnightly)[^\n.]*)',
            r'((?:calendar|billing)\s+month[^\n.]*)',
            r'(billing\s+period\s*[:\-]\s*[^\n]+)',
            r'(monthly\s+in\s+arrears[^\n.]*)',
            r'(invoice[sd]?\s+(?:monthly|weekly)[^\n.]*)',
        ],
        flat,
    )
    if mp:
        period_rule = mp.group(1).strip()[:140]

    invoice_split = None
    ms = re.search(r'(separate\s+invoices?\s+(?:per|for\s+each|by)\s+[\w\s/-]{3,40}|one\s+invoice\s+per\s+[\w\s/-]{3,40}|single\s+(?:consolidated\s+)?invoice)', flat, re.I)
    if ms:
        invoice_split = ms.group(1).strip()

    mandatory: List[str] = []
    for mm in re.finditer(r'(?:must\s+(?:quote|include|state|reference|show|bear)|mandatory[^:\n]*:|(?:quote|state)\s+the)\s*([^\n.]{3,140})', flat, re.I):
        items = re.split(r',|\band\b|;', mm.group(1))
        for it in items:
            it = re.sub(r'^(?:the|a|an|on\s+(?:the\s+)?invoice|on\s+each\s+invoice)\s+', '', it.strip(), flags=re.I).strip(' .')
            if 2 < len(it) < 60 and it.lower() not in [x.lower() for x in mandatory]:
                mandatory.append(it[:1].upper() + it[1:])
    if not mandatory and ref:
        mandatory = ['PO number'] if doc_type == 'PO' else ['Quotation number']

    supporting: List[str] = []
    for kw, label in [
        (r'approved\s+timesheet|signed\s+timesheet|timesheets?', 'Approved timesheets'),
        (r'delivery\s+order', 'Delivery order'),
        (r'copy\s+of\s+(?:the\s+)?(?:PO|purchase\s+order)', 'Copy of PO'),
        (r'leave\s+records?|medical\s+certificates?', 'Leave records'),
        (r'overtime\s+(?:approval|form)', 'Overtime approval'),
    ]:
        if re.search(kw, flat, re.I):
            supporting.append(label)

    tax = None
    mt = re.search(r'(GST[^\n.]{0,60}(?:exclusive|inclusive|standard[\s-]?rated|zero[\s-]?rated|exempt)[^\n.]{0,30}|(?:prices?|rates?)\s+(?:are\s+)?(?:exclusive|inclusive)\s+of\s+GST)', flat, re.I)
    if mt:
        tax = mt.group(1).strip()
    elif gst_pct is not None:
        tax = f'GST {gst_pct:g}% standard-rated'

    channel = None
    mc = _first(
        [
            r'(?:submit|send|email|e-mail)[^\n.]{0,40}?(?:to|via)\s+([\w.+-]+@[\w-]+\.[\w.-]+)',
            r'\b(Ariba|Coupa|SAP\s+portal|supplier\s+portal|e-?invoicing\s+portal|Peppol)\b',
        ],
        flat,
    )
    if mc:
        channel = mc.group(1).strip().rstrip('.')
        if '@' in channel:
            channel = f'Email: {channel}'

    # ---- staff
    low_text = low
    staff_ids = []
    for e in employees:
        n = (e.get('name') or '').strip().lower()
        if n and n in low_text:
            staff_ids.append(e['id'])

    # ---- confidence
    score = 0
    score += 15 if ref else 0
    score += 10 if party else 0
    score += 15 if basis else 0
    score += 25 if (fee_pct is not None or has_rates) else 0
    score += 10 if gst_pct is not None else 0
    score += 15 if (valid_from or valid_to) else 0
    score += 5 if period_rule else 0
    score += 5 if (invoice_split or mandatory) else 0
    confidence = min(100, score)

    instructions = {
        'billing_basis': basis,
        'fee_pct': fee_pct,
        'gst_pct': gst_pct,
        'rates': rates,
        'period_rule': period_rule,
        'invoice_split': invoice_split,
        'mandatory_references': mandatory,
        'supporting_documents': supporting,
        'tax_treatment': tax,
        'submission_channel': channel,
        'valid_from': valid_from,
        'valid_to': valid_to,
        'clause_refs': clause_refs,
    }
    return {
        'ref': ref,
        'doc_type': doc_type,
        'party': party,
        'instructions': instructions,
        'confidence': confidence,
        'staff_ids': staff_ids,
    }


def status_for(confidence: int, instructions: dict, today: Optional[date] = None) -> str:
    today = today or date.today()
    vt = instructions.get('valid_to')
    if vt and vt < today.isoformat():
        return 'Expired'
    return 'Ready' if confidence >= 80 else 'Needs confirmation'

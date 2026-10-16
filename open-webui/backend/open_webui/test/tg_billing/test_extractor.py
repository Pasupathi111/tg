import io

import pytest

from tg_billing_pkg import extractor

PO_TEXT = """PURCHASE ORDER
Purchase Order No: 4500-0182
Bill to: Agency A
Staffing services are billed on a cost-plus basis (Clause 3.2).
Management fee of 10% on total employment cost (Clause 4.1).
GST 9% applies (Clause 5.2). All prices are exclusive of GST.
Valid from 01/01/2026 to 31 December 2026.
Invoices must quote the PO number and billing period. Bill monthly in arrears.
Submit invoices to ap@agencya.example. Approved timesheets must be attached.
"""

QTN_TEXT = """Quotation No: QTN-2231
Customer: Agency B
Rate card:
Monthly rate: SGD 5,200
S$180 per half day
S$340 per day
Hourly rate S$45
S$1,500 per week
Quote valid until 28/02/2027. GST 9%.
"""


def test_cost_plus_po():
    r = extractor.parse_instructions(PO_TEXT, 'po.txt')
    i = r['instructions']
    assert r['ref'] == '4500-0182' and r['doc_type'] == 'PO' and r['party'] == 'Agency A'
    assert i['billing_basis'] == 'cost_plus'
    assert i['fee_pct'] == 10 and i['gst_pct'] == 9
    assert i['valid_from'] == '2026-01-01' and i['valid_to'] == '2026-12-31'
    assert 'PO number' in i['mandatory_references']
    assert i['clause_refs']['fee_pct'].lower() == 'clause 4.1'
    assert 'Approved timesheets' in i['supporting_documents']
    assert i['submission_channel'] == 'Email: ap@agencya.example'
    assert r['confidence'] >= 80


def test_rate_card_quotation():
    r = extractor.parse_instructions(QTN_TEXT, 'q.txt')
    i = r['instructions']
    assert r['ref'] == 'QTN-2231' and r['doc_type'] == 'Quotation' and r['party'] == 'Agency B'
    assert i['billing_basis'] == 'rate_card'
    assert i['rates'] == {'monthly': 5200.0, 'half_day': 180.0, 'daily': 340.0, 'weekly': 1500.0, 'hourly': 45.0}
    assert i['valid_to'] == '2027-02-28' and i['valid_from'] is None
    assert i['gst_pct'] == 9


def test_low_confidence_needs_confirmation():
    r = extractor.parse_instructions('Please bill us as agreed. Thanks.', 'note.txt')
    assert r['confidence'] < 50
    assert extractor.status_for(r['confidence'], r['instructions']) == 'Needs confirmation'


def test_status_expired():
    assert extractor.status_for(95, {'valid_to': '2020-01-01'}) == 'Expired'
    assert extractor.status_for(95, {'valid_to': '2999-01-01'}) == 'Ready'


@pytest.mark.parametrize(
    's,exp',
    [
        ('2026-03-05', '2026-03-05'),
        ('05/03/2026', '2026-03-05'),
        ('5 March 2026', '2026-03-05'),
        ('March 5, 2026', '2026-03-05'),
        ('31/02/2026', None),
    ],
)
def test_parse_date(s, exp):
    assert extractor.parse_date(s) == exp


def test_staff_matching():
    emps = [{'id': 'E1', 'name': 'Tan Wei Ming'}, {'id': 'E2', 'name': 'Nobody Here'}]
    r = extractor.parse_instructions('Staff: Tan Wei Ming (Admin).\nPO No: PO-77', 'a.txt', emps)
    assert r['staff_ids'] == ['E1']


def test_extract_txt_and_csv():
    assert extractor.extract_text('a.txt', PO_TEXT.encode()).startswith('PURCHASE ORDER')
    out = extractor.extract_text('r.csv', b'role,rate\nAdmin,5200\n')
    assert 'role | rate' in out and 'Admin | 5200' in out


def _mini_pdf(lines):
    body = ' 0 -20 Td '.join(f'({l}) Tj' for l in lines)
    stream = ('BT /F1 12 Tf 50 750 Td ' + body + ' ET').encode()
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    pdf = b'%PDF-1.4\n'
    offs = []
    for n, o in enumerate(objs, 1):
        offs.append(len(pdf))
        pdf += b'%d 0 obj\n' % n + o + b'\nendobj\n'
    xref = len(pdf)
    pdf += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offs:
        pdf += b'%010d 00000 n \n' % o
    pdf += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(objs) + 1, xref)
    return pdf


def test_extract_docx():
    docx = pytest.importorskip('docx')
    d = docx.Document()
    d.add_paragraph('Purchase Order No: 4500-0999')
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = 'Monthly rate'
    t.rows[0].cells[1].text = 'SGD 4,000'
    buf = io.BytesIO()
    d.save(buf)
    text = extractor.extract_text('x.docx', buf.getvalue())
    assert '4500-0999' in text and 'Monthly rate | SGD 4,000' in text
    assert extractor.parse_instructions(text, 'x.docx')['instructions']['rates']['monthly'] == 4000.0


def test_extract_xlsx():
    openpyxl = pytest.importorskip('openpyxl')
    wb = openpyxl.Workbook()
    wb.active.append(['Quotation No', 'QTN-5'])
    wb.active.append(['Management fee', '12%'])
    buf = io.BytesIO()
    wb.save(buf)
    text = extractor.extract_text('x.xlsx', buf.getvalue())
    assert 'QTN-5' in text
    assert extractor.parse_instructions(text, 'x.xlsx')['instructions']['fee_pct'] == 12.0


def test_extract_pdf():
    pytest.importorskip('pypdf')
    text = extractor.extract_text('x.pdf', _mini_pdf(['Purchase Order No: 4500-0777', 'Management fee of 8%']))
    r = extractor.parse_instructions(text, 'x.pdf')
    assert r['ref'] == '4500-0777' and r['instructions']['fee_pct'] == 8.0

"""Invoice JSON / printable HTML / billing report CSV rendering."""

from __future__ import annotations

import calendar
import math
import csv
import io
from datetime import date
from html import escape
from typing import Optional

from .engine import period_bounds


def period_label(period: str) -> str:
    y, m = period.split('-')
    return f'{calendar.month_name[int(m)]} {y}'


def build_invoice(run: dict, doc: Optional[dict], settings: dict) -> dict:
    doc = doc or {}
    instr = doc.get('instructions') or {}
    start, end = period_bounds(run['period'])
    approved = run.get('status') == 'Approved'
    return {
        'invoice_no': run.get('invoice_no'),
        'status': run.get('status'),
        'is_draft': not approved,
        'date': (run.get('approved_at') or date.today().isoformat())[:10],
        'currency': settings.get('currency', 'SGD'),
        'company': {'name': settings.get('company', '')},
        'bill_to': {'party': run.get('party') or doc.get('party')},
        'references': {
            'document_ref': doc.get('ref') or run.get('document_ref'),
            'doc_type': doc.get('doc_type'),
            'mandatory': instr.get('mandatory_references') or [],
        },
        'period': {'period': run['period'], 'label': period_label(run['period']), 'start': start, 'end': end},
        'instructions': {
            'billing_basis': run.get('basis'),
            'fee_pct': instr.get('fee_pct'),
            'gst_pct': run.get('gst_pct'),
            'rates': instr.get('rates') or {},
            'period_rule': instr.get('period_rule'),
            'invoice_split': instr.get('invoice_split'),
            'tax_treatment': instr.get('tax_treatment'),
            'valid_from': instr.get('valid_from'),
            'valid_to': instr.get('valid_to'),
        },
        'lines': [
            {
                'employee_id': l['employee_id'],
                'officer': l['name'],
                'pay_basis': l['pay_basis'],
                'employment_cost': l['cost'],
                'mgmt_fee': l['fee'],
                'amount': l['amount'],
            }
            for l in run['lines']
        ],
        'subtotal': run['subtotal'],
        'gst_pct': run['gst_pct'],
        'gst': run['gst'],
        'total': run['total'],
    }


def _m(v) -> str:
    return f'{float(v):,.2f}'


_LOGO = (
    '<svg width="46" height="46" viewBox="0 0 46 46" xmlns="http://www.w3.org/2000/svg">'
    '<g stroke="#E8892B" stroke-width="3" stroke-linecap="round">'
    + ''.join(
        f'<line x1="23" y1="23" x2="{23 + 20 * math.cos(a * 3.14159265 / 6):.1f}" '
        f'y2="{23 + 20 * math.sin(a * 3.14159265 / 6):.1f}"/>'
        for a in range(12)
    )
    + '</g><circle cx="23" cy="23" r="7" fill="#C8610F"/></svg>'
)


def render_html(inv: dict) -> str:
    e = escape
    basis = inv['instructions'].get('billing_basis')
    rows = ''.join(
        f'<tr><td>{e(l["officer"] or "")}</td><td>{e(l["pay_basis"])}</td>'
        f'<td class="r">{_m(l["employment_cost"])}</td><td class="r">{_m(l["mgmt_fee"])}</td>'
        f'<td class="r">{_m(l["amount"])}</td></tr>'
        for l in inv['lines']
    )
    ins = inv['instructions']
    ins_bits = [f'Basis: {e(str(basis or "-"))}']
    if ins.get('fee_pct') is not None:
        ins_bits.append(f'Management fee: {ins["fee_pct"]:g}%')
    if ins.get('period_rule'):
        ins_bits.append(e(ins['period_rule']))
    if ins.get('tax_treatment'):
        ins_bits.append(e(ins['tax_treatment']))
    rates = {k: v for k, v in (ins.get('rates') or {}).items() if v}
    if rates:
        ins_bits.append('Rates: ' + ', '.join(f'{k.replace("_", " ")} {_m(v)}' for k, v in rates.items()))
    draft = '<div class="draft">DRAFT - not approved</div>' if inv.get('is_draft') else ''
    cur = e(inv['currency'])
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Tax Invoice {e(inv.get('invoice_no') or 'DRAFT')}</title>
<style>
body{{font-family:Roboto,Inter,Arial,sans-serif;background:#F6F7F9;color:#33414F;margin:0;padding:24px}}
.sheet{{max-width:820px;margin:0 auto;background:#fff;border:1px solid #E3E7EC;border-radius:12px;padding:36px}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}}
.brand{{display:flex;gap:12px;align-items:center;color:#22344A;font-weight:700}}
h1{{margin:0;color:#22344A;font-size:26px;letter-spacing:1px}}
.cols{{display:flex;gap:24px;margin:28px 0}} .cols>div{{flex:1;font-size:13px}}
.lbl{{font-size:11px;color:#6B7785;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.box{{background:#F1F3F6;border-radius:8px;padding:12px 14px;font-size:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#F1F3F6;text-transform:uppercase;font-size:11px;color:#6B7785;text-align:left;padding:8px}}
td{{padding:8px;border-bottom:1px solid #E3E7EC}} .r{{text-align:right}} th.r{{text-align:right}}
.tot{{margin-left:auto;width:300px;margin-top:16px;font-size:14px}}
.tot div{{display:flex;justify-content:space-between;padding:4px 0}}
.tot .grand{{font-weight:700;color:#22344A;border-top:2px solid #22344A;margin-top:6px;padding-top:8px}}
.draft{{color:#B4560A;background:#FCE9D8;display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;margin-top:6px}}
@media print{{body{{background:#fff;padding:0}} .sheet{{border:0}}}}
</style></head><body><div class="sheet">
<div class="top"><div class="brand">{_LOGO}<div>{e(inv['company'].get('name', ''))}</div></div>
<div style="text-align:right"><h1>TAX INVOICE</h1><div>{e(inv.get('invoice_no') or 'DRAFT')}</div>{draft}</div></div>
<div class="cols">
<div><div class="lbl">Bill to</div><b>{e(inv['bill_to'].get('party') or '-')}</b></div>
<div><div class="lbl">References</div>{e(inv['references'].get('doc_type') or '')} {e(inv['references'].get('document_ref') or '-')}<br>Invoice date: {e(inv['date'])}</div>
<div><div class="lbl">Billing period</div>{e(inv['period']['label'])}<br>{e(inv['period']['start'])} to {e(inv['period']['end'])}</div>
</div>
<div class="box"><b>Billing instructions (from {e(inv['references'].get('document_ref') or 'PO')})</b><br>{' &middot; '.join(ins_bits)}</div>
<table><thead><tr><th>Officer</th><th>Pay basis</th><th class="r">Employment cost</th><th class="r">Mgmt fee</th><th class="r">Amount ({cur})</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="tot"><div><span>Subtotal</span><span>{_m(inv['subtotal'])}</span></div>
<div><span>GST {inv['gst_pct']:g}%</span><span>{_m(inv['gst'])}</span></div>
<div class="grand"><span>Total {cur}</span><span>{_m(inv['total'])}</span></div></div>
</div></body></html>"""


def render_csv(run: dict, inv: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Run', run['id'], 'Invoice', inv.get('invoice_no') or 'DRAFT', 'Period', run['period'], 'Document', inv['references'].get('document_ref')])
    w.writerow([])
    w.writerow(['Officer', 'Pay basis', 'Section', 'Item', 'Calculation', 'Amount', 'Source', 'Adjusted'])
    for l in run['lines']:
        for s in l['sections']:
            for r in s['rows']:
                w.writerow([l['name'], l['pay_basis'], f'{s["key"]} {s["title"]}', r['label'], r['calc'], f'{r["amount"]:.2f}', r['source'], 'yes' if r.get('adjusted') else ''])
        w.writerow([l['name'], l['pay_basis'], '', 'Line total', f'cost {l["cost"]:.2f} + fee {l["fee"]:.2f}', f'{l["amount"]:.2f}', '', ''])
    w.writerow([])
    w.writerow(['', '', '', 'Subtotal', '', f'{run["subtotal"]:.2f}'])
    w.writerow(['', '', '', f'GST {run["gst_pct"]:g}%', '', f'{run["gst"]:.2f}'])
    w.writerow(['', '', '', 'Total', '', f'{run["total"]:.2f}'])
    return out.getvalue()

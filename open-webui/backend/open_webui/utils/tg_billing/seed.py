"""Demo seed data for TG Billing Coworker."""

from __future__ import annotations

from datetime import datetime, timezone


PERIODS = ['2026-08', '2026-09', '2026-10']
SCHEDULED = {'2026-08': 21, '2026-09': 22, '2026-10': 22}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _emp(id_, name, code, party, desig, basis, age=34, res='citizen', **kw):
    e = {
        'id': id_,
        'name': name,
        'code': code,
        'party': party,
        'designation': desig,
        'pay_basis': basis,
        'age': age,
        'residency': res,
        'monthly_salary': 0,
        'hourly_rate': 0,
        'weekly_rate': 0,
        'half_day_rate': 0,
        'daily_rate': 0,
        'allowances': [],
        'other_contributions': [],
        'active': True,
    }
    e.update(kw)
    return e


def employees():
    return [
        _emp('EMP-A', 'Officer A - Tan Wei Ming', 'TG-0041', 'Agency A', 'Admin Executive', 'monthly', 34, 'citizen',
             monthly_salary=4200, allowances=[{'label': 'Transport allowance', 'amount': 150}]),
        _emp('EMP-B', 'Officer B - Siti Nurhaliza', 'TG-0057', 'Agency A', 'Customer Service Associate', 'hourly', 29, 'pr',
             hourly_rate=22.5),
        _emp('EMP-G', 'Officer G - Rajesh Kumar', 'TG-0102', 'Agency A', 'Warehouse Assistant', 'weekly', 41, 'foreign',
             weekly_rate=1100, other_contributions=[{'label': 'Foreign worker levy', 'amount': 300}]),
        _emp('EMP-C', 'Officer C - Lim Mei Ling', 'TG-0063', 'Agency B', 'Project Coordinator', 'monthly', 38, 'citizen',
             monthly_salary=4800),
        _emp('EMP-D', 'Officer D - Daniel Ong', 'TG-0088', 'Agency B', 'Event Support', 'half_day', 24, 'citizen',
             half_day_rate=90),
        _emp('EMP-E', 'Officer E - Priya Nair', 'TG-0071', 'Agency D', 'Finance Associate', 'monthly', 57, 'citizen',
             monthly_salary=5600),
        _emp('EMP-F', 'Officer F - Mohd Faisal', 'TG-0095', 'Agency D', 'Driver', 'daily', 45, 'citizen',
             daily_rate=160),
        _emp('EMP-H', 'Officer H - Chen Li', 'TG-0034', 'Agency C', 'HR Assistant', 'monthly', 31, 'citizen',
             monthly_salary=3900),
    ]


def timesheets():
    out = []
    spec = {
        # emp: (worked, paid_leave, unpaid, ot, hours, weeks, half_days) per period offset
        'EMP-A': [(21, 0, 0, 0), (20, 1, 1, 6), (21, 0, 1, 4)],
        'EMP-B': [(21, 0, 0, 0), (22, 0, 0, 5), (22, 0, 0, 3)],
        'EMP-G': [(21, 0, 0, 8), (22, 0, 0, 10), (22, 0, 0, 6)],
        'EMP-C': [(21, 0, 0, 0), (21, 1, 0, 0), (22, 0, 0, 0)],
        'EMP-D': [(21, 0, 0, 0), (22, 0, 0, 0), (22, 0, 0, 0)],
        'EMP-E': [(21, 0, 0, 0), (22, 0, 0, 0), (22, 0, 0, 0)],
        'EMP-F': [(21, 0, 0, 0), (22, 0, 0, 0), None],  # Oct timesheet missing
        'EMP-H': [(21, 0, 0, 0), (22, 0, 0, 0), (22, 0, 0, 0)],
    }
    hours_of = {'EMP-B': [168, 176, 176]}
    weeks_of = {'EMP-G': [4.2, 4.4, 4.4]}
    half_days_of = {'EMP-D': [28, 30, 31]}
    for emp, rows in spec.items():
        for i, r in enumerate(rows):
            if r is None:
                continue
            p = PERIODS[i]
            worked, pl, ul, ot = r
            ts = {
                'id': f'TS-{emp}-{p}',
                'employee_id': emp,
                'period': p,
                'scheduled_days': SCHEDULED[p],
                'worked_days': worked,
                'paid_leave_days': pl,
                'unpaid_leave_days': ul,
                'ot_hours': ot,
                'hours': hours_of[emp][i] if emp in hours_of else worked * 8,
                'weeks': weeks_of[emp][i] if emp in weeks_of else round(worked / 5, 2),
                'half_days': half_days_of[emp][i] if emp in half_days_of else worked * 2,
                'deductions': 0,
                'status': 'Received',
            }
            out.append(ts)
    return out


def _doc(id_, ref, doc_type, party, status, conf, fname, excerpt, instr, staff, **kw):
    base_instr = {
        'billing_basis': 'cost_plus',
        'fee_pct': None,
        'gst_pct': 9,
        'rates': {'monthly': None, 'half_day': None, 'daily': None, 'weekly': None, 'hourly': None},
        'period_rule': 'Bill monthly in arrears (calendar month)',
        'invoice_split': 'Single invoice',
        'mandatory_references': ['PO number', 'Billing period'],
        'supporting_documents': ['Approved timesheets'],
        'tax_treatment': 'GST 9% standard-rated',
        'submission_channel': 'Email: ap@example.com',
        'valid_from': None,
        'valid_to': None,
        'clause_refs': {},
    }
    base_instr.update(instr)
    return {
        'id': id_,
        'ref': ref,
        'doc_type': doc_type,
        'party': party,
        'status': status,
        'confidence': conf,
        'source_filename': fname,
        'text_excerpt': excerpt,
        'instructions': base_instr,
        'staff_ids': staff,
        'created_at': _now(),
        **kw,
    }


def documents():
    return [
        _doc('DOC-0182', '4500-0182', 'PO', 'Agency A', 'Ready', 96, 'PO_4500-0182_AgencyA.pdf',
             'Purchase Order No: 4500-0182. Bill to: Agency A. Staffing services on a cost-plus basis. '
             'Management fee of 10% on total employment cost (Clause 4.1). Bill monthly in arrears. '
             'Valid from 01/01/2026 to 31/12/2026. GST 9%.',
             {'billing_basis': 'cost_plus', 'fee_pct': 10, 'valid_from': '2026-01-01', 'valid_to': '2026-12-31',
              'clause_refs': {'fee_pct': 'Clause 4.1', 'validity': 'Clause 2.3', 'gst_pct': 'Clause 5.2'}},
             ['EMP-A', 'EMP-B', 'EMP-G']),
        _doc('DOC-2231', 'QTN-2231', 'Quotation', 'Agency B', 'Ready', 91, 'QTN-2231_AgencyB.docx',
             'Quotation QTN-2231 for Agency B. Rate card: S$5,200 per month; S$180 per half day; S$340 per day; '
             'S$45 per hour. Valid from 01/03/2026 to 28/02/2027. GST 9%.',
             {'billing_basis': 'rate_card', 'fee_pct': None,
              'rates': {'monthly': 5200, 'half_day': 180, 'daily': 340, 'weekly': 1500, 'hourly': 45},
              'mandatory_references': ['Quotation number', 'Billing period'],
              'valid_from': '2026-03-01', 'valid_to': '2027-02-28',
              'clause_refs': {'rates': 'Annex A'}},
             ['EMP-C', 'EMP-D']),
        _doc('DOC-0215', '4500-0215', 'PO', 'Agency D', 'Needs confirmation', 62, 'PO_4500-0215_AgencyD.pdf',
             'Purchase Order 4500-0215. Agency D. Management fee 12% (unclear whether payroll or total cost). '
             'Validity unclear.',
             {'billing_basis': 'cost_plus', 'fee_pct': 12, 'valid_from': '2026-06-01', 'valid_to': '2027-05-31',
              'invoice_split': None, 'tax_treatment': None},
             ['EMP-E', 'EMP-F']),
        _doc('DOC-0201', '4500-0201', 'PO', 'Agency C', 'Expired', 88, 'PO_4500-0201_AgencyC.pdf',
             'Purchase Order 4500-0201. Agency C. Cost-plus with 9% management fee. Valid until 31/12/2025.',
             {'billing_basis': 'cost_plus', 'fee_pct': 9, 'valid_from': '2025-01-01', 'valid_to': '2025-12-31'},
             ['EMP-H']),
    ]


def reviews():
    now = _now()

    def r(id_, cat, title, party, detail, doc=None):
        return {
            'id': id_,
            'category': cat,
            'title': title,
            'party': party,
            'detail': detail,
            'document_id': doc,
            'status': 'Open',
            'assignee': None,
            'note': None,
            'created_at': now,
        }

    return [
        r('EX-01', 'missing_po', 'Timesheet received with no PO on file', 'Agency E', 'Officer timesheet for 2026-09 has no matching PO or quotation.'),
        r('EX-02', 'missing_po', 'PO 4500-0201 expired 31 Dec 2025', 'Agency C', 'Officer H still has timesheets in 2026 against an expired PO.', 'DOC-0201'),
        r('EX-03', 'project_timesheet', 'Project timesheet missing for 2026-10', 'Agency D', 'Officer F has no timesheet for 2026-10.', 'DOC-0215'),
        r('EX-04', 'project_timesheet', 'Hours exceed scheduled hours', 'Agency A', 'Officer B logged 176 h; scheduled 168 h in 2026-08 (OT approval needed).', 'DOC-0182'),
        r('EX-05', 'rate_approval', 'Rate not approved for new role', 'Agency B', 'Event Support half-day rate S$90 pending approval against quotation Annex A.', 'DOC-2231'),
        r('EX-06', 'rate_approval', 'Rate differs from quotation', 'Agency B', 'Officer C monthly salary S$4,800 vs billed rate S$5,200 requires sign-off.', 'DOC-2231'),
        r('EX-07', 'invoicing_instruction', 'Fee basis unclear', 'Agency D', 'PO 4500-0215 states 12% fee; payroll cost vs total cost not specified (confidence 62%).', 'DOC-0215'),
        r('EX-08', 'invoicing_instruction', 'Invoice split not specified', 'Agency D', 'No split-by-project instruction found in PO 4500-0215.', 'DOC-0215'),
    ]


def seed(store) -> None:
    store.write('documents', documents())
    store.write('employees', employees())
    store.write('timesheets', timesheets())
    store.write('runs', [])
    store.write('reviews', reviews())
    store.write('audit', [])
    store.write('settings', {})
    store.audit('system', 'seed', 'Demo data loaded')

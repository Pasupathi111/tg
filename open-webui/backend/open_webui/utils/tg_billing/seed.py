"""Demo seed data for TG Billing Coworker."""

from __future__ import annotations

from datetime import datetime, timezone


PERIODS = ['2026-07', '2026-08', '2026-09', '2026-10']
SCHEDULED = {'2026-07': 23, '2026-08': 21, '2026-09': 22, '2026-10': 22}


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
        _emp('EMP-I', 'Officer I - Kavitha Menon', 'TG-0110', 'Agency A', 'Senior Admin Officer', 'monthly', 58, 'citizen',
             monthly_salary=5100, allowances=[{'label': 'Meal allowance', 'amount': 120}]),
        _emp('EMP-J', 'Officer J - Ahmad Zulkifli', 'TG-0118', 'Agency B', 'Site Coordinator', 'daily', 36, 'pr',
             daily_rate=300),
        _emp('EMP-K', 'Officer K - Grace Lee', 'TG-0124', 'Agency F', 'Marketing Executive', 'monthly', 27, 'citizen',
             monthly_salary=4500),
        _emp('EMP-L', 'Officer L - Wang Jun', 'TG-0131', 'Agency F', 'Data Entry Clerk', 'hourly', 33, 'foreign',
             hourly_rate=18, other_contributions=[{'label': 'Foreign worker levy', 'amount': 250}]),
    ]


def timesheets():
    """Jul-Oct 2026 timesheets. Rows are (paid_leave, unpaid_leave, ot_hours) per period;
    worked days = scheduled - paid leave - unpaid leave. None = timesheet not received."""
    out = []
    spec = {
        # A: clean Jul; annual leave Aug; sick (paid) + unpaid Sep; unpaid Oct
        'EMP-A': [(0, 0, 0), (2, 0, 0), (1, 1, 6), (0, 1, 4)],
        # B hourly: leave shows as fewer hours; OT in Aug/Sep
        'EMP-B': [(0, 0, 0), (0, 0, 5), (0, 0, 5), (0, 0, 3)],
        'EMP-G': [(0, 0, 4), (0, 0, 8), (0, 0, 10), (0, 0, 6)],
        'EMP-C': [(0, 0, 0), (0, 0, 0), (1, 0, 0), (0, 3, 0)],  # Oct: 3 days unpaid leave
        'EMP-D': [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
        'EMP-E': [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
        'EMP-F': [(0, 0, 0), (0, 0, 0), (0, 0, 0), None],  # Oct timesheet missing
        'EMP-H': [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
        # I (senior, CPF 15.5%): long medical leave Aug (3 paid + 5 unpaid), unpaid Oct
        'EMP-I': [(0, 0, 0), (3, 5, 0), (0, 0, 2), (0, 2, 0)],
        # J daily: leave days simply not billed
        'EMP-J': [(0, 0, 0), (0, 2, 0), (0, 0, 0), (0, 4, 0)],
        # K: starts Aug (new PO window) - Jul timesheet exists but PO not yet valid
        'EMP-K': [(0, 0, 0), (1, 0, 0), (0, 0, 0), (2, 2, 0)],
        'EMP-L': [(0, 0, 0), (0, 0, 6), (0, 0, 0), (0, 0, 0)],
    }
    half_days_of = {'EMP-D': [30, 28, 30, 31]}
    for emp, rows in spec.items():
        for i, r in enumerate(rows):
            if r is None:
                continue
            p = PERIODS[i]
            pl, ul, ot = r
            sched = SCHEDULED[p]
            worked = sched - pl - ul
            out.append(
                {
                    'id': f'TS-{emp}-{p}',
                    'employee_id': emp,
                    'period': p,
                    'scheduled_days': sched,
                    'worked_days': worked,
                    'paid_leave_days': pl,
                    'unpaid_leave_days': ul,
                    'ot_hours': ot,
                    'hours': worked * 8,
                    'weeks': round(worked / 5, 2),
                    'half_days': half_days_of[emp][i] if emp in half_days_of else worked * 2,
                    'deductions': 0,
                    'status': 'Received',
                }
            )
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
             ['EMP-A', 'EMP-B', 'EMP-G', 'EMP-I']),
        _doc('DOC-2231', 'QTN-2231', 'Quotation', 'Agency B', 'Ready', 91, 'QTN-2231_AgencyB.docx',
             'Quotation QTN-2231 for Agency B. Rate card: S$5,200 per month; S$180 per half day; S$340 per day; '
             'S$45 per hour. Valid from 01/03/2026 to 28/02/2027. GST 9%.',
             {'billing_basis': 'rate_card', 'fee_pct': None,
              'rates': {'monthly': 5200, 'half_day': 180, 'daily': 340, 'weekly': 1500, 'hourly': 45},
              'mandatory_references': ['Quotation number', 'Billing period'],
              'valid_from': '2026-03-01', 'valid_to': '2027-02-28',
              'clause_refs': {'rates': 'Annex A'}},
             ['EMP-C', 'EMP-D', 'EMP-J']),
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
        _doc('DOC-3300', '4500-0330', 'PO', 'Agency F', 'Ready', 84, 'PO_4500-0330_AgencyF.pdf',
             'Purchase Order 4500-0330. Agency F. Cost-plus, management fee 8%. GST 8% as stated. '
             'Valid from 01/08/2026 to 31/07/2027.',
             {'billing_basis': 'cost_plus', 'fee_pct': 8, 'gst_pct': 8, 'valid_from': '2026-08-01',
              'valid_to': '2027-07-31', 'clause_refs': {'fee_pct': 'Clause 3.2', 'gst_pct': 'Clause 6.1'}},
             ['EMP-K', 'EMP-L']),
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
        r('EX-09', 'missing_po', 'July timesheet before PO start date', 'Agency F', 'Officers K and L logged 2026-07 hours but PO 4500-0330 starts 1 Aug 2026.', 'DOC-3300'),
        r('EX-10', 'invoicing_instruction', 'GST rate differs from standard', 'Agency F', 'PO 4500-0330 states GST 8%; Settings use 9%. Confirm with customer.', 'DOC-3300'),
        r('EX-11', 'project_timesheet', 'Unpaid leave in 2026-10 reduces billing', 'Agency B', 'Officer C (3 days) and Officer J (4 days) unpaid leave in October; billing reduced pro rata.', 'DOC-2231'),
        r('EX-12', 'project_timesheet', 'Extended medical leave 2026-08', 'Agency A', 'Officer I: 3 paid + 5 unpaid leave days; confirm MC documents.', 'DOC-0182'),
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
    generate_runs(store)


def generate_runs(store) -> None:
    """Pre-calculate runs for every document x period (Jul-Oct 2026).

    Jul-Sep with no failing checks are Approved (invoice numbers assigned, history);
    October and anything with a failing check stay Draft so they can be reviewed.
    """
    from . import engine

    docs, emps, tss = documents(), employees(), timesheets()
    by_id = {e['id']: e for e in emps}
    runs = []
    seq = {}
    for period in PERIODS:
        for doc in docs:
            staff = [by_id[i] for i in doc['staff_ids']]
            built = engine.build_run(doc, period, staff, tss, {}, {})
            failing = [c for c in built['checks'] if c['result'] == 'Fail']
            approved = period != PERIODS[-1] and not failing
            run = {
                'id': f'RUN-{doc["id"][4:]}-{period.replace("-", "")}',
                'document_id': doc['id'],
                'period': period,
                'invoice_no': None,
                'adjustments': [],
                'created_at': _now(),
                'created_by': 'system (seed)',
                'status': 'Draft',
                'overrides': {},
                'validation': None,
                'document_ref': doc['ref'],
                'party': doc['party'],
                'updated_at': _now(),
                **built,
            }
            if approved:
                seq[period] = seq.get(period, 0) + 1
                run['status'] = 'Approved'
                run['invoice_no'] = f'INV-{period.replace("-", "")}-{seq[period]:04d}'
                run['approved_at'] = _now()
                run['approved_by'] = 'system (seed)'
            runs.append(run)
    store.write('runs', runs)
    store.audit('system', 'seed.runs', f'Generated {len(runs)} runs for {PERIODS[0]} to {PERIODS[-1]}')

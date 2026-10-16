import { WEBUI_API_BASE_URL } from '$lib/constants';

const BASE = `${WEBUI_API_BASE_URL}/tg-billing`;

// ---------- Types ----------
export type Rates = {
	monthly?: number | null;
	half_day?: number | null;
	daily?: number | null;
	weekly?: number | null;
	hourly?: number | null;
};

export type Instructions = {
	billing_basis?: 'cost_plus' | 'rate_card' | string;
	fee_pct?: number | null;
	gst_pct?: number | null;
	rates?: Rates;
	period_rule?: string;
	invoice_split?: string;
	mandatory_references?: string[];
	supporting_documents?: string[];
	tax_treatment?: string;
	submission_channel?: string;
	valid_from?: string | null;
	valid_to?: string | null;
	clause_refs?: Record<string, string>;
};

export type TgDocument = {
	id: string;
	ref: string;
	doc_type: string;
	party: string;
	status: 'Ready' | 'Needs confirmation' | 'Expired' | string;
	confidence: number;
	source_filename?: string;
	text_excerpt?: string;
	instructions: Instructions;
	staff_ids: string[];
	created_at?: string;
};

export type Employee = {
	id: string;
	name: string;
	[key: string]: any;
};

export type Timesheet = {
	employee_id: string;
	period: string;
	[key: string]: any;
};

export type ReviewItem = {
	id: string;
	category: string;
	title: string;
	summary?: string;
	status?: string;
	rule?: string;
	evidence?: string[] | string;
	suggestion?: string;
	assignee?: string;
	note?: string;
	[key: string]: any;
};

export type ReviewQueue = {
	counts: {
		all: number;
		missing_po: number;
		project_timesheet: number;
		rate_approval: number;
		invoicing_instruction: number;
	};
	items: ReviewItem[];
};

export type CalcRow = {
	label: string;
	calc?: string;
	amount?: number | null;
	source?: string;
	adjusted?: boolean;
};
export type CalcSection = { key: string; title: string; rows: CalcRow[] };
export type RunLine = {
	employee_id: string;
	name: string;
	pay_basis: string;
	sections: CalcSection[];
	cost: number;
	fee: number;
	amount: number;
};
export type Check = { label: string; result: 'Pass' | 'Match' | 'Differs' | 'Fail' | string; value?: string };
export type Run = {
	id: string;
	document_id: string;
	period: string;
	status: 'Draft' | 'Awaiting validation' | 'Approved' | string;
	basis: string;
	lines: RunLine[];
	subtotal: number;
	gst_pct: number;
	gst: number;
	total: number;
	checks: Check[];
	invoice_no?: string | null;
	adjustments: any[];
	[key: string]: any;
};

export type AuditEntry = {
	id?: string;
	ts?: string;
	timestamp?: string;
	actor?: string;
	action?: string;
	detail?: string;
	[key: string]: any;
};

export type Chip = { label: string; tone: 'ok' | 'warn' | 'bad' | 'grey' };
export type Assignment = {
	employee_id: string;
	worker: string;
	code?: string;
	party?: string;
	project_code: string;
	po_ref: string;
	document_id?: string | null;
	timesheet: Chip;
	po: Chip;
	rate: Chip;
	instruction: Chip;
	status: 'Ready' | 'Not ready' | 'Needs confirmation' | 'Blocked';
	group: 'Ready' | 'Not ready' | 'Blocked';
};

export type Dashboard = {
	period: string;
	assignments: Assignment[];
	exceptions: { category: string; label: string; count: number }[];
	pipeline: { draft: number; awaiting: number; approved: number; stalled: number; stall_hours: number };
	kpis: {
		pos_ready: number;
		needs_confirmation: number;
		open_exceptions: number;
		runs_awaiting: number;
	};
	runs: any[];
	activity: any[];
};

export type AskResponse = {
	answer: string;
	steps?: { n: number; title: string; text: string; source?: string }[];
	proposal?: any;
};

export type AdjustmentProposal = {
	proposal?: { from: any; to: any; delta_total?: number };
	[key: string]: any;
};

// ---------- Request helper ----------
const request = async (
	token: string,
	path: string,
	opts: { method?: string; body?: any; form?: FormData } = {}
) => {
	let error = null;
	const headers: Record<string, string> = {
		Accept: 'application/json',
		authorization: `Bearer ${token}`
	};
	if (opts.body !== undefined) headers['Content-Type'] = 'application/json';

	const res = await fetch(`${BASE}${path}`, {
		method: opts.method ?? 'GET',
		headers,
		body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json().catch(() => ({ detail: res.statusText }));
			if (res.status === 204) return null;
			return res.json().catch(() => null);
		})
		.catch((err) => {
			error = err?.detail ?? err?.message ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw typeof error === 'string' ? error : JSON.stringify(error);
	}
	return res;
};

const download = async (token: string, path: string): Promise<Blob> => {
	const res = await fetch(`${BASE}${path}`, { headers: { authorization: `Bearer ${token}` } });
	if (!res.ok) throw await res.text();
	return await res.blob();
};

// ---------- Endpoints ----------
export const getDashboard = (token: string, period?: string): Promise<Dashboard> =>
	request(token, `/dashboard${period ? `?period=${period}` : ''}`);

export const getDocuments = (token: string): Promise<TgDocument[]> => request(token, '/documents');
export const getDocument = (token: string, id: string): Promise<TgDocument> =>
	request(token, `/documents/${id}`);
export const uploadDocument = (
	token: string,
	file: File,
	meta: { doc_type?: string; party?: string } = {}
): Promise<TgDocument> => {
	const form = new FormData();
	form.append('file', file);
	if (meta.doc_type) form.append('doc_type', meta.doc_type);
	if (meta.party) form.append('party', meta.party);
	return request(token, '/documents', { method: 'POST', form });
};
export const updateDocumentInstructions = (
	token: string,
	id: string,
	instructions: Instructions
): Promise<TgDocument> =>
	request(token, `/documents/${id}/instructions`, { method: 'PUT', body: instructions });
export const confirmDocument = (token: string, id: string): Promise<TgDocument> =>
	request(token, `/documents/${id}/confirm`, { method: 'POST' });
export const deleteDocument = (token: string, id: string) =>
	request(token, `/documents/${id}`, { method: 'DELETE' });

export const getEmployees = (token: string): Promise<Employee[]> => request(token, '/employees');
export const createEmployee = (token: string, body: Partial<Employee>): Promise<Employee> =>
	request(token, '/employees', { method: 'POST', body });
export const updateEmployee = (token: string, id: string, body: Partial<Employee>): Promise<Employee> =>
	request(token, `/employees/${id}`, { method: 'PUT', body });
export const deleteEmployee = (token: string, id: string) =>
	request(token, `/employees/${id}`, { method: 'DELETE' });

export const getTimesheets = (token: string, period?: string): Promise<Timesheet[]> =>
	request(token, `/timesheets${period ? `?period=${encodeURIComponent(period)}` : ''}`);
export const upsertTimesheet = (token: string, body: Timesheet): Promise<Timesheet> =>
	request(token, '/timesheets', { method: 'PUT', body });

export const getReviewQueue = (token: string, category?: string): Promise<ReviewQueue> =>
	request(
		token,
		`/review-queue${category && category !== 'all' ? `?category=${encodeURIComponent(category)}` : ''}`
	);
export const resolveReviewItem = (
	token: string,
	id: string,
	body: { assignee?: string; note?: string; status: string }
): Promise<ReviewItem> => request(token, `/review-queue/${id}/resolve`, { method: 'POST', body });

export const calculateRun = (
	token: string,
	body: { document_id: string; period: string }
): Promise<Run> => request(token, '/calculate', { method: 'POST', body });
export const getRuns = (token: string): Promise<Run[]> => request(token, '/runs');
export const getRun = (token: string, id: string): Promise<Run> => request(token, `/runs/${id}`);
export const adjustRun = (
	token: string,
	id: string,
	body: { employee_id: string; field: string; new_value: any; reason: string; confirm: boolean }
): Promise<any> => request(token, `/runs/${id}/adjustments`, { method: 'POST', body });
export const validateRun = (
	token: string,
	id: string,
	body: { outcome: 'approve' | 'fix' | 'flag'; note?: string }
): Promise<Run> => request(token, `/runs/${id}/validate`, { method: 'POST', body });
export const approveRun = (token: string, id: string): Promise<Run> =>
	request(token, `/runs/${id}/approve`, { method: 'POST' });
export const getInvoice = (token: string, id: string): Promise<any> =>
	request(token, `/runs/${id}/invoice`);
export const getInvoiceHtml = async (token: string, id: string): Promise<string> =>
	await (await download(token, `/runs/${id}/invoice.html`)).text();
export const getBillingReportCsv = (token: string, id: string): Promise<Blob> =>
	download(token, `/runs/${id}/billing-report.csv`);

export const askBillingCoworker = (
	token: string,
	body: { question: string; run_id?: string; document_id?: string }
): Promise<AskResponse> => request(token, '/ask', { method: 'POST', body });

export const getAudit = (token: string): Promise<AuditEntry[]> => request(token, '/audit');

export const getBillingSettings = (token: string): Promise<any> => request(token, '/settings');
export const updateBillingSettings = (token: string, body: any): Promise<any> =>
	request(token, '/settings', { method: 'PUT', body });
export const resetDemo = (token: string) => request(token, '/reset-demo', { method: 'POST' });

// ---------- Utilities ----------
export const saveBlob = (blob: Blob, filename: string) => {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export const fmtMoney = (n: number | null | undefined) =>
	n === null || n === undefined || isNaN(Number(n))
		? '—'
		: Number(n).toLocaleString('en-SG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const deleteRun = (token: string, id: string) => request(token, `/runs/${id}`, { method: 'DELETE' });
export const deleteTimesheet = (token: string, id: string) => request(token, `/timesheets/${id}`, { method: 'DELETE' });
export const createReviewItem = (
	token: string,
	body: { category: string; title: string; party?: string; detail?: string; document_id?: string }
): Promise<ReviewItem> => request(token, '/review-queue', { method: 'POST', body });
export const deleteReviewItem = (token: string, id: string) =>
	request(token, `/review-queue/${id}`, { method: 'DELETE' });
export const updateReviewItem = (token: string, id: string, body: Record<string, any>): Promise<ReviewItem> =>
	request(token, `/review-queue/${id}`, { method: 'PUT', body });

<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import {
		getDocuments,
		getEmployees,
		getTimesheets,
		confirmDocument,
		calculateRun,
		getRun,
		getRuns,
		deleteRun,
		validateRun,
		approveRun,
		getInvoiceHtml,
		getBillingReportCsv,
		getAudit,
		saveBlob,
		fmtMoney,
		type TgDocument,
		type Employee,
		type Run,
		type AuditEntry
	} from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import Pill from '$lib/components/tg-billing/Pill.svelte';
	import Stepper from '$lib/components/tg-billing/Stepper.svelte';
	import CalcTable from '$lib/components/tg-billing/CalcTable.svelte';
	import InvoiceSheet from '$lib/components/tg-billing/InvoiceSheet.svelte';
	import CoworkerChat from '$lib/components/tg-billing/CoworkerChat.svelte';
	import {
		docStatusVariant,
		checkVariant,
		runStatusVariant
	} from '$lib/components/tg-billing/statusVariant';

	const defaultPeriod = () => {
		const d = new Date();
		d.setDate(1);
		d.setMonth(d.getMonth() - 1);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
	};

	let step = 1;
	let maxStep = 1;
	let loading = true;
	let busy = false;
	let error = '';
	let notice = '';

	let docs: TgDocument[] = [];
	let employees: Employee[] = [];
	let timesheetCount = 0;
	let timesheets: any[] = [];
	let period = defaultPeriod();
	let selectedDocId: string | null = null;

	let run: Run | null = null;
	let activeLine = 0;
	let panelOpen = false;

	let runs: Run[] = [];
	let audit: AuditEntry[] = [];
	let allRuns: Run[] = [];
	let selected: string[] = [];
	let dlFormat: 'both' | 'invoice' | 'report' = 'both';
	let dlBusy = false;
	let preview: { run: any; html: string } | null = null;
	let previewFrame: HTMLIFrameElement;

	$: periodRuns = allRuns.filter((r: any) => r.period === period);
	$: approvedRuns = periodRuns.filter((r: any) => r.status === 'Approved');
	$: awaitingRuns = periodRuns.filter((r: any) => r.status !== 'Approved');
	$: flaggedRuns = periodRuns.filter((r: any) => isFlagged(r));
	$: stalledRuns = awaitingRuns.filter(
		(r: any) => r.status === 'Awaiting validation' && Date.now() - new Date(r.updated_at).getTime() > 48 * 3600e3
	);
	$: periodAudit = audit.filter((a: any) => !a.run_id || periodRuns.some((r: any) => r.id === a.run_id)).slice(-30).reverse();
	$: selected = selected.filter((id) => approvedRuns.some((r: any) => r.id === id));

	const isFlagged = (r: any) => r.flagged ?? (r.validation?.outcome === 'flag' && r.status !== 'Approved');

	const toggleAll = () => {
		selected = selected.length === approvedRuns.length ? [] : approvedRuns.map((r: any) => r.id);
	};

	const previewRun = async (r: any) => {
		try {
			preview = { run: r, html: await getInvoiceHtml(localStorage.token, r.id) };
		} catch (e) {
			error = `${e}`;
		}
	};

	const printPreview = () => previewFrame?.contentWindow?.print();

	const downloadMany = async (rs: any[]) => {
		if (!rs.length) return;
		dlBusy = true;
		error = '';
		try {
			const files: { name: string; data: Blob }[] = [];
			for (const r of rs) {
				const n = r.invoice_no ?? r.id;
				if (dlFormat !== 'report') {
					files.push({ name: `${n}.html`, data: new Blob([await getInvoiceHtml(localStorage.token, r.id)], { type: 'text/html' }) });
				}
				if (dlFormat !== 'invoice') {
					files.push({ name: `${n}-billing-report.csv`, data: await getBillingReportCsv(localStorage.token, r.id) });
				}
			}
			if (files.length === 1) {
				saveBlob(files[0].data, files[0].name);
			} else {
				const { default: JSZip } = await import('jszip');
				const zip = new JSZip();
				for (const f of files) zip.file(f.name, f.data);
				saveBlob(await zip.generateAsync({ type: 'blob' }), rs.length === 1 ? `${rs[0].invoice_no ?? rs[0].id}.zip` : `invoices-${period}.zip`);
			}
			notice = `Downloaded ${rs.length} invoice${rs.length > 1 ? 's' : ''}.`;
		} catch (e) {
			error = `Download failed: ${e}`;
		}
		dlBusy = false;
	};

	const approveRow = async (r: any) => {
		busy = true;
		error = '';
		try {
			await approveRun(localStorage.token, r.id);
			await loadStep4();
			notice = `${r.invoice_no ?? r.id} approved.`;
		} catch (e) {
			error = `${e}`;
		}
		busy = false;
	};
	let onlyValid = true;

	const periodBounds = (p: string) => {
		const [y, m] = p.split('-').map(Number);
		const last = new Date(y, m, 0).getDate();
		return [`${p}-01`, `${p}-${String(last).padStart(2, '0')}`];
	};
	// null = valid for the period, otherwise the reason it is not
	const validityIssue = (d: TgDocument, p: string): string | null => {
		const [start, end] = periodBounds(p);
		const vf = d.instructions?.valid_from;
		const vt = d.instructions?.valid_to;
		if (vt && vt < start) return `Expired ${vt}`;
		if (vf && vf > end) return `Starts ${vf}`;
		return null;
	};
	$: periodDocs = docs.map((d) => ({
		d,
		issue: validityIssue(d, period),
		run: allRuns.find((r) => r.document_id === d.id && r.period === period) ?? null
	}));
	$: visibleDocs = onlyValid ? periodDocs.filter((x) => !x.issue) : periodDocs;
	// keep the selection on a document that applies to the chosen period
	$: if (!loading && visibleDocs.length && !visibleDocs.some((x) => x.d.id === selectedDocId)) {
		selectedDocId = (visibleDocs.find((x) => x.d.status === 'Ready') ?? visibleDocs[0]).d.id;
	}

	$: selectedDoc = docs.find((d) => d.id === selectedDocId) ?? null;
	$: ins = selectedDoc?.instructions ?? {};
	$: staff = selectedDoc?.staff_ids?.length
		? selectedDoc.staff_ids.map((id) => employees.find((e) => e.id === id)?.name ?? id)
		: employees
				.filter((e) => e.party && e.party === selectedDoc?.party && e.active !== false)
				.map((e) => e.name);
	$: staffRows = (selectedDoc?.staff_ids?.length
		? selectedDoc.staff_ids.map((id) => employees.find((e) => e.id === id)).filter(Boolean)
		: employees.filter((e) => e.party && e.party === selectedDoc?.party && e.active !== false)
	).map((e) => {
		const t = timesheets.find((x) => x.employee_id === e.id);
		const gap = t ? (t.scheduled_days ?? 0) - ((t.worked_days ?? 0) + (t.paid_leave_days ?? 0) + (t.unpaid_leave_days ?? 0)) : 0;
		return {
			name: e.name,
			basis: e.pay_basis,
			status: !t ? 'Missing' : gap > 0 ? `Missing ${gap} days` : 'Complete',
			ok: !!t && gap <= 0,
			leave: t ? `${t.paid_leave_days ?? 0} paid · ${t.unpaid_leave_days ?? 0} unpaid` : '—',
			ot: t ? t.ot_hours ?? 0 : '—'
		};
	});
	$: staffReady = staffRows.filter((r) => r.ok).length;
	$: periodRun = allRuns.find((r) => r.document_id === selectedDocId && r.period === period) ?? null;
	$: validCount = periodDocs.filter((x) => !x.issue).length;
	$: rateEntries = Object.entries(ins.rates ?? {}).filter(([, v]) => v !== null && v !== undefined);

	const goStep = (n: number) => {
		step = n;
		maxStep = Math.max(maxStep, n);
		if (n === 4) loadStep4();
		if (n !== 2) panelOpen = false;
	};

	const loadSources = async () => {
		loading = true;
		error = '';
		try {
			[docs, employees, allRuns] = await Promise.all([
				getDocuments(localStorage.token),
				getEmployees(localStorage.token),
				getRuns(localStorage.token)
			]);
			if (!selectedDocId) selectedDocId = docs.find((d) => d.status === 'Ready')?.id ?? docs[0]?.id ?? null;
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
		if (allRuns.length) maxStep = 4;
		loadTimesheets();
	};

	const loadTimesheets = async () => {
		try {
			timesheets = (await getTimesheets(localStorage.token, period)) ?? [];
			timesheetCount = timesheets.length;
		} catch {
			timesheets = [];
			timesheetCount = 0;
		}
	};

	onMount(loadSources);

	const confirmAndCalculate = async () => {
		if (!selectedDoc) return;
		busy = true;
		error = '';
		try {
			if (selectedDoc.status === 'Needs confirmation') {
				await confirmDocument(localStorage.token, selectedDoc.id);
				docs = await getDocuments(localStorage.token);
			}
			run = await calculateRun(localStorage.token, { document_id: selectedDoc.id, period });
			allRuns = await getRuns(localStorage.token);
			activeLine = 0;
			goStep(2);
		} catch (e) {
			error = `Calculation failed: ${e}`;
		}
		busy = false;
	};

	const openExisting = async () => {
		if (!periodRun) return;
		busy = true;
		error = '';
		try {
			run = await getRun(localStorage.token, periodRun.id);
			activeLine = 0;
			if (run.status === 'Approved') {
				await loadStep4();
				goStep(4);
			} else {
				goStep(2);
			}
		} catch (e) {
			error = `${e}`;
		}
		busy = false;
	};

	const deleteDraft = async () => {
		if (!periodRun || !confirm(`Delete draft invoice ${periodRun.invoice_no ?? periodRun.id}?`)) return;
		try {
			await deleteRun(localStorage.token, periodRun.id);
			allRuns = await getRuns(localStorage.token);
			if (run?.id === periodRun.id) run = null;
			notice = 'Draft invoice deleted.';
		} catch (e) {
			error = `${e}`;
		}
	};

	const flagToOps = () => {
		notice = 'Flagged. Opening the Review Queue so Billing Ops can follow up.';
		goto('/billing/review-queue');
	};

	const refreshRun = async () => {
		if (!run) return;
		try {
			run = await getRun(localStorage.token, run.id);
		} catch (e) {
			error = `${e}`;
		}
	};

	const validate = async (outcome: 'approve' | 'fix' | 'flag') => {
		if (!run) return;
		let note: string | undefined;
		if (outcome === 'flag') {
			note = prompt('Describe the source-data problem for the team:') ?? undefined;
			if (note === undefined) return;
		}
		busy = true;
		error = '';
		try {
			const res = await validateRun(localStorage.token, run.id, { outcome, note });
			if (res?.lines) run = res;
			if (outcome === 'approve') {
				await loadStep4();
				goStep(4);
			} else if (outcome === 'fix') {
				goStep(2);
				panelOpen = true;
			} else {
				notice = 'Flagged to the data owners. The invoice stays awaiting validation.';
			}
		} catch (e) {
			error = `${e}`;
		}
		busy = false;
	};

	const loadStep4 = async () => {
		try {
			const [r, a] = await Promise.all([getRuns(localStorage.token), getAudit(localStorage.token)]);
			allRuns = r ?? [];
			runs = r ?? [];
			audit = a ?? [];
		} catch (e) {
			error = `${e}`;
		}
	};

	const approve = async () => {
		if (!run) return;
		busy = true;
		error = '';
		try {
			run = await approveRun(localStorage.token, run.id);
			await loadStep4();
		} catch (e) {
			error = `${e}`;
		}
		busy = false;
	};

	const openInvoice = async () => {
		if (!run) return;
		try {
			const html = await getInvoiceHtml(localStorage.token, run.id);
			const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
			const w = window.open(url, '_blank');
			if (!w) saveBlob(new Blob([html], { type: 'text/html' }), `${run.invoice_no ?? run.id}.html`);
		} catch (e) {
			error = `${e}`;
		}
	};
	const downloadInvoice = async () => {
		if (!run) return;
		try {
			const html = await getInvoiceHtml(localStorage.token, run.id);
			saveBlob(new Blob([html], { type: 'text/html' }), `${run.invoice_no ?? run.id}.html`);
		} catch (e) {
			error = `${e}`;
		}
	};
	const downloadCsv = async () => {
		if (!run) return;
		try {
			saveBlob(
				await getBillingReportCsv(localStorage.token, run.id),
				`billing-report-${run.invoice_no ?? run.id}.csv`
			);
		} catch (e) {
			error = `${e}`;
		}
	};

	const notChanged = [
		'PO / Quotation / Contract terms',
		'Employee master records',
		'Timesheet entries',
		'Rates and billing instructions'
	];
</script>

<div class="flex h-full">
	<div class="min-w-0 flex-1 overflow-y-auto">
		<div class="mx-auto max-w-6xl p-4 sm:p-6">
			<PageHeader
				title="Invoice Preparation"
				subtitle="Four steps from source documents to an approved invoice. All figures come from the deterministic rule engine."
			/>

			<Stepper {step} {maxStep} onSelect={(n) => goStep(n)} />

			{#if error}
				<div class="mt-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">
					{error}
				</div>
			{/if}
			{#if notice}
				<div class="mt-4 rounded-xl bg-[#DDF1F5] p-3 text-sm text-[#0E7C8F]">{notice}</div>
			{/if}

			<!-- STEP 1 -->
			{#if step === 1}
				<div class="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
					{#each [{ t: 'Timesheets', v: selectedDoc ? `${staffReady} of ${staffRows.length} complete for ${period}` : `${timesheetCount} for ${period}`, ok: selectedDoc ? staffReady === staffRows.length && staffRows.length > 0 : timesheetCount > 0 }, { t: 'Invoice', v: periodRun ? `${periodRun.invoice_no ?? periodRun.id} · ${periodRun.status}` : `None yet for ${period}`, ok: !!periodRun, label: periodRun ? periodRun.status : 'Not started' }, { t: 'PO / Quotation', v: `${validCount} valid of ${docs.length} for ${period}`, ok: validCount > 0 }, { t: 'Employee details', v: selectedDoc ? `${staffRows.length} linked to ${selectedDoc.ref}` : `${employees.length} on file`, ok: staffRows.length > 0 || employees.length > 0 }] as c}
						<div class="rounded-xl border border-[#E3E7EC] bg-white p-3">
							<div class="flex items-center justify-between">
								<div class="text-sm font-semibold text-[#22344A]">{c.t}</div>
								<Pill variant={c.ok ? 'teal' : 'warn'}>{c.label ?? (c.ok ? 'Received' : 'Missing')}</Pill>
							</div>
							<div class="mt-1 text-xs text-[#6B7785]">{c.v}</div>
						</div>
					{/each}
				</div>

				<div class="mt-4 flex flex-wrap items-center gap-3">
					<label class="text-xs text-[#6B7785]">
						Billing period
						<input
							type="month"
							bind:value={period}
							on:change={() => {
								run = null;
								loadTimesheets();
							}}
							class="ml-2 rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
						/>
					</label>
					<label class="flex items-center gap-1.5 text-xs text-[#6B7785]">
						<input type="checkbox" bind:checked={onlyValid} />
						Only documents valid for {period}
					</label>
				</div>

				<div class="mt-4 grid gap-4 lg:grid-cols-5">
					<div class="space-y-2 lg:col-span-2">
						<div class="text-[11px] font-bold uppercase tracking-wide text-[#6B7785]">
							PO / Quotation / Contract
						</div>
						{#if loading}
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-5 text-sm text-[#6B7785]">Loading…</div>
						{:else if !docs.length}
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-5 text-sm text-[#6B7785]">
								No documents yet. Upload one in <a class="text-[#0E7C8F] underline" href="/billing/master-data">Master Data</a>.
							</div>
						{:else if !visibleDocs.length}
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-5 text-sm text-[#6B7785]">
								No PO / quotation is valid for {period}. Untick the filter to see all documents.
							</div>
						{:else}
							{#each visibleDocs as { d, issue, run: pr }}
								<button
									class="block w-full rounded-xl border bg-white p-3 text-left transition {selectedDocId === d.id
										? 'border-[#E8892B] ring-1 ring-[#E8892B]'
										: 'border-[#E3E7EC] hover:border-[#E8892B]'}"
									on:click={() => (selectedDocId = d.id)}
								>
									<div class="flex items-center justify-between gap-2">
										<span class="font-mono text-xs font-semibold text-[#22344A]">{d.ref}</span>
										<Pill variant={issue ? 'warn' : docStatusVariant(d.status)}>{issue ?? (d.status === 'Expired' ? 'PO expired' : d.status)}</Pill>
									</div>
									<div class="mt-1 flex justify-between text-xs text-[#6B7785]">
										<span>{d.party}</span>
										<span>Confidence {d.confidence ?? 0}%</span>
									</div>
									{#if pr}
										<div class="mt-1 text-xs text-[#6B7785]">
											{period}: {pr.status}{pr.invoice_no ? ` · ${pr.invoice_no}` : ''} · SGD {fmtMoney(pr.total)}
										</div>
									{/if}
								</button>
							{/each}
						{/if}
					</div>

					<div class="rounded-xl border border-[#E3E7EC] bg-white p-4 lg:col-span-3">
						{#if !selectedDoc}
							<div class="text-sm text-[#6B7785]">Select a PO or quotation to see its billing instructions.</div>
						{:else}
							<div class="flex items-center justify-between">
								<div class="font-semibold text-[#22344A]">Billing instructions — {selectedDoc.ref}</div>
								<Pill variant={docStatusVariant(selectedDoc.status)}>{selectedDoc.status}</Pill>
							</div>
							<table class="mt-3 w-full text-sm">
								<tbody>
									{#each [['Billing basis', ins.billing_basis], ['Management fee', ins.fee_pct != null ? `${ins.fee_pct}%` : null], ['GST', ins.gst_pct != null ? `${ins.gst_pct}%` : null], ['Rates', rateEntries.map(([k, v]) => `${k.replace('_', '-')}: ${v}`).join(' · ')], ['Period rule', ins.period_rule], ['Invoice split', ins.invoice_split], ['Mandatory references', (ins.mandatory_references ?? []).join(', ')], ['Supporting documents', (ins.supporting_documents ?? []).join(', ')], ['Tax treatment', ins.tax_treatment], ['Submission channel', ins.submission_channel], ['Valid', ins.valid_from || ins.valid_to ? `${ins.valid_from ?? '—'} → ${ins.valid_to ?? '—'}` : null]] as [k, v]}
										<tr class="border-t border-[#EEF0F3]">
											<td class="w-28 py-1.5 pr-3 align-top text-xs text-[#6B7785] sm:w-40">{k}</td>
											<td class="break-words py-1.5">{v || '—'}</td>
										</tr>
									{/each}
								</tbody>
							</table>

							<div class="mt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B7785]">Staff · {period}</div>
							{#if staffRows.length}
								<div class="mt-1 overflow-x-auto">
									<table class="w-full min-w-[420px] text-xs">
										<thead class="text-left text-[10px] uppercase text-[#6B7785]">
											<tr><th class="py-1">Officer</th><th>Basis</th><th>Leave</th><th>OT h</th><th>Timesheet</th></tr>
										</thead>
										<tbody>
											{#each staffRows as r}
												<tr class="border-t border-[#EEF0F3]">
													<td class="py-1.5 pr-2">{r.name}</td>
													<td class="pr-2">{r.basis}</td>
													<td class="pr-2">{r.leave}</td>
													<td class="pr-2">{r.ot}</td>
													<td><Pill variant={r.ok ? 'teal' : 'warn'}>{r.status}</Pill></td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else}
								<div class="mt-1 text-xs text-[#6B7785]">No staff linked.</div>
							{/if}

							{#if periodRun}
								<div class="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[#F1F3F6] p-3 text-xs">
									<div>
										<span class="font-mono font-semibold text-[#22344A]">{periodRun.invoice_no ?? periodRun.id}</span>
										· {periodRun.status} · SGD {fmtMoney(periodRun.total)}
									</div>
									<div class="flex gap-3">
										<button class="font-semibold text-[#0E7C8F] underline" on:click={openExisting}>Open invoice</button>
										{#if periodRun.status !== 'Approved'}
											<button class="font-semibold text-[#B42318] underline" on:click={deleteDraft}>Delete draft</button>
										{/if}
									</div>
								</div>
							{/if}

							{#if selectedDoc.status === 'Expired'}
								<div class="mt-3 rounded-lg bg-[#FBE1E1] p-2.5 text-xs text-[#B42318]">
									This PO has expired. Flag it to Billing Ops to obtain a renewed PO before invoicing.
								</div>
							{/if}

							<div class="mt-4 flex flex-wrap gap-2">
								<button
									class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
									disabled={busy || (selectedDoc.status === 'Expired' && !periodRun)}
									on:click={() => (periodRun?.status === 'Approved' ? openExisting() : confirmAndCalculate())}
								>
									{busy ? 'Calculating…' : periodRun ? (periodRun.status === 'Approved' ? 'View approved invoice' : 'Recalculate draft invoice') : 'Confirm instructions & generate draft invoice'}
								</button>
								<button
									class="rounded-lg border border-[#C8610F] px-4 py-2 text-sm font-semibold text-[#C8610F] hover:bg-[#FDF1E6]"
									on:click={flagToOps}
								>
									Flag to Billing Ops
								</button>
							</div>
						{/if}
					</div>
				</div>

				<!-- STEP 2 -->
			{:else if step === 2}
				{#if !run}
					<div class="mt-5 rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
						No calculation yet. Go back to step 1.
					</div>
				{:else}
					<div class="mt-5 flex flex-wrap items-stretch gap-3 rounded-xl border border-[#E3E7EC] bg-white p-4">
						{#each [['Billing basis', run.basis], ['Period', run.period], ['Staff', String(run.lines.length)], ['Total billable', `SGD ${fmtMoney(run.total)}`]] as [k, v]}
							<div class="min-w-[120px] flex-1">
								<div class="text-[10px] font-bold uppercase tracking-wide text-[#6B7785]">{k}</div>
								<div class="mt-0.5 text-lg font-bold text-[#22344A]">{v}</div>
							</div>
						{/each}
						<div class="flex items-center gap-2">
							<Pill variant="dark">Deterministic rule engine</Pill>
							<button
								class="rounded-lg border border-[#C8610F] px-3 py-1.5 text-sm font-semibold text-[#C8610F] hover:bg-[#FDF1E6]"
								on:click={() => (panelOpen = !panelOpen)}
							>
								{panelOpen ? 'Hide' : 'Ask'} Billing Coworker
							</button>
						</div>
					</div>

					<div class="mt-4 flex flex-wrap gap-1 border-b border-[#E3E7EC]" role="tablist">
						{#each run.lines as l, i}
							<button
								role="tab"
								aria-selected={activeLine === i}
								class="border-b-2 px-4 py-2 text-sm font-semibold {activeLine === i
									? 'border-[#E8892B] text-[#22344A]'
									: 'border-transparent text-[#6B7785] hover:text-[#22344A]'}"
								on:click={() => (activeLine = i)}
							>
								{l.name}
							</button>
						{/each}
					</div>

					<div class="mt-4 grid gap-4 xl:grid-cols-3">
						<div class="xl:col-span-2">
							{#if run.lines[activeLine]}
								<CalcTable line={run.lines[activeLine]} />
							{/if}
						</div>
						<div class="space-y-4">
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-2 font-semibold text-[#22344A]">Checks</div>
								{#each run.checks ?? [] as c}
									<div class="flex items-center justify-between gap-2 border-t border-[#EEF0F3] py-1.5 text-sm first:border-0">
										<span>
											{c.label}
											{#if c.value}<span class="text-xs text-[#6B7785]"> · {c.value}</span>{/if}
										</span>
										<Pill variant={checkVariant(c.result)}>{c.result}</Pill>
									</div>
								{:else}
									<div class="text-sm text-[#6B7785]">No checks returned.</div>
								{/each}
							</div>
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-2 font-semibold text-[#22344A]">Not changed by Billing Coworker</div>
								<ul class="space-y-1 text-sm text-[#33414F]">
									{#each notChanged as n}
										<li class="flex items-center gap-2">
											<span class="text-[#0E7C8F]">✓</span>{n}
										</li>
									{/each}
								</ul>
							</div>
						</div>
					</div>

					<div class="mt-5 flex justify-end gap-2">
						<button
							class="rounded-lg border border-[#D5DBE2] px-4 py-2 text-sm text-[#33414F]"
							on:click={() => goStep(1)}
						>
							Back
						</button>
						<button
							class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A]"
							on:click={() => goStep(3)}
						>
							Generate invoice &amp; billing report
						</button>
					</div>
				{/if}

				<!-- STEP 3 -->
			{:else if step === 3}
				{#if !run}
					<div class="mt-5 rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
						No run to preview.
					</div>
				{:else}
					<div class="mt-5 grid gap-4 lg:grid-cols-3">
						<div class="lg:col-span-2">
							<InvoiceSheet {run} doc={docs.find((d) => d.id === run?.document_id) ?? selectedDoc} />
						</div>
						<div class="space-y-4">
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-3 font-semibold text-[#22344A]">Validate</div>
								<div class="space-y-2">
									<button
										class="w-full rounded-lg bg-[#C8610F] px-3 py-2 text-left text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
										disabled={busy}
										on:click={() => validate('approve')}
									>
										Amount correct · approve billing
									</button>
									<button
										class="w-full rounded-lg border border-[#D5DBE2] px-3 py-2 text-left text-sm text-[#33414F] hover:bg-[#F6F7F9] disabled:opacity-50"
										disabled={busy}
										on:click={() => validate('fix')}
									>
										Calculation wrong · fix with Billing Coworker
									</button>
									<button
										class="w-full rounded-lg border border-[#D5DBE2] px-3 py-2 text-left text-sm text-[#33414F] hover:bg-[#F6F7F9] disabled:opacity-50"
										disabled={busy}
										on:click={() => validate('flag')}
									>
										Source data wrong · flag &amp; email team
									</button>
								</div>
							</div>
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-2 font-semibold text-[#22344A]">Checks</div>
								{#each run.checks ?? [] as c}
									<div class="flex items-center justify-between gap-2 border-t border-[#EEF0F3] py-1.5 text-sm first:border-0">
										<span>{c.label}</span>
										<Pill variant={checkVariant(c.result)}>{c.result}</Pill>
									</div>
								{/each}
							</div>
						</div>
					</div>
				{/if}

				<!-- STEP 4 -->
			{:else if step === 4}
				<div class="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
					{#each [['Approved', approvedRuns.length, ''], ['Awaiting validation', awaitingRuns.length, ''], ['Flagged to teams', flaggedRuns.length, 'text-[#C8610F]'], ['Stalled > 48h', stalledRuns.length, 'text-[#C8610F]']] as [l, v, c]}
						<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
							<div class="text-[11px] font-semibold uppercase tracking-wide text-[#6B7785]">{l}</div>
							<div class="mt-1 text-3xl font-bold {c || 'text-[#22344A]'}">{v}</div>
						</div>
					{/each}
				</div>

				<div class="mt-4 rounded-xl border border-[#E3E7EC] bg-[#F6F7F9]">
					<div class="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
						<div class="font-semibold text-[#22344A]">
							Invoices for {period} · select approved invoices to download in bulk
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<label class="flex items-center gap-2 text-xs text-[#6B7785]">
								Format
								<select bind:value={dlFormat} class="rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]">
									<option value="both">Invoice + billing report</option>
									<option value="invoice">Invoice only (HTML)</option>
									<option value="report">Billing report only (CSV)</option>
								</select>
							</label>
							<button
								class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
								disabled={!selected.length || dlBusy}
								on:click={() => downloadMany(periodRuns.filter((r) => selected.includes(r.id)))}
							>
								{dlBusy ? 'Preparing…' : `Download selected (ZIP)${selected.length ? ` · ${selected.length}` : ''}`}
							</button>
						</div>
					</div>
					{#if !periodRuns.length}
						<div class="border-t border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
							No invoices for {period}. Generate one in step 1.
						</div>
					{:else}
						<div class="overflow-x-auto border-t border-[#E3E7EC] bg-white">
							<table class="w-full min-w-[860px] text-sm">
								<thead class="text-left text-xs font-semibold text-[#33414F]">
									<tr>
										<th class="px-4 py-3">
											<input
												type="checkbox"
												aria-label="Select all approved"
												checked={approvedRuns.length > 0 && selected.length === approvedRuns.length}
												on:change={toggleAll}
											/>
										</th>
										<th class="px-2 py-3">Invoice</th>
										<th class="px-2 py-3">PO / Quotation</th>
										<th class="px-2 py-3">Agency</th>
										<th class="px-2 py-3 text-right">Staff</th>
										<th class="px-2 py-3 text-right">Total (SGD)</th>
										<th class="px-2 py-3">Status</th>
										<th class="px-2 py-3">Reviewer</th>
										<th class="px-4 py-3"></th>
									</tr>
								</thead>
								<tbody>
									{#each periodRuns as r}
										<tr class="border-t border-[#E3E7EC]">
											<td class="px-4 py-3">
												<input type="checkbox" disabled={r.status !== 'Approved'} bind:group={selected} value={r.id} aria-label="Select {r.invoice_no ?? r.id}" />
											</td>
											<td class="whitespace-nowrap px-2 py-3 font-mono text-xs">{r.invoice_no ?? r.id}</td>
											<td class="whitespace-nowrap px-2 py-3 font-mono text-xs">{r.document_ref ?? ''}</td>
											<td class="px-2 py-3">{r.party ?? ''}</td>
											<td class="px-2 py-3 text-right">{r.staff ?? r.lines?.length ?? ''}</td>
											<td class="px-2 py-3 text-right tabular-nums">{fmtMoney(r.total)}</td>
											<td class="px-2 py-3">
												<Pill variant={isFlagged(r) ? 'warn' : runStatusVariant(r.status)}>{isFlagged(r) ? 'Flagged' : r.status}</Pill>
											</td>
											<td class="px-2 py-3 text-xs text-[#6B7785]">{r.approved_by ?? '—'}</td>
											<td class="whitespace-nowrap px-4 py-3 text-right text-xs">
												<button class="font-semibold text-[#0E7C8F] underline" on:click={() => previewRun(r)}>Preview</button>
												{#if r.status === 'Approved'}
													· <button class="font-semibold text-[#0E7C8F] underline" disabled={dlBusy} on:click={() => downloadMany([r])}>Download</button>
												{:else}
													· <button class="font-semibold text-[#C8610F] underline" disabled={busy} on:click={() => approveRow(r)}>Approve</button>
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>

				<div class="mt-4 rounded-xl border border-[#E3E7EC] bg-white p-4">
					<div class="font-semibold text-[#22344A]">Audit log</div>
					<div class="text-xs text-[#6B7785]">All validations, fixes, approvals and downloads are recorded.</div>
					{#if !periodAudit.length}
						<div class="mt-2 text-sm text-[#6B7785]">No audit entries yet.</div>
					{:else}
						<ul class="mt-2 max-h-64 space-y-1 overflow-y-auto font-mono text-[11px] text-[#33414F]">
							{#each periodAudit as a}
								<li class="flex gap-3"><span class="shrink-0 text-[#6B7785]">[{(a.ts ?? '').replace('T', ' ').slice(5, 16)}]</span><span><b>[{a.actor}]</b> {a.detail ?? a.action}</span></li>
							{/each}
						</ul>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<!-- slide-in assistant panel (step 2 only) -->
	{#if step === 2 && panelOpen}
		<aside
			class="fixed inset-y-0 right-0 z-30 flex w-[min(320px,100vw)] flex-col border-l border-[#E3E7EC] bg-white shadow-xl xl:static xl:z-auto xl:shadow-none"
			aria-label="Billing Coworker"
		>
			<div class="flex items-center justify-between border-b border-[#E3E7EC] px-4 py-3">
				<div class="font-semibold text-[#22344A]">Billing Coworker</div>
				<button
					class="rounded p-1 text-[#6B7785] hover:bg-[#F1F3F6]"
					aria-label="Close assistant"
					on:click={() => (panelOpen = false)}>✕</button
				>
			</div>
			<div class="min-h-0 flex-1">
				<CoworkerChat {run} focusName={run?.lines?.[activeLine]?.name ?? ''} on:changed={refreshRun} />
			</div>
		</aside>
	{/if}
</div>

{#if preview}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2 sm:p-6" role="dialog" aria-modal="true">
		<div class="flex h-full max-h-[92dvh] w-full max-w-4xl flex-col rounded-xl bg-white shadow-xl">
			<div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#E3E7EC] px-4 py-3">
				<div class="font-semibold text-[#22344A]">
					Preview {preview.run.invoice_no ?? preview.run.id}
					<span class="ml-2 text-xs font-normal text-[#6B7785]">{preview.run.status}</span>
				</div>
				<div class="flex gap-2">
					<button class="rounded-lg border border-[#D5DBE2] px-3 py-1.5 text-sm" on:click={printPreview}>Print / Save as PDF</button>
					{#if preview.run.status === 'Approved'}
						<button class="rounded-lg bg-[#C8610F] px-3 py-1.5 text-sm font-semibold text-white" on:click={() => downloadMany([preview.run])}>Download</button>
					{/if}
					<button class="rounded-lg border border-[#D5DBE2] px-3 py-1.5 text-sm" on:click={() => (preview = null)}>Close</button>
				</div>
			</div>
			<iframe bind:this={previewFrame} title="Invoice preview" class="min-h-0 w-full flex-1 rounded-b-xl" srcdoc={preview.html}></iframe>
		</div>
	</div>
{/if}

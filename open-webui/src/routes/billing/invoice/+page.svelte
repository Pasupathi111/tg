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
	let period = defaultPeriod();
	let selectedDocId: string | null = null;

	let run: Run | null = null;
	let activeLine = 0;
	let panelOpen = false;

	let runs: Run[] = [];
	let audit: AuditEntry[] = [];
	let allRuns: Run[] = [];
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
	$: rateEntries = Object.entries(ins.rates ?? {}).filter(([, v]) => v !== null && v !== undefined);

	const goStep = (n: number) => {
		step = n;
		maxStep = Math.max(maxStep, n);
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
		loadTimesheets();
	};

	const loadTimesheets = async () => {
		try {
			timesheetCount = (await getTimesheets(localStorage.token, period))?.length ?? 0;
		} catch {
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
				notice = 'Flagged to the data owners. The run stays awaiting validation.';
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
			runs = (r ?? []).filter((x) => !run || x.document_id === run.document_id);
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
					{#each [{ t: 'Timesheets', v: `${timesheetCount} for ${period}`, ok: timesheetCount > 0 }, { t: 'Billing report', v: 'Generated in step 4', ok: true }, { t: 'PO / Quotation', v: `${docs.length} on file`, ok: docs.length > 0 }, { t: 'Employee details', v: `${employees.length} on file`, ok: employees.length > 0 }] as c}
						<div class="rounded-xl border border-[#E3E7EC] bg-white p-3">
							<div class="flex items-center justify-between">
								<div class="text-sm font-semibold text-[#22344A]">{c.t}</div>
								<Pill variant={c.ok ? 'teal' : 'warn'}>{c.ok ? 'Received' : 'Missing'}</Pill>
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

							<div class="mt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B7785]">Staff</div>
							<div class="mt-1 flex flex-wrap gap-1.5">
								{#each staff as s}
									<span class="rounded-full bg-[#F1F3F6] px-2.5 py-1 text-xs text-[#22344A]">{s}</span>
								{:else}
									<span class="text-xs text-[#6B7785]">No staff linked.</span>
								{/each}
							</div>

							{#if selectedDoc.status === 'Expired'}
								<div class="mt-3 rounded-lg bg-[#FBE1E1] p-2.5 text-xs text-[#B42318]">
									This PO has expired. Flag it to Billing Ops to obtain a renewed PO before invoicing.
								</div>
							{/if}

							<div class="mt-4 flex flex-wrap gap-2">
								<button
									class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
									disabled={busy || selectedDoc.status === 'Expired'}
									on:click={confirmAndCalculate}
								>
									{busy ? 'Calculating…' : 'Confirm instructions & calculate'}
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
				{#if !run}
					<div class="mt-5 rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
						No run to approve.
					</div>
				{:else}
					<div class="mt-5 grid gap-4 lg:grid-cols-3">
						<div class="space-y-4 lg:col-span-2">
							<div class="rounded-xl border border-[#E3E7EC] bg-white">
								<div class="border-b border-[#E3E7EC] px-4 py-3 font-semibold text-[#22344A]">Invoices</div>
								<div class="overflow-x-auto">
								<table class="w-full min-w-[480px] text-sm">
									<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
										<tr>
											<th class="px-4 py-2">Invoice</th>
											<th class="px-4 py-2">Period</th>
											<th class="px-4 py-2">Status</th>
											<th class="px-4 py-2 text-right">Total (SGD)</th>
										</tr>
									</thead>
									<tbody>
										{#each runs.length ? runs : [run] as r}
											<tr class="border-t border-[#EEF0F3] {r.id === run.id ? 'bg-[#FDF1E6]' : ''}">
												<td class="px-4 py-2 font-mono text-xs">{r.invoice_no ?? `${r.id} (no number yet)`}</td>
												<td class="px-4 py-2">{r.period}</td>
												<td class="px-4 py-2"><Pill variant={runStatusVariant(r.status)}>{r.status}</Pill></td>
												<td class="px-4 py-2 text-right tabular-nums">{fmtMoney(r.total)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
								</div>
							</div>

							<div class="rounded-xl border border-[#E3E7EC] bg-white">
								<div class="border-b border-[#E3E7EC] px-4 py-3 font-semibold text-[#22344A]">Audit log</div>
								{#if !audit.length}
									<div class="p-4 text-sm text-[#6B7785]">No audit entries yet.</div>
								{:else}
									<ul class="max-h-72 divide-y divide-[#EEF0F3] overflow-y-auto text-sm">
										{#each audit as a}
											<li class="px-4 py-2">
												<div>{a.action ?? a.detail ?? JSON.stringify(a)}</div>
												<div class="text-[11px] text-[#6B7785]">{a.actor ?? ''} {a.ts ?? a.timestamp ?? ''}</div>
											</li>
										{/each}
									</ul>
								{/if}
							</div>
						</div>

						<div class="space-y-4">
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-1 font-semibold text-[#22344A]">Approve</div>
								<div class="mb-3 text-sm text-[#6B7785]">
									Total SGD {fmtMoney(run.total)} · <Pill variant={runStatusVariant(run.status)}>{run.status}</Pill>
								</div>
								<button
									class="w-full rounded-lg bg-[#C8610F] px-3 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
									disabled={busy || run.status === 'Approved'}
									on:click={approve}
								>
									{run.status === 'Approved' ? `Approved ${run.invoice_no ?? ''}` : 'Approve invoice'}
								</button>
							</div>
							<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
								<div class="mb-3 font-semibold text-[#22344A]">Download</div>
								<div class="space-y-2">
									<button
										class="w-full rounded-lg border border-[#D5DBE2] px-3 py-2 text-left text-sm hover:bg-[#F6F7F9] disabled:opacity-50"
										disabled={run.status !== 'Approved'}
										on:click={downloadInvoice}
									>
										Download invoice (HTML)
									</button>
									<button
										class="w-full rounded-lg border border-[#D5DBE2] px-3 py-2 text-left text-sm hover:bg-[#F6F7F9] disabled:opacity-50"
										disabled={run.status !== 'Approved'}
										on:click={openInvoice}
									>
										Open printable invoice
									</button>
									<button
										class="w-full rounded-lg border border-[#D5DBE2] px-3 py-2 text-left text-sm hover:bg-[#F6F7F9] disabled:opacity-50"
										disabled={run.status !== 'Approved'}
										on:click={downloadCsv}
									>
										Download billing report (CSV)
									</button>
									{#if run.status !== 'Approved'}
										<div class="text-[11px] text-[#6B7785]">Downloads unlock after approval.</div>
									{/if}
								</div>
							</div>
						</div>
					</div>
				{/if}
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

<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getDocuments,
		uploadDocument,
		deleteDocument,
		confirmDocument,
		getEmployees,
		createEmployee,
		updateEmployee,
		deleteEmployee,
		type TgDocument,
		type Employee
	} from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import Pill from '$lib/components/tg-billing/Pill.svelte';
	import { docStatusVariant } from '$lib/components/tg-billing/statusVariant';

	let tab: 'documents' | 'employees' = 'documents';

	let docs: TgDocument[] = [];
	let employees: Employee[] = [];
	let loading = true;
	let error = '';
	let notice = '';

	let uploading = false;
	let dragOver = false;
	let docType = '';
	let party = '';
	let fileInput: HTMLInputElement;
	let selectedDoc: TgDocument | null = null;

	// employee editor
	let editing: Partial<Employee> | null = null;
	let savingEmp = false;

	const empFields: { key: string; label: string; type?: string }[] = [
		{ key: 'name', label: 'Name' },
		{ key: 'pay_basis', label: 'Pay basis' },
		{ key: 'monthly_salary', label: 'Monthly salary', type: 'number' },
		{ key: 'hourly_rate', label: 'Hourly rate', type: 'number' },
		{ key: 'weekly_rate', label: 'Weekly rate', type: 'number' },
		{ key: 'age', label: 'Age', type: 'number' },
		{ key: 'residency', label: 'Residency' },
		{ key: 'half_day_rate', label: 'Half-day rate', type: 'number' },
		{ key: 'party', label: 'Agency / party' }
	];

	const load = async () => {
		loading = true;
		error = '';
		try {
			[docs, employees] = await Promise.all([
				getDocuments(localStorage.token),
				getEmployees(localStorage.token)
			]);
			if (selectedDoc) selectedDoc = docs.find((d) => d.id === selectedDoc?.id) ?? null;
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	};
	onMount(load);

	const uploadFiles = async (files: FileList | File[]) => {
		if (!files?.length) return;
		uploading = true;
		error = '';
		notice = '';
		for (const f of Array.from(files)) {
			try {
				const d = await uploadDocument(localStorage.token, f, {
					doc_type: docType || undefined,
					party: party || undefined
				});
				notice = `Uploaded ${f.name}${d?.ref ? ` as ${d.ref}` : ''}.`;
			} catch (e) {
				error = `Upload failed for ${f.name}: ${e}`;
			}
		}
		uploading = false;
		if (fileInput) fileInput.value = '';
		await load();
	};

	const onDrop = (e: DragEvent) => {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) uploadFiles(e.dataTransfer.files);
	};

	const removeDoc = async (d: TgDocument) => {
		if (!confirm(`Delete ${d.ref}?`)) return;
		try {
			await deleteDocument(localStorage.token, d.id);
			if (selectedDoc?.id === d.id) selectedDoc = null;
			await load();
		} catch (e) {
			error = `${e}`;
		}
	};

	const confirmDoc = async (d: TgDocument) => {
		try {
			await confirmDocument(localStorage.token, d.id);
			await load();
		} catch (e) {
			error = `${e}`;
		}
	};

	const saveEmp = async () => {
		if (!editing) return;
		savingEmp = true;
		error = '';
		try {
			const body: any = { ...editing };
			for (const f of empFields) {
				if (f.type === 'number') {
					if (body[f.key] === '' || body[f.key] === undefined) delete body[f.key];
					else body[f.key] = Number(body[f.key]);
				}
			}
			if (editing.id) await updateEmployee(localStorage.token, editing.id, body);
			else await createEmployee(localStorage.token, body);
			editing = null;
			await load();
		} catch (e) {
			error = `${e}`;
		}
		savingEmp = false;
	};

	const removeEmp = async (e: Employee) => {
		if (!confirm(`Delete ${e.name}?`)) return;
		try {
			await deleteEmployee(localStorage.token, e.id);
			await load();
		} catch (err) {
			error = `${err}`;
		}
	};

	const staffNames = (d: TgDocument) =>
		(d.staff_ids ?? []).map((id) => employees.find((e) => e.id === id)?.name ?? id).join(', ');
</script>

<div class="mx-auto max-w-6xl p-4 sm:p-6">
	<PageHeader
		title="Master Data"
		subtitle="Knowledge base of POs, quotations and contracts, plus the employee master. The assistant never edits these records."
	>
		<Pill variant="dark">Read-only for the assistant</Pill>
	</PageHeader>

	<div class="mb-4 flex gap-1 border-b border-[#E3E7EC]" role="tablist">
		{#each [['documents', `Documents & POs (${docs.length})`], ['employees', `Employees (${employees.length})`]] as [k, label]}
			<button
				role="tab"
				aria-selected={tab === k}
				class="border-b-2 px-4 py-2 text-sm font-semibold transition {tab === k
					? 'border-[#E8892B] text-[#22344A]'
					: 'border-transparent text-[#6B7785] hover:text-[#22344A]'}"
				on:click={() => (tab = k === 'documents' ? 'documents' : 'employees')}
			>
				{label}
			</button>
		{/each}
	</div>

	{#if error}
		<div class="mb-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">
			{error}
		</div>
	{/if}
	{#if notice}
		<div class="mb-4 rounded-xl bg-[#DDF1F5] p-3 text-sm text-[#0E7C8F]">{notice}</div>
	{/if}

	{#if tab === 'documents'}
		<!-- upload -->
		<div
			class="mb-5 rounded-xl border-2 border-dashed bg-white p-5 transition {dragOver
				? 'border-[#E8892B] bg-[#FDF1E6]'
				: 'border-[#D5DBE2]'}"
			on:dragover|preventDefault={() => (dragOver = true)}
			on:dragleave={() => (dragOver = false)}
			on:drop={onDrop}
			role="region"
			aria-label="Upload documents"
		>
			<div class="flex flex-wrap items-end gap-3">
				<div class="min-w-[220px] flex-1">
					<div class="font-semibold text-[#22344A]">Upload PO / Quotation / Contract</div>
					<div class="text-xs text-[#6B7785]">
						Drop files here or browse. PDF, DOCX, TXT, CSV or XLSX. Billing instructions are extracted
						automatically.
					</div>
				</div>
				<label class="text-xs text-[#6B7785]">
					Type
					<select
						bind:value={docType}
						class="mt-1 block rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
					>
						<option value="">Auto-detect</option>
						<option>PO</option>
						<option>Quotation</option>
						<option>Contract</option>
					</select>
				</label>
				<label class="text-xs text-[#6B7785]">
					Party (optional)
					<input
						bind:value={party}
						placeholder="e.g. Agency A"
						class="mt-1 block rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
					/>
				</label>
				<input
					bind:this={fileInput}
					type="file"
					multiple
					class="hidden"
					accept=".pdf,.docx,.txt,.csv,.xlsx"
					on:change={(e) => uploadFiles(e.currentTarget.files ?? [])}
				/>
				<button
					class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
					disabled={uploading}
					on:click={() => fileInput.click()}
				>
					{uploading ? 'Uploading…' : 'Upload files'}
				</button>
			</div>
		</div>

		<div class="grid gap-4 lg:grid-cols-5">
			<div class="rounded-xl border border-[#E3E7EC] bg-white lg:col-span-3">
				{#if loading}
					<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
				{:else if !docs.length}
					<div class="p-6 text-sm text-[#6B7785]">
						No documents yet. Upload a PO or quotation to get started.
					</div>
				{:else}
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
								<tr>
									<th class="px-4 py-2">Reference</th>
									<th class="px-4 py-2">Party</th>
									<th class="px-4 py-2">Status</th>
									<th class="px-4 py-2 text-right">Confidence</th>
									<th class="px-4 py-2"></th>
								</tr>
							</thead>
							<tbody>
								{#each docs as d}
									<tr
										class="cursor-pointer border-t border-[#E3E7EC] hover:bg-[#FAFBFC] {selectedDoc?.id ===
										d.id
											? 'bg-[#FDF1E6]'
											: ''}"
										on:click={() => (selectedDoc = d)}
									>
										<td class="px-4 py-2">
											<div class="font-mono text-xs font-semibold text-[#22344A]">{d.ref}</div>
											<div class="text-[11px] text-[#6B7785]">{d.doc_type}</div>
										</td>
										<td class="px-4 py-2">{d.party}</td>
										<td class="px-4 py-2"><Pill variant={docStatusVariant(d.status)}>{d.status}</Pill></td>
										<td class="px-4 py-2 text-right">{d.confidence ?? 0}%</td>
										<td class="px-4 py-2 text-right">
											<button
												class="text-xs text-[#B42318] hover:underline"
												on:click|stopPropagation={() => removeDoc(d)}
											>
												Delete
											</button>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<div class="rounded-xl border border-[#E3E7EC] bg-white p-4 lg:col-span-2">
				{#if !selectedDoc}
					<div class="text-sm text-[#6B7785]">Select a document to see the extracted instructions.</div>
				{:else}
					{@const ins = selectedDoc.instructions ?? {}}
					<div class="flex items-start justify-between gap-2">
						<div>
							<div class="font-mono text-sm font-bold text-[#22344A]">{selectedDoc.ref}</div>
							<div class="text-xs text-[#6B7785]">
								{selectedDoc.party} · {selectedDoc.source_filename ?? ''}
							</div>
						</div>
						<Pill variant={docStatusVariant(selectedDoc.status)}>{selectedDoc.status}</Pill>
					</div>
					<dl class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
						<dt class="text-[#6B7785]">Billing basis</dt>
						<dd>{ins.billing_basis ?? '—'}</dd>
						<dt class="text-[#6B7785]">Management fee</dt>
						<dd>{ins.fee_pct ?? '—'}%</dd>
						<dt class="text-[#6B7785]">GST</dt>
						<dd>{ins.gst_pct ?? '—'}%</dd>
						<dt class="text-[#6B7785]">Rates (SGD)</dt>
						<dd>
							{#each Object.entries(ins.rates ?? {}).filter(([, v]) => v) as [k, v]}
								<div>{k.replace('_', '-')}: {Number(v).toLocaleString('en-SG', { minimumFractionDigits: 2 })}</div>
							{:else}
								—
							{/each}
						</dd>
						<dt class="text-[#6B7785]">Valid</dt>
						<dd>{ins.valid_from ?? '—'} → {ins.valid_to ?? '—'}</dd>
						<dt class="text-[#6B7785]">Period rule</dt>
						<dd>{ins.period_rule ?? '—'}</dd>
						<dt class="text-[#6B7785]">Staff</dt>
						<dd>{staffNames(selectedDoc) || '—'}</dd>
					</dl>
					{#if selectedDoc.text_excerpt}
						<div class="mt-3 max-h-40 overflow-y-auto rounded-lg bg-[#F6F7F9] p-2.5 font-mono text-[11px] text-[#33414F]">
							{selectedDoc.text_excerpt}
						</div>
					{/if}
					{#if selectedDoc.status === 'Needs confirmation'}
						<button
							class="mt-3 rounded-lg bg-[#C8610F] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#B4560A]"
							on:click={() => selectedDoc && confirmDoc(selectedDoc)}
						>
							Confirm instructions
						</button>
					{/if}
				{/if}
			</div>
		</div>
	{:else}
		<div class="mb-3 flex justify-end">
			<button
				class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A]"
				on:click={() => (editing = { name: '' })}
			>
				Add employee
			</button>
		</div>
		<div class="overflow-x-auto rounded-xl border border-[#E3E7EC] bg-white">
			{#if loading}
				<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
			{:else if !employees.length}
				<div class="p-6 text-sm text-[#6B7785]">No employees yet.</div>
			{:else}
				<table class="w-full text-sm">
					<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
						<tr>
							<th class="px-4 py-2">ID</th>
							{#each empFields as f}
								<th class="px-4 py-2 {f.type === 'number' ? 'text-right' : ''}">{f.label}</th>
							{/each}
							<th class="px-4 py-2"></th>
						</tr>
					</thead>
					<tbody>
						{#each employees as e}
							<tr class="border-t border-[#E3E7EC]">
								<td class="px-4 py-2 font-mono text-xs">{e.id}</td>
								{#each empFields as f}
									<td class="px-4 py-2 {f.type === 'number' ? 'text-right' : ''}">{e[f.key] ?? '—'}</td>
								{/each}
								<td class="whitespace-nowrap px-4 py-2 text-right text-xs">
									<button class="mr-3 text-[#0E7C8F] hover:underline" on:click={() => (editing = { ...e })}>
										Edit
									</button>
									<button class="text-[#B42318] hover:underline" on:click={() => removeEmp(e)}>
										Delete
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>
	{/if}
</div>

{#if editing}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
		<form
			class="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-4 shadow-xl sm:p-5"
			on:submit|preventDefault={saveEmp}
		>
			<div class="mb-3 text-lg font-bold text-[#22344A]">
				{editing.id ? 'Edit employee' : 'Add employee'}
			</div>
			<div class="grid grid-cols-2 gap-3">
				{#each empFields as f}
					<label class="text-xs text-[#6B7785]">
						{f.label}
						<input
							type={f.type ?? 'text'}
							step="any"
							required={f.key === 'name'}
							bind:value={editing[f.key]}
							class="mt-1 block w-full rounded-lg border border-[#E3E7EC] px-2 py-1.5 text-sm text-[#33414F]"
						/>
					</label>
				{/each}
			</div>
			<div class="mt-4 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-lg border border-[#D5DBE2] px-4 py-2 text-sm text-[#33414F]"
					on:click={() => (editing = null)}
				>
					Cancel
				</button>
				<button
					class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
					disabled={savingEmp}
				>
					{savingEmp ? 'Saving…' : 'Save'}
				</button>
			</div>
		</form>
	</div>
{/if}

<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import { getDashboard, fmtMoney, type Dashboard, type Assignment } from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import Pill from '$lib/components/tg-billing/Pill.svelte';
	import { runStatusVariant } from '$lib/components/tg-billing/statusVariant';

	let data: Dashboard | null = null;
	let loading = true;
	let error = '';
	let period = new Date().toISOString().slice(0, 7);
	let query = '';
	let poFilter = '';
	let group: 'All' | 'Ready' | 'Not ready' | 'Blocked' = 'All';
	let askText = '';

	const load = async () => {
		loading = true;
		error = '';
		try {
			data = await getDashboard(localStorage.token, period);
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	};

	onMount(load);

	const tone: Record<string, string> = {
		ok: 'bg-[#DDF1F5] text-[#0B6272]',
		warn: 'bg-[#FCE9D8] text-[#B4560A]',
		bad: 'bg-[#8A4A12] text-white',
		grey: 'bg-[#EEF0F3] text-[#6B7785]'
	};
	const statusTone = (s: string) =>
		s === 'Ready' ? 'bg-[#2B3C50] text-white' : s === 'Blocked' ? 'bg-[#8A4A12] text-white' : 'bg-[#FCE9D8] text-[#B4560A]';

	$: all = data?.assignments ?? [];
	$: poRefs = [...new Set(all.map((a) => a.po_ref).filter((r) => r && r !== '—'))];
	$: counts = {
		All: all.length,
		Ready: all.filter((a) => a.group === 'Ready').length,
		'Not ready': all.filter((a) => a.group === 'Not ready').length,
		Blocked: all.filter((a) => a.group === 'Blocked').length
	};
	$: rows = all.filter(
		(a: Assignment) =>
			(group === 'All' || a.group === group) &&
			(!poFilter || a.po_ref === poFilter) &&
			(!query ||
				`${a.worker} ${a.code ?? ''} ${a.project_code} ${a.po_ref} ${a.party ?? ''}`
					.toLowerCase()
					.includes(query.toLowerCase()))
	);
	$: openExceptions = (data?.exceptions ?? []).reduce((n, e) => n + e.count, 0);
	$: maxExc = Math.max(1, ...(data?.exceptions ?? []).map((e) => e.count));
	const excColor = ['#8A4A12', '#E8892B', '#E8892B', '#0E7C8F'];
	const clear = () => {
		query = '';
		poFilter = '';
		group = 'All';
	};
	const ask = () => goto(`/billing/ask${askText.trim() ? `?q=${encodeURIComponent(askText.trim())}` : ''}`);

	$: kpis = [
		{ label: 'POs ready', value: data?.kpis?.pos_ready, href: '/billing/master-data', tone: 'text-[#0E7C8F]' },
		{
			label: 'Needs confirmation',
			value: data?.kpis?.needs_confirmation,
			href: '/billing/master-data',
			tone: 'text-[#B4560A]'
		},
		{
			label: 'Open exceptions',
			value: data?.kpis?.open_exceptions,
			href: '/billing/review-queue',
			tone: 'text-[#C8610F]'
		},
		{
			label: 'Runs awaiting validation',
			value: data?.kpis?.runs_awaiting,
			href: '/billing/invoice',
			tone: 'text-[#22344A]'
		}
	];
</script>

<div class="mx-auto max-w-6xl p-4 sm:p-6">
	<PageHeader
		title="Dashboard"
		subtitle="Welcome{$user?.name ? `, ${$user.name}` : ''}. APBA TG Human Resource Pte Ltd — invoice orchestration overview."
	>
		<a
			href="/billing/invoice"
			class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A]"
		>
			Prepare invoice
		</a>
	</PageHeader>

	{#if error}
		<div class="mb-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">
			Could not load dashboard: {error}
			<button class="ml-2 font-semibold underline" on:click={load}>Retry</button>
		</div>
	{/if}

	<div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
		{#each kpis as k}
			<a
				href={k.href}
				class="rounded-xl border border-[#E3E7EC] bg-white p-4 transition hover:border-[#E8892B]"
			>
				<div class="text-[11px] font-semibold uppercase tracking-wide text-[#6B7785]">{k.label}</div>
				<div class="mt-2 text-3xl font-bold {k.tone}">
					{#if loading}<span class="text-[#C5CCD4]">…</span>{:else}{k.value ?? '—'}{/if}
				</div>
			</a>
		{/each}
	</div>

	<div class="mt-6 flex flex-wrap items-center gap-2 text-xs text-[#6B7785]">
		<label>
			Billing period
			<input
				type="month"
				bind:value={period}
				on:change={load}
				class="ml-2 rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
			/>
		</label>
	</div>

	<div class="mt-3 grid gap-4 xl:grid-cols-3">
		<section class="rounded-xl border border-[#E3E7EC] bg-white xl:col-span-2">
			<div class="flex flex-wrap items-center justify-between gap-2 px-4 pt-4">
				<div class="font-semibold text-[#22344A]">Assignment readiness</div>
				<div class="text-xs text-[#6B7785]">Showing {rows.length} of {all.length} · {period}</div>
			</div>
			<div class="flex flex-wrap items-center gap-2 px-4 pt-3">
				<div class="relative min-w-[200px] flex-1">
					<svg class="absolute left-3 top-2.5 size-4 text-[#6B7785]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7" /><path stroke-linecap="round" d="M20 20l-3.5-3.5" /></svg>
					<input
						bind:value={query}
						placeholder="Search worker name, employee ID or project code"
						class="w-full rounded-lg border border-[#E3E7EC] bg-white py-2 pl-9 pr-3 text-sm placeholder:text-[#8A95A3]"
					/>
				</div>
				<label class="flex items-center gap-2 text-xs text-[#6B7785]">
					PO
					<select bind:value={poFilter} class="rounded-lg border border-[#E3E7EC] bg-white px-2 py-2 text-sm text-[#33414F]">
						<option value="">All POs ({poRefs.length})</option>
						{#each poRefs as r}<option value={r}>{r}</option>{/each}
					</select>
				</label>
				<button class="rounded-lg border border-[#E3E7EC] bg-white px-4 py-2 text-sm font-semibold text-[#22344A] hover:border-[#E8892B]" on:click={clear}>Clear</button>
			</div>
			<div class="flex flex-wrap gap-2 px-4 py-3">
				{#each ['All', 'Ready', 'Not ready', 'Blocked'] as g}
					<button
						class="rounded-full border px-3.5 py-1.5 text-xs font-semibold {group === g
							? 'border-[#C8610F] bg-[#C8610F] text-white'
							: 'border-[#E3E7EC] bg-white text-[#33414F] hover:border-[#E8892B]'}"
						on:click={() => (group = g)}>{g} ({counts[g]})</button
					>
				{/each}
			</div>
			{#if loading}
				<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
			{:else if !rows.length}
				<div class="p-6 text-sm text-[#6B7785]">No assignments match the filters.</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full min-w-[820px] text-xs">
						<thead class="bg-[#F1F3F6] text-left text-[11px] font-semibold text-[#33414F]">
							<tr>
								<th class="px-4 py-2.5">Worker</th>
								<th class="px-2 py-2.5">Project code</th>
								<th class="px-2 py-2.5">PO ref</th>
								<th class="px-2 py-2.5">Timesheet</th>
								<th class="px-2 py-2.5">PO</th>
								<th class="px-2 py-2.5">Rate</th>
								<th class="px-2 py-2.5">Instruction</th>
								<th class="px-2 py-2.5">Status</th>
							</tr>
						</thead>
						<tbody>
							{#each rows as a}
								<tr class="border-t border-[#E3E7EC] align-middle">
									<td class="whitespace-nowrap px-4 py-3">
										<div class="font-semibold text-[#22344A]">{a.worker.split(' - ')[0]}</div>
										<div class="font-mono text-[10px] text-[#6B7785]">{a.code ?? a.employee_id}</div>
									</td>
									<td class="whitespace-nowrap px-2 py-3 font-mono">{a.project_code}</td>
									<td class="whitespace-nowrap px-2 py-3 font-mono">{a.po_ref}</td>
									{#each [a.timesheet, a.po, a.rate, a.instruction] as c}
										<td class="px-2 py-3">
											<span class="inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold {tone[c.tone]}">{c.label}</span>
										</td>
									{/each}
									<td class="px-2 py-3">
										<span class="inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold {statusTone(a.status)}">{a.status}</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<div class="space-y-4">
			<section class="rounded-xl border border-[#E3E7EC] bg-white p-4">
				<div class="font-semibold text-[#22344A]">Exceptions by type</div>
				<div class="mt-3 space-y-3">
					{#each data?.exceptions ?? [] as e, i}
						<div>
							<div class="flex justify-between gap-3 text-xs text-[#33414F]">
								<span>{e.label}</span><span class="font-bold">{e.count}</span>
							</div>
							<div class="mt-1 h-1.5 rounded-full bg-[#EEF0F3]">
								<div class="h-1.5 rounded-full" style="width:{(e.count / maxExc) * 100}%;background:{excColor[i % 4]}"></div>
							</div>
						</div>
					{/each}
				</div>
				<a href="/billing/review-queue" class="mt-4 block rounded-lg border border-[#E3E7EC] py-2 text-center text-xs font-bold text-[#22344A] hover:border-[#E8892B]">Open Review Queue ({openExceptions})</a>
			</section>

			<section class="rounded-xl border border-[#E3E7EC] bg-white p-4">
				<div class="font-semibold text-[#22344A]">Approval pipeline</div>
				<div class="mt-3 grid grid-cols-3 gap-2 text-center">
					{#each [['Draft', data?.pipeline?.draft], ['Awaiting sign-off', data?.pipeline?.awaiting], ['Approved', data?.pipeline?.approved]] as [l, v]}
						<div class="rounded-lg bg-[#F1F3F6] px-1 py-3">
							<div class="text-xl font-bold text-[#22344A]">{v ?? '—'}</div>
							<div class="text-[11px] text-[#6B7785]">{l}</div>
						</div>
					{/each}
				</div>
				{#if data?.pipeline?.stalled}
					<div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-[#33414F]">
						<span class="rounded-full bg-[#8A4A12] px-2.5 py-0.5 text-[11px] font-semibold text-white">Stalled</span>
						{data.pipeline.stalled} case{data.pipeline.stalled > 1 ? 's' : ''} waiting &gt; {data.pipeline.stall_hours}h for sign-off
					</div>
				{/if}
				<a href="/billing/invoice" class="mt-3 block text-xs font-semibold text-[#0E7C8F] underline">Open approval queue</a>
			</section>

			<section class="rounded-xl border border-[#E3E7EC] bg-[#F1F3F6] p-4">
				<div class="text-[11px] font-bold uppercase tracking-wide text-[#6B7785]">Ask me</div>
				<form class="mt-2" on:submit|preventDefault={ask}>
					<input
						bind:value={askText}
						placeholder="Which assignments aren't billing-ready and why?"
						class="w-full rounded-lg border border-[#E3E7EC] bg-white px-3 py-2 text-xs"
					/>
				</form>
			</section>
		</div>
	</div>

	<div class="mt-4 grid gap-4 lg:grid-cols-3">
		<section class="rounded-xl border border-[#E3E7EC] bg-white lg:col-span-2">
			<div class="border-b border-[#E3E7EC] px-4 py-3 font-semibold text-[#22344A]">
				Recent invoice runs
			</div>
			{#if loading}
				<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
			{:else if !data?.runs?.length}
				<div class="p-6 text-sm text-[#6B7785]">
					No invoice runs yet. Start one from
					<a class="text-[#0E7C8F] underline" href="/billing/invoice">Invoice Preparation</a>.
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
							<tr>
								<th class="px-4 py-2">Run</th>
								<th class="px-4 py-2">Document</th>
								<th class="px-4 py-2">Period</th>
								<th class="px-4 py-2">Status</th>
								<th class="px-4 py-2 text-right">Total (SGD)</th>
							</tr>
						</thead>
						<tbody>
							{#each data.runs as r}
								<tr class="border-t border-[#E3E7EC]">
									<td class="px-4 py-2 font-mono text-xs">{r.invoice_no ?? r.id}</td>
									<td class="px-4 py-2">{r.document_ref ?? r.document_id ?? ''}</td>
									<td class="px-4 py-2">{r.period ?? ''}</td>
									<td class="px-4 py-2">
										<Pill variant={runStatusVariant(r.status)}>{r.status}</Pill>
									</td>
									<td class="px-4 py-2 text-right">{fmtMoney(r.total)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<section class="rounded-xl border border-[#E3E7EC] bg-white">
			<div class="border-b border-[#E3E7EC] px-4 py-3 font-semibold text-[#22344A]">
				Recent activity
			</div>
			{#if loading}
				<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
			{:else if !data?.activity?.length}
				<div class="p-6 text-sm text-[#6B7785]">No activity yet.</div>
			{:else}
				<ul class="divide-y divide-[#E3E7EC] text-sm">
					{#each data.activity as a}
						<li class="px-4 py-2.5">
							<div class="text-[#33414F]">{a.action ?? a.text ?? a.detail ?? ''}</div>
							<div class="text-[11px] text-[#6B7785]">
								{a.actor ?? ''}
								{a.ts ?? a.timestamp ?? ''}
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</div>
</div>

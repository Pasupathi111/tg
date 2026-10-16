<script lang="ts">
	import { onMount } from 'svelte';
	import { user } from '$lib/stores';
	import { getDashboard, fmtMoney, type Dashboard } from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import Pill from '$lib/components/tg-billing/Pill.svelte';
	import { runStatusVariant } from '$lib/components/tg-billing/statusVariant';

	let data: Dashboard | null = null;
	let loading = true;
	let error = '';

	const load = async () => {
		loading = true;
		error = '';
		try {
			data = await getDashboard(localStorage.token);
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	};

	onMount(load);

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

<div class="mx-auto max-w-6xl p-6">
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

	<div class="mt-6 grid gap-4 lg:grid-cols-3">
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

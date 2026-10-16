<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getReviewQueue,
		resolveReviewItem,
		type ReviewItem,
		type ReviewQueue
	} from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import Pill from '$lib/components/tg-billing/Pill.svelte';

	const filters = [
		{ key: 'all', label: 'All' },
		{ key: 'missing_po', label: 'Missing PO' },
		{ key: 'project_timesheet', label: 'Project code / timesheet' },
		{ key: 'rate_approval', label: 'Rate approval' },
		{ key: 'invoicing_instruction', label: 'Invoicing instruction' }
	];

	let category = 'all';
	let queue: ReviewQueue | null = null;
	let loading = true;
	let error = '';
	let selectedId: string | null = null;

	let assignee = '';
	let note = '';
	let saving = false;

	$: items = queue?.items ?? [];
	$: selected = items.find((i) => i.id === selectedId) ?? null;

	const load = async () => {
		loading = true;
		error = '';
		try {
			queue = await getReviewQueue(localStorage.token, category);
			const cur = queue?.items?.find((i) => i.id === selectedId) ?? queue?.items?.[0];
			if (cur) select(cur);
			else selectedId = null;
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	};
	onMount(load);

	const setCategory = (c: string) => {
		category = c;
		load();
	};

	const select = (i: ReviewItem) => {
		selectedId = i.id;
		assignee = i.assignee ?? '';
		note = i.note ?? '';
	};

	const act = async (status: string) => {
		if (!selected) return;
		saving = true;
		error = '';
		try {
			await resolveReviewItem(localStorage.token, selected.id, {
				assignee: assignee || undefined,
				note: note || undefined,
				status
			});
			await load();
		} catch (e) {
			error = `${e}`;
		}
		saving = false;
	};

	const evidenceList = (ev: ReviewItem['evidence']) =>
		Array.isArray(ev) ? ev : ev ? [ev] : [];

	const isResolved = (i: ReviewItem) => /resolved/i.test(i.status ?? '');
</script>

<div class="mx-auto max-w-6xl p-6">
	<PageHeader
		title="Review Queue"
		subtitle="Exceptions raised by the rule engine. Resolve them before invoicing."
	/>

	<div class="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Exception category">
		{#each filters as f}
			<button
				role="tab"
				aria-selected={category === f.key}
				class="rounded-full border px-3.5 py-1.5 text-sm transition {category === f.key
					? 'border-[#C8610F] bg-[#C8610F] text-white'
					: 'border-[#D5DBE2] bg-white text-[#33414F] hover:border-[#E8892B]'}"
				on:click={() => setCategory(f.key)}
			>
				{f.label}
				{#if queue?.counts}
					<span class="ml-1 text-xs opacity-80">{queue.counts[f.key as keyof typeof queue.counts] ?? 0}</span>
				{/if}
			</button>
		{/each}
	</div>

	{#if error}
		<div class="mb-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">
			{error}
			<button class="ml-2 font-semibold underline" on:click={load}>Retry</button>
		</div>
	{/if}

	<div class="grid gap-4 lg:grid-cols-5">
		<div class="space-y-2 lg:col-span-2">
			{#if loading}
				<div class="rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
					Loading…
				</div>
			{:else if !items.length}
				<div class="rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">
					No exceptions in this category.
				</div>
			{:else}
				{#each items as i}
					<button
						class="block w-full rounded-xl border bg-white p-3 text-left transition {selectedId === i.id
							? 'border-[#E8892B] ring-1 ring-[#E8892B]'
							: 'border-[#E3E7EC] hover:border-[#E8892B]'}"
						on:click={() => select(i)}
					>
						<div class="flex items-center justify-between gap-2">
							<span class="font-mono text-xs font-semibold text-[#22344A]">{i.id}</span>
							<Pill variant={isResolved(i) ? 'teal' : 'warn'}>{i.status ?? 'Open'}</Pill>
						</div>
						<div class="mt-1 text-sm font-semibold text-[#22344A]">{i.title}</div>
						{#if i.summary}
							<div class="mt-0.5 line-clamp-2 text-xs text-[#6B7785]">{i.summary}</div>
						{/if}
					</button>
				{/each}
			{/if}
		</div>

		<div class="rounded-xl border border-[#E3E7EC] bg-white p-5 lg:col-span-3">
			{#if !selected}
				<div class="text-sm text-[#6B7785]">Select an exception to review it.</div>
			{:else}
				<div class="flex items-start justify-between gap-2">
					<div>
						<div class="font-mono text-xs text-[#6B7785]">{selected.id}</div>
						<h2 class="text-lg font-bold text-[#22344A]">{selected.title}</h2>
					</div>
					<Pill variant={isResolved(selected) ? 'teal' : 'warn'}>{selected.status ?? 'Open'}</Pill>
				</div>

				<div class="mt-4 text-[11px] font-semibold uppercase tracking-wide text-[#6B7785]">
					Rule triggered
				</div>
				<div class="mt-1 rounded-lg bg-[#F6F7F9] p-2.5 font-mono text-xs">
					{selected.rule ?? selected.summary ?? '—'}
				</div>

				<div class="mt-4 text-[11px] font-semibold uppercase tracking-wide text-[#6B7785]">
					Evidence
				</div>
				{#if evidenceList(selected.evidence).length}
					<ul class="mt-1 list-disc space-y-1 pl-5 text-sm">
						{#each evidenceList(selected.evidence) as ev}
							<li>{typeof ev === 'string' ? ev : JSON.stringify(ev)}</li>
						{/each}
					</ul>
				{:else}
					<div class="mt-1 text-sm text-[#6B7785]">No evidence attached.</div>
				{/if}

				<div class="mt-4 text-[11px] font-semibold uppercase tracking-wide text-[#6B7785]">
					Suggested resolution
				</div>
				<div class="mt-1 rounded-lg border border-[#F3D3B5] bg-[#FDF1E6] p-2.5 text-sm">
					{selected.suggestion ?? '—'}
				</div>

				<div class="mt-4 grid gap-3 sm:grid-cols-2">
					<label class="text-xs text-[#6B7785]">
						Assign to
						<input
							bind:value={assignee}
							placeholder="Name or email"
							class="mt-1 block w-full rounded-lg border border-[#E3E7EC] px-2.5 py-1.5 text-sm text-[#33414F]"
						/>
					</label>
					<label class="text-xs text-[#6B7785] sm:col-span-2">
						Note
						<textarea
							bind:value={note}
							rows="3"
							class="mt-1 block w-full rounded-lg border border-[#E3E7EC] px-2.5 py-1.5 text-sm text-[#33414F]"
						></textarea>
					</label>
				</div>

				<div class="mt-4 flex flex-wrap gap-2">
					<button
						class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
						disabled={saving}
						on:click={() => act('Resolved')}
					>
						Mark resolved
					</button>
					<button
						class="rounded-lg border border-[#D5DBE2] px-4 py-2 text-sm text-[#33414F] hover:bg-[#F6F7F9] disabled:opacity-50"
						disabled={saving}
						on:click={() => act('Assigned')}
					>
						Save assignment
					</button>
				</div>
			{/if}
		</div>
	</div>
</div>

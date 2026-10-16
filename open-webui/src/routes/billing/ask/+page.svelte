<script lang="ts">
	import { onMount } from 'svelte';
	import { getRuns, getDocuments, type Run, type TgDocument } from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';
	import CoworkerChat from '$lib/components/tg-billing/CoworkerChat.svelte';

	let runs: Run[] = [];
	let docs: TgDocument[] = [];
	let runId = '';
	let docId = '';
	let error = '';
	let loading = true;

	$: run = runs.find((r) => r.id === runId) ?? null;

	onMount(async () => {
		try {
			[runs, docs] = await Promise.all([getRuns(localStorage.token), getDocuments(localStorage.token)]);
			runId = runs?.[0]?.id ?? '';
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	});
</script>

<div class="mx-auto flex h-full max-w-4xl flex-col p-3 sm:p-6">
	<PageHeader
		title="Ask Me"
		subtitle="Ask about a PO, a rule or a calculation. The assistant explains; the rule engine calculates."
	/>

	{#if error}
		<div class="mb-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">{error}</div>
	{/if}

	<div class="mb-3 flex flex-wrap gap-3">
		<label class="text-xs text-[#6B7785]">
			Invoice run
			<select
				bind:value={runId}
				class="mt-1 block rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
			>
				<option value="">None</option>
				{#each runs as r}
					<option value={r.id}>{r.invoice_no ?? r.id} · {r.period}</option>
				{/each}
			</select>
		</label>
		<label class="text-xs text-[#6B7785]">
			Document
			<select
				bind:value={docId}
				class="mt-1 block rounded-lg border border-[#E3E7EC] bg-white px-2 py-1.5 text-sm text-[#33414F]"
			>
				<option value="">None</option>
				{#each docs as d}
					<option value={d.id}>{d.ref} · {d.party}</option>
				{/each}
			</select>
		</label>
	</div>

	<div class="min-h-[420px] flex-1 overflow-hidden rounded-xl border border-[#E3E7EC] bg-white">
		{#if loading}
			<div class="p-6 text-sm text-[#6B7785]">Loading…</div>
		{:else}
			{#key runId + docId}
				<CoworkerChat
					{run}
					documentId={docId || undefined}
					chips={[
						'Summarise the billing instructions',
						'When does this PO expire?',
						'How is employer CPF calculated?',
						'Which exceptions are open?'
					]}
				/>
			{/key}
		{/if}
	</div>
</div>

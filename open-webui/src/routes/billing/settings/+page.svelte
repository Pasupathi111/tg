<script lang="ts">
	import { onMount } from 'svelte';
	import { getBillingSettings, updateBillingSettings, resetDemo } from '$lib/apis/tg-billing';
	import PageHeader from '$lib/components/tg-billing/PageHeader.svelte';

	let s: any = null;
	let loading = true;
	let saving = false;
	let error = '';
	let notice = '';

	const load = async () => {
		loading = true;
		error = '';
		try {
			s = await getBillingSettings(localStorage.token);
		} catch (e) {
			error = `${e}`;
		}
		loading = false;
	};
	onMount(load);

	const num = (v: any) => (v === '' || v === null || v === undefined ? v : Number(v));

	const save = async () => {
		saving = true;
		error = '';
		notice = '';
		try {
			s = await updateBillingSettings(localStorage.token, s);
			notice = 'Settings saved.';
		} catch (e) {
			error = `${e}`;
		}
		saving = false;
	};

	const reset = async () => {
		if (!confirm('Reseed the demo data? Current billing data will be replaced.')) return;
		try {
			await resetDemo(localStorage.token);
			notice = 'Demo data reseeded.';
			await load();
		} catch (e) {
			error = `${e}`;
		}
	};

	// [label, getter path, setter] groups of editable numeric fields
	const groups: { title: string; fields: { label: string; path: string[]; step?: string }[] }[] = [
		{
			title: 'Invoicing',
			fields: [
				{ label: 'GST %', path: ['gst_pct'], step: '0.01' },
				{ label: 'Default management fee %', path: ['default_fee_pct'], step: '0.01' },
				{ label: 'OT multiplier', path: ['ot_multiplier'], step: '0.01' }
			]
		},
		{
			title: 'Employer CPF',
			fields: [
				{ label: 'CPF rate %', path: ['cpf', 'rate_pct'], step: '0.01' },
				{ label: 'OW ceiling (SGD)', path: ['cpf', 'ow_ceiling'], step: '1' }
			]
		},
		{
			title: 'SDL',
			fields: [
				{ label: 'SDL rate %', path: ['sdl', 'rate_pct'], step: '0.01' },
				{ label: 'Minimum (SGD)', path: ['sdl', 'min'], step: '0.01' },
				{ label: 'Maximum (SGD)', path: ['sdl', 'max'], step: '0.01' }
			]
		}
	];

	const get = (path: string[]) => path.reduce((o, k) => o?.[k], s);
	const set = (path: string[], v: any) => {
		let o = s;
		for (const k of path.slice(0, -1)) {
			o[k] = o[k] ?? {};
			o = o[k];
		}
		o[path[path.length - 1]] = num(v);
		s = s;
	};
</script>

<div class="mx-auto max-w-4xl p-4 sm:p-6">
	<PageHeader
		title="Settings"
		subtitle="Company details and the Singapore calculation rules used by the rule engine."
	/>

	{#if error}
		<div class="mb-4 rounded-xl border border-[#F3C1C1] bg-[#FBE1E1] p-3 text-sm text-[#B42318]">
			{error}
			<button class="ml-2 font-semibold underline" on:click={load}>Retry</button>
		</div>
	{/if}
	{#if notice}
		<div class="mb-4 rounded-xl bg-[#DDF1F5] p-3 text-sm text-[#0E7C8F]">{notice}</div>
	{/if}

	{#if loading}
		<div class="rounded-xl border border-[#E3E7EC] bg-white p-6 text-sm text-[#6B7785]">Loading…</div>
	{:else if s}
		<form class="space-y-4" on:submit|preventDefault={save}>
			<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
				<div class="mb-3 font-semibold text-[#22344A]">Company</div>
				<label class="text-xs text-[#6B7785]">
					Company name
					<input
						bind:value={s.company}
						class="mt-1 block w-full rounded-lg border border-[#E3E7EC] px-2.5 py-1.5 text-sm text-[#33414F]"
					/>
				</label>
			</div>

			{#each groups as g}
				<div class="rounded-xl border border-[#E3E7EC] bg-white p-4">
					<div class="mb-3 font-semibold text-[#22344A]">{g.title}</div>
					<div class="grid gap-3 sm:grid-cols-3">
						{#each g.fields as f}
							<label class="text-xs text-[#6B7785]">
								{f.label}
								<input
									type="number"
									step={f.step}
									value={get(f.path) ?? ''}
									on:input={(e) => set(f.path, e.currentTarget.value)}
									class="mt-1 block w-full rounded-lg border border-[#E3E7EC] px-2.5 py-1.5 text-sm text-[#33414F]"
								/>
							</label>
						{/each}
					</div>
				</div>
			{/each}

			<div class="flex flex-wrap justify-between gap-2">
				<button
					type="button"
					class="rounded-lg border border-[#D5DBE2] px-4 py-2 text-sm text-[#33414F] hover:bg-[#F6F7F9]"
					on:click={reset}
				>
					Reset demo data
				</button>
				<button
					class="rounded-lg bg-[#C8610F] px-5 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
					disabled={saving}
				>
					{saving ? 'Saving…' : 'Save settings'}
				</button>
			</div>
		</form>
	{/if}
</div>

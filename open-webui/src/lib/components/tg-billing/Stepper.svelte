<script lang="ts">
	export let step = 1;
	export let maxStep = 1; // furthest step reachable
	export let onSelect: (n: number) => void = () => {};

	const steps = [
		'Sources & instructions',
		'Calculate',
		'Preview & validate',
		'Approve & download'
	];
</script>

<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
	{#each steps as label, i}
		{@const n = i + 1}
		<button
			class="flex items-center gap-3 rounded-xl border-2 bg-white p-3 text-left transition disabled:cursor-not-allowed {step ===
			n
				? 'border-[#E8892B]'
				: 'border-[#E3E7EC]'}"
			disabled={n > maxStep}
			on:click={() => onSelect(n)}
			aria-current={step === n ? 'step' : undefined}
		>
			<span
				class="flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white {step ===
				n
					? 'bg-[#C8610F]'
					: n < step
						? 'bg-[#0E7C8F]'
						: 'bg-[#B8C0CA]'}"
			>
				{#if n < step}✓{:else}{n}{/if}
			</span>
			<span class="min-w-0">
				<span class="block text-[10px] font-bold uppercase tracking-wide text-[#6B7785]">Step {n}</span>
				<span class="block truncate text-sm font-semibold text-[#22344A]">{label}</span>
			</span>
		</button>
	{/each}
</div>

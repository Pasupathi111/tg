<script lang="ts">
	export let title: string;
	export let subtitle = '';
</script>

<div class="mb-5 flex flex-wrap items-start justify-between gap-3">
	<div>
		<h1 class="text-2xl font-bold text-[#22344A]">{title}</h1>
		{#if subtitle}
			<p class="mt-1 text-sm text-[#6B7785]">{subtitle}</p>
		{/if}
	</div>
	<div class="flex flex-wrap items-center gap-2">
		<slot />
	</div>
</div>

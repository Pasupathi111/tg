<script lang="ts">
	import { fmtMoney, type RunLine } from '$lib/apis/tg-billing';

	export let line: RunLine;
</script>

<div class="overflow-x-auto rounded-xl border border-[#E3E7EC] bg-white">
	<table class="w-full text-sm">
		<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
			<tr>
				<th class="px-4 py-2">Component</th>
				<th class="px-4 py-2">Calculation</th>
				<th class="whitespace-nowrap px-4 py-2 text-right">Amount (SGD)</th>
				<th class="px-4 py-2">Source</th>
			</tr>
		</thead>
		<tbody>
			{#each line.sections ?? [] as sec}
				<tr class="border-t border-[#E3E7EC] bg-[#F6F7F9]">
					<td colspan="4" class="px-4 py-1.5 text-[11px] font-bold uppercase tracking-wide text-[#22344A]">
						{sec.key} · {sec.title}
					</td>
				</tr>
				{#each sec.rows as r}
					<tr class="border-t border-[#EEF0F3] {r.adjusted ? 'bg-[#FDF1E6]' : ''}">
						<td class="px-4 py-2 text-[#22344A]">
							{r.label}
							{#if r.adjusted}<span class="ml-1 text-[10px] font-semibold text-[#B4560A]">ADJUSTED</span>{/if}
						</td>
						<td class="px-4 py-2 font-mono text-xs text-[#6B7785]">{r.calc ?? ''}</td>
						<td class="whitespace-nowrap px-4 py-2 text-right tabular-nums">{fmtMoney(r.amount)}</td>
						<td class="px-4 py-2 text-xs text-[#0E7C8F] underline">{r.source ?? ''}</td>
					</tr>
				{/each}
			{/each}
		</tbody>
		<tfoot>
			<tr class="border-t-2 border-[#D5DBE2] bg-[#F6F7F9] font-semibold">
				<td class="px-4 py-2 text-[#22344A]" colspan="2">Officer total (cost + management fee)</td>
				<td class="whitespace-nowrap px-4 py-2 text-right tabular-nums">{fmtMoney(line.amount)}</td>
				<td></td>
			</tr>
		</tfoot>
	</table>
</div>

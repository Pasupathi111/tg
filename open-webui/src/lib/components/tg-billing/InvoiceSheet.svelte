<script lang="ts">
	import { fmtMoney, type Run, type TgDocument } from '$lib/apis/tg-billing';
	import TgLogo from './TgLogo.svelte';

	export let run: Run;
	export let doc: TgDocument | null = null;
	export let company = 'APBA TG Human Resource Pte Ltd';

	$: ins = doc?.instructions ?? {};
	$: refs = ins.mandatory_references ?? [];
</script>

<div class="rounded-xl border border-[#E3E7EC] bg-white p-4 shadow-sm sm:p-8">
	<div class="flex items-start justify-between">
		<div class="flex items-center gap-2">
			<TgLogo size={36} />
			<div>
				<div class="text-sm font-bold text-[#22344A]">{company}</div>
				<div class="text-[11px] text-[#6B7785]">Singapore</div>
			</div>
		</div>
		<div class="text-right">
			<div class="text-2xl font-bold tracking-wide text-[#22344A]">TAX INVOICE</div>
			<div class="font-mono text-xs text-[#6B7785]">{run.invoice_no ?? 'Draft — number assigned on approval'}</div>
		</div>
	</div>

	<div class="mt-6 grid gap-4 text-sm sm:grid-cols-3">
		<div>
			<div class="text-[10px] font-bold uppercase tracking-wide text-[#6B7785]">Bill to</div>
			<div class="mt-1 font-semibold text-[#22344A]">{doc?.party ?? '—'}</div>
		</div>
		<div>
			<div class="text-[10px] font-bold uppercase tracking-wide text-[#6B7785]">References</div>
			<div class="mt-1 text-[#22344A]">{doc?.ref ?? '—'}</div>
			{#each refs as r}<div class="text-xs text-[#6B7785]">{r}</div>{/each}
		</div>
		<div>
			<div class="text-[10px] font-bold uppercase tracking-wide text-[#6B7785]">Billing period</div>
			<div class="mt-1 text-[#22344A]">{run.period}</div>
		</div>
	</div>

	<div class="mt-5 rounded-lg bg-[#F1F3F6] p-3 text-xs text-[#33414F]">
		<div class="mb-1 font-semibold text-[#22344A]">Billing instructions (from {doc?.ref ?? 'PO'})</div>
		Basis: {run.basis}{#if ins.fee_pct != null} · Management fee {ins.fee_pct}%{/if} · GST {run.gst_pct}%
		{#if ins.invoice_split} · Split: {ins.invoice_split}{/if}
		{#if ins.tax_treatment} · {ins.tax_treatment}{/if}
	</div>

	<div class="mt-5 overflow-x-auto">
		<table class="w-full text-sm">
			<thead class="bg-[#F1F3F6] text-left text-[11px] uppercase text-[#6B7785]">
				<tr>
					<th class="px-3 py-2">Officer</th>
					<th class="px-3 py-2">Pay basis</th>
					<th class="px-3 py-2 text-right">Employment cost</th>
					<th class="px-3 py-2 text-right">Mgmt fee</th>
					<th class="px-3 py-2 text-right">Amount</th>
				</tr>
			</thead>
			<tbody>
				{#each run.lines as l}
					<tr class="border-t border-[#EEF0F3]">
						<td class="px-3 py-2 font-medium text-[#22344A]">{l.name}</td>
						<td class="px-3 py-2">{l.pay_basis}</td>
						<td class="px-3 py-2 text-right tabular-nums">{fmtMoney(l.cost)}</td>
						<td class="px-3 py-2 text-right tabular-nums">{fmtMoney(l.fee)}</td>
						<td class="px-3 py-2 text-right tabular-nums">{fmtMoney(l.amount)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="mt-4 ml-auto w-full max-w-xs space-y-1 text-sm">
		<div class="flex justify-between"><span>Subtotal</span><span class="tabular-nums">{fmtMoney(run.subtotal)}</span></div>
		<div class="flex justify-between"><span>GST {run.gst_pct}%</span><span class="tabular-nums">{fmtMoney(run.gst)}</span></div>
		<div class="flex justify-between border-t border-[#D5DBE2] pt-2 text-base font-bold text-[#22344A]">
			<span>Total SGD</span><span class="tabular-nums">{fmtMoney(run.total)}</span>
		</div>
	</div>
</div>

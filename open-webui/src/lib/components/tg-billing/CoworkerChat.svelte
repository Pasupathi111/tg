<script lang="ts">
	import { createEventDispatcher, onMount, tick } from 'svelte';
	import { askBillingCoworker, adjustRun, fmtMoney, type Run } from '$lib/apis/tg-billing';

	export let run: Run | null = null;
	export let initialQuestion = '';
	export let documentId: string | undefined = undefined;
	export let chips: string[] = [
		'Why is this amount what it is?',
		'Explain CPF for this officer',
		'Set unpaid leave days to 1',
		'Which checks differ?'
	];

	const dispatch = createEventDispatcher();

	type Msg = {
		role: 'user' | 'assistant';
		text: string;
		steps?: { n: number; title: string; text: string; source?: string }[];
		proposal?: any;
		reason?: string;
		state?: 'pending' | 'applied' | 'discarded';
		error?: string;
	};

	let messages: Msg[] = [];
	let input = '';
	let busy = false;
	let scroller: HTMLDivElement;

	// Name of the officer currently open in the calculation tabs; used when the question does not name anyone.
	export let focusName = '';

	const withFocus = (question: string) => {
		if (!focusName || !run) return question;
		const lower = question.toLowerCase();
		const named = (run.lines ?? []).some((l: any) => lower.includes(`${l.name}`.toLowerCase()));
		if (named || /\b(total|gst|invoice)\b/i.test(question)) return question;
		const m = question.match(/^(.*?)\s+to\s+(-?\d+(?:\.\d+)?)\s*$/i);
		if (m) return `${m[1]} for ${focusName} to ${m[2]}`;
		return `${question.replace(/[?.!]+$/, '')} for ${focusName}`;
	};

	const scrollDown = async () => {
		await tick();
		if (scroller) scroller.scrollTop = scroller.scrollHeight;
	};

	onMount(() => {
		if (initialQuestion) send(initialQuestion);
	});

	const send = async (q?: string) => {
		const question = (q ?? input).trim();
		if (!question || busy) return;
		input = '';
		messages = [...messages, { role: 'user', text: question }];
		const sendText = withFocus(question);
		busy = true;
		scrollDown();
		try {
			const res = await askBillingCoworker(localStorage.token, {
				question: sendText,
				run_id: run?.id,
				document_id: documentId ?? run?.document_id
			});
			messages = [
				...messages,
				{
					role: 'assistant',
					text: res?.answer ?? '',
					steps: res?.steps,
					proposal: res?.proposal,
					state: res?.proposal ? 'pending' : undefined,
					reason: ''
				}
			];
		} catch (e) {
			messages = [...messages, { role: 'assistant', text: '', error: `${e}` }];
		}
		busy = false;
		scrollDown();
	};

	// A proposal from /ask is expected to carry: employee_id, field, new_value, from, to (and optionally delta_total / reason)
	const apply = async (m: Msg) => {
		if (!run || !m.proposal) return;
		const p = m.proposal;
		const prop = p.proposal ?? p;
		try {
			const res = await adjustRun(localStorage.token, run.id, {
				employee_id: p.employee_id ?? prop.employee_id,
				field: p.field ?? prop.field,
				new_value: p.new_value ?? prop.new_value ?? prop.to,
				reason: m.reason || p.reason || 'Adjustment via Billing Coworker',
				confirm: true
			});
			m.state = 'applied';
			messages = messages;
			dispatch('changed', res);
		} catch (e) {
			m.error = `${e}`;
			messages = messages;
		}
	};

	const discard = (m: Msg) => {
		m.state = 'discarded';
		messages = messages;
	};

	const show = (v: any) =>
		v !== null && typeof v === 'object' ? JSON.stringify(v) : (v ?? '—');
</script>

<div class="flex h-full min-h-0 flex-col">
	<div class="flex flex-wrap gap-1.5 border-b border-[#E3E7EC] px-4 py-2">
		{#if run}
			<span class="rounded-full bg-[#F1F3F6] px-2.5 py-0.5 text-[11px] text-[#6B7785]">Run {run.id}</span>
			<span class="rounded-full bg-[#F1F3F6] px-2.5 py-0.5 text-[11px] text-[#6B7785]">{run.period}</span>
		{:else}
			<span class="rounded-full bg-[#F1F3F6] px-2.5 py-0.5 text-[11px] text-[#6B7785]">No run selected</span>
		{/if}
	</div>

	<div bind:this={scroller} class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
		{#if !messages.length}
			<div class="text-sm text-[#6B7785]">
				Ask me to explain how any figure was derived or to propose an adjustment. Every change needs
				your confirmation and is written to the audit log.
			</div>
		{/if}

		{#each messages as m}
			{#if m.role === 'user'}
				<div class="ml-8 rounded-xl rounded-tr-sm bg-[#2B3C50] px-3 py-2 text-sm text-white">{m.text}</div>
			{:else}
				<div class="mr-4 space-y-2">
					{#if m.error}
						<div class="rounded-xl bg-[#FBE1E1] px-3 py-2 text-sm text-[#B42318]">{m.error}</div>
					{:else}
						{#if m.text}
							<div class="whitespace-pre-wrap rounded-xl rounded-tl-sm bg-[#F1F3F6] px-3 py-2 text-sm text-[#33414F]">
								{m.text}
							</div>
						{/if}
						{#if m.steps?.length}
							<ol class="space-y-1.5">
								{#each m.steps as s}
									<li class="flex gap-2 text-xs">
										<span
											class="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#DDF1F5] font-bold text-[#0E7C8F]"
											>{s.n}</span
										>
										<span>
											<span class="font-semibold text-[#22344A]">{s.title}</span>
											<span class="text-[#33414F]"> {s.text}</span>
											{#if s.source}<span class="text-[#0E7C8F] underline"> {s.source}</span>{/if}
										</span>
									</li>
								{/each}
							</ol>
						{/if}
						{#if m.proposal}
							{@const p = m.proposal.proposal ?? m.proposal}
							<div class="rounded-xl border-2 border-[#E8892B] bg-white p-3">
								<div class="text-[11px] font-bold uppercase tracking-wide text-[#B4560A]">
									{m.state === 'applied'
										? 'Change applied'
										: m.state === 'discarded'
											? 'Change discarded'
											: 'Needs your confirmation'}
								</div>
								<table class="mt-2 w-full text-xs">
									<thead class="text-left text-[10px] uppercase text-[#6B7785]">
										<tr><th>Field</th><th>From</th><th>To</th></tr>
									</thead>
									<tbody>
										<tr>
											<td class="py-1">{m.proposal.field ?? p.field ?? 'Value'}</td>
											<td>{show(p.from)}</td>
											<td class="font-semibold">{show(p.to)}</td>
										</tr>
										{#if p.delta_total != null}
											<tr>
												<td colspan="2" class="pt-1 text-[#6B7785]">Change to invoice total</td>
												<td class="pt-1 font-semibold">{fmtMoney(p.delta_total)}</td>
											</tr>
										{/if}
									</tbody>
								</table>
								{#if m.state === 'pending'}
									<input
										bind:value={m.reason}
										placeholder="Reason (recorded in audit log)"
										class="mt-2 w-full rounded-lg border border-[#E3E7EC] px-2 py-1.5 text-xs"
									/>
									<div class="mt-2 flex gap-2">
										<button
											class="rounded-lg bg-[#C8610F] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#B4560A]"
											on:click={() => apply(m)}
										>
											Apply change
										</button>
										<button
											class="rounded-lg border border-[#C8610F] px-3 py-1.5 text-xs font-semibold text-[#C8610F]"
											on:click={() => discard(m)}
										>
											Discard
										</button>
									</div>
								{/if}
							</div>
						{/if}
					{/if}
				</div>
			{/if}
		{/each}
		{#if busy}<div class="text-xs text-[#6B7785]">Thinking…</div>{/if}
	</div>

	<div class="border-t border-[#E3E7EC] p-3">
		<div class="mb-2 flex flex-wrap gap-1.5">
			{#each chips as c}
				<button
					class="rounded-full border border-[#D5DBE2] bg-white px-2.5 py-1 text-[11px] text-[#33414F] hover:border-[#E8892B] disabled:opacity-50"
					disabled={busy}
					on:click={() => send(c)}
				>
					{c}
				</button>
			{/each}
		</div>
		<form class="flex gap-2" on:submit|preventDefault={() => send()}>
			<input
				bind:value={input}
				placeholder="Ask about this calculation…"
				class="min-w-0 flex-1 rounded-lg border border-[#E3E7EC] px-3 py-2 text-sm"
			/>
			<button
				class="rounded-lg bg-[#C8610F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B4560A] disabled:opacity-50"
				disabled={busy || !input.trim()}
			>
				Send
			</button>
		</form>
		<p class="mt-2 text-[10px] leading-snug text-[#6B7785]">
			The assistant explains and proposes. Numbers come from the deterministic rule engine; POs,
			employee records and timesheets are never changed.
		</p>
	</div>
</div>

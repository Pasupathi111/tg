<script lang="ts">
	// teal: Pass/Received/Match, warn: needs attention, dark: Ready/Read-only, grey: neutral, red: Fail
	export let variant: 'teal' | 'warn' | 'dark' | 'grey' | 'red' = 'grey';

	const styles = {
		teal: 'bg-[#DDF1F5] text-[#0E7C8F]',
		warn: 'bg-[#FCE9D8] text-[#B4560A]',
		dark: 'bg-[#2B3C50] text-white',
		grey: 'bg-[#EDF0F3] text-[#6B7785]',
		red: 'bg-[#FBE1E1] text-[#B42318]'
	};
</script>

<span
	class="inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold {styles[
		variant
	]}"
>
	<slot />
</span>

<script lang="ts">
	export let size = 32;
	export let color = '#E8892B';
	export let className = '';

	const rays = Array.from({ length: 16 }, (_, i) => i * 22.5);
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 64 64"
	width={size}
	height={size}
	class={className}
	role="img"
	aria-label="TG"
>
	{#each rays as a, i}
		<line
			x1="32"
			y1={i % 2 === 0 ? 4 : 9}
			x2="32"
			y2="17"
			stroke={color}
			stroke-width={i % 2 === 0 ? 4 : 3}
			stroke-linecap="round"
			transform="rotate({a} 32 32)"
		/>
	{/each}
	<circle cx="32" cy="32" r="9" fill={color} />
</svg>

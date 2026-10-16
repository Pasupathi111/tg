<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { user } from '$lib/stores';
	import { getSessionUser, userSignOut, getLogoutRedirectUrl } from '$lib/apis/auths';
	import TgLogo from '$lib/components/tg-billing/TgLogo.svelte';

	let ready = false;
	let navOpen = false;

	const nav = [
		{ href: '/billing', label: 'Dashboard', icon: 'M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10' },
		{
			href: '/billing/master-data',
			label: 'Master Data',
			icon: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6m-16 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6'
		},
		{
			href: '/billing/review-queue',
			label: 'Review Queue',
			icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4'
		},
		{
			href: '/billing/invoice',
			label: 'Invoice Preparation',
			icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.6a1 1 0 01.7.3l5.4 5.4a1 1 0 01.3.7V19a2 2 0 01-2 2z'
		},
		{
			href: '/billing/ask',
			label: 'Ask Me',
			icon: 'M8 10h8M8 14h5m-9 6l2.5-3H19a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v14z'
		}
	];

	const isActive = (href: string, path: string) =>
		href === '/billing' ? path === '/billing' : path === href || path.startsWith(href + '/');

	const gotoAuth = async () => {
		const currentUrl = `${$page.url.pathname}${$page.url.search}`;
		await goto(`/auth?redirect=${encodeURIComponent(currentUrl)}`);
	};

	const signOut = async () => {
		const res = await userSignOut().catch(() => null);
		localStorage.removeItem('token');
		location.href = getLogoutRedirectUrl(res?.redirect_url);
	};

	onMount(async () => {
		if ($user === undefined || $user === null) {
			await gotoAuth();
			return;
		}
		if (!['user', 'admin'].includes($user?.role)) {
			await gotoAuth();
			return;
		}
		// validate the stored token is still good
		if (localStorage.token) {
			const sessionUser = await getSessionUser(localStorage.token).catch(() => null);
			if (!sessionUser) {
				localStorage.removeItem('token');
				await gotoAuth();
				return;
			}
		}
		ready = true;
	});

	$: path = $page.url.pathname;
	$: if (path) navOpen = false;
</script>

<svelte:head>
	<title>Billing Coworker</title>
</svelte:head>

{#if ready}
	<div class="flex h-screen max-h-[100dvh] w-full bg-[#F6F7F9] text-[#33414F] font-sans">
		<!-- mobile overlay -->
		{#if navOpen}
			<button
				class="fixed inset-0 z-30 bg-black/40 md:hidden"
				aria-label="Close menu"
				on:click={() => (navOpen = false)}
			></button>
		{/if}

		<aside
			class="fixed inset-y-0 left-0 z-40 flex w-[220px] shrink-0 flex-col bg-[#2B3C50] text-white transition-transform md:static md:translate-x-0 {navOpen
				? 'translate-x-0'
				: '-translate-x-full'}"
		>
			<div class="p-3">
				<div class="flex items-center gap-2.5 rounded-xl bg-[#34475D] p-2.5">
					<div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-white">
						<TgLogo size={28} />
					</div>
					<div class="min-w-0">
						<div class="truncate text-sm font-bold leading-tight text-white">Billing Coworker</div>
						<div class="text-[11px] text-white/60">Powered by DBiz</div>
					</div>
				</div>
			</div>

			<nav class="mt-1 flex-1 space-y-0.5 overflow-y-auto" aria-label="Billing navigation">
				{#each nav as item}
					<a
						href={item.href}
						class="flex items-center gap-3 border-l-[3px] px-4 py-2.5 text-sm transition {isActive(
							item.href,
							path
						)
							? 'border-[#E8892B] bg-[#3A4E65] font-semibold text-white'
							: 'border-transparent text-white/80 hover:bg-[#34475D]'}"
						aria-current={isActive(item.href, path) ? 'page' : undefined}
					>
						<svg
							class="size-[18px] shrink-0"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="1.6"
							stroke-linecap="round"
							stroke-linejoin="round"
						>
							<path d={item.icon} />
						</svg>
						{item.label}
					</a>
				{/each}
			</nav>

			<div class="space-y-0.5 pb-3">
				<a
					href="/billing/settings"
					class="flex items-center gap-3 border-l-[3px] px-4 py-2.5 text-sm transition {isActive(
						'/billing/settings',
						path
					)
						? 'border-[#E8892B] bg-[#3A4E65] font-semibold'
						: 'border-transparent text-white/80 hover:bg-[#34475D]'}"
				>
					<svg
						class="size-[18px] shrink-0"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="1.6"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<circle cx="12" cy="12" r="3" />
						<path
							d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"
						/>
					</svg>
					Settings
				</a>
				<button
					class="flex w-full items-center gap-3 border-l-[3px] border-transparent px-4 py-2.5 text-left text-sm text-white/80 transition hover:bg-[#34475D]"
					on:click={signOut}
				>
					<svg
						class="size-[18px] shrink-0"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="1.6"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m7 14l5-5-5-5m5 5H9" />
					</svg>
					Sign out
				</button>
				<a
					href="/"
					class="block px-4 pt-2 text-[11px] text-white/50 hover:text-white/80"
					title="Back to chat"
				>
					Back to chat
				</a>
			</div>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="flex items-center gap-3 border-b border-[#E3E7EC] bg-white px-4 py-2.5 md:hidden">
				<button
					class="rounded-md p-1.5 text-[#22344A] hover:bg-[#F1F3F6]"
					aria-label="Open menu"
					on:click={() => (navOpen = true)}
				>
					<svg class="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" d="M4 6h16M4 12h16M4 18h16" />
					</svg>
				</button>
				<TgLogo size={22} />
				<span class="text-sm font-semibold text-[#22344A]">Billing Coworker</span>
			</header>

			<main class="min-h-0 flex-1 overflow-y-auto">
				<slot />
			</main>
		</div>
	</div>
{:else}
	<div class="flex h-screen items-center justify-center bg-[#F6F7F9] text-sm text-[#6B7785]">
		Loading…
	</div>
{/if}

export const docStatusVariant = (s: string) =>
	s === 'Ready' ? 'dark' : s === 'Expired' ? 'red' : s === 'Needs confirmation' ? 'warn' : 'grey';

export const checkVariant = (r: string) =>
	r === 'Pass' || r === 'Match' ? 'teal' : r === 'Differs' ? 'warn' : r === 'Fail' ? 'red' : 'grey';

export const runStatusVariant = (s: string) =>
	s === 'Approved' ? 'teal' : s === 'Awaiting validation' ? 'warn' : 'grey';

"""Shared, parameterized name matching for Desk item searches."""


def terms(text):
	return list(dict.fromkeys(str(text or '').strip().lower().split()))


def contains_pattern(text):
	# Treat user wildcard characters literally (SQL LIKE uses '=' as escape).
	return '%' + text.replace('=', '==').replace('%', '=%').replace('_', '=_') + '%'


def condition(field, text, values, key='word'):
	parts = []
	for index, word in enumerate(terms(text)):
		param = f'{key}{index}'
		values[param] = contains_pattern(word)
		parts.append(f"lower(coalesce({field}, '')) like %({param})s escape '='")
	return '(' + ' and '.join(parts or ['1=1']) + ')'


def ranking(field, text, values):
	text = ' '.join(terms(text))
	values['name_exact'] = text
	values['name_phrase'] = contains_pattern(text)
	values['name_prefix'] = contains_pattern(text)[1:]
	# Independent word starts rank ahead of arbitrary substrings.
	prefixes = []
	for i, word in enumerate(terms(text)):
		values[f'begin{i}'] = contains_pattern(word)[1:]
		values[f'boundary{i}'] = '% ' + contains_pattern(word)[1:]
		prefixes.append(f"(lower({field}) like %(begin{i})s escape '=' or lower({field}) like %(boundary{i})s escape '=')")
	return f"""case when lower({field}) = %(name_exact)s then 0
		when lower({field}) like %(name_prefix)s escape '=' then 1
		when lower({field}) like %(name_phrase)s escape '=' then 2
		when {' and '.join(prefixes) or '1=1'} then 3 else 4 end,
		length({field})"""
